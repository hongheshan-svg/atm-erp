package supplier

// CreateInput 新建供应商入参。code 可空(留空则后端生成,见 service)。
type CreateInput struct {
	Code             string `json:"code"`
	Name             string `json:"name" binding:"required"`
	ShortName        string `json:"short_name"`
	ContactPerson    string `json:"contact_person"`
	Phone            string `json:"phone"`
	Email            string `json:"email"`
	Address          string `json:"address"`
	PaymentTerms     string `json:"payment_terms"`
	SettlementMethod string `json:"settlement_method"`
	InvoiceTitle     string `json:"invoice_title"`
	TaxNumber        string `json:"tax_number"`
	BankName         string `json:"bank_name"`
	BankAccount      string `json:"bank_account"`
	RegisteredAddr   string `json:"registered_address"`
	RegisteredTel    string `json:"registered_phone"`
	Status           string `json:"status"`
	Notes            string `json:"notes"`
}

// UpdateInput 局部更新入参。
type UpdateInput struct {
	Name             *string `json:"name"`
	ShortName        *string `json:"short_name"`
	ContactPerson    *string `json:"contact_person"`
	Phone            *string `json:"phone"`
	Email            *string `json:"email"`
	Address          *string `json:"address"`
	PaymentTerms     *string `json:"payment_terms"`
	SettlementMethod *string `json:"settlement_method"`
	InvoiceTitle     *string `json:"invoice_title"`
	TaxNumber        *string `json:"tax_number"`
	BankName         *string `json:"bank_name"`
	BankAccount      *string `json:"bank_account"`
	RegisteredAddr   *string `json:"registered_address"`
	RegisteredTel    *string `json:"registered_phone"`
	Status           *string `json:"status"`
	Notes            *string `json:"notes"`
}

// ListQuery 列表筛选条件。
type ListQuery struct {
	Keyword string
	Status  string
}

// ChangeStatusInput 状态流转入参。
type ChangeStatusInput struct {
	Status string `json:"status" binding:"required"`
}
