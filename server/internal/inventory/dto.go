package inventory

// ── Stock DTO ──────────────────────────────────────────────────────────

// StockListQuery 库存列表筛选。
type StockListQuery struct {
	WarehouseID uint64
	ItemID      uint64
	LowStock    bool // TODO(verify): 低于安全库存筛选,需物料安全库存字段(跨模块),暂仅占位。
}

// ── StockMove DTO ──────────────────────────────────────────────────────

// StockMoveCreateInput 新建库存移动。move_no 留空则自动生成。
type StockMoveCreateInput struct {
	ItemID        uint64  `json:"item_id" binding:"required"`
	WarehouseFrom *uint64 `json:"warehouse_from"`
	WarehouseTo   *uint64 `json:"warehouse_to"`
	Qty           float64 `json:"qty" binding:"required"`
	UnitCost      float64 `json:"unit_cost"`
	MoveType      string  `json:"move_type" binding:"required"`
	ReferenceType string  `json:"reference_type"`
	ReferenceID   *int64  `json:"reference_id"`
	ProjectID     *uint64 `json:"project"`
	MoveDate      string  `json:"move_date" binding:"required"` // YYYY-MM-DD
	Status        string  `json:"status"`                       // 默认 DRAFT
	Notes         string  `json:"notes"`
}

// StockMoveUpdateInput 局部更新(仅草稿可改;指针区分未传)。
type StockMoveUpdateInput struct {
	Qty           *float64 `json:"qty"`
	UnitCost      *float64 `json:"unit_cost"`
	WarehouseFrom *uint64  `json:"warehouse_from"`
	WarehouseTo   *uint64  `json:"warehouse_to"`
	MoveType      *string  `json:"move_type"`
	MoveDate      *string  `json:"move_date"`
	Notes         *string  `json:"notes"`
}

// StockMoveListQuery 库存移动列表筛选。
type StockMoveListQuery struct {
	ItemID   uint64
	MoveType string
	Status   string
}

// ── Batch DTO ──────────────────────────────────────────────────────────

type BatchCreateInput struct {
	BatchNo         string  `json:"batch_no" binding:"required"`
	ItemID          uint64  `json:"item_id" binding:"required"`
	WarehouseID     uint64  `json:"warehouse_id" binding:"required"`
	ManufactureDate *string `json:"manufacture_date"` // YYYY-MM-DD
	ExpiryDate      *string `json:"expiry_date"`
	QtyOnHand       float64 `json:"qty_on_hand"`
	UnitCost        float64 `json:"unit_cost"`
	SupplierBatchNo string  `json:"supplier_batch_no"`
	QualityStatus   string  `json:"quality_status"`
	Notes           string  `json:"notes"`
}

type BatchUpdateInput struct {
	ManufactureDate *string  `json:"manufacture_date"`
	ExpiryDate      *string  `json:"expiry_date"`
	QtyOnHand       *float64 `json:"qty_on_hand"`
	UnitCost        *float64 `json:"unit_cost"`
	SupplierBatchNo *string  `json:"supplier_batch_no"`
	QualityStatus   *string  `json:"quality_status"`
	Notes           *string  `json:"notes"`
}

type BatchListQuery struct {
	ItemID        uint64
	WarehouseID   uint64
	QualityStatus string
	ExpiringOnly  bool // 仅显示已设到期日的批次(到期排序)
}

// ── StockAlert DTO ─────────────────────────────────────────────────────

type AlertCreateInput struct {
	RuleID         *uint64 `json:"rule"`
	ItemID         uint64  `json:"item_id" binding:"required"`
	WarehouseID    *uint64 `json:"warehouse"`
	AlertType      string  `json:"alert_type" binding:"required"`
	Severity       string  `json:"severity"`
	Title          string  `json:"title" binding:"required"`
	Description    string  `json:"description"`
	CurrentQty     float64 `json:"current_qty"`
	ThresholdValue float64 `json:"threshold_value"`
}

type AlertListQuery struct {
	ItemID    uint64
	Status    string
	Severity  string
	AlertType string
}

// AlertResolveInput resolve / ignore 动作的请求体。
type AlertResolveInput struct {
	Resolution string `json:"resolution"`
	Reason     string `json:"reason"`
}
