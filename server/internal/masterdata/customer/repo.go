package customer

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
	q := r.db.WithContext(ctx).Model(&Customer{})
	if u, ok := iam.AuthUserFrom(ctx); ok {
		q = iam.ApplyScope(q, u, scopeModule, "created_by_id")
	}
	return q
}

func (r *Repo) List(ctx context.Context, q ListQuery, offset, limit int) ([]Customer, int64, error) {
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
	var rows []Customer
	if err := tx.Order("created_at DESC").Offset(offset).Limit(limit).Find(&rows).Error; err != nil {
		return nil, 0, err
	}
	return rows, total, nil
}

func (r *Repo) Get(ctx context.Context, id uint64) (*Customer, error) {
	var row Customer
	if err := r.scoped(ctx).Where("id = ?", id).First(&row).Error; err != nil {
		return nil, err
	}
	return &row, nil
}

// ExistsByCode 校验编码唯一性(忽略软删除记录由默认 scope 过滤)。
func (r *Repo) ExistsByCode(ctx context.Context, code string) (bool, error) {
	var cnt int64
	if err := r.db.WithContext(ctx).Model(&Customer{}).Where("code = ?", code).Count(&cnt).Error; err != nil {
		return false, err
	}
	return cnt > 0, nil
}

// MaxCodeLike 取指定前缀下最大编码,用于流水号生成。
func (r *Repo) MaxCodeLike(ctx context.Context, prefix string) (string, error) {
	var max string
	err := r.db.WithContext(ctx).Model(&Customer{}).
		Where("code LIKE ?", prefix+"%").
		Select("COALESCE(MAX(code), '')").Scan(&max).Error
	return max, err
}

func (r *Repo) Create(ctx context.Context, row *Customer) error {
	return r.db.WithContext(ctx).Create(row).Error
}

func (r *Repo) Update(ctx context.Context, row *Customer) error {
	return r.db.WithContext(ctx).Save(row).Error
}

func (r *Repo) SoftDelete(ctx context.Context, id uint64) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&Customer{}).Error
}
