// Package purchase 是采购限界上下文的 Go 重写,忠实移植 Django apps.purchase 的
// 主要实体:采购申请(PR)、询价(RFQ)、采购订单(PO)、收货(GoodsReceipt)。
// 严格同构于 masterdata/item 样板:model→dto→repo→service→handler→Routes。
package purchase

import (
	"time"

	"github.com/atm-erp/server/internal/platform/model"
)

// ============================ 采购申请 PurchaseRequest ============================

// PurchaseRequest 采购申请单,对齐 Django PurchaseRequest(db_table=purchase_request)。
type PurchaseRequest struct {
	model.Base
	RequestNo string `gorm:"column:request_no;size:50;uniqueIndex" json:"request_no"`
	// project / supplier / requestor 为跨模块外键,这里保留裸 ID 列(忠实映射 db 列名),
	// 关联对象本轮不跨模块 join。
	ProjectID  *uint64 `gorm:"column:project_id" json:"project_id,omitempty"`
	SupplierID *uint64 `gorm:"column:supplier_id" json:"supplier_id,omitempty"`
	// requestor 在 Django 是 PROTECT 必填外键;Go 侧用裸列。
	RequestorID  uint64    `gorm:"column:requestor_id" json:"requestor_id"`
	RequestDate  time.Time `gorm:"column:request_date" json:"request_date"`
	RequiredDate time.Time `gorm:"column:required_date" json:"required_date"`
	Status       string    `gorm:"column:status;size:20;default:DRAFT" json:"status"`

	TaxRate      int     `gorm:"column:tax_rate;default:13" json:"tax_rate"`
	TotalAmount  float64 `gorm:"column:total_amount" json:"total_amount"`
	TaxAmount    float64 `gorm:"column:tax_amount" json:"tax_amount"`
	TotalWithTax float64 `gorm:"column:total_with_tax" json:"total_with_tax"`
	Notes        string  `gorm:"column:notes" json:"notes"`

	Lines []PurchaseRequestLine `gorm:"foreignKey:PRID" json:"lines,omitempty"`
}

func (PurchaseRequest) TableName() string { return "purchase_request" }

// PurchaseRequestLine 采购申请明细(db_table=purchase_request_line)。
type PurchaseRequestLine struct {
	model.Base
	PRID           uint64     `gorm:"column:pr_id" json:"pr_id"`
	ItemID         uint64     `gorm:"column:item_id" json:"item_id"`
	Qty            float64    `gorm:"column:qty" json:"qty"`
	EstimatedPrice float64    `gorm:"column:estimated_price" json:"estimated_price"`
	LineAmount     float64    `gorm:"column:line_amount" json:"line_amount"`
	RequiredDate   *time.Time `gorm:"column:required_date" json:"required_date,omitempty"`
	ProjectID      *uint64    `gorm:"column:project_id" json:"project_id,omitempty"`

	// BOM 关联字段(非标自动化)。
	BOMItemID      *uint64 `gorm:"column:bom_item_id" json:"bom_item_id,omitempty"`
	IsCritical     bool    `gorm:"column:is_critical" json:"is_critical"`
	IsLongLead     bool    `gorm:"column:is_long_lead" json:"is_long_lead"`
	FunctionModule string  `gorm:"column:function_module;size:100" json:"function_module"`
	Notes          string  `gorm:"column:notes" json:"notes"`
}

func (PurchaseRequestLine) TableName() string { return "purchase_request_line" }

// ============================ 采购订单 PurchaseOrder ============================

// PurchaseOrder 采购订单(db_table=purchase_order)。
type PurchaseOrder struct {
	model.Base
	OrderNo      string    `gorm:"column:order_no;size:50;uniqueIndex" json:"order_no"`
	SupplierID   uint64    `gorm:"column:supplier_id" json:"supplier_id"`
	ProjectID    *uint64   `gorm:"column:project_id" json:"project_id,omitempty"`
	OrderDate    time.Time `gorm:"column:order_date" json:"order_date"`
	DeliveryDate time.Time `gorm:"column:delivery_date" json:"delivery_date"`
	Status       string    `gorm:"column:status;size:20;default:DRAFT" json:"status"`

	TaxRate      int     `gorm:"column:tax_rate;default:13" json:"tax_rate"`
	TotalAmount  float64 `gorm:"column:total_amount" json:"total_amount"`
	TaxAmount    float64 `gorm:"column:tax_amount" json:"tax_amount"`
	TotalWithTax float64 `gorm:"column:total_with_tax" json:"total_with_tax"`

	PaymentTerms       string `gorm:"column:payment_terms;size:20;default:NET30" json:"payment_terms"`
	PaymentMethod      string `gorm:"column:payment_method;size:20;default:WIRE" json:"payment_method"`
	PaymentTermsDetail string `gorm:"column:payment_terms_detail;size:200" json:"payment_terms_detail"`
	Notes              string `gorm:"column:notes" json:"notes"`

	Lines []PurchaseOrderLine `gorm:"foreignKey:POID" json:"lines,omitempty"`
}

