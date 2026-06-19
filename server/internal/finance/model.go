// Package finance 是「财务」限界上下文的 Go 重写,忠实移植 Django apps.finance。
// 涵盖应收(AccountReceivable)、应付(AccountPayable)、付款(Payment)、
// 费用(Expense)、发票(Invoice/InvoiceItem)及货币(Currency)主数据。
//
// 金额一律用 float64 占位(Django 用 DecimalField);精度敏感处标 TODO,
// 待引入 decimal 库后替换(见 todos)。所有外键暂以 *uint64 ID 列表达,
// 不跨模块 import(见 // TODO(port))。
package finance

import (
	"time"

	"github.com/atm-erp/server/internal/platform/model"
)

// scopeModule 标识本上下文的权限/数据范围模块名。
const scopeModule = "finance"

// Currency 货币主数据,对应 Django Currency(db_table=currency)。
type Currency struct {
	model.Base
	Code           string  `gorm:"column:code;size:3;uniqueIndex" json:"code"`
	Name           string  `gorm:"column:name;size:50" json:"name"`
	Symbol         string  `gorm:"column:symbol;size:5" json:"symbol"`
	ExchangeRate   float64 `gorm:"column:exchange_rate" json:"exchange_rate"`
	IsBaseCurrency bool    `gorm:"column:is_base_currency" json:"is_base_currency"`
	IsActive       bool    `gorm:"column:is_active" json:"is_active"`
}

func (Currency) TableName() string { return "currency" }

// Expense 费用,对应 Django Expense(db_table=expense)。
type Expense struct {
	model.Base
	ExpenseNo         string     `gorm:"column:expense_no;size:50;uniqueIndex" json:"expense_no"`
	ProjectID         *uint64    `gorm:"column:project_id" json:"project_id,omitempty"`       // TODO(port): projects.Project
	DepartmentID      *uint64    `gorm:"column:department_id" json:"department_id,omitempty"` // TODO(port): accounts.Department
	UserID            uint64     `gorm:"column:user_id" json:"user_id"`                       // TODO(port): accounts.User 申请人
	ExpenseDate       time.Time  `gorm:"column:expense_date" json:"expense_date"`
	Category          string     `gorm:"column:category;size:20" json:"category"`
	CurrencyID        *uint64    `gorm:"column:currency_id" json:"currency_id,omitempty"`
	Amount            float64    `gorm:"column:amount" json:"amount"`
	ExchangeRate      float64    `gorm:"column:exchange_rate" json:"exchange_rate"`
	BaseAmount        *float64   `gorm:"column:base_amount" json:"base_amount,omitempty"`
	Description       string     `gorm:"column:description" json:"description"`
	Status            string     `gorm:"column:status;size:20" json:"status"`
	ReimbursementDate *time.Time `gorm:"column:reimbursement_date" json:"reimbursement_date,omitempty"`
}

func (Expense) TableName() string { return "expense" }

// 费用类别 / 状态枚举(忠实 Django CATEGORY_CHOICES / STATUS_CHOICES)。
const (
	ExpenseStatusDraft     = "DRAFT"
	ExpenseStatusSubmitted = "SUBMITTED"
	ExpenseStatusApproved  = "APPROVED"
	ExpenseStatusRejected  = "REJECTED"
	ExpenseStatusPaid      = "PAID"
)

// AccountReceivable 应收账款,对应 Django AccountReceivable(db_table=account_receivable)。
type AccountReceivable struct {
	model.Base
	ARNo         string    `gorm:"column:ar_no;size:50;uniqueIndex" json:"ar_no"`
	CustomerID   uint64    `gorm:"column:customer_id" json:"customer_id"` // TODO(port): masterdata.Customer
	SOID         *uint64   `gorm:"column:so_id" json:"so_id,omitempty"`   // TODO(port): sales.SalesOrder
	ProjectID    *uint64   `gorm:"column:project_id" json:"project_id,omitempty"`
	InvoiceNo    string    `gorm:"column:invoice_no;size:50" json:"invoice_no"`
	InvoiceDate  time.Time `gorm:"column:invoice_date" json:"invoice_date"`
	CurrencyID   *uint64   `gorm:"column:currency_id" json:"currency_id,omitempty"`
	AmountDue    float64   `gorm:"column:amount_due" json:"amount_due"`
	AmountPaid   float64   `gorm:"column:amount_paid" json:"amount_paid"`
	ExchangeRate float64   `gorm:"column:exchange_rate" json:"exchange_rate"`
	DueDate      time.Time `gorm:"column:due_date" json:"due_date"`
	Status       string    `gorm:"column:status;size:20" json:"status"`
}

