// Package cost 实现库存移动加权平均成本核算,1:1 对齐 Django
// apps.inventory.cost_accounting.CostCalculationService(经运行中的旧系统裁判验证)。
// 金额一律用 shopspring/decimal,禁用 float64,以匹配 Django Decimal 的量化口径:
//   - 单价(unit/balance_unit_cost):4 位小数,ROUND_HALF_UP
//   - 金额(total_cost/balance_cost):2 位小数,ROUND_HALF_UP
//   - 出库金额 = (qty × balance_unit_cost) 先量化到 2 位,再从结存金额扣减(关键细节)
package cost

import (
	"context"
	"time"

	"github.com/atm-erp/server/internal/platform/model"
	"github.com/shopspring/decimal"
	"gorm.io/gorm"
)

// ItemCostRecord 物料成本记录(append-only 账本),对齐 inventory_item_cost_record。
type ItemCostRecord struct {
	model.Base
	ItemID          uint64          `gorm:"column:item_id;index" json:"item_id"`
	WarehouseID     *uint64         `gorm:"column:warehouse_id;index" json:"warehouse_id,omitempty"`
	TransactionType string          `gorm:"column:transaction_type;size:20" json:"transaction_type"`
	ReferenceType   string          `gorm:"column:reference_type;size:50" json:"reference_type"`
	ReferenceNo     string          `gorm:"column:reference_no;size:50;index" json:"reference_no"`
	ReferenceID     *uint64         `gorm:"column:reference_id" json:"reference_id,omitempty"`
	TransactionDate time.Time       `gorm:"column:transaction_date" json:"transaction_date"`
	Quantity        decimal.Decimal `gorm:"column:quantity;type:numeric(18,4)" json:"quantity"`
	UnitCost        decimal.Decimal `gorm:"column:unit_cost;type:numeric(18,4)" json:"unit_cost"`
	TotalCost       decimal.Decimal `gorm:"column:total_cost;type:numeric(18,2)" json:"total_cost"`
	BalanceQty      decimal.Decimal `gorm:"column:balance_qty;type:numeric(18,4)" json:"balance_qty"`
	BalanceCost     decimal.Decimal `gorm:"column:balance_cost;type:numeric(18,2)" json:"balance_cost"`
	BalanceUnitCost decimal.Decimal `gorm:"column:balance_unit_cost;type:numeric(18,4)" json:"balance_unit_cost"`
	Remarks         string          `gorm:"column:remarks;size:500" json:"remarks"`
}

func (ItemCostRecord) TableName() string { return "inventory_item_cost_record" }

// ---- 纯计算(无 DB,可单测,直接对账 Django 数字)----

// Inbound 计算入库后的结存(移动加权平均),对齐 process_inbound。
// 返回:新结存数量、新结存金额(2dp)、新结存单价(4dp)。
func Inbound(prevQty, prevCost, qty, unitCost decimal.Decimal) (newQty, newCost, newUnit decimal.Decimal) {
	total := qty.Mul(unitCost)
	newQty = prevQty.Add(qty)
	full := prevCost.Add(total) // 单价用全精度金额计算,再量化(对齐 Django 在内存中用未量化的 new_total_cost)
	if newQty.IsPositive() {
		newUnit = full.DivRound(newQty, 8).Round(4)
	} else {
		newUnit = unitCost
	}
	newCost = full.Round(2)
	return
}

// Outbound 计算出库后的结存,对齐 process_outbound。
// 返回:新结存数量、新结存金额(2dp)、新结存单价(4dp)、出库单价、出库金额(2dp)。
func Outbound(prevQty, prevCost, prevUnit, qty decimal.Decimal) (newQty, newCost, newUnit, outUnit, outTotal decimal.Decimal) {
	outUnit = prevUnit
	outTotal = qty.Mul(prevUnit).Round(2) // 关键:先量化到 2dp 再扣减
	newQty = prevQty.Sub(qty)
	full := prevCost.Sub(outTotal)
	if newQty.IsPositive() {
		newUnit = full.DivRound(newQty, 8).Round(4)
		newCost = full.Round(2)
	} else {
		newUnit = prevUnit
		newCost = decimal.Zero
	}
	return
}

// ---- DB 服务(append-only,与 Django 同表)----

type Service struct{ db *gorm.DB }

func NewService(db *gorm.DB) *Service { return &Service{db: db} }

func (s *Service) last(ctx context.Context, itemID uint64, warehouseID *uint64) (*ItemCostRecord, error) {
	q := s.db.WithContext(ctx).Model(&ItemCostRecord{}).Where("item_id = ?", itemID)
	if warehouseID != nil {
		q = q.Where("warehouse_id = ?", *warehouseID)
	} else {
		q = q.Where("warehouse_id IS NULL")
	}
	var r ItemCostRecord
	err := q.Order("created_at DESC").Order("id DESC").First(&r).Error
	if err == gorm.ErrRecordNotFound {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &r, nil
}

// ProcessInbound 落一条入库成本记录并返回(移动加权平均)。
func (s *Service) ProcessInbound(ctx context.Context, itemID uint64, warehouseID *uint64, qty, unitCost decimal.Decimal, txType, refNo string) (*ItemCostRecord, error) {
	prevQty, prevCost := decimal.Zero, decimal.Zero
	if last, err := s.last(ctx, itemID, warehouseID); err != nil {
		return nil, err
	} else if last != nil {
		prevQty, prevCost = last.BalanceQty, last.BalanceCost
	}
	newQty, newCost, newUnit := Inbound(prevQty, prevCost, qty, unitCost)
	rec := &ItemCostRecord{
		ItemID: itemID, WarehouseID: warehouseID, TransactionType: txType, ReferenceNo: refNo,
		TransactionDate: time.Now(), Quantity: qty, UnitCost: unitCost, TotalCost: qty.Mul(unitCost).Round(2),
		BalanceQty: newQty, BalanceCost: newCost, BalanceUnitCost: newUnit,
	}
	if err := s.db.WithContext(ctx).Create(rec).Error; err != nil {
		return nil, err
	}
	return rec, nil
}

// ProcessOutbound 落一条出库成本记录并返回。
func (s *Service) ProcessOutbound(ctx context.Context, itemID uint64, warehouseID *uint64, qty decimal.Decimal, txType, refNo string) (*ItemCostRecord, error) {
	prevQty, prevCost, prevUnit := decimal.Zero, decimal.Zero, decimal.Zero
	if last, err := s.last(ctx, itemID, warehouseID); err != nil {
		return nil, err
	} else if last != nil {
		prevQty, prevCost, prevUnit = last.BalanceQty, last.BalanceCost, last.BalanceUnitCost
	}
	newQty, newCost, newUnit, outUnit, outTotal := Outbound(prevQty, prevCost, prevUnit, qty)
	rec := &ItemCostRecord{
		ItemID: itemID, WarehouseID: warehouseID, TransactionType: txType, ReferenceNo: refNo,
		TransactionDate: time.Now(), Quantity: qty.Neg(), UnitCost: outUnit, TotalCost: outTotal.Neg(),
		BalanceQty: newQty, BalanceCost: newCost, BalanceUnitCost: newUnit,
	}
	if err := s.db.WithContext(ctx).Create(rec).Error; err != nil {
		return nil, err
	}
	return rec, nil
}