func (PurchaseOrder) TableName() string { return "purchase_order" }

// PurchaseOrderLine 采购订单明细(db_table=purchase_order_line)。
type PurchaseOrderLine struct {
	model.Base
	POID        uint64  `gorm:"column:po_id" json:"po_id"`
	ItemID      uint64  `gorm:"column:item_id" json:"item_id"`
	Qty         float64 `gorm:"column:qty" json:"qty"`
	UnitPrice   float64 `gorm:"column:unit_price" json:"unit_price"`
	LineAmount  float64 `gorm:"column:line_amount" json:"line_amount"`
	ReceivedQty float64 `gorm:"column:received_qty" json:"received_qty"`

	BOMItemID            *uint64 `gorm:"column:bom_item_id" json:"bom_item_id,omitempty"`
	IsCritical           bool    `gorm:"column:is_critical" json:"is_critical"`
	IsLongLead           bool    `gorm:"column:is_long_lead" json:"is_long_lead"`
	FunctionModule       string  `gorm:"column:function_module;size:100" json:"function_module"`
	DrawingNo            string  `gorm:"column:drawing_no;size:100" json:"drawing_no"`
	TechnicalRequirement string  `gorm:"column:technical_requirement" json:"technical_requirement"`
	Notes                string  `gorm:"column:notes" json:"notes"`
}

func (PurchaseOrderLine) TableName() string { return "purchase_order_line" }

// ============================ 收货 GoodsReceipt ============================

// GoodsReceipt 收货单(db_table=goods_receipt)。
type GoodsReceipt struct {
	model.Base
	ReceiptNo   string    `gorm:"column:receipt_no;size:50;uniqueIndex" json:"receipt_no"`
	POID        uint64    `gorm:"column:po_id" json:"po_id"`
	WarehouseID uint64    `gorm:"column:warehouse_id" json:"warehouse_id"`
	ReceiptDate time.Time `gorm:"column:receipt_date" json:"receipt_date"`
	Status      string    `gorm:"column:status;size:20;default:DRAFT" json:"status"`
	Notes       string    `gorm:"column:notes" json:"notes"`

	Lines []GoodsReceiptLine `gorm:"foreignKey:ReceiptID" json:"lines,omitempty"`
}

func (GoodsReceipt) TableName() string { return "goods_receipt" }

// GoodsReceiptLine 收货明细(db_table=goods_receipt_line)。
type GoodsReceiptLine struct {
	model.Base
	ReceiptID     uint64  `gorm:"column:receipt_id" json:"receipt_id"`
	POLineID      uint64  `gorm:"column:po_line_id" json:"po_line_id"`
	ItemID        uint64  `gorm:"column:item_id" json:"item_id"`
	Qty           float64 `gorm:"column:qty" json:"qty"`
	QualityStatus string  `gorm:"column:quality_status;size:20;default:PENDING" json:"quality_status"`
	Notes         string  `gorm:"column:notes" json:"notes"`
}

func (GoodsReceiptLine) TableName() string { return "goods_receipt_line" }

// ============================ 询价 RFQ ============================

// RFQ 询价单(db_table=rfq)。
type RFQ struct {
	model.Base
	RFQNo            string    `gorm:"column:rfq_no;size:50;uniqueIndex" json:"rfq_no"`
	ProjectID        *uint64   `gorm:"column:project_id" json:"project_id,omitempty"`
	RequestDate      time.Time `gorm:"column:request_date" json:"request_date"`
	ResponseDeadline time.Time `gorm:"column:response_deadline" json:"response_deadline"`
	Status           string    `gorm:"column:status;size:20;default:DRAFT" json:"status"`
	Notes            string    `gorm:"column:notes" json:"notes"`

	RFQType    string  `gorm:"column:rfq_type;size:20;default:NORMAL" json:"rfq_type"`
	Priority   string  `gorm:"column:priority;size:20;default:NORMAL" json:"priority"`
	TemplateID *uint64 `gorm:"column:template_id" json:"template_id,omitempty"`

	TechnicalRequirements string `gorm:"column:technical_requirements" json:"technical_requirements"`
	QualityRequirements   string `gorm:"column:quality_requirements" json:"quality_requirements"`
	PackagingRequirements string `gorm:"column:packaging_requirements" json:"packaging_requirements"`
	DeliveryRequirements  string `gorm:"column:delivery_requirements" json:"delivery_requirements"`

	AttachmentCount int `gorm:"column:attachment_count" json:"attachment_count"`

	Lines        []RFQLine     `gorm:"foreignKey:RFQID" json:"lines,omitempty"`
	SupplierRFQs []RFQSupplier `gorm:"foreignKey:RFQID" json:"supplier_rfqs,omitempty"`
}

