package workorder

import (
	"context"

	"github.com/atm-erp/server/internal/iam"
	"gorm.io/gorm"
)

// scopeModule 标识权限/数据范围模块(对齐 Django permission_module='production')。
const scopeModule = "production"

type Repo struct{ db *gorm.DB }

func NewRepo(db *gorm.DB) *Repo { return &Repo{db: db} }

// scoped 套用数据范围过滤(软删除由 gorm.DeletedAt 默认过滤)。
func (r *Repo) scoped(ctx context.Context) *gorm.DB {
	q := r.db.WithContext(ctx).Model(&WorkOrder{})
	if u, ok := iam.AuthUserFrom(ctx); ok {
		q = iam.ApplyScope(q, u, scopeModule, "created_by_id")
	}
	return q
}

func (r *Repo) List(ctx context.Context, q ListQuery, offset, limit int) ([]WorkOrder, int64, error) {
	tx := r.scoped(ctx)
	if q.Keyword != "" {
		tx = tx.Where("order_no LIKE ?", "%"+q.Keyword+"%")
	}
	if q.Status != "" {
		tx = tx.Where("status = ?", q.Status)
	}
	if q.Priority != nil {
		tx = tx.Where("priority = ?", *q.Priority)
	}
	if q.WorkCenterID != nil {
		tx = tx.Where("work_center_id = ?", *q.WorkCenterID)
	}
	if q.ProjectID != nil {
		tx = tx.Where("project_id = ?", *q.ProjectID)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var rows []WorkOrder
	// Django Meta.ordering=['priority','required_date']
	if err := tx.Order("priority ASC, required_date ASC").Offset(offset).Limit(limit).Find(&rows).Error; err != nil {
		return nil, 0, err
	}
	return rows, total, nil
}

func (r *Repo) Get(ctx context.Context, id uint64) (*WorkOrder, error) {
	var wo WorkOrder
	if err := r.scoped(ctx).Where("id = ?", id).First(&wo).Error; err != nil {
		return nil, err
	}
	return &wo, nil
}

func (r *Repo) Create(ctx context.Context, wo *WorkOrder) error {
	return r.db.WithContext(ctx).Create(wo).Error
}

func (r *Repo) Update(ctx context.Context, wo *WorkOrder) error {
	return r.db.WithContext(ctx).Save(wo).Error
}

func (r *Repo) SoftDelete(ctx context.Context, id uint64) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&WorkOrder{}).Error
}

// ExistsOrderNo 编号唯一性校验(对齐 unique=True)。
func (r *Repo) ExistsOrderNo(ctx context.Context, no string) (bool, error) {
	var cnt int64
	if err := r.db.WithContext(ctx).Model(&WorkOrder{}).Where("order_no = ?", no).Count(&cnt).Error; err != nil {
		return false, err
	}
	return cnt > 0, nil
}
