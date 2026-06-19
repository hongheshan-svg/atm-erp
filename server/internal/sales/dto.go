package sales

// ===== Quotation =====

type QuotationLineInput struct {
	ItemID     *uint64 `json:"item_id"`
	CustomName string  `json:"custom_name"`
	CustomSpec string  `json:"custom_spec"`
	CustomUnit string  `json:"custom_unit"`
	Qty        float64 `json:"qty" binding:"required"`
	UnitPrice  float64 `json:"unit_price"`
	Notes      string  `json:"notes"`
}

type QuotationCreateInput struct {
	CustomerID uint64               `json:"customer_id" binding:"required"`
	ProjectID  *uint64              `json:"project_id"`
	ValidUntil *string              `json:"valid_until"`
	TaxRate    *int                 `json:"tax_rate"`
	Notes      string               `json:"notes"`
	Lines      []QuotationLineInput `json:"lines"`
}

type QuotationUpdateInput struct {
	CustomerID *uint64 `json:"customer_id"`
	ProjectID  *uint64 `json:"project_id"`
	ValidUntil *string `json:"valid_until"`
	TaxRate    *int    `json:"tax_rate"`
	Status     *string `json:"status"`
	Notes      *string `json:"notes"`
}

// ConvertToSOInput 报价转订单入参。
type ConvertToSOInput struct {
	DeliveryDate *string `json:"delivery_date"`
}

// ===== SalesOrder =====

type SalesOrderLineInput struct {
	ItemID     *uint64 `json:"item_id"`
	CustomName string  `json:"custom_name"`
	CustomSpec string  `json:"custom_spec"`
	CustomUnit string  `json:"custom_unit"`
	Qty        float64 `json:"qty" binding:"required"`
	UnitPrice  float64 `json:"unit_price"`
	Notes      string  `json:"notes"`
}

type SalesOrderCreateInput struct {
	CustomerID      uint64                `json:"customer_id" binding:"required"`
	ProjectID       *uint64               `json:"project_id"`
	CustomerOrderNo string                `json:"customer_order_no"`
	DeliveryDate    *string               `json:"delivery_date"`
	TaxRate         *int                  `json:"tax_rate"`
	PaymentTerms    string                `json:"payment_terms"`
	PaymentMethod   string                `json:"payment_method"`
	Notes           string                `json:"notes"`
	Lines           []SalesOrderLineInput `json:"lines"`
}

type SalesOrderUpdateInput struct {
	CustomerID      *uint64 `json:"customer_id"`
	ProjectID       *uint64 `json:"project_id"`
	CustomerOrderNo *string `json:"customer_order_no"`
	DeliveryDate    *string `json:"delivery_date"`
	TaxRate         *int    `json:"tax_rate"`
	PaymentTerms    *string `json:"payment_terms"`
	PaymentMethod   *string `json:"payment_method"`
	Status          *string `json:"status"`
	Notes           *string `json:"notes"`
}

// ===== DeliveryOrder =====

type DeliveryLineInput struct {
	SOLineID uint64  `json:"so_line_id" binding:"required"`
	ItemID   *uint64 `json:"item_id"`
	Qty      float64 `json:"qty" binding:"required"`
	Notes    string  `json:"notes"`
}

type DeliveryCreateInput struct {
	SOID            uint64              `json:"so_id" binding:"required"`
	WarehouseID     uint64              `json:"warehouse_id" binding:"required"`
	DeliveryDate    *string             `json:"delivery_date"`
	ReceiverName    string              `json:"receiver_name"`
	ReceiverPhone   string              `json:"receiver_phone"`
	ReceiverAddress string              `json:"receiver_address"`
	PackagingType   string              `json:"packaging_type"`
	Notes           string              `json:"notes"`
	Lines           []DeliveryLineInput `json:"lines"`
}

type DeliveryUpdateInput struct {
	WarehouseID     *uint64 `json:"warehouse_id"`
	DeliveryDate    *string `json:"delivery_date"`
	ReceiverName    *string `json:"receiver_name"`
	ReceiverPhone   *string `json:"receiver_phone"`
	ReceiverAddress *string `json:"receiver_address"`
	PackagingType   *string `json:"packaging_type"`
	Status          *string `json:"status"`
	Notes           *string `json:"notes"`
}

// ===== Lead =====

