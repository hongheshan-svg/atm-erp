package routing

import (
	"context"

	"github.com/atm-erp/server/internal/iam"
	"gorm.io/gorm"
)

const scopeModule = "production"

type Repo struct{ db *gorm.DB }

func NewRepo(db *gorm.DB) *Repo { return &Repo{db: db} }

func (r *Repo) scoped(ctx context.Context) *gorm.DB {
	q := r.db.WithContext(ctx).Model(&Routing{})
	if u, ok := iam.AuthUserFrom(ctx); ok {
		q = iam.ApplyScope(q, u, scopeModule, "created_by_id")
	}
	return q
}

func (r *Repo) List(ctx context.Context, q ListQuery, offset, limit int) ([]Routing, int64, error) {
	tx := r.scoped(ctx)
	if q.Keyword != "" {
		kw := "%" + q.Keyword + "%"
		tx = tx.Where("code LIKE ? OR name LIKE ?", kw, kw)
	}
	if q.Status != "" {
		tx = tx.Where("status = ?", q.Status)
	}
	if q.ProductCategoryID != nil {
		tx = tx.Where("product_category_id = ?", *q.ProductCategoryID)
	}
	if q.IsActive != nil {
		tx = tx.Where("is_active = ?", *q.IsActive)
	}
	if q.IsCurrent != nil {
		tx = tx.Where("is_current = ?", *q.IsCurrent)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var rows []Routing
	if err := tx.Order("code ASC").Offset(offset).Limit(limit).Find(&rows).Error; err != nil {
		return nil, 0, err
	}
	return rows, total, nil
}

func (r *Repo) Get(ctx context.Context, id uint64) (*Routing, error) {
	var rt Routing
	if err := r.scoped(ctx).Where("id = ?", id).First(&rt).Error; err != nil {
		return nil, err
	}
	return &rt, nil
}

func (r *Repo) Create(ctx context.Context, rt *Routing) error {
	return r.db.WithContext(ctx).Create(rt).Error
}

func (r *Repo) Update(ctx context.Context, rt *Routing) error {
	return r.db.WithContext(ctx).Save(rt).Error
}

func (r *Repo) SoftDelete(ctx context.Context, id uint64) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&Routing{}).Error
}

func (r *Repo) ExistsCode(ctx context.Context, code string) (bool, error) {
	var cnt int64
	if err := r.db.WithContext(ctx).Model(&Routing{}).Where("code = ?", code).Count(&cnt).Error; err != nil {
		return false, err
	}
	return cnt > 0, nil
}

// SumOperationHours 汇总该路线下未软删除工序的 standard_hours / setup_hours,
// 对齐 Django RoutingTemplate.calculate_totals。表名硬编码避免跨包 import process。
func (r *Repo) SumOperationHours(ctx context.Context, routingID uint64) (standard, setup float64, err error) {
	var res struct {
		Standard float64
		Setup    float64
	}
	q := r.db.WithContext(ctx).
		Table("production_routing_operation").
		Select("COALESCE(SUM(standard_hours),0) AS standard, COALESCE(SUM(setup_hours),0) AS setup").
		Where("routing_id = ? AND is_deleted = ?", routingID, false)
	if err = q.Scan(&res).Error; err != nil {
		return 0, 0, err
	}
	return res.Standard, res.Setup, nil
}
