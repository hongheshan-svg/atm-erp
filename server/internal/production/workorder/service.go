package workorder

import (
	"context"
	"errors"
	"fmt"
	"time"

	"gorm.io/gorm"
)

var (
	ErrNotFound      = errors.New("工单不存在")
	ErrBadTransition = errors.New("工单状态不允许该操作")
	ErrQtyNegative   = errors.New("完成数量不能为负")
	ErrQtyExceed     = errors.New("完成数量不能超过工单数量")
)

type Service struct{ repo *Repo }

func NewService(repo *Repo) *Service { return &Service{repo: repo} }

func (s *Service) List(ctx context.Context, q ListQuery, offset, limit int) ([]WorkOrder, int64, error) {
	return s.repo.List(ctx, q, offset, limit)
}

func (s *Service) Get(ctx context.Context, id uint64) (*WorkOrder, error) {
	wo, err := s.repo.Get(ctx, id)
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, ErrNotFound
	}
	return wo, err
}

func (s *Service) Create(ctx context.Context, in CreateInput) (*WorkOrder, error) {
	wo := &WorkOrder{
		OrderNo:       in.OrderNo,
		ProjectID:     in.ProjectID,
		SalesOrderID:  in.SalesOrderID,
		ItemID:        in.ItemID,
		Quantity:      in.Quantity,
		RequiredDate:  in.RequiredDate,
		EarliestStart: in.EarliestStart,
		WorkCenterID:  in.WorkCenterID,
		Status:        StatusPending,
		Remarks:       in.Remarks,
	}
	wo.Priority = 3
	if in.Priority != nil {
		wo.Priority = *in.Priority
	}
	// 自动编号:Django save() 用 generate_code('SCH')。本轮用时间序占位,确切规则待 CodeRule 迁移。
	if wo.OrderNo == "" {
		wo.OrderNo = s.genOrderNo(ctx)
	}
	if err := s.repo.Create(ctx, wo); err != nil {
		return nil, err
	}
	return wo, nil
}

// genOrderNo 生成工单号占位实现。
// TODO(port): 接入 apps.core.utils.generate_code('SCH') 对应的 CodeRule 序列,保证与 Django 同源。
func (s *Service) genOrderNo(ctx context.Context) string {
	for i := 0; i < 5; i++ {
		no := fmt.Sprintf("SCH%s", time.Now().Format("20060102150405.000"))
		if exists, err := s.repo.ExistsOrderNo(ctx, no); err == nil && !exists {
			return no
		}
		time.Sleep(time.Millisecond)
	}
	return fmt.Sprintf("SCH%d", time.Now().UnixNano())
}

func (s *Service) Update(ctx context.Context, id uint64, in UpdateInput) (*WorkOrder, error) {
	wo, err := s.Get(ctx, id)
	if err != nil {
		return nil, err
	}
	if in.ProjectID != nil {
		wo.ProjectID = in.ProjectID
	}
	if in.SalesOrderID != nil {
		wo.SalesOrderID = in.SalesOrderID
	}
	if in.ItemID != nil {
		wo.ItemID = in.ItemID
	}
	if in.Quantity != nil {
		wo.Quantity = *in.Quantity
	}
	if in.RequiredDate != nil {
		wo.RequiredDate = *in.RequiredDate
	}
	if in.EarliestStart != nil {
		wo.EarliestStart = in.EarliestStart
	}
	if in.WorkCenterID != nil {
		wo.WorkCenterID = in.WorkCenterID
	}
	if in.PlannedStart != nil {
		wo.PlannedStart = in.PlannedStart
	}
	if in.PlannedEnd != nil {
		wo.PlannedEnd = in.PlannedEnd
	}
	if in.PlannedHours != nil {
		wo.PlannedHours = in.PlannedHours
	}
	if in.Priority != nil {
		wo.Priority = *in.Priority
	}
	if in.Remarks != nil {
		wo.Remarks = *in.Remarks
	}
	if err := s.repo.Update(ctx, wo); err != nil {
		return nil, err
	}
	return wo, nil
}

func (s *Service) Delete(ctx context.Context, id uint64) error {
	if _, err := s.Get(ctx, id); err != nil {
		return err
	}
	return s.repo.SoftDelete(ctx, id)
}

// Start 开始生产:仅允许 SCHEDULED→IN_PROGRESS(忠实迁移 Django start action)。
func (s *Service) Start(ctx context.Context, id uint64) (*WorkOrder, error) {
	wo, err := s.Get(ctx, id)
	if err != nil {
		return nil, err
	}
	if wo.Status != StatusScheduled {
		return nil, fmt.Errorf("%w:只有已排程的工单可以开始生产", ErrBadTransition)
	}
	now := time.Now()
	wo.Status = StatusInProgress
	wo.ActualStart = &now
	if err := s.repo.Update(ctx, wo); err != nil {
		return nil, err
	}
	return wo, nil
}

// Complete 完成生产:仅允许 IN_PROGRESS→COMPLETED,并校验完成数量(忠实迁移 Django complete action)。
// TODO(port): Django 在同一事务内联动库存(完工入库 + 领料出库,见 post_completion_stock_moves),
// 需 inventory 模块落地后补全;本轮仅做状态流转与数量校验。
func (s *Service) Complete(ctx context.Context, id uint64, in CompleteInput) (*WorkOrder, error) {
	wo, err := s.Get(ctx, id)
	if err != nil {
		return nil, err
	}
	if wo.Status != StatusInProgress {
		return nil, fmt.Errorf("%w:只有生产中的工单可以完成", ErrBadTransition)
	}
	qty := wo.Quantity // 默认取工单数量(对齐 Django request.data.get('completed_qty', order.quantity))
	if in.CompletedQty != nil {
		qty = *in.CompletedQty
	}
	if qty < 0 {
		return nil, ErrQtyNegative
	}
	if qty > wo.Quantity {
		return nil, fmt.Errorf("%w %g", ErrQtyExceed, wo.Quantity)
	}
	now := time.Now()
	wo.Status = StatusCompleted
	wo.ActualEnd = &now
	wo.CompletedQty = qty
	if err := s.repo.Update(ctx, wo); err != nil {
		return nil, err
	}
	return wo, nil
}
