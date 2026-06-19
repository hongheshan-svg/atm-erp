package inventory

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/atm-erp/server/internal/iam"
	"github.com/atm-erp/server/internal/inventory/cost"
	"github.com/shopspring/decimal"
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
			return applyMoveToStock(ctx, tx, m, uid)
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
		return applyMoveToStock(ctx, tx, m, uid)
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

// applyMoveToStock 按移动类型落库存,并在同一事务内同步写「成本账本」(append-only ItemCostRecord)。
// tx 须为外层事务句柄,行锁防并发。对齐 Django StockMove._update_stock;
// 账本忠实 Django CostCalculationService.process_inbound/outbound(在 Django 为死代码,Go 侧补成活台账)。
//
// 联动统一原则:Stock 与账本消费同一 m.UnitCost 输入、同事务各自记账;账本不回填 Stock、Stock 不读账本。
// 账本仅在 Stock 实际变更时写(出库无库存被跳过则不写),保证账本与 Stock 一致。
// 并发安全:每次账本写入前,本事务已对同 (item,warehouse) 的 Stock 行加 FOR UPDATE 锁(账本键=Stock 键),
// 故同键并发移动在 Stock 行锁处串行化,账本结存游标无需再单独加锁。
func applyMoveToStock(ctx context.Context, tx *gorm.DB, m *StockMove, uid *uint64) error {
	switch m.MoveType {
	case MoveTypeInPurchase:
		wh := derefWH(m.WarehouseTo)
		if err := stockIn(tx, wh, m.ItemID, m.Qty, m.UnitCost, uid); err != nil {
			return err
		}
		return ledgerIn(ctx, tx, m, wh)
	case MoveTypeOutSales, MoveTypeOutProject:
		wh := derefWH(m.WarehouseFrom)
		applied, err := stockOut(tx, wh, m.ItemID, m.Qty)
		if err != nil {
			return err
		}
		if applied {
			return ledgerOut(ctx, tx, m, wh)
		}
		return nil
	case MoveTypeTransfer:
		// 账本按 (item,warehouse) 分账:from 仓出库行 + to 仓入库行(顺序与 Stock 一致)。
		from, to := derefWH(m.WarehouseFrom), derefWH(m.WarehouseTo)
		applied, err := stockOut(tx, from, m.ItemID, m.Qty)
		if err != nil {
			return err
		}
		if applied {
			if err := ledgerOut(ctx, tx, m, from); err != nil {
				return err
			}
		}
		if err := stockIn(tx, to, m.ItemID, m.Qty, m.UnitCost, uid); err != nil {
			return err
		}
		return ledgerIn(ctx, tx, m, to)
	case MoveTypeAdjustment:
		// qty 恒为正;方向由仓库字段决定:to=盘盈入库,from=盘亏出库。
		if m.WarehouseTo != nil {
			if err := stockIn(tx, *m.WarehouseTo, m.ItemID, m.Qty, m.UnitCost, uid); err != nil {
				return err
			}
			return ledgerIn(ctx, tx, m, *m.WarehouseTo)
		}
		if m.WarehouseFrom != nil {
			applied, err := stockOut(tx, *m.WarehouseFrom, m.ItemID, m.Qty)
			if err != nil {
				return err
			}
			if applied {
				return ledgerOut(ctx, tx, m, *m.WarehouseFrom)
			}
			return nil
		}
		return nil
	}
	return ErrBadMoveType
}

// ledgerTxTypeIn/Out 把 Go 移动类型映射到 Django ItemCostRecord.TRANSACTION_TYPES 合法值,
// 并按方向区分(TRANSFER/ADJUSTMENT 入出两行各自落 *_IN / *_OUT,不丢方向语义)。
func ledgerTxTypeIn(moveType string) string {
	switch moveType {
	case MoveTypeInPurchase:
		return "PURCHASE_IN"
	case MoveTypeTransfer:
		return "TRANSFER_IN"
	case MoveTypeAdjustment:
		return "ADJUST_IN"
	}
	return "PURCHASE_IN"
}

