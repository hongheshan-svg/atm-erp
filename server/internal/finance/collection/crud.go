package collection

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/atm-erp/server/internal/iam"
	"gorm.io/gorm"
)

var (
	ErrPlanNotFound      = errors.New("回款计划不存在")
	ErrMilestoneNotFound = errors.New("回款节点不存在")
	ErrBadDate           = errors.New("日期格式应为 YYYY-MM-DD")
)

const (
	scopeModule = "finance"
	dateLayout  = "2006-01-02"
)

func parseDateOr(s string, fallback time.Time) (time.Time, error) {
	if s == "" {
		return fallback, nil
	}
	t, err := time.Parse(dateLayout, s)
	if err != nil {
		return time.Time{}, ErrBadDate
	}
	return t, nil
}

func (s *Service) scopedPlans(ctx context.Context) *gorm.DB {
	q := s.db.WithContext(ctx).Model(&CollectionPlan{})
	if u, ok := iam.AuthUserFrom(ctx); ok {
		q = iam.ApplyScope(q, u, scopeModule, "created_by_id")
	}
	return q
}

// ── 计划 ──────────────────────────────────────────────────────────

func (s *Service) ListPlans(ctx context.Context, q PlanListQuery, offset, limit int) ([]CollectionPlan, int64, error) {
	tx := s.scopedPlans(ctx)
	if q.Keyword != "" {
		kw := "%" + q.Keyword + "%"
		tx = tx.Where("plan_no LIKE ? OR name LIKE ?", kw, kw)
	}
	if q.CustomerID != "" {
		tx = tx.Where("customer_id = ?", q.CustomerID)
	}
	if q.Status != "" {
		tx = tx.Where("status = ?", q.Status)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var plans []CollectionPlan
	if err := tx.Order("id DESC").Offset(offset).Limit(limit).Find(&plans).Error; err != nil {
		return nil, 0, err
	}
	return plans, total, nil
}

func (s *Service) GetPlan(ctx context.Context, id uint64) (*CollectionPlan, error) {
	var p CollectionPlan
	if err := s.scopedPlans(ctx).Where("id = ?", id).First(&p).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil, ErrPlanNotFound
		}
		return nil, err
	}
	return &p, nil
}

// PlanMilestones 返回某计划下的全部节点(按计划日期)。
func (s *Service) PlanMilestones(ctx context.Context, planID uint64) ([]CollectionMilestone, error) {
	var ms []CollectionMilestone
	err := s.db.WithContext(ctx).Where("plan_id = ?", planID).Order("planned_date, id").Find(&ms).Error
	return ms, err
}

func (s *Service) CreatePlan(ctx context.Context, in CreatePlanInput) (*CollectionPlan, error) {
	planNo := in.PlanNo
	if planNo == "" {
		// TODO(verify): 对齐 Django CodeRule('COLLECTION_PLAN');此处临时发号。
		planNo = fmt.Sprintf("CP%d", time.Now().UnixNano())
	}
	p := &CollectionPlan{
		PlanNo:       planNo,
		Name:         in.Name,
		CustomerID:   in.CustomerID,
		ProjectID:    in.ProjectID,
		SalesOrderID: in.SalesOrderID,
		ContractID:   in.ContractID,
		TotalAmount:  in.TotalAmount,
		OwnerID:      in.OwnerID,
		Notes:        in.Notes,
		Status:       PlanDraft,
	}
	if err := s.db.WithContext(ctx).Create(p).Error; err != nil {
		return nil, err
	}
	return p, nil
}

func (s *Service) UpdatePlan(ctx context.Context, id uint64, in UpdatePlanInput) (*CollectionPlan, error) {
	p, err := s.GetPlan(ctx, id)
	if err != nil {
		return nil, err
	}
	if in.Name != nil {
		p.Name = *in.Name
	}
	if in.TotalAmount != nil {
		p.TotalAmount = *in.TotalAmount
	}
	if in.OwnerID != nil {
		p.OwnerID = in.OwnerID
	}
	if in.Notes != nil {
		p.Notes = *in.Notes
	}
	if err := s.db.WithContext(ctx).Save(p).Error; err != nil {
		return nil, err
	}
	return p, nil
}

func (s *Service) DeletePlan(ctx context.Context, id uint64) error {
	if _, err := s.GetPlan(ctx, id); err != nil {
		return err
	}
	return s.db.WithContext(ctx).Where("id = ?", id).Delete(&CollectionPlan{}).Error
}

// ── 节点 ──────────────────────────────────────────────────────────

func (s *Service) CreateMilestone(ctx context.Context, planID uint64, in CreateMilestoneInput) (*CollectionMilestone, error) {
	if _, err := s.GetPlan(ctx, planID); err != nil {
		return nil, err
	}
	pd, err := parseDateOr(in.PlannedDate, time.Now())
	if err != nil {
		return nil, err
	}
	m := &CollectionMilestone{
		PlanID:        planID,
		MilestoneType: in.MilestoneType,
		Name:          in.Name,
		Description:   in.Description,
		Percentage:    in.Percentage,
		PlannedAmount: in.PlannedAmount,
		PlannedDate:   pd,
		Status:        MilestonePending,
		ReminderDays:  7,
	}
	if err := s.db.WithContext(ctx).Create(m).Error; err != nil {
		return nil, err
	}
	return m, nil
}

// ── 收款记录(级联汇总)──────────────────────────────────────────

// AddRecordTo 新增一条收款记录到指定节点并级联汇总(记录→节点→计划)。
func (s *Service) AddRecordTo(ctx context.Context, milestoneID uint64, in CreateRecordInput) (*CollectionRecord, error) {
	var m CollectionMilestone
	if err := s.db.WithContext(ctx).Where("id = ?", milestoneID).First(&m).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil, ErrMilestoneNotFound
		}
		return nil, err
	}
	cd, err := parseDateOr(in.CollectionDate, time.Now())
	if err != nil {
		return nil, err
	}
	pm := in.PaymentMethod
	if pm == "" {
		pm = "BANK"
	}
	rec := &CollectionRecord{
		MilestoneID:    milestoneID,
		CollectionDate: cd,
		Amount:         in.Amount,
		PaymentMethod:  pm,
		BankName:       in.BankName,
		BankAccount:    in.BankAccount,
		TransactionNo:  in.TransactionNo,
		Notes:          in.Notes,
	}
	if err := s.AddRecord(ctx, rec); err != nil {
		return nil, err
	}
	return rec, nil
}
