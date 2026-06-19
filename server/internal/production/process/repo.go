package process

import (
	"context"

	"github.com/atm-erp/server/internal/iam"
	"gorm.io/gorm"
)

const scopeModule = "production"

type Repo struct{ db *gorm.DB }

func NewRepo(db *gorm.DB) *Repo { return &Repo{db: db} }

func (r *Repo) scoped(ctx context.Context) *gorm.DB {
	q := r.db.WithContext(ctx).Model(&Process{})
	if u, ok := iam.AuthUserFrom(ctx); ok {
		q = iam.ApplyScope(q, u, scopeModule, "created_by_id")
	}
	return q
}

func (r *Repo) List(ctx context.Context, q ListQuery, offset, limit int) ([]Process, int64, error) {
	tx := r.scoped(ctx)
	if q.RoutingID != nil {
		tx = tx.Where("routing_id = ?", *q.RoutingID)
	}
	if q.OperationType != "" {
		tx = tx.Where("operation_type = ?", q.OperationType)
	}
	if q.WorkStationID != nil {
		tx = tx.Where("work_station_id = ?", *q.WorkStationID)
	}
	if q.IsOutsourced != nil {
		tx = tx.Where("is_outsourced = ?", *q.IsOutsourced)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var rows []Process
	// Django Meta.ordering=['routing','sequence']
	if err := tx.Order("routing_id ASC, sequence ASC").Offset(offset).Limit(limit).Find(&rows).Error; err != nil {
		return nil, 0, err
	}
	return rows, total, nil
}

func (r *Repo) Get(ctx context.Context, id uint64) (*Process, error) {
	var p Process
	if err := r.scoped(ctx).Where("id = ?", id).First(&p).Error; err != nil {
		return nil, err
	}
	return &p, nil
}

func (r *Repo) Create(ctx context.Context, p *Process) error {
	return r.db.WithContext(ctx).Create(p).Error
}

func (r *Repo) Update(ctx context.Context, p *Process) error {
	return r.db.WithContext(ctx).Save(p).Error
}

func (r *Repo) SoftDelete(ctx context.Context, id uint64) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&Process{}).Error
}

// ExistsSequence 校验同一路线下工序号唯一(对齐 unique_together=['routing','sequence'])。
func (r *Repo) ExistsSequence(ctx context.Context, routingID uint64, seq int, excludeID uint64) (bool, error) {
	tx := r.db.WithContext(ctx).Model(&Process{}).Where("routing_id = ? AND sequence = ?", routingID, seq)
	if excludeID > 0 {
		tx = tx.Where("id <> ?", excludeID)
	}
	var cnt int64
	if err := tx.Count(&cnt).Error; err != nil {
		return false, err
	}
	return cnt > 0, nil
}

// RecalcRoutingTotals 工序增改删后回写所属路线的工时合计,
// 对齐 Django RoutingOperationViewSet.perform_create/update → routing.calculate_totals()。
// 直接写 production_routing_template 表,避免跨包 import routing。
func (r *Repo) RecalcRoutingTotals(ctx context.Context, routingID uint64) error {
	var res struct {
		Standard float64
		Setup    float64
	}
	if err := r.db.WithContext(ctx).
		Table("production_routing_operation").
		Select("COALESCE(SUM(standard_hours),0) AS standard, COALESCE(SUM(setup_hours),0) AS setup").
		Where("routing_id = ? AND is_deleted = ?", routingID, false).
		Scan(&res).Error; err != nil {
		return err
	}
	return r.db.WithContext(ctx).
		Table("production_routing_template").
		Where("id = ?", routingID).
		Updates(map[string]any{
			"total_standard_hours": res.Standard,
			"total_setup_hours":    res.Setup,
		}).Error
}
