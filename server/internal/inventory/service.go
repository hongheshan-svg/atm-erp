package inventory

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/atm-erp/server/internal/iam"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

var (
	ErrNotFound      = errors.New("记录不存在")
	ErrInsufficient  = errors.New("库存不足")
	ErrInvalidStatus = errors.New("状态不允许该操作")
	ErrBadMoveType   = errors.New("无效的移动类型")
	ErrBadDate       = errors.New("日期格式应为 YYYY-MM-DD")
)

const dateLayout = "2006-01-02"

type Service struct{ repo *Repo }

func NewService(repo *Repo) *Service { return &Service{repo: repo} }

func parseDate(s string) (time.Time, error) {
	t, err := time.Parse(dateLayout, s)
	if err != nil {
		return time.Time{}, ErrBadDate
	}
	return t, nil
}

func parseDatePtr(s *string) (*time.Time, error) {
	if s == nil || *s == "" {
		return nil, nil
	}
	t, err := parseDate(*s)
	if err != nil {
		return nil, err
	}
	return &t, nil
}

// ── Stock(只读)────────────────────────────────────────────────────────

func (s *Service) ListStock(ctx context.Context, q StockListQuery, offset, limit int) ([]Stock, int64, error) {
	return s.repo.ListStock(ctx, q, offset, limit)
}

func (s *Service) GetStock(ctx context.Context, id uint64) (*Stock, error) {
	st, err := s.repo.GetStock(ctx, id)
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, ErrNotFound
	}
	return st, err
}

// ── StockMove ──────────────────────────────────────────────────────────

func (s *Service) ListMove(ctx context.Context, q StockMoveListQuery, offset, limit int) ([]StockMove, int64, error) {
	return s.repo.ListMove(ctx, q, offset, limit)
}

func (s *Service) GetMove(ctx context.Context, id uint64) (*StockMove, error) {
	m, err := s.repo.GetMove(ctx, id)
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, ErrNotFound
	}
	return m, err
}

func validMoveType(t string) bool {
	switch t {
	case MoveTypeInPurchase, MoveTypeOutSales, MoveTypeOutProject, MoveTypeTransfer, MoveTypeAdjustment:
		return true
	}
	return false
}

// CreateMove 新建移动。move_no 留空自动生成。若 status=COMPLETED 则同步扣/加库存。
// 忠实迁移 Django StockMove.save:本行写入与库存更新置于同一事务,
// 出库不足时整笔回滚,杜绝残留假移动 + 账实不符。
func (s *Service) CreateMove(ctx context.Context, in StockMoveCreateInput) (*StockMove, error) {
	if !validMoveType(in.MoveType) {
		return nil, ErrBadMoveType
	}
	md, err := parseDate(in.MoveDate)
	if err != nil {
		return nil, err
	}
	status := in.Status
	if status == "" {
		status = MoveStatusDraft
	}
	m := &StockMove{
		ItemID:        in.ItemID,
		WarehouseFrom: in.WarehouseFrom,
		WarehouseTo:   in.WarehouseTo,
		Qty:           in.Qty,
		UnitCost:      in.UnitCost,
		MoveType:      in.MoveType,
		ReferenceType: in.ReferenceType,
		ReferenceID:   in.ReferenceID,
		ProjectID:     in.ProjectID,
		MoveDate:      md,
		Status:        status,
		Notes:         in.Notes,
	}

	uid := currentUserID(ctx)
	err = s.repo.DB().WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		if m.MoveNo == "" {
			m.MoveNo = generateMoveNo(tx)
		}
		if e := tx.Create(m).Error; e != nil {
			return e
		}
		if m.Status == MoveStatusCompleted {
			return applyMoveToStock(tx, m, uid)
		}
		return nil
	})
	if err != nil {
		return nil, err
	}
	return m, nil
}

