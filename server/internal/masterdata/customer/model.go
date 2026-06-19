// Package customer 是客户主数据(masterdata.Customer)的 Go 实现,
// 忠实映射 Django apps.masterdata.models.Customer。
package customer

import "github.com/atm-erp/server/internal/platform/model"

// Customer 客户主数据。字段对齐 Django Meta.db_table='customer'。
type Customer struct {
	model.Base
	Code           string  `gorm:"column:code;size:50;uniqueIndex" json:"code"`
	Name           string  `gorm:"column:name;size:200" json:"name"`
	ShortName      string  `gorm:"column:short_name;size:100" json:"short_name"`
	ContactPerson  string  `gorm:"column:contact_person;size:100" json:"contact_person"`
	Phone          string  `gorm:"column:phone;size:50" json:"phone"`
	Email          string  `gorm:"column:email;size:254" json:"email"`
	Address        string  `gorm:"column:address" json:"address"`
	CreditLimit    float64 `gorm:"column:credit_limit" json:"credit_limit"`
	PaymentTerms   string  `gorm:"column:payment_terms;size:100" json:"payment_terms"`
	InvoiceTitle   string  `gorm:"column:invoice_title;size:200" json:"invoice_title"`
	TaxNumber      string  `gorm:"column:tax_number;size:100" json:"tax_number"`
	BankName       string  `gorm:"column:bank_name;size:200" json:"bank_name"`
	BankAccount    string  `gorm:"column:bank_account;size:100" json:"bank_account"`
	RegisteredAddr string  `gorm:"column:registered_address" json:"registered_address"`
	RegisteredTel  string  `gorm:"column:registered_phone;size:50" json:"registered_phone"`
	Status         string  `gorm:"column:status;size:20" json:"status"`
	Notes          string  `gorm:"column:notes" json:"notes"`
}

// TableName 对齐 Django Meta.db_table。
func (Customer) TableName() string { return "customer" }

// 状态枚举,对齐 Django STATUS_CHOICES。
const (
	StatusActive    = "ACTIVE"
	StatusInactive  = "INACTIVE"
	StatusPotential = "POTENTIAL"
)
