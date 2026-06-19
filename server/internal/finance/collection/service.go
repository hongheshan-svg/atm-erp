package collection

import (
	"context"

	"github.com/shopspring/decimal"
	"gorm.io/gorm"
)

// 节点状态。
const (
	MilestonePending   = "PENDING"
	MilestonePartial   = "PARTIAL"
	MilestoneCollected = "COLLECTED"
)

// 计划状态。
const (
	PlanDraft      = "DRAFT"
	PlanInProgress = "IN_PROGRESS"
	PlanCompleted  = "COMPLETED"
)

// MilestoneStatus 纯函数,对齐 Django:>=planned → COLLECTED;>0 → PARTIAL;否则 PENDING。
func MilestoneStatus(collected, planned decimal.Decimal) string {
	if collected.GreaterThanOrEqual(planned) {
		return MilestoneCollected
	}
	if collected.IsPositive() {
		return MilestonePartial
	}
	return MilestonePending
}

// PlanStatus 纯函数,对齐 Django:>=total → COMPLETED;否则当前为 DRAFT → IN_PROGRESS;否则不变。
func PlanStatus(collected, total decimal.Decimal, current string) string {
	if collected.GreaterThanOrEqual(total) {
		return PlanCompleted
	}
	if current == PlanDraft {
		return PlanInProgress
	}
	return current
}

type Service struct{ db *gorm.DB }

func NewService(db *gorm.DB) *Service { return &Service{db: db} }

// AddRecord 新增一条收款记录并级联汇总(记录→节点→计划),对齐 CollectionRecord.save。
// 整个级联在一个事务内完成。
func (s *Service) AddRecord(ctx context.Context, rec *CollectionRecord) error {
	return s.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		if err := tx.Create(rec).Error; err != nil {
			return err
		}

		// 1) 节点汇总
		var m CollectionMilestone
		if err := tx.First(&m, rec.MilestoneID).Error; err != nil {
			return err
		}
		var mSum decimal.Decimal
		if err := tx.Raw(
			"SELECT COALESCE(SUM(amount),0) FROM collection_record WHERE milestone_id = ? AND deleted_at IS NULL",
			m.ID,
		).Row().Scan(&mSum); err != nil {
			return err
		}
		m.CollectedAmount = mSum
		m.Status = MilestoneStatus(mSum, m.PlannedAmount)
		if m.Status == MilestoneCollected && m.ActualDate == nil {
			d := rec.CollectionDate
			m.ActualDate = &d
		}
		if err := tx.Save(&m).Error; err != nil {
			return err
		}

		// 2) 计划汇总(该计划下所有节点的所有记录)
		var p CollectionPlan
		if err := tx.First(&p, m.PlanID).Error; err != nil {
			return err
		}
		var pSum decimal.Decimal
		if err := tx.Raw(
			`SELECT COALESCE(SUM(r.amount),0) FROM collection_record r
			 JOIN collection_milestone cm ON cm.id = r.milestone_id
			 WHERE cm.plan_id = ? AND r.deleted_at IS NULL AND cm.deleted_at IS NULL`,
			p.ID,
		).Row().Scan(&pSum); err != nil {
			return err
		}
		p.CollectedAmount = pSum
		p.Status = PlanStatus(pSum, p.TotalAmount, p.Status)
		return tx.Save(&p).Error
	})
}