// CompleteMove 将草稿移动置为 COMPLETED 并落库存(对齐 Django status 跃迁触发 _update_stock)。
func (s *Service) CompleteMove(ctx context.Context, id uint64) (*StockMove, error) {
	m, err := s.GetMove(ctx, id)
	if err != nil {
		return nil, err
	}
	if m.Status == MoveStatusCompleted {
		return m, nil // 已完成,幂等
	}
	if m.Status == MoveStatusCancelled {
		return nil, fmt.Errorf("%w: 已取消的移动不能完成", ErrInvalidStatus)
	}
	uid := currentUserID(ctx)
	err = s.repo.DB().WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		if e := tx.Model(&StockMove{}).Where("id = ?", id).Update("status", MoveStatusCompleted).Error; e != nil {
			return e
		}
		m.Status = MoveStatusCompleted
		return applyMoveToStock(tx, m, uid)
	})
	if err != nil {
		return nil, err
	}
	return m, nil
}

// UpdateMove 仅允许修改草稿移动(已完成的会影响账实,禁改)。
func (s *Service) UpdateMove(ctx context.Context, id uint64, in StockMoveUpdateInput) (*StockMove, error) {
	m, err := s.GetMove(ctx, id)
	if err != nil {
		return nil, err
	}
	if m.Status == MoveStatusCompleted {
		return nil, fmt.Errorf("%w: 已完成的移动不可修改", ErrInvalidStatus)
	}
	if in.Qty != nil {
		m.Qty = *in.Qty
	}
	if in.UnitCost != nil {
		m.UnitCost = *in.UnitCost
	}
	if in.WarehouseFrom != nil {
		m.WarehouseFrom = in.WarehouseFrom
	}
	if in.WarehouseTo != nil {
		m.WarehouseTo = in.WarehouseTo
	}
	if in.MoveType != nil {
		if !validMoveType(*in.MoveType) {
			return nil, ErrBadMoveType
		}
		m.MoveType = *in.MoveType
	}
	if in.MoveDate != nil {
		d, e := parseDate(*in.MoveDate)
		if e != nil {
			return nil, e
		}
		m.MoveDate = d
	}
	if in.Notes != nil {
		m.Notes = *in.Notes
	}
	if err := s.repo.UpdateMove(ctx, m); err != nil {
		return nil, err
	}
	return m, nil
}

func (s *Service) DeleteMove(ctx context.Context, id uint64) error {
	m, err := s.GetMove(ctx, id)
	if err != nil {
		return err
	}
	if m.Status == MoveStatusCompleted {
		return fmt.Errorf("%w: 已完成的移动不可删除", ErrInvalidStatus)
	}
	return s.repo.SoftDeleteMove(ctx, id)
}

// ── 账实更新核心(忠实迁移 Django _update_stock / 加权平均)──────────────

// applyMoveToStock 按移动类型落库存。tx 须为外层事务句柄,行锁防并发。
// 对齐 Django StockMove._update_stock。
func applyMoveToStock(tx *gorm.DB, m *StockMove, uid *uint64) error {
	switch m.MoveType {
	case MoveTypeInPurchase:
		return stockIn(tx, derefWH(m.WarehouseTo), m.ItemID, m.Qty, m.UnitCost, uid)
	case MoveTypeOutSales, MoveTypeOutProject:
		return stockOut(tx, derefWH(m.WarehouseFrom), m.ItemID, m.Qty)
	case MoveTypeTransfer:
		if err := stockOut(tx, derefWH(m.WarehouseFrom), m.ItemID, m.Qty); err != nil {
			return err
		}
		return stockIn(tx, derefWH(m.WarehouseTo), m.ItemID, m.Qty, m.UnitCost, uid)
	case MoveTypeAdjustment:
		// qty 恒为正;方向由仓库字段决定:to=盘盈入库,from=盘亏出库。
		if m.WarehouseTo != nil {
			return stockIn(tx, *m.WarehouseTo, m.ItemID, m.Qty, m.UnitCost, uid)
		}
		if m.WarehouseFrom != nil {
			return stockOut(tx, *m.WarehouseFrom, m.ItemID, m.Qty)
		}
		return nil
	}
	return ErrBadMoveType
}

func derefWH(p *uint64) uint64 {
	if p == nil {
		return 0
	}
	return *p
}

