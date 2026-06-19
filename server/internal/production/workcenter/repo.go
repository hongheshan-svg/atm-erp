package workcenter

import (
	"context"

	"github.com/atm-erp/server/internal/iam"
	"gorm.io/gorm"
)

const scopeModule = "production"

type Repo struct{ db *gorm.DB }

func NewRepo(db *gorm.DB) *Repo { return &Repo{db: db} }

func (r *Repo) scoped(ctx context.Context) *gorm.DB {
	q := r.db.WithContext(ctx).Model(&WorkCenter{})
	if u, ok := iam.AuthUserFrom(ctx); ok {
		q = iam.ApplyScope(q, u, scopeModule, "created_by")
	}
	return q
}

func (r *Repo) List(ctx context.Context, q ListQuery, offset, limit int) ([]WorkCenter, int64, error) {
	tx := r.scoped(ctx)
	if q.Keyword != "" {
		kw := "%" + q.Keyword + "%"
		tx = tx.Where("code LIKE ? OR name LIKE ?", kw, kw)
	}
	if q.IsActive != nil {
		tx = tx.Where("is_active = ?", *q.IsActive)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var rows []WorkCenter
	if err := tx.Order("code ASC").Offset(offset).Limit(limit).Find(&rows).Error; err != nil {
		return nil, 0, err
	}
	return rows, total, nil
}

func (r *Repo) Get(ctx context.Context, id uint64) (*WorkCenter, error) {
	var wc WorkCenter
	if err := r.scoped(ctx).Where("id = ?", id).First(&wc).Error; err != nil {
		return nil, err
	}
	return &wc, nil
}

func (r *Repo) Create(ctx context.Context, wc *WorkCenter) error {
	return r.db.WithContext(ctx).Create(wc).Error
}

func (r *Repo) Update(ctx context.Context, wc *WorkCenter) error {
	return r.db.WithContext(ctx).Save(wc).Error
}

func (r *Repo) SoftDelete(ctx context.Context, id uint64) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&WorkCenter{}).Error
}

func (r *Repo) ExistsCode(ctx context.Context, code string) (bool, error) {
	var cnt int64
	if err := r.db.WithContext(ctx).Model(&WorkCenter{}).Where("code = ?", code).Count(&cnt).Error; err != nil {
		return false, err
	}
	return cnt > 0, nil
}