func ledgerTxTypeOut(moveType string) string {
	switch moveType {
	case MoveTypeOutSales:
		return "SALES_OUT"
	case MoveTypeOutProject: // 项目领料 → 生产领料
		return "PRODUCTION_OUT"
	case MoveTypeTransfer:
		return "TRANSFER_OUT"
	case MoveTypeAdjustment:
		return "ADJUST_OUT"
	}
	return "SALES_OUT"
}

// ledgerIn 同事务写一条入库成本账本行(移动加权平均),unit_cost 与喂给 Stock 的同源、交易日期用业务日期。
func ledgerIn(ctx context.Context, tx *gorm.DB, m *StockMove, wh uint64) error {
	if wh == 0 {
		return nil
	}
	whp := &wh
	_, err := cost.NewService(tx).ProcessInbound(ctx, m.ItemID, whp,
		decimal.NewFromFloat(m.Qty), decimal.NewFromFloat(m.UnitCost), ledgerTxTypeIn(m.MoveType), m.MoveNo, m.MoveDate)
	return err
}

// ledgerOut 同事务写一条出库成本账本行(出库成本取账本自身结存单价,对齐 process_outbound)。
func ledgerOut(ctx context.Context, tx *gorm.DB, m *StockMove, wh uint64) error {
	if wh == 0 {
		return nil
	}
	whp := &wh
	_, err := cost.NewService(tx).ProcessOutbound(ctx, m.ItemID, whp,
		decimal.NewFromFloat(m.Qty), ledgerTxTypeOut(m.MoveType), m.MoveNo, m.MoveDate)
	return err
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

	// 首次入库(新建):avg=cost、qty=qty,均为 2dp 输入,无除法,float64 精确。
	if st.ID == 0 {
		st.QtyOnHand = qty
		st.WeightedAvgCost = cost
		return tx.Create(&st).Error
	}

	// 已有库存:加权平均用 decimal 计算并存入,匹配 Django Decimal 口径
	// (PG numeric(15,2) 量化与 Django 一致,消除 float64 在分位边界的偏差)。
	oldQty := decimal.NewFromFloat(st.QtyOnHand)
	oldAvg := decimal.NewFromFloat(st.WeightedAvgCost)
	newQty := oldQty.Add(decimal.NewFromFloat(qty))
	newAvg := decimal.NewFromFloat(cost)
	if newQty.IsPositive() {
		newAvg = oldQty.Mul(oldAvg).Add(decimal.NewFromFloat(qty).Mul(decimal.NewFromFloat(cost))).Div(newQty)
	}
	return tx.Model(&Stock{}).Where("id = ?", st.ID).
		Updates(map[string]any{"qty_on_hand": newQty, "weighted_avg_cost": newAvg}).Error
}

// stockOut 出库。对齐 Django _update_stock_out:库存不足抛错;Stock 不存在则静默跳过。
// 返回 applied:true=确实扣减了库存(调用方据此决定是否写出库账本,保证账本与 Stock 一致)。
func stockOut(tx *gorm.DB, warehouseID, itemID uint64, qty float64) (bool, error) {
	if warehouseID == 0 {
		return false, errors.New("出库缺少来源仓库")
	}
	var st Stock
	err := tx.Clauses(clause.Locking{Strength: "UPDATE"}).
		Where("warehouse_id = ? AND item_id = ?", warehouseID, itemID).
		First(&st).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return false, nil // Django: except Stock.DoesNotExist: pass(无库存→不动账本)
	}
	if err != nil {
		return false, err
	}
	if st.QtyOnHand < qty {
		return false, fmt.Errorf("%w: 物料 %d 在仓库 %d 当前库存 %.2f, 需要 %.2f",
			ErrInsufficient, itemID, warehouseID, st.QtyOnHand, qty)
	}
	st.QtyOnHand -= qty
	if err := tx.Model(&Stock{}).Where("id = ?", st.ID).Update("qty_on_hand", st.QtyOnHand).Error; err != nil {
		return false, err
	}
	return true, nil
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
