package finance

import "time"

// ---- Currency ----

type CurrencyCreateInput struct {
	Code           string  `json:"code" binding:"required"`
	Name           string  `json:"name" binding:"required"`
	Symbol         string  `json:"symbol"`
	ExchangeRate   float64 `json:"exchange_rate"`
	IsBaseCurrency bool    `json:"is_base_currency"`
	IsActive       *bool   `json:"is_active"`
}

type CurrencyUpdateInput struct {
	Name           *string  `json:"name"`
	Symbol         *string  `json:"symbol"`
	ExchangeRate   *float64 `json:"exchange_rate"`
	IsBaseCurrency *bool    `json:"is_base_currency"`
	IsActive       *bool    `json:"is_active"`
}

type CurrencyListQuery struct {
	Keyword  string
	IsActive *bool
}

// ---- Expense ----

type ExpenseCreateInput struct {
	ProjectID    *uint64   `json:"project_id"`
	DepartmentID *uint64   `json:"department_id"`
	UserID       uint64    `json:"user_id" binding:"required"`
	ExpenseDate  time.Time `json:"expense_date" binding:"required"`
	Category     string    `json:"category" binding:"required"`
	CurrencyID   *uint64   `json:"currency_id"`
	Amount       float64   `json:"amount" binding:"required"`
	ExchangeRate *float64  `json:"exchange_rate"`
	Description  string    `json:"description"`
}

type ExpenseUpdateInput struct {
	ProjectID         *uint64    `json:"project_id"`
	DepartmentID      *uint64    `json:"department_id"`
	ExpenseDate       *time.Time `json:"expense_date"`
	Category          *string    `json:"category"`
	CurrencyID        *uint64    `json:"currency_id"`
	Amount            *float64   `json:"amount"`
	ExchangeRate      *float64   `json:"exchange_rate"`
	Description       *string    `json:"description"`
	Status            *string    `json:"status"`
	ReimbursementDate *time.Time `json:"reimbursement_date"`
}

type ExpenseListQuery struct {
	Keyword   string
	Status    string
	Category  string
	ProjectID *uint64
}

// ---- AccountReceivable ----

type ReceivableCreateInput struct {
	CustomerID   uint64    `json:"customer_id" binding:"required"`
	SOID         *uint64   `json:"so_id"`
	ProjectID    *uint64   `json:"project_id"`
	InvoiceNo    string    `json:"invoice_no"`
	InvoiceDate  time.Time `json:"invoice_date" binding:"required"`
	CurrencyID   *uint64   `json:"currency_id"`
	AmountDue    float64   `json:"amount_due" binding:"required"`
	AmountPaid   *float64  `json:"amount_paid"`
	ExchangeRate *float64  `json:"exchange_rate"`
	DueDate      time.Time `json:"due_date" binding:"required"`
}

type ReceivableUpdateInput struct {
	CustomerID   *uint64    `json:"customer_id"`
	SOID         *uint64    `json:"so_id"`
	ProjectID    *uint64    `json:"project_id"`
	InvoiceNo    *string    `json:"invoice_no"`
	InvoiceDate  *time.Time `json:"invoice_date"`
	CurrencyID   *uint64    `json:"currency_id"`
	AmountDue    *float64   `json:"amount_due"`
	AmountPaid   *float64   `json:"amount_paid"`
	ExchangeRate *float64   `json:"exchange_rate"`
	DueDate      *time.Time `json:"due_date"`
	Status       *string    `json:"status"`
}

type ReceivableListQuery struct {
	Keyword    string
	Status     string
	CustomerID *uint64
	ProjectID  *uint64
}

// ---- AccountPayable ----

type PayableCreateInput struct {
	SupplierID   uint64    `json:"supplier_id" binding:"required"`
	POID         *uint64   `json:"po_id"`
	ProjectID    *uint64   `json:"project_id"`
	InvoiceNo    string    `json:"invoice_no"`
	InvoiceDate  time.Time `json:"invoice_date" binding:"required"`
	CurrencyID   *uint64   `json:"currency_id"`
	AmountDue    float64   `json:"amount_due" binding:"required"`
	AmountPaid   *float64  `json:"amount_paid"`
	ExchangeRate *float64  `json:"exchange_rate"`
	DueDate      time.Time `json:"due_date" binding:"required"`
}

