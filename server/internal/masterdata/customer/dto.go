package customer

// CreateInput 新建客户入参。code 可空(留空则后端生成,见 service)。
type CreateInput struct {
	Code           string  `json:"code"`
	Name           string  `json:"name" binding:"required"`
	ShortName      string  `json:"short_name"`
	ContactPerson  string  `json:"contact_person"`
	Phone          string  `json:"phone"`
	Email          string  `json:"email"`
	Address        string  `json:"address"`
	CreditLimit    float64 `json:"credit_limit"`
	PaymentTerms   string  `json:"payment_terms"`
	InvoiceTitle   string  `json:"invoice_title"`
	TaxNumber      string  `json:"tax_number"`
	BankName       string  `json:"bank_name"`
	BankAccount    string  `json:"bank_account"`
	RegisteredAddr string  `json:"registered_address"`
	RegisteredTel  string  `json:"registered_phone"`
	Status         string  `json:"status"`
	Notes          string  `json:"notes"`
}

// UpdateInput 局部更新入参(指针区分“未传”与“置零值”)。
type UpdateInput struct {
	Name           *string  `json:"name"`
	ShortName      *string  `json:"short_name"`
	ContactPerson  *string  `json:"contact_person"`
	Phone          *string  `json:"phone"`
	Email          *string  `json:"email"`
	Address        *string  `json:"address"`
	CreditLimit    *float64 `json:"credit_limit"`
	PaymentTerms   *string  `json:"payment_terms"`
	InvoiceTitle   *string  `json:"invoice_title"`
	TaxNumber      *string  `json:"tax_number"`
	BankName       *string  `json:"bank_name"`
	BankAccount    *string  `json:"bank_account"`
	RegisteredAddr *string  `json:"registered_address"`
	RegisteredTel  *string  `json:"registered_phone"`
	Status         *string  `json:"status"`
	Notes          *string  `json:"notes"`
}

// ListQuery 列表筛选条件。
type ListQuery struct {
	Keyword string // code/name/short_name 模糊
	Status  string
}

// ChangeStatusInput 状态流转入参。
type ChangeStatusInput struct {
	Status string `json:"status" binding:"required"`
}
