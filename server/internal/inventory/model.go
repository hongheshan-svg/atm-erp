// Package inventory 是「库存与MRP」限界上下文的 Go 移植,
// 忠实迁移 Django apps.inventory 的核心实体与库存账实/加权平均逻辑。
// 主要实体:Stock(库存)、StockMove(库存移动)、Batch(批次)、StockAlert(库存预警)。
// 次要实体(InventoryLot/LotConsumption/BatchMove/StockAdjustment/MaterialRequisition 等)
// 标 TODO 留待后续逐步移植。
package inventory

import (
	"time"

	"github.com/atm-erp/server/internal/platform/model"
)

// ── 移动类型 / 状态枚举(对齐 Django choices)──────────────────────────────

const (
	MoveTypeInPurchase = "IN_PURCHASE" // 采购入库
	MoveTypeOutSales   = "OUT_SALES"   // 销售出库
	MoveTypeOutProject = "OUT_PROJECT" // 项目领料
	MoveTypeTransfer   = "TRANSFER"    // 调拨
	MoveTypeAdjustment = "ADJUSTMENT"  // 调整

	MoveStatusDraft     = "DRAFT"     // 草稿
	MoveStatusCompleted = "COMPLETED" // 完成
	MoveStatusCancelled = "CANCELLED" // 已取消
)

const (
	BatchQualityPending    = "PENDING"    // 待检
	BatchQualityPassed     = "PASSED"     // 合格
	BatchQualityFailed     = "FAILED"     // 不合格
	BatchQualityQuarantine = "QUARANTINE" // 隔离
)

const (
	AlertStatusActive       = "ACTIVE"       // 活跃
	AlertStatusAcknowledged = "ACKNOWLEDGED" // 已确认
	AlertStatusResolved     = "RESOLVED"     // 已解决
	AlertStatusIgnored      = "IGNORED"      // 已忽略

	AlertSeverityInfo     = "INFO"     // 提示
	AlertSeverityWarning  = "WARNING"  // 警告
	AlertSeverityCritical = "CRITICAL" // 严重
)

// ── Stock 库存(账面/预留/加权平均成本)──────────────────────────────────

// Stock 实时库存(由 StockMove 聚合更新)。
// Django: apps.inventory.models.Stock,Meta.db_table='stock'。
// qty_available 为计算属性(qty_on_hand-qty_reserved),不入库,通过 JSON 输出。
type Stock struct {
	model.Base
	WarehouseID     uint64  `gorm:"column:warehouse_id;index" json:"warehouse_id"`
	ItemID          uint64  `gorm:"column:item_id;index" json:"item_id"`
	QtyOnHand       float64 `gorm:"column:qty_on_hand;type:numeric(15,2);default:0" json:"qty_on_hand"`
	QtyReserved     float64 `gorm:"column:qty_reserved;type:numeric(15,2);default:0" json:"qty_reserved"`
	WeightedAvgCost float64 `gorm:"column:weighted_avg_cost;type:numeric(15,2);default:0" json:"weighted_avg_cost"`
	// QtyAvailable 计算属性(不持久化)。
	QtyAvailable float64 `gorm:"-" json:"qty_available"`
}

// TableName 对齐 Django Meta.db_table(ADR-004,禁 AutoMigrate)。
func (Stock) TableName() string { return "stock" }

// AfterFind 填充计算属性 qty_available(对齐 Django @property)。
func (s *Stock) computeAvailable() { s.QtyAvailable = s.QtyOnHand - s.QtyReserved }

// ── StockMove 库存移动(账实变动的唯一真相来源)──────────────────────────

// StockMove Django: apps.inventory.models.StockMove,Meta.db_table='stock_move'。
type StockMove struct {
	model.Base
	MoveNo        string    `gorm:"column:move_no;size:50;uniqueIndex" json:"move_no"`
	ItemID        uint64    `gorm:"column:item_id;index" json:"item_id"`
	WarehouseFrom *uint64   `gorm:"column:warehouse_from_id" json:"warehouse_from"`
	WarehouseTo   *uint64   `gorm:"column:warehouse_to_id" json:"warehouse_to"`
	Qty           float64   `gorm:"column:qty;type:numeric(15,2)" json:"qty"`
	UnitCost      float64   `gorm:"column:unit_cost;type:numeric(15,2)" json:"unit_cost"`
	MoveType      string    `gorm:"column:move_type;size:20" json:"move_type"`
	ReferenceType string    `gorm:"column:reference_type;size:50" json:"reference_type"`
	ReferenceID   *int64    `gorm:"column:reference_id" json:"reference_id"`
	ProjectID     *uint64   `gorm:"column:project_id" json:"project"`
	MoveDate      time.Time `gorm:"column:move_date;type:date" json:"move_date"`
	Status        string    `gorm:"column:status;size:20;default:DRAFT" json:"status"`
	Notes         string    `gorm:"column:notes;type:text" json:"notes"`
}