// stockIn 入库(加权平均成本)。对齐 Django _update_stock_in。
// new_avg = (old_qty*old_avg + qty*cost) / (old_qty+qty);new_qty<=0 时退回 cost。
func stockIn(tx *gorm.DB, warehouseID, itemID uint64, qty, cost float64, uid *uint64) error {
	if warehouseID == 0 {
		return errors.New("入库缺少目标仓库")
	}
	var st Stock
	err := tx.Clauses(clause.Locking{Strength: "UPDATE"}).
		Where("warehouse_id = ? AND item_id = ?", warehouseID, itemID).
		First(&st).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		// get_or_create defaults qty_on_hand=0, weighted_avg_cost=0
		st = Stock{WarehouseID: warehouseID, ItemID: itemID}
		st.CreatedBy = uid
		st.UpdatedBy = uid
	} else if err != nil {
		return err
	}

	oldValue := st.QtyOnHand * st.WeightedAvgCost
	newValue := qty * cost
	newQty := st.QtyOnHand + qty
	if newQty > 0 {
		st.WeightedAvgCost = (oldValue + newValue) / newQty
	} else {
		st.WeightedAvgCost = cost
	}
	st.QtyOnHand = newQty

	if st.ID == 0 {
		return tx.Create(&st).Error
	}
	return tx.Model(&Stock{}).Where("id = ?", st.ID).
		Updates(map[string]any{"qty_on_hand": st.QtyOnHand, "weighted_avg_cost": st.WeightedAvgCost}).Error
}

// stockOut 出库。对齐 Django _update_stock_out:库存不足抛错;Stock 不存在则静默跳过。
func stockOut(tx *gorm.DB, warehouseID, itemID uint64, qty float64) error {
	if warehouseID == 0 {
		return errors.New("出库缺少来源仓库")
	}
	var st Stock
	err := tx.Clauses(clause.Locking{Strength: "UPDATE"}).
		Where("warehouse_id = ? AND item_id = ?", warehouseID, itemID).
		First(&st).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil // Django: except Stock.DoesNotExist: pass
	}
	if err != nil {
		return err
	}
	if st.QtyOnHand < qty {
		return fmt.Errorf("%w: 物料 %d 在仓库 %d 当前库存 %.2f, 需要 %.2f",
			ErrInsufficient, itemID, warehouseID, st.QtyOnHand, qty)
	}
	st.QtyOnHand -= qty
	return tx.Model(&Stock{}).Where("id = ?", st.ID).Update("qty_on_hand", st.QtyOnHand).Error
}

// ── Batch ──────────────────────────────────────────────────────────────

func (s *Service) ListBatch(ctx context.Context, q BatchListQuery, offset, limit int) ([]Batch, int64, error) {
	return s.repo.ListBatch(ctx, q, offset, limit)
}

func (s *Service) GetBatch(ctx context.Context, id uint64) (*Batch, error) {
	b, err := s.repo.GetBatch(ctx, id)
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, ErrNotFound
	}
	return b, err
}

func (s *Service) CreateBatch(ctx context.Context, in BatchCreateInput) (*Batch, error) {
	mfg, err := parseDatePtr(in.ManufactureDate)
	if err != nil {
		return nil, err
	}
	exp, err := parseDatePtr(in.ExpiryDate)
	if err != nil {
		return nil, err
	}
	qs := in.QualityStatus
	if qs == "" {
		qs = BatchQualityPending
	}
	b := &Batch{
		BatchNo:         in.BatchNo,
		ItemID:          in.ItemID,
		WarehouseID:     in.WarehouseID,
		ManufactureDate: mfg,
		ExpiryDate:      exp,
		QtyOnHand:       in.QtyOnHand,
		UnitCost:        in.UnitCost,
		SupplierBatchNo: in.SupplierBatchNo,
		QualityStatus:   qs,
		Notes:           in.Notes,
	}
	if err := s.repo.CreateBatch(ctx, b); err != nil {
		return nil, err
	}
	b.computeExpiry()
	return b, nil
}

