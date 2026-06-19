package kanban

import (
	"context"

	"github.com/atm-erp/server/internal/iam"
	"gorm.io/gorm"
)

const scopeModule = "production"

type Repo struct{ db *gorm.DB }

func NewRepo(db *gorm.DB) *Repo { return &Repo{db: db} }

func (r *Repo) scoped(ctx context.Context) *gorm.DB {
	q := r.db.WithContext(ctx).Model(&KanbanWIPRule{})
	if u, ok := iam.AuthUserFrom(ctx); ok {
		q = iam.ApplyScope(q, u, scopeModule, "created_by_id")
	}
	return q
}

func (r *Repo) List(ctx context.Context, q ListQuery, offset, limit int) ([]KanbanWIPRule, int64, error) {
	tx := r.scoped(ctx)
	if q.Keyword != "" {
		tx = tx.Where("process_name LIKE ?", "%"+q.Keyword+"%")
	}
	if q.IsActive != nil {
		tx = tx.Where("is_active = ?", *q.IsActive)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var rows []KanbanWIPRule
	if err := tx.Order("id DESC").Offset(offset).Limit(limit).Find(&rows).Error; err != nil {
		return nil, 0, err
	}
	return rows, total, nil
}

func (r *Repo) Get(ctx context.Context, id uint64) (*KanbanWIPRule, error) {
	var k KanbanWIPRule
	if err := r.scoped(ctx).Where("id = ?", id).First(&k).Error; err != nil {
		return nil, err
	}
	return &k, nil
}

func (r *Repo) Create(ctx context.Context, k *KanbanWIPRule) error {
	return r.db.WithContext(ctx).Create(k).Error
}

func (r *Repo) Update(ctx context.Context, k *KanbanWIPRule) error {
	return r.db.WithContext(ctx).Save(k).Error
}

func (r *Repo) SoftDelete(ctx context.Context, id uint64) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&KanbanWIPRule{}).Error
}

// ExistsProcessName 工序名唯一性校验(对齐 unique=True)。
func (r *Repo) ExistsProcessName(ctx context.Context, name string, excludeID uint64) (bool, error) {
	tx := r.db.WithContext(ctx).Model(&KanbanWIPRule{}).Where("process_name = ?", name)
	if excludeID > 0 {
		tx = tx.Where("id <> ?", excludeID)
	}
	var cnt int64
	if err := tx.Count(&cnt).Error; err != nil {
		return false, err
	}
	return cnt > 0, nil
}
