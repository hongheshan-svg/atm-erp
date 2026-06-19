// Package supplier 是供应商主数据(masterdata.Supplier)的 Go 实现,
// 忠实映射 Django apps.masterdata.models.Supplier。
package supplier

import "github.com/atm-erp/server/internal/platform/model"

// Supplier 供应商主数据。字段对齐 Django Meta.db_table='supplier'。
type Supplier struct {
	model.Base
	Code             string `gorm:"column:code;size:50;uniqueIndex" json:"code"`
	Name             string `gorm:"column:name;size:200" json:"name"`
	ShortName        string `gorm:"column:short_name;size:100" json:"short_name"`
	ContactPerson    string `gorm:"column:contact_person;size:100" json:"contact_person"`
	Phone            string `gorm:"column:phone;size:50" json:"phone"`
	Email            string `gorm:"column:email;size:254" json:"email"`
	Address          string `gorm:"column:address" json:"address"`
	PaymentTerms     string `gorm:"column:payment_terms;size:100" json:"payment_terms"`
	SettlementMethod string `gorm:"column:settlement_method;size:20" json:"settlement_method"`
	InvoiceTitle     string `gorm:"column:invoice_title;size:200" json:"invoice_title"`
	TaxNumber        string `gorm:"column:tax_number;size:100" json:"tax_number"`
	BankName         string `gorm:"column:bank_name;size:200" json:"bank_name"`
	BankAccount      string `gorm:"column:bank_account;size:100" json:"bank_account"`
	RegisteredAddr   string `gorm:"column:registered_address" json:"registered_address"`
	RegisteredTel    string `gorm:"column:registered_phone;size:50" json:"registered_phone"`
	Status           string `gorm:"column:status;size:20" json:"status"`
	Notes            string `gorm:"column:notes" json:"notes"`
}

// TableName 对齐 Django Meta.db_table。
func (Supplier) TableName() string { return "supplier" }

// 状态枚举,对齐 Django STATUS_CHOICES。
const (
	StatusActive    = "ACTIVE"
	StatusInactive  = "INACTIVE"
	StatusPotential = "POTENTIAL"
)

// settlementMethods 对齐 Django SETTLEMENT_METHOD_CHOICES。
var settlementMethods = map[string]bool{
	"PREPAY": true, "COD": true, "NET15": true, "NET30": true, "NET45": true,
	"NET60": true, "NET90": true, "NET120": true, "ACCEPTANCE": true, "OTHER": true,
}