func (AccountReceivable) TableName() string { return "account_receivable" }

// AmountRemaining 复刻 Django @property amount_remaining。
func (a AccountReceivable) AmountRemaining() float64 { return a.AmountDue - a.AmountPaid }

// AccountPayable 应付账款,对应 Django AccountPayable(db_table=account_payable)。
type AccountPayable struct {
	model.Base
	APNo         string    `gorm:"column:ap_no;size:50;uniqueIndex" json:"ap_no"`
	SupplierID   uint64    `gorm:"column:supplier_id" json:"supplier_id"` // TODO(port): masterdata.Supplier
	POID         *uint64   `gorm:"column:po_id" json:"po_id,omitempty"`   // TODO(port): purchase.PurchaseOrder
	ProjectID    *uint64   `gorm:"column:project_id" json:"project_id,omitempty"`
	InvoiceNo    string    `gorm:"column:invoice_no;size:50" json:"invoice_no"`
	InvoiceDate  time.Time `gorm:"column:invoice_date" json:"invoice_date"`
	CurrencyID   *uint64   `gorm:"column:currency_id" json:"currency_id,omitempty"`
	AmountDue    float64   `gorm:"column:amount_due" json:"amount_due"`
	AmountPaid   float64   `gorm:"column:amount_paid" json:"amount_paid"`
	ExchangeRate float64   `gorm:"column:exchange_rate" json:"exchange_rate"`
	DueDate      time.Time `gorm:"column:due_date" json:"due_date"`
	Status       string    `gorm:"column:status;size:20" json:"status"`
}

func (AccountPayable) TableName() string { return "account_payable" }

// AmountRemaining 复刻 Django @property amount_remaining。
func (a AccountPayable) AmountRemaining() float64 { return a.AmountDue - a.AmountPaid }

// 应收/应付状态枚举(忠实 Django STATUS_CHOICES)。
const (
	ARAPStatusPending   = "PENDING"
	ARAPStatusPartial   = "PARTIAL"
	ARAPStatusPaid      = "PAID"
	ARAPStatusOverdue   = "OVERDUE"
	ARAPStatusCancelled = "CANCELLED"
)

// Payment 付款记录,对应 Django Payment(db_table=payment)。
type Payment struct {
	model.Base
	PaymentNo     string    `gorm:"column:payment_no;size:50;uniqueIndex" json:"payment_no"`
	PaymentType   string    `gorm:"column:payment_type;size:10" json:"payment_type"` // AR / AP
	ARID          *uint64   `gorm:"column:ar_id" json:"ar_id,omitempty"`
	APID          *uint64   `gorm:"column:ap_id" json:"ap_id,omitempty"`
	PaymentDate   time.Time `gorm:"column:payment_date" json:"payment_date"`
	PaymentMethod string    `gorm:"column:payment_method;size:20" json:"payment_method"`
	CurrencyID    *uint64   `gorm:"column:currency_id" json:"currency_id,omitempty"`
	Amount        float64   `gorm:"column:amount" json:"amount"`
	ExchangeRate  float64   `gorm:"column:exchange_rate" json:"exchange_rate"`
	Notes         string    `gorm:"column:notes" json:"notes"`
}

func (Payment) TableName() string { return "payment" }

// 付款类型 / 付款方式枚举。
const (
	PaymentTypeAR = "AR"
	PaymentTypeAP = "AP"
)