func (StockMove) TableName() string { return "stock_move" }

// ── Batch 批次追溯 ─────────────────────────────────────────────────────

// Batch Django: apps.inventory.batch_models.Batch,Meta.db_table='batch'。
// 唯一约束 (batch_no, item, warehouse)。
type Batch struct {
	model.Base
	BatchNo         string     `gorm:"column:batch_no;size:50;index:idx_batch_unique,unique" json:"batch_no"`
	ItemID          uint64     `gorm:"column:item_id;index:idx_batch_unique,unique;index:idx_batch_item_wh" json:"item_id"`
	WarehouseID     uint64     `gorm:"column:warehouse_id;index:idx_batch_unique,unique;index:idx_batch_item_wh" json:"warehouse_id"`
	ManufactureDate *time.Time `gorm:"column:manufacture_date;type:date" json:"manufacture_date"`
	ExpiryDate      *time.Time `gorm:"column:expiry_date;type:date;index" json:"expiry_date"`
	QtyOnHand       float64    `gorm:"column:qty_on_hand;type:numeric(12,3);default:0" json:"qty_on_hand"`
	UnitCost        float64    `gorm:"column:unit_cost;type:numeric(12,2);default:0" json:"unit_cost"`
	SupplierBatchNo string     `gorm:"column:supplier_batch_no;size:100" json:"supplier_batch_no"`
	QualityStatus   string     `gorm:"column:quality_status;size:20;default:PENDING" json:"quality_status"`
	Notes           string     `gorm:"column:notes;type:text" json:"notes"`
	// 计算属性(不持久化,对齐 Django @property)。
	IsExpired    bool   `gorm:"-" json:"is_expired"`
	DaysToExpiry *int64 `gorm:"-" json:"days_to_expiry"`
}

func (Batch) TableName() string { return "batch" }

func (b *Batch) computeExpiry() {
	if b.ExpiryDate == nil {
		b.IsExpired = false
		b.DaysToExpiry = nil
		return
	}
	today := time.Now().Truncate(24 * time.Hour)
	exp := b.ExpiryDate.Truncate(24 * time.Hour)
	b.IsExpired = exp.Before(today)
	d := int64(exp.Sub(today).Hours() / 24)
	b.DaysToExpiry = &d
}

// ── StockAlert 库存预警记录 ────────────────────────────────────────────

// StockAlert Django: apps.inventory.stock_alert.StockAlert,Meta.db_table='inventory_stock_alert'。
type StockAlert struct {
	model.Base
	RuleID         *uint64    `gorm:"column:rule_id" json:"rule"`
	ItemID         uint64     `gorm:"column:item_id;index" json:"item_id"`
	WarehouseID    *uint64    `gorm:"column:warehouse_id" json:"warehouse"`
	AlertType      string     `gorm:"column:alert_type;size:20" json:"alert_type"`
	Severity       string     `gorm:"column:severity;size:20;default:WARNING" json:"severity"`
	Title          string     `gorm:"column:title;size:200" json:"title"`
	Description    string     `gorm:"column:description;type:text" json:"description"`
	CurrentQty     float64    `gorm:"column:current_qty;type:numeric(18,4);default:0" json:"current_qty"`
	ThresholdValue float64    `gorm:"column:threshold_value;type:numeric(18,4);default:0" json:"threshold_value"`
	Status         string     `gorm:"column:status;size:20;default:ACTIVE" json:"status"`
	HandlerID      *uint64    `gorm:"column:handler_id" json:"handler"`
	HandledAt      *time.Time `gorm:"column:handled_at" json:"handled_at"`
	Resolution     string     `gorm:"column:resolution;type:text" json:"resolution"`
}

func (StockAlert) TableName() string { return "inventory_stock_alert" }
