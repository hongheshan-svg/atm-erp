package supplier

import (
	"context"

	"github.com/atm-erp/server/internal/iam"
	"gorm.io/gorm"
)

const scopeModule = "masterdata"

type Repo struct{ db *gorm.DB }

func NewRepo(db *gorm.DB) *Repo { return &Repo{db: db} }

func (r *Repo) scoped(ctx context.Context) *gorm.DB {
	q := r.db.WithContext(ctx).Model(&Supplier{})
	if u, ok := iam.AuthUserFrom(ctx); ok {
		q = iam.ApplyScope(q, u, scopeModule, "created_by")
	}
	return q
}

func (r *Repo) List(ctx context.Context, q ListQuery, offset, limit int) ([]Supplier, int64, error) {
	tx := r.scoped(ctx)
	if q.Keyword != "" {
		kw := "%" + q.Keyword + "%"
		tx = tx.Where("code LIKE ? OR name LIKE ? OR short_name LIKE ?", kw, kw, kw)
	}
	if q.Status != "" {
		tx = tx.Where("status = ?", q.Status)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var rows []Supplier
	if err := tx.Order("created_at DESC").Offset(offset).Limit(limit).Find(&rows).Error; err != nil {
		return nil, 0, err
	}
	return rows, total, nil
}

func (r *Repo) Get(ctx context.Context, id uint64) (*Supplier, error) {
	var row Supplier
	if err := r.scoped(ctx).Where("id = ?", id).First(&row).Error; err != nil {
		return nil, err
	}
	return &row, nil
}

func (r *Repo) ExistsByCode(ctx context.Context, code string) (bool, error) {
	var cnt int64
	if err := r.db.WithContext(ctx).Model(&Supplier{}).Where("code = ?", code).Count(&cnt).Error; err != nil {
		return false, err
	}
	return cnt > 0, nil
}

func (r *Repo) MaxCodeLike(ctx context.Context, prefix string) (string, error) {
	var max string
	err := r.db.WithContext(ctx).Model(&Supplier{}).
		Where("code LIKE ?", prefix+"%").
		Select("COALESCE(MAX(code), '')").Scan(&max).Error
	return max, err
}

func (r *Repo) Create(ctx context.Context, row *Supplier) error {
	return r.db.WithContext(ctx).Create(row).Error
}

func (r *Repo) Update(ctx context.Context, row *Supplier) error {
	return r.db.WithContext(ctx).Save(row).Error
}

func (r *Repo) SoftDelete(ctx context.Context, id uint64) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&Supplier{}).Error
}