// Invoice 发票,对应 Django Invoice(db_table=invoice)。
type Invoice struct {
	model.Base
	InvoiceType      string    `gorm:"column:invoice_type;size:10" json:"invoice_type"` // INPUT / OUTPUT
	InvoiceNo        string    `gorm:"column:invoice_no;size:50;uniqueIndex" json:"invoice_no"`
	InvoiceCode      string    `gorm:"column:invoice_code;size:50" json:"invoice_code"`
	DigitalInvoiceNo string    `gorm:"column:digital_invoice_no;size:50" json:"digital_invoice_no"`
	InvoiceDate      time.Time `gorm:"column:invoice_date" json:"invoice_date"`
	SellerTaxNo      string    `gorm:"column:seller_tax_no;size:50" json:"seller_tax_no"`
	SellerName       string    `gorm:"column:seller_name;size:200" json:"seller_name"`
	BuyerTaxNo       string    `gorm:"column:buyer_tax_no;size:50" json:"buyer_tax_no"`
	BuyerName        string    `gorm:"column:buyer_name;size:200" json:"buyer_name"`
	PartyName        string    `gorm:"column:party_name;size:200" json:"party_name"`
	TaxNumber        string    `gorm:"column:tax_number;size:50" json:"tax_number"`
	AmountBeforeTax  float64   `gorm:"column:amount_before_tax" json:"amount_before_tax"`
	TaxAmount        float64   `gorm:"column:tax_amount" json:"tax_amount"`
	TotalAmount      float64   `gorm:"column:total_amount" json:"total_amount"`
	InvoiceSource    string    `gorm:"column:invoice_source;size:100" json:"invoice_source"`
	InvoiceCategory  string    `gorm:"column:invoice_category;size:50" json:"invoice_category"`
	ReferenceType    *string   `gorm:"column:reference_type;size:20" json:"reference_type,omitempty"`
	ReferenceID      *int64    `gorm:"column:reference_id" json:"reference_id,omitempty"`
	ProjectID        *uint64   `gorm:"column:project_id" json:"project_id,omitempty"`
	Status           string    `gorm:"column:status;size:20" json:"status"`
	Notes            string    `gorm:"column:notes" json:"notes"`
}

func (Invoice) TableName() string { return "invoice" }

// 发票类型 / 状态枚举(忠实 Django INVOICE_TYPE_CHOICES / STATUS_CHOICES)。
const (
	InvoiceTypeInput  = "INPUT"
	InvoiceTypeOutput = "OUTPUT"

	InvoiceStatusRegistered = "REGISTERED"
	InvoiceStatusCertified  = "CERTIFIED"
	InvoiceStatusVoid       = "VOID"
	InvoiceStatusNormal     = "NORMAL"
	InvoiceStatusRed        = "RED"
)

// InvoiceItem 发票明细行,对应 Django InvoiceItem(db_table=invoice_item)。
type InvoiceItem struct {
	model.Base
	InvoiceID       uint64   `gorm:"column:invoice_id" json:"invoice_id"`
	LineNo          int      `gorm:"column:line_no" json:"line_no"`
	TaxCategoryCode string   `gorm:"column:tax_category_code;size:50" json:"tax_category_code"`
	BusinessType    string   `gorm:"column:business_type;size:100" json:"business_type"`
	ItemName        string   `gorm:"column:item_name;size:500" json:"item_name"`
	Specification   string   `gorm:"column:specification;size:200" json:"specification"`
	Unit            string   `gorm:"column:unit;size:50" json:"unit"`
	Quantity        *float64 `gorm:"column:quantity" json:"quantity,omitempty"`
	UnitPrice       *float64 `gorm:"column:unit_price" json:"unit_price,omitempty"`
	Amount          float64  `gorm:"column:amount" json:"amount"`
	TaxRate         *float64 `gorm:"column:tax_rate" json:"tax_rate,omitempty"`
	TaxAmount       *float64 `gorm:"column:tax_amount" json:"tax_amount,omitempty"`
}

func (InvoiceItem) TableName() string { return "invoice_item" }
