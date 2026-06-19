package inventory

import (
	"context"

	"github.com/atm-erp/server/internal/iam"
	"gorm.io/gorm"
)

// scopeModule 标识库存模块的权限/数据范围归属。
const scopeModule = "inventory"

type Repo struct{ db *gorm.DB }

func NewRepo(db *gorm.DB) *Repo { return &Repo{db: db} }

// DB 暴露底层 *gorm.DB,供 service 跑事务(账实更新需同库事务)。
func (r *Repo) DB() *gorm.DB { return r.db }

// scoped 套用数据范围过滤(软删除由 gorm.DeletedAt 默认过滤)。
func (r *Repo) scoped(ctx context.Context, m any) *gorm.DB {
	q := r.db.WithContext(ctx).Model(m)
	if u, ok := iam.AuthUserFrom(ctx); ok {
		q = iam.ApplyScope(q, u, scopeModule, "created_by_id")
	}
	return q
}

// ── Stock ──────────────────────────────────────────────────────────────

func (r *Repo) ListStock(ctx context.Context, q StockListQuery, offset, limit int) ([]Stock, int64, error) {
	tx := r.scoped(ctx, &Stock{})
	if q.WarehouseID != 0 {
		tx = tx.Where("warehouse_id = ?", q.WarehouseID)
	}
	if q.ItemID != 0 {
		tx = tx.Where("item_id = ?", q.ItemID)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var rows []Stock
	if err := tx.Order("warehouse_id ASC, item_id ASC").Offset(offset).Limit(limit).Find(&rows).Error; err != nil {
		return nil, 0, err
	}
	for i := range rows {
		rows[i].computeAvailable()
	}
	return rows, total, nil
}

func (r *Repo) GetStock(ctx context.Context, id uint64) (*Stock, error) {
	var s Stock
	if err := r.scoped(ctx, &Stock{}).Where("id = ?", id).First(&s).Error; err != nil {
		return nil, err
	}
	s.computeAvailable()
	return &s, nil
}

// ── StockMove ──────────────────────────────────────────────────────────

func (r *Repo) ListMove(ctx context.Context, q StockMoveListQuery, offset, limit int) ([]StockMove, int64, error) {
	tx := r.scoped(ctx, &StockMove{})
	if q.ItemID != 0 {
		tx = tx.Where("item_id = ?", q.ItemID)
	}
	if q.MoveType != "" {
		tx = tx.Where("move_type = ?", q.MoveType)
	}
	if q.Status != "" {
		tx = tx.Where("status = ?", q.Status)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var rows []StockMove
	if err := tx.Order("move_date DESC, created_at DESC").Offset(offset).Limit(limit).Find(&rows).Error; err != nil {
		return nil, 0, err
	}
	return rows, total, nil
}

func (r *Repo) GetMove(ctx context.Context, id uint64) (*StockMove, error) {
	var m StockMove
	if err := r.scoped(ctx, &StockMove{}).Where("id = ?", id).First(&m).Error; err != nil {
		return nil, err
	}
	return &m, nil
}

func (r *Repo) CreateMove(ctx context.Context, m *StockMove) error {
	return r.db.WithContext(ctx).Create(m).Error
}

func (r *Repo) UpdateMove(ctx context.Context, m *StockMove) error {
	return r.db.WithContext(ctx).Save(m).Error
}

func (r *Repo) SoftDeleteMove(ctx context.Context, id uint64) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&StockMove{}).Error
}

// ── Batch ──────────────────────────────────────────────────────────────

func (r *Repo) ListBatch(ctx context.Context, q BatchListQuery, offset, limit int) ([]Batch, int64, error) {
	tx := r.scoped(ctx, &Batch{})
	if q.ItemID != 0 {
		tx = tx.Where("item_id = ?", q.ItemID)
	}
	if q.WarehouseID != 0 {
		tx = tx.Where("warehouse_id = ?", q.WarehouseID)
	}
	if q.QualityStatus != "" {
		tx = tx.Where("quality_status = ?", q.QualityStatus)
	}
	if q.ExpiringOnly {
		tx = tx.Where("expiry_date IS NOT NULL")
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var rows []Batch
	// Django ordering: ['expiry_date', '-manufacture_date']
	if err := tx.Order("expiry_date ASC, manufacture_date DESC").Offset(offset).Limit(limit).Find(&rows).Error; err != nil {
		return nil, 0, err
	}
	for i := range rows {
		rows[i].computeExpiry()
	}
	return rows, total, nil
}

func (r *Repo) GetBatch(ctx context.Context, id uint64) (*Batch, error) {
	var b Batch
	if err := r.scoped(ctx, &Batch{}).Where("id = ?", id).First(&b).Error; err != nil {
		return nil, err
	}
	b.computeExpiry()
	return &b, nil
}

func (r *Repo) CreateBatch(ctx context.Context, b *Batch) error {
	return r.db.WithContext(ctx).Create(b).Error
}

func (r *Repo) UpdateBatch(ctx context.Context, b *Batch) error {
	return r.db.WithContext(ctx).Save(b).Error
}

func (r *Repo) SoftDeleteBatch(ctx context.Context, id uint64) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&Batch{}).Error
}

// ── StockAlert ─────────────────────────────────────────────────────────

func (r *Repo) ListAlert(ctx context.Context, q AlertListQuery, offset, limit int) ([]StockAlert, int64, error) {
	tx := r.scoped(ctx, &StockAlert{})
	if q.ItemID != 0 {
		tx = tx.Where("item_id = ?", q.ItemID)
	}
	if q.Status != "" {
		tx = tx.Where("status = ?", q.Status)
	}
	if q.Severity != "" {
		tx = tx.Where("severity = ?", q.Severity)
	}
	if q.AlertType != "" {
		tx = tx.Where("alert_type = ?", q.AlertType)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var rows []StockAlert
	if err := tx.Order("created_at DESC").Offset(offset).Limit(limit).Find(&rows).Error; err != nil {
		return nil, 0, err
	}
	return rows, total, nil
}

func (r *Repo) GetAlert(ctx context.Context, id uint64) (*StockAlert, error) {
	var a StockAlert
	if err := r.scoped(ctx, &StockAlert{}).Where("id = ?", id).First(&a).Error; err != nil {
		return nil, err
	}
	return &a, nil
}

func (r *Repo) CreateAlert(ctx context.Context, a *StockAlert) error {
	return r.db.WithContext(ctx).Create(a).Error
}

func (r *Repo) UpdateAlert(ctx context.Context, a *StockAlert) error {
	return r.db.WithContext(ctx).Save(a).Error
}

func (r *Repo) SoftDeleteAlert(ctx context.Context, id uint64) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&StockAlert{}).Error
}