func (s *Service) UpdateBatch(ctx context.Context, id uint64, in BatchUpdateInput) (*Batch, error) {
	b, err := s.GetBatch(ctx, id)
	if err != nil {
		return nil, err
	}
	if in.ManufactureDate != nil {
		d, e := parseDatePtr(in.ManufactureDate)
		if e != nil {
			return nil, e
		}
		b.ManufactureDate = d
	}
	if in.ExpiryDate != nil {
		d, e := parseDatePtr(in.ExpiryDate)
		if e != nil {
			return nil, e
		}
		b.ExpiryDate = d
	}
	if in.QtyOnHand != nil {
		b.QtyOnHand = *in.QtyOnHand
	}
	if in.UnitCost != nil {
		b.UnitCost = *in.UnitCost
	}
	if in.SupplierBatchNo != nil {
		b.SupplierBatchNo = *in.SupplierBatchNo
	}
	if in.QualityStatus != nil {
		b.QualityStatus = *in.QualityStatus
	}
	if in.Notes != nil {
		b.Notes = *in.Notes
	}
	if err := s.repo.UpdateBatch(ctx, b); err != nil {
		return nil, err
	}
	b.computeExpiry()
	return b, nil
}

func (s *Service) DeleteBatch(ctx context.Context, id uint64) error {
	if _, err := s.GetBatch(ctx, id); err != nil {
		return err
	}
	return s.repo.SoftDeleteBatch(ctx, id)
}

// ── StockAlert ─────────────────────────────────────────────────────────

func (s *Service) ListAlert(ctx context.Context, q AlertListQuery, offset, limit int) ([]StockAlert, int64, error) {
	return s.repo.ListAlert(ctx, q, offset, limit)
}

func (s *Service) GetAlert(ctx context.Context, id uint64) (*StockAlert, error) {
	a, err := s.repo.GetAlert(ctx, id)
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, ErrNotFound
	}
	return a, err
}

func (s *Service) CreateAlert(ctx context.Context, in AlertCreateInput) (*StockAlert, error) {
	sev := in.Severity
	if sev == "" {
		sev = AlertSeverityWarning
	}
	a := &StockAlert{
		RuleID:         in.RuleID,
		ItemID:         in.ItemID,
		WarehouseID:    in.WarehouseID,
		AlertType:      in.AlertType,
		Severity:       sev,
		Title:          in.Title,
		Description:    in.Description,
		CurrentQty:     in.CurrentQty,
		ThresholdValue: in.ThresholdValue,
		Status:         AlertStatusActive,
	}
	if err := s.repo.CreateAlert(ctx, a); err != nil {
		return nil, err
	}
	return a, nil
}

// Acknowledge 确认预警(ACTIVE→ACKNOWLEDGED),记录处理人/时间。对齐 Django acknowledge。
func (s *Service) Acknowledge(ctx context.Context, id uint64) (*StockAlert, error) {
	return s.transition(ctx, id, AlertStatusAcknowledged, "")
}

// Resolve 解决预警,写入 resolution。对齐 Django resolve。
func (s *Service) Resolve(ctx context.Context, id uint64, resolution string) (*StockAlert, error) {
	return s.transition(ctx, id, AlertStatusResolved, resolution)
}

// Ignore 忽略预警,reason 写入 resolution(缺省"已忽略")。对齐 Django ignore。
func (s *Service) Ignore(ctx context.Context, id uint64, reason string) (*StockAlert, error) {
	if reason == "" {
		reason = "已忽略"
	}
	return s.transition(ctx, id, AlertStatusIgnored, reason)
}

func (s *Service) transition(ctx context.Context, id uint64, status, resolution string) (*StockAlert, error) {
	a, err := s.GetAlert(ctx, id)
	if err != nil {
		return nil, err
	}
	a.Status = status
	if status != AlertStatusAcknowledged {
		a.Resolution = resolution
	}
	now := time.Now()
	a.HandledAt = &now
	a.HandlerID = currentUserID(ctx)
	if err := s.repo.UpdateAlert(ctx, a); err != nil {
		return nil, err
	}
	return a, nil
}

func (s *Service) DeleteAlert(ctx context.Context, id uint64) error {
	if _, err := s.GetAlert(ctx, id); err != nil {
		return err
	}
	return s.repo.SoftDeleteAlert(ctx, id)
}

// ── helpers ────────────────────────────────────────────────────────────

func currentUserID(ctx context.Context) *uint64 {
	if u, ok := iam.AuthUserFrom(ctx); ok {
		id := u.ID
		return &id
	}
	return nil
}
