// Package sales 是「销售与CRM」限界上下文的 Go 重写:
// 报价 Quotation、销售订单 SalesOrder、发货 DeliveryOrder、线索 Lead、商机 Opportunity。
// 严格对齐 backend/apps/sales 的 Django 模型(字段/db_table/状态机/编号/金额计算)。
//
// 跨模块引用(masterdata.Customer/Item/Warehouse、projects.Project、accounts.User、
// finance 应收、core.workflow 审批、core.CodeRule 编号)在本轮用窄字段(外键 *uint64)
// + // TODO(port) 占位,避免跨业务包 import 造成编译耦合。
package sales

import "github.com/atm-erp/server/internal/platform/model"

// ---- 报价 Quotation ----

// Quotation 销售报价单,对齐 Django SalesQuotation(db_table=sales_quotation)。
type Quotation struct {
	model.Base
	QuoteNo string `gorm:"column:quote_no;size:50;uniqueIndex" json:"quote_no"`
	// 外键以 *uint64 承载(对齐 Django 整型 FK 列名 <field>_id)。
	CustomerID uint64  `gorm:"column:customer_id" json:"customer_id"`
	ProjectID  *uint64 `gorm:"column:project_id" json:"project_id,omitempty"`
	QuoteDate  *string `gorm:"column:quote_date" json:"quote_date,omitempty"`
	ValidUntil *string `gorm:"column:valid_until" json:"valid_until,omitempty"`
	Status     string  `gorm:"column:status;size:20" json:"status"`
	Version    int     `gorm:"column:version" json:"version"`

	TaxRate      int     `gorm:"column:tax_rate" json:"tax_rate"`
	TotalAmount  float64 `gorm:"column:total_amount" json:"total_amount"`
	TaxAmount    float64 `gorm:"column:tax_amount" json:"tax_amount"`
	TotalWithTax float64 `gorm:"column:total_with_tax" json:"total_with_tax"`
	Notes        string  `gorm:"column:notes" json:"notes"`
}

func (Quotation) TableName() string { return "sales_quotation" }

// QuotationLine 报价明细,对齐 Django SalesQuotationLine(db_table=sales_quotation_line)。
type QuotationLine struct {
	model.Base
	QuotationID uint64  `gorm:"column:quotation_id" json:"quotation_id"`
	ItemID      *uint64 `gorm:"column:item_id" json:"item_id,omitempty"`
	CustomName  string  `gorm:"column:custom_name;size:200" json:"custom_name"`
	CustomSpec  string  `gorm:"column:custom_spec;size:200" json:"custom_spec"`
	CustomUnit  string  `gorm:"column:custom_unit;size:50" json:"custom_unit"`
	Qty         float64 `gorm:"column:qty" json:"qty"`
	UnitPrice   float64 `gorm:"column:unit_price" json:"unit_price"`
	LineAmount  float64 `gorm:"column:line_amount" json:"line_amount"`
	Notes       string  `gorm:"column:notes" json:"notes"`
}

func (QuotationLine) TableName() string { return "sales_quotation_line" }

// ---- 销售订单 SalesOrder ----

// SalesOrder 销售订单,对齐 Django SalesOrder(db_table=sales_order)。
type SalesOrder struct {
	model.Base
	OrderNo         string  `gorm:"column:order_no;size:50;uniqueIndex" json:"order_no"`
	CustomerOrderNo string  `gorm:"column:customer_order_no;size:100" json:"customer_order_no"`
	CustomerID      uint64  `gorm:"column:customer_id" json:"customer_id"`
	ProjectID       *uint64 `gorm:"column:project_id" json:"project_id,omitempty"`
	OrderDate       *string `gorm:"column:order_date" json:"order_date,omitempty"`
	DeliveryDate    *string `gorm:"column:delivery_date" json:"delivery_date,omitempty"`
	Status          string  `gorm:"column:status;size:20" json:"status"`

	TaxRate      int     `gorm:"column:tax_rate" json:"tax_rate"`
	TotalAmount  float64 `gorm:"column:total_amount" json:"total_amount"`
	TaxAmount    float64 `gorm:"column:tax_amount" json:"tax_amount"`
	TotalWithTax float64 `gorm:"column:total_with_tax" json:"total_with_tax"`

	PaymentTerms       string `gorm:"column:payment_terms;size:20" json:"payment_terms"`
	PaymentMethod      string `gorm:"column:payment_method;size:20" json:"payment_method"`
	PaymentTermsDetail string `gorm:"column:payment_terms_detail;size:500" json:"payment_terms_detail"`
	Notes              string `gorm:"column:notes" json:"notes"`
}

