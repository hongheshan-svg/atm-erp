package collection

import "github.com/shopspring/decimal"

// CreatePlanInput 新建回款计划。
type CreatePlanInput struct {
	PlanNo       string          `json:"plan_no"`
	Name         string          `json:"name" binding:"required"`
	CustomerID   uint64          `json:"customer_id" binding:"required"`
	ProjectID    *uint64         `json:"project_id"`
	SalesOrderID *uint64         `json:"sales_order_id"`
	ContractID   *uint64         `json:"contract_id"`
	TotalAmount  decimal.Decimal `json:"total_amount"`
	OwnerID      *uint64         `json:"owner_id"`
	Notes        string          `json:"notes"`
}

// UpdatePlanInput 局部更新计划(指针区分未传)。
type UpdatePlanInput struct {
	Name        *string          `json:"name"`
	TotalAmount *decimal.Decimal `json:"total_amount"`
	OwnerID     *uint64          `json:"owner_id"`
	Notes       *string          `json:"notes"`
}

// CreateMilestoneInput 新建回款节点。
type CreateMilestoneInput struct {
	MilestoneType string          `json:"milestone_type"`
	Name          string          `json:"name" binding:"required"`
	Description   string          `json:"description"`
	Percentage    decimal.Decimal `json:"percentage"`
	PlannedAmount decimal.Decimal `json:"planned_amount"`
	PlannedDate   string          `json:"planned_date"`
}

// CreateRecordInput 新增一条收款记录(触发节点/计划级联汇总)。
type CreateRecordInput struct {
	Amount         decimal.Decimal `json:"amount"`
	CollectionDate string          `json:"collection_date"`
	PaymentMethod  string          `json:"payment_method"`
	BankName       string          `json:"bank_name"`
	BankAccount    string          `json:"bank_account"`
	TransactionNo  string          `json:"transaction_no"`
	Notes          string          `json:"notes"`
}

// PlanListQuery 计划列表筛选。
type PlanListQuery struct {
	Keyword    string
	CustomerID string
	Status     string
}
