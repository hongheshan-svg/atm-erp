package item

import (
	"context"

	"github.com/atm-erp/server/internal/iam"
	"gorm.io/gorm"
)

// scopeModule 标识该资源所属权限/数据范围模块。
const scopeModule = "masterdata"

type Repo struct{ db *gorm.DB }

func NewRepo(db *gorm.DB) *Repo { return &Repo{db: db} }

// scoped 返回已套用数据范围过滤的查询(软删除由 gorm.DeletedAt 默认过滤)。
func (r *Repo) scoped(ctx context.Context) *gorm.DB {
	q := r.db.WithContext(ctx).Model(&Item{})
	if u, ok := iam.AuthUserFrom(ctx); ok {
		q = iam.ApplyScope(q, u, scopeModule, "created_by_id")
	}
	return q
}

func (r *Repo) List(ctx context.Context, q ListQuery, offset, limit int) ([]Item, int64, error) {
	tx := r.scoped(ctx)
	if q.Keyword != "" {
		kw := "%" + q.Keyword + "%"
		tx = tx.Where("sku LIKE ? OR name LIKE ?", kw, kw)
	}
	if q.CategoryID != "" {
		tx = tx.Where("category_id = ?", q.CategoryID)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var items []Item
	if err := tx.Order("id DESC").Offset(offset).Limit(limit).Find(&items).Error; err != nil {
		return nil, 0, err
	}
	return items, total, nil
}

func (r *Repo) Get(ctx context.Context, id uint64) (*Item, error) {
	var it Item
	if err := r.scoped(ctx).Where("id = ?", id).First(&it).Error; err != nil {
		return nil, err
	}
	return &it, nil
}

func (r *Repo) Create(ctx context.Context, it *Item) error {
	return r.db.WithContext(ctx).Create(it).Error
}

func (r *Repo) Update(ctx context.Context, it *Item) error {
	return r.db.WithContext(ctx).Save(it).Error
}

func (r *Repo) SoftDelete(ctx context.Context, id uint64) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&Item{}).Error
}