func (RFQ) TableName() string { return "rfq" }

// RFQLine 询价单明细(db_table=rfq_line)。字段较多,忠实映射。
type RFQLine struct {
	model.Base
	RFQID          uint64    `gorm:"column:rfq_id" json:"rfq_id"`
	ItemID         uint64    `gorm:"column:item_id" json:"item_id"`
	Qty            float64   `gorm:"column:qty" json:"qty"`
	RequiredDate   time.Time `gorm:"column:required_date" json:"required_date"`
	Specifications string    `gorm:"column:specifications" json:"specifications"`

	BOMItemID      *uint64 `gorm:"column:bom_item_id" json:"bom_item_id,omitempty"`
	DrawingID      *uint64 `gorm:"column:drawing_id" json:"drawing_id,omitempty"`
	DrawingNo      string  `gorm:"column:drawing_no;size:100" json:"drawing_no"`
	DrawingVersion string  `gorm:"column:drawing_version;size:50" json:"drawing_version"`

	// technical_specs 在 Django 是 JSONField;Go 侧暂存原始 JSON 字符串。
	// TODO(verify): 若前端需结构化读写,改为 datatypes.JSON(当前依赖未引入)。
	TechnicalSpecs string `gorm:"column:technical_specs;type:jsonb" json:"technical_specs"`

	IsCritical bool `gorm:"column:is_critical" json:"is_critical"`
	IsLongLead bool `gorm:"column:is_long_lead" json:"is_long_lead"`
	IsCustom   bool `gorm:"column:is_custom" json:"is_custom"`

	SampleQty          *float64   `gorm:"column:sample_qty" json:"sample_qty,omitempty"`
	SampleRequiredDate *time.Time `gorm:"column:sample_required_date" json:"sample_required_date,omitempty"`
	TargetPrice        *float64   `gorm:"column:target_price" json:"target_price,omitempty"`

	LastSupplierID  *uint64  `gorm:"column:last_supplier_id" json:"last_supplier_id,omitempty"`
	LastPrice       *float64 `gorm:"column:last_price" json:"last_price,omitempty"`
	AttachmentCount int      `gorm:"column:attachment_count" json:"attachment_count"`
}

func (RFQLine) TableName() string { return "rfq_line" }

// RFQSupplier 询价单-供应商关联(db_table=rfq_supplier)。
type RFQSupplier struct {
	model.Base
	RFQID       uint64     `gorm:"column:rfq_id" json:"rfq_id"`
	SupplierID  uint64     `gorm:"column:supplier_id" json:"supplier_id"`
	SentDate    *time.Time `gorm:"column:sent_date" json:"sent_date,omitempty"`
	IsResponded bool       `gorm:"column:is_responded" json:"is_responded"`
}

func (RFQSupplier) TableName() string { return "rfq_supplier" }

// SupplierQuotation 供应商报价(db_table=supplier_quotation)。
type SupplierQuotation struct {
	model.Base
	QuotationNo   string    `gorm:"column:quotation_no;size:50;uniqueIndex" json:"quotation_no"`
	RFQSupplierID uint64    `gorm:"column:rfq_supplier_id" json:"rfq_supplier_id"`
	QuotationDate time.Time `gorm:"column:quotation_date" json:"quotation_date"`
	ValidUntil    time.Time `gorm:"column:valid_until" json:"valid_until"`
	PaymentTerms  string    `gorm:"column:payment_terms;size:200" json:"payment_terms"`
	DeliveryTerms string    `gorm:"column:delivery_terms;size:200" json:"delivery_terms"`

	TotalAmount  float64 `gorm:"column:total_amount" json:"total_amount"`
	TaxRate      int     `gorm:"column:tax_rate;default:13" json:"tax_rate"`
	TaxAmount    float64 `gorm:"column:tax_amount" json:"tax_amount"`
	TotalWithTax float64 `gorm:"column:total_with_tax" json:"total_with_tax"`

	WarrantyPeriod int      `gorm:"column:warranty_period;default:12" json:"warranty_period"`
	MinOrderQty    *float64 `gorm:"column:min_order_qty" json:"min_order_qty,omitempty"`

	LastPurchasePrice *float64 `gorm:"column:last_purchase_price" json:"last_purchase_price,omitempty"`
	PriceChangeRate   *float64 `gorm:"column:price_change_rate" json:"price_change_rate,omitempty"`

	Status string `gorm:"column:status;size:20;default:DRAFT" json:"status"`
	Notes  string `gorm:"column:notes" json:"notes"`
}

func (SupplierQuotation) TableName() string { return "supplier_quotation" }