func (SalesOrder) TableName() string { return "sales_order" }

// SalesOrderLine 销售订单明细,对齐 Django SalesOrderLine(db_table=sales_order_line)。
type SalesOrderLine struct {
	model.Base
	SOID         uint64  `gorm:"column:so_id" json:"so_id"`
	ItemID       *uint64 `gorm:"column:item_id" json:"item_id,omitempty"`
	CustomName   string  `gorm:"column:custom_name;size:200" json:"custom_name"`
	CustomSpec   string  `gorm:"column:custom_spec;size:200" json:"custom_spec"`
	CustomUnit   string  `gorm:"column:custom_unit;size:50" json:"custom_unit"`
	Qty          float64 `gorm:"column:qty" json:"qty"`
	UnitPrice    float64 `gorm:"column:unit_price" json:"unit_price"`
	LineAmount   float64 `gorm:"column:line_amount" json:"line_amount"`
	DeliveredQty float64 `gorm:"column:delivered_qty" json:"delivered_qty"`
	Notes        string  `gorm:"column:notes" json:"notes"`
}

func (SalesOrderLine) TableName() string { return "sales_order_line" }

// ---- 发货单 DeliveryOrder ----

// DeliveryOrder 发货单,对齐 Django DeliveryOrder(db_table=delivery_order)。
type DeliveryOrder struct {
	model.Base
	DeliveryNo         string  `gorm:"column:delivery_no;size:50;uniqueIndex" json:"delivery_no"`
	SOID               uint64  `gorm:"column:so_id" json:"so_id"`
	WarehouseID        uint64  `gorm:"column:warehouse_id" json:"warehouse_id"`
	DeliveryDate       *string `gorm:"column:delivery_date" json:"delivery_date,omitempty"`
	ActualDeliveryDate *string `gorm:"column:actual_delivery_date" json:"actual_delivery_date,omitempty"`
	Status             string  `gorm:"column:status;size:20" json:"status"`

	ReceiverName    string `gorm:"column:receiver_name;size:100" json:"receiver_name"`
	ReceiverPhone   string `gorm:"column:receiver_phone;size:50" json:"receiver_phone"`
	ReceiverAddress string `gorm:"column:receiver_address" json:"receiver_address"`

	PackagingType  string   `gorm:"column:packaging_type;size:20" json:"packaging_type"`
	PackagingNotes string   `gorm:"column:packaging_notes" json:"packaging_notes"`
	NeedsInsurance bool     `gorm:"column:needs_insurance" json:"needs_insurance"`
	InsuranceAmt   *float64 `gorm:"column:insurance_amount" json:"insurance_amount,omitempty"`

	LogisticsCompany string   `gorm:"column:logistics_company;size:100" json:"logistics_company"`
	LogisticsContact string   `gorm:"column:logistics_contact;size:100" json:"logistics_contact"`
	LogisticsPhone   string   `gorm:"column:logistics_phone;size:50" json:"logistics_phone"`
	TrackingNumber   string   `gorm:"column:tracking_number;size:100" json:"tracking_number"`
	LogisticsNotes   string   `gorm:"column:logistics_notes" json:"logistics_notes"`
	LogisticsCost    *float64 `gorm:"column:logistics_cost" json:"logistics_cost,omitempty"`

	SignedReceipt string  `gorm:"column:signed_receipt;size:200" json:"signed_receipt"`
	SignedDate    *string `gorm:"column:signed_date" json:"signed_date,omitempty"`
	SignedBy      string  `gorm:"column:signed_by;size:100" json:"signed_by"`

	Notes           string `gorm:"column:notes" json:"notes"`
	RejectionReason string `gorm:"column:rejection_reason" json:"rejection_reason"`
}

func (DeliveryOrder) TableName() string { return "delivery_order" }

// DeliveryOrderLine 发货明细,对齐 Django DeliveryOrderLine(db_table=delivery_order_line)。
type DeliveryOrderLine struct {
	model.Base
	DeliveryID uint64  `gorm:"column:delivery_id" json:"delivery_id"`
	SOLineID   uint64  `gorm:"column:so_line_id" json:"so_line_id"`
	ItemID     *uint64 `gorm:"column:item_id" json:"item_id,omitempty"`
	Qty        float64 `gorm:"column:qty" json:"qty"`
	Notes      string  `gorm:"column:notes" json:"notes"`
}

func (DeliveryOrderLine) TableName() string { return "delivery_order_line" }

// ---- 线索 Lead ----

