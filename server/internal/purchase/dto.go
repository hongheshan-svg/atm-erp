package purchase

import "time"

// ============================ 采购申请 DTO ============================

// PRLineInput 采购申请明细入参。
type PRLineInput struct {
	ItemID         uint64     `json:"item_id" binding:"required"`
	Qty            float64    `json:"qty" binding:"required"`
	EstimatedPrice float64    `json:"estimated_price"`
	RequiredDate   *time.Time `json:"required_date"`
	ProjectID      *uint64    `json:"project_id"`
	BOMItemID      *uint64    `json:"bom_item_id"`
	IsCritical     bool       `json:"is_critical"`
	IsLongLead     bool       `json:"is_long_lead"`
	FunctionModule string     `json:"function_module"`
	Notes          string     `json:"notes"`
}

// PRCreateInput 新建采购申请入参。
type PRCreateInput struct {
	ProjectID    *uint64       `json:"project_id"`
	SupplierID   *uint64       `json:"supplier_id"`
	RequestorID  uint64        `json:"requestor_id"`
	RequiredDate time.Time     `json:"required_date" binding:"required"`
	TaxRate      *int          `json:"tax_rate"`
	Notes        string        `json:"notes"`
	Lines        []PRLineInput `json:"lines"`
}

// PRUpdateInput 局部更新采购申请(指针区分未传/置零)。
type PRUpdateInput struct {
	ProjectID    *uint64    `json:"project_id"`
	SupplierID   *uint64    `json:"supplier_id"`
	RequiredDate *time.Time `json:"required_date"`
	TaxRate      *int       `json:"tax_rate"`
	Notes        *string    `json:"notes"`
}

// ============================ 采购订单 DTO ============================

// POLineInput 采购订单明细入参。
type POLineInput struct {
	ItemID               uint64  `json:"item_id" binding:"required"`
	Qty                  float64 `json:"qty" binding:"required"`
	UnitPrice            float64 `json:"unit_price" binding:"required"`
	BOMItemID            *uint64 `json:"bom_item_id"`
	IsCritical           bool    `json:"is_critical"`
	IsLongLead           bool    `json:"is_long_lead"`
	FunctionModule       string  `json:"function_module"`
	DrawingNo            string  `json:"drawing_no"`
	TechnicalRequirement string  `json:"technical_requirement"`
	Notes                string  `json:"notes"`
}

// POCreateInput 新建采购订单入参。
type POCreateInput struct {
	SupplierID         uint64        `json:"supplier_id" binding:"required"`
	ProjectID          *uint64       `json:"project_id"`
	DeliveryDate       time.Time     `json:"delivery_date" binding:"required"`
	TaxRate            *int          `json:"tax_rate"`
	PaymentTerms       string        `json:"payment_terms"`
	PaymentMethod      string        `json:"payment_method"`
	PaymentTermsDetail string        `json:"payment_terms_detail"`
	Notes              string        `json:"notes"`
	Lines              []POLineInput `json:"lines"`
}

// POUpdateInput 局部更新采购订单。
type POUpdateInput struct {
	SupplierID         *uint64    `json:"supplier_id"`
	ProjectID          *uint64    `json:"project_id"`
	DeliveryDate       *time.Time `json:"delivery_date"`
	TaxRate            *int       `json:"tax_rate"`
	PaymentTerms       *string    `json:"payment_terms"`
	PaymentMethod      *string    `json:"payment_method"`
	PaymentTermsDetail *string    `json:"payment_terms_detail"`
	Notes              *string    `json:"notes"`
}

// ============================ 收货 DTO ============================

// GRLineInput 收货明细入参。
type GRLineInput struct {
	POLineID      uint64  `json:"po_line_id" binding:"required"`
	ItemID        uint64  `json:"item_id" binding:"required"`
	Qty           float64 `json:"qty" binding:"required"`
	QualityStatus string  `json:"quality_status"`
	Notes         string  `json:"notes"`
}

// GRCreateInput 新建收货单入参。
type GRCreateInput struct {
	POID        uint64        `json:"po_id" binding:"required"`
	WarehouseID uint64        `json:"warehouse_id" binding:"required"`
	ReceiptDate time.Time     `json:"receipt_date" binding:"required"`
	Notes       string        `json:"notes"`
	Lines       []GRLineInput `json:"lines"`
}

// GRUpdateInput 局部更新收货单。
type GRUpdateInput struct {
	WarehouseID *uint64    `json:"warehouse_id"`
	ReceiptDate *time.Time `json:"receipt_date"`
	Notes       *string    `json:"notes"`
}

// ============================ 询价 RFQ DTO ============================

// RFQLineInput 询价明细入参。
type RFQLineInput struct {
	ItemID         uint64    `json:"item_id" binding:"required"`
	Qty            float64   `json:"qty" binding:"required"`
	RequiredDate   time.Time `json:"required_date" binding:"required"`
	Specifications string    `json:"specifications"`
	BOMItemID      *uint64   `json:"bom_item_id"`
	DrawingID      *uint64   `json:"drawing_id"`
	DrawingNo      string    `json:"drawing_no"`
	DrawingVersion string    `json:"drawing_version"`
	TechnicalSpecs string    `json:"technical_specs"`
	IsCritical     bool      `json:"is_critical"`
	IsLongLead     bool      `json:"is_long_lead"`
	IsCustom       bool      `json:"is_custom"`
	TargetPrice    *float64  `json:"target_price"`
}

// RFQCreateInput 新建询价单入参。
type RFQCreateInput struct {
	ProjectID             *uint64        `json:"project_id"`
	ResponseDeadline      time.Time      `json:"response_deadline" binding:"required"`
	RFQType               string         `json:"rfq_type"`
	Priority              string         `json:"priority"`
	TemplateID            *uint64        `json:"template_id"`
	TechnicalRequirements string         `json:"technical_requirements"`
	QualityRequirements   string         `json:"quality_requirements"`
	PackagingRequirements string         `json:"packaging_requirements"`
	DeliveryRequirements  string         `json:"delivery_requirements"`
	Notes                 string         `json:"notes"`
	Lines                 []RFQLineInput `json:"lines"`
	SupplierIDs           []uint64       `json:"supplier_ids"`
}

// RFQUpdateInput 局部更新询价单。
type RFQUpdateInput struct {
	ProjectID             *uint64    `json:"project_id"`
	ResponseDeadline      *time.Time `json:"response_deadline"`
	RFQType               *string    `json:"rfq_type"`
	Priority              *string    `json:"priority"`
	TechnicalRequirements *string    `json:"technical_requirements"`
	QualityRequirements   *string    `json:"quality_requirements"`
	PackagingRequirements *string    `json:"packaging_requirements"`
	DeliveryRequirements  *string    `json:"delivery_requirements"`
	Notes                 *string    `json:"notes"`
}

// SendToSuppliersInput 发送询价给供应商。
type SendToSuppliersInput struct {
	SupplierIDs []uint64 `json:"supplier_ids"`
}

// ListQuery 列表通用筛选。
type ListQuery struct {
	Keyword string
	Status  string
}