type PayableUpdateInput struct {
	SupplierID   *uint64    `json:"supplier_id"`
	POID         *uint64    `json:"po_id"`
	ProjectID    *uint64    `json:"project_id"`
	InvoiceNo    *string    `json:"invoice_no"`
	InvoiceDate  *time.Time `json:"invoice_date"`
	CurrencyID   *uint64    `json:"currency_id"`
	AmountDue    *float64   `json:"amount_due"`
	AmountPaid   *float64   `json:"amount_paid"`
	ExchangeRate *float64   `json:"exchange_rate"`
	DueDate      *time.Time `json:"due_date"`
	Status       *string    `json:"status"`
}

type PayableListQuery struct {
	Keyword    string
	Status     string
	SupplierID *uint64
	ProjectID  *uint64
}

// ---- Payment ----

type PaymentCreateInput struct {
	PaymentType   string    `json:"payment_type" binding:"required"` // AR / AP
	ARID          *uint64   `json:"ar_id"`
	APID          *uint64   `json:"ap_id"`
	PaymentDate   time.Time `json:"payment_date" binding:"required"`
	PaymentMethod string    `json:"payment_method" binding:"required"`
	CurrencyID    *uint64   `json:"currency_id"`
	Amount        float64   `json:"amount" binding:"required"`
	ExchangeRate  *float64  `json:"exchange_rate"`
	Notes         string    `json:"notes"`
}

type PaymentListQuery struct {
	Keyword     string
	PaymentType string
	ARID        *uint64
	APID        *uint64
}

// ---- Invoice / InvoiceItem ----

type InvoiceItemInput struct {
	LineNo          int      `json:"line_no"`
	TaxCategoryCode string   `json:"tax_category_code"`
	BusinessType    string   `json:"business_type"`
	ItemName        string   `json:"item_name" binding:"required"`
	Specification   string   `json:"specification"`
	Unit            string   `json:"unit"`
	Quantity        *float64 `json:"quantity"`
	UnitPrice       *float64 `json:"unit_price"`
	Amount          float64  `json:"amount"`
	TaxRate         *float64 `json:"tax_rate"`
	TaxAmount       *float64 `json:"tax_amount"`
}

type InvoiceCreateInput struct {
	InvoiceType      string             `json:"invoice_type" binding:"required"`
	InvoiceNo        string             `json:"invoice_no" binding:"required"`
	InvoiceCode      string             `json:"invoice_code"`
	DigitalInvoiceNo string             `json:"digital_invoice_no"`
	InvoiceDate      time.Time          `json:"invoice_date" binding:"required"`
	SellerTaxNo      string             `json:"seller_tax_no"`
	SellerName       string             `json:"seller_name"`
	BuyerTaxNo       string             `json:"buyer_tax_no"`
	BuyerName        string             `json:"buyer_name"`
	PartyName        string             `json:"party_name"`
	TaxNumber        string             `json:"tax_number"`
	AmountBeforeTax  float64            `json:"amount_before_tax"`
	TaxAmount        float64            `json:"tax_amount"`
	TotalAmount      *float64           `json:"total_amount"`
	InvoiceSource    string             `json:"invoice_source"`
	InvoiceCategory  string             `json:"invoice_category"`
	ReferenceType    *string            `json:"reference_type"`
	ReferenceID      *int64             `json:"reference_id"`
	ProjectID        *uint64            `json:"project_id"`
	Notes            string             `json:"notes"`
	Items            []InvoiceItemInput `json:"items"`
}

type InvoiceUpdateInput struct {
	InvoiceType      *string    `json:"invoice_type"`
	InvoiceCode      *string    `json:"invoice_code"`
	DigitalInvoiceNo *string    `json:"digital_invoice_no"`
	InvoiceDate      *time.Time `json:"invoice_date"`
	SellerTaxNo      *string    `json:"seller_tax_no"`
	SellerName       *string    `json:"seller_name"`
	BuyerTaxNo       *string    `json:"buyer_tax_no"`
	BuyerName        *string    `json:"buyer_name"`
	PartyName        *string    `json:"party_name"`
	TaxNumber        *string    `json:"tax_number"`
	AmountBeforeTax  *float64   `json:"amount_before_tax"`
	TaxAmount        *float64   `json:"tax_amount"`
	TotalAmount      *float64   `json:"total_amount"`
	InvoiceSource    *string    `json:"invoice_source"`
	InvoiceCategory  *string    `json:"invoice_category"`
	ReferenceType    *string    `json:"reference_type"`
	ReferenceID      *int64     `json:"reference_id"`
	ProjectID        *uint64    `json:"project_id"`
	Status           *string    `json:"status"`
	Notes            *string    `json:"notes"`
}

type InvoiceListQuery struct {
	Keyword     string
	InvoiceType string
	Status      string
	ProjectID   *uint64
}