// Lead 销售线索,对齐 Django crm_models.Lead(db_table=lead)。
type Lead struct {
	model.Base
	LeadNo          string `gorm:"column:lead_no;size:50;uniqueIndex" json:"lead_no"`
	CompanyName     string `gorm:"column:company_name;size:200" json:"company_name"`
	ContactName     string `gorm:"column:contact_name;size:50" json:"contact_name"`
	ContactPhone    string `gorm:"column:contact_phone;size:20" json:"contact_phone"`
	ContactEmail    string `gorm:"column:contact_email;size:100" json:"contact_email"`
	ContactPosition string `gorm:"column:contact_position;size:50" json:"contact_position"`

	Industry    string `gorm:"column:industry;size:50" json:"industry"`
	CompanySize string `gorm:"column:company_size;size:50" json:"company_size"`
	Address     string `gorm:"column:address" json:"address"`
	Website     string `gorm:"column:website;size:200" json:"website"`

	Requirement     string  `gorm:"column:requirement" json:"requirement"`
	ProductInterest string  `gorm:"column:product_interest;size:200" json:"product_interest"`
	BudgetRange     string  `gorm:"column:budget_range;size:50" json:"budget_range"`
	ExpectedDate    *string `gorm:"column:expected_date" json:"expected_date,omitempty"`

	SourceID     *uint64 `gorm:"column:source_id" json:"source_id,omitempty"`
	SourceDetail string  `gorm:"column:source_detail;size:200" json:"source_detail"`
	Status       string  `gorm:"column:status;size:20" json:"status"`

	OwnerID                *uint64 `gorm:"column:owner_id" json:"owner_id,omitempty"`
	ConvertedCustomerID    *uint64 `gorm:"column:converted_customer_id" json:"converted_customer_id,omitempty"`
	ConvertedOpportunityID *uint64 `gorm:"column:converted_opportunity_id" json:"converted_opportunity_id,omitempty"`
	ConvertedAt            *string `gorm:"column:converted_at" json:"converted_at,omitempty"`

	Score int    `gorm:"column:score" json:"score"`
	Notes string `gorm:"column:notes" json:"notes"`
}

func (Lead) TableName() string { return "lead" }

// ---- 商机 Opportunity ----

// Opportunity 销售商机,对齐 Django crm_models.Opportunity(db_table=opportunity)。
type Opportunity struct {
	model.Base
	OpportunityNo string `gorm:"column:opportunity_no;size:50;uniqueIndex" json:"opportunity_no"`
	Name          string `gorm:"column:name;size:200" json:"name"`
	CustomerID    uint64 `gorm:"column:customer_id" json:"customer_id"`
	ContactName   string `gorm:"column:contact_name;size:50" json:"contact_name"`
	ContactPhone  string `gorm:"column:contact_phone;size:20" json:"contact_phone"`

	Stage       string `gorm:"column:stage;size:20" json:"stage"`
	Priority    string `gorm:"column:priority;size:20" json:"priority"`
	Probability int    `gorm:"column:probability" json:"probability"`

	EstimatedAmount float64 `gorm:"column:estimated_amount" json:"estimated_amount"`
	WeightedAmount  float64 `gorm:"column:weighted_amount" json:"weighted_amount"`

	ProductType           string `gorm:"column:product_type;size:100" json:"product_type"`
	Requirement           string `gorm:"column:requirement" json:"requirement"`
	TechnicalRequirements string `gorm:"column:technical_requirements" json:"technical_requirements"`

	ExpectedCloseDate    *string `gorm:"column:expected_close_date" json:"expected_close_date,omitempty"`
	ExpectedDeliveryDate *string `gorm:"column:expected_delivery_date" json:"expected_delivery_date,omitempty"`
	ActualCloseDate      *string `gorm:"column:actual_close_date" json:"actual_close_date,omitempty"`

	OwnerID *uint64 `gorm:"column:owner_id" json:"owner_id,omitempty"`

	Competitors          string `gorm:"column:competitors" json:"competitors"`
	CompetitiveAdvantage string `gorm:"column:competitive_advantage" json:"competitive_advantage"`

	WonQuotationID *uint64 `gorm:"column:won_quotation_id" json:"won_quotation_id,omitempty"`
	WonOrderID     *uint64 `gorm:"column:won_order_id" json:"won_order_id,omitempty"`
	LostReason     string  `gorm:"column:lost_reason" json:"lost_reason"`
	Notes          string  `gorm:"column:notes" json:"notes"`
}

func (Opportunity) TableName() string { return "opportunity" }

// TODO(verify): 次要实体未本轮实现 — SalesContract(sales_contract)、LeadSource(lead_source)、
// OpportunityActivity(opportunity_activity)、SalesForecast(sales_forecast)、WinLossReason、
// 报价预测/估价/绩效/售后/培训 等子模块。需补五件套。