type LeadCreateInput struct {
	CompanyName     string  `json:"company_name" binding:"required"`
	ContactName     string  `json:"contact_name" binding:"required"`
	ContactPhone    string  `json:"contact_phone"`
	ContactEmail    string  `json:"contact_email"`
	ContactPosition string  `json:"contact_position"`
	Industry        string  `json:"industry"`
	CompanySize     string  `json:"company_size"`
	Address         string  `json:"address"`
	Website         string  `json:"website"`
	Requirement     string  `json:"requirement"`
	ProductInterest string  `json:"product_interest"`
	BudgetRange     string  `json:"budget_range"`
	ExpectedDate    *string `json:"expected_date"`
	SourceID        *uint64 `json:"source_id"`
	SourceDetail    string  `json:"source_detail"`
	OwnerID         *uint64 `json:"owner_id"`
	Score           int     `json:"score"`
	Notes           string  `json:"notes"`
}

type LeadUpdateInput struct {
	CompanyName     *string `json:"company_name"`
	ContactName     *string `json:"contact_name"`
	ContactPhone    *string `json:"contact_phone"`
	ContactEmail    *string `json:"contact_email"`
	ContactPosition *string `json:"contact_position"`
	Industry        *string `json:"industry"`
	CompanySize     *string `json:"company_size"`
	Address         *string `json:"address"`
	Website         *string `json:"website"`
	Requirement     *string `json:"requirement"`
	ProductInterest *string `json:"product_interest"`
	BudgetRange     *string `json:"budget_range"`
	ExpectedDate    *string `json:"expected_date"`
	SourceID        *uint64 `json:"source_id"`
	SourceDetail    *string `json:"source_detail"`
	Status          *string `json:"status"`
	OwnerID         *uint64 `json:"owner_id"`
	Score           *int    `json:"score"`
	Notes           *string `json:"notes"`
}

// LeadConvertInput 线索转化入参(对齐 Django LeadConvertSerializer)。
type LeadConvertInput struct {
	CreateCustomer    *bool   `json:"create_customer"`
	CustomerID        *uint64 `json:"customer_id"`
	CreateOpportunity *bool   `json:"create_opportunity"`
	OpportunityName   string  `json:"opportunity_name"`
	EstimatedAmount   float64 `json:"estimated_amount"`
}

// ===== Opportunity =====

type OpportunityCreateInput struct {
	Name                  string  `json:"name" binding:"required"`
	CustomerID            uint64  `json:"customer_id" binding:"required"`
	ContactName           string  `json:"contact_name"`
	ContactPhone          string  `json:"contact_phone"`
	Stage                 string  `json:"stage"`
	Priority              string  `json:"priority"`
	Probability           *int    `json:"probability"`
	EstimatedAmount       float64 `json:"estimated_amount"`
	ProductType           string  `json:"product_type"`
	Requirement           string  `json:"requirement"`
	TechnicalRequirements string  `json:"technical_requirements"`
	ExpectedCloseDate     *string `json:"expected_close_date"`
	ExpectedDeliveryDate  *string `json:"expected_delivery_date"`
	OwnerID               *uint64 `json:"owner_id"`
	Competitors           string  `json:"competitors"`
	CompetitiveAdvantage  string  `json:"competitive_advantage"`
	Notes                 string  `json:"notes"`
}

type OpportunityUpdateInput struct {
	Name                  *string  `json:"name"`
	CustomerID            *uint64  `json:"customer_id"`
	ContactName           *string  `json:"contact_name"`
	ContactPhone          *string  `json:"contact_phone"`
	Stage                 *string  `json:"stage"`
	Priority              *string  `json:"priority"`
	Probability           *int     `json:"probability"`
	EstimatedAmount       *float64 `json:"estimated_amount"`
	ProductType           *string  `json:"product_type"`
	Requirement           *string  `json:"requirement"`
	TechnicalRequirements *string  `json:"technical_requirements"`
	ExpectedCloseDate     *string  `json:"expected_close_date"`
	ExpectedDeliveryDate  *string  `json:"expected_delivery_date"`
	OwnerID               *uint64  `json:"owner_id"`
	Competitors           *string  `json:"competitors"`
	CompetitiveAdvantage  *string  `json:"competitive_advantage"`
	LostReason            *string  `json:"lost_reason"`
	Notes                 *string  `json:"notes"`
}

// ===== 公共 ListQuery =====

// ListQuery 通用列表筛选(各实体复用,按需取字段)。
type ListQuery struct {
	Keyword    string
	Status     string // Quotation/SalesOrder/DeliveryOrder/Lead 状态
	Stage      string // Opportunity 阶段
	CustomerID string
	SOID       string // DeliveryOrder 按销售订单过滤
}
