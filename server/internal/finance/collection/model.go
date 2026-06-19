// Package collection 移植 Django apps.finance.collection_models 的回款核销三级模型与级联汇总
// (回款计划 → 回款节点 → 收款记录),金额用 shopspring/decimal。经运行中的 Django 对账。
package collection

import (
	"time"

	"github.com/atm-erp/server/internal/platform/model"
	"github.com/shopspring/decimal"
)

// CollectionPlan 回款计划,对齐 collection_plan。
type CollectionPlan struct {
	model.Base
	PlanNo          string          `gorm:"column:plan_no;size:50;uniqueIndex" json:"plan_no"`
	Name            string          `gorm:"column:name;size:200" json:"name"`
	ProjectID       *uint64         `gorm:"column:project_id" json:"project_id,omitempty"`
	SalesOrderID    *uint64         `gorm:"column:sales_order_id" json:"sales_order_id,omitempty"`
	ContractID      *uint64         `gorm:"column:contract_id" json:"contract_id,omitempty"`
	CustomerID      uint64          `gorm:"column:customer_id;index" json:"customer_id"`
	TotalAmount     decimal.Decimal `gorm:"column:total_amount;type:numeric(14,2)" json:"total_amount"`
	PlannedAmount   decimal.Decimal `gorm:"column:planned_amount;type:numeric(14,2)" json:"planned_amount"`
	CollectedAmount decimal.Decimal `gorm:"column:collected_amount;type:numeric(14,2)" json:"collected_amount"`
	Status          string          `gorm:"column:status;size:20" json:"status"`
	OwnerID         *uint64         `gorm:"column:owner_id" json:"owner_id,omitempty"`
	Notes           string          `gorm:"column:notes" json:"notes"`
}

func (CollectionPlan) TableName() string { return "collection_plan" }

// RemainingAmount 剩余应收 = 合同总额 - 已回款(对齐 Django remaining_amount)。
func (p *CollectionPlan) RemainingAmount() decimal.Decimal {
	return p.TotalAmount.Sub(p.CollectedAmount)
}

// CollectionMilestone 回款节点,对齐 collection_milestone。
type CollectionMilestone struct {
	model.Base
	PlanID           uint64          `gorm:"column:plan_id;index" json:"plan_id"`
	MilestoneType    string          `gorm:"column:milestone_type;size:20" json:"milestone_type"`
	Name             string          `gorm:"column:name;size:100" json:"name"`
	Description      string          `gorm:"column:description" json:"description"`
	Percentage       decimal.Decimal `gorm:"column:percentage;type:numeric(5,2)" json:"percentage"`
	PlannedAmount    decimal.Decimal `gorm:"column:planned_amount;type:numeric(14,2)" json:"planned_amount"`
	CollectedAmount  decimal.Decimal `gorm:"column:collected_amount;type:numeric(14,2)" json:"collected_amount"`
	PlannedDate      time.Time       `gorm:"column:planned_date" json:"planned_date"`
	ActualDate       *time.Time      `gorm:"column:actual_date" json:"actual_date,omitempty"`
	TriggerCondition string          `gorm:"column:trigger_condition;size:200" json:"trigger_condition"`
	IsTriggered      bool            `gorm:"column:is_triggered" json:"is_triggered"`
	TriggeredAt      *time.Time      `gorm:"column:triggered_at" json:"triggered_at,omitempty"`
	Status           string          `gorm:"column:status;size:20" json:"status"`
	ReminderDays     int             `gorm:"column:reminder_days" json:"reminder_days"`
	LastReminder     *time.Time      `gorm:"column:last_reminder" json:"last_reminder,omitempty"`
	Notes            string          `gorm:"column:notes" json:"notes"`
}

func (CollectionMilestone) TableName() string { return "collection_milestone" }

// CollectionRecord 收款记录,对齐 collection_record。
type CollectionRecord struct {
	model.Base
	MilestoneID    uint64          `gorm:"column:milestone_id;index" json:"milestone_id"`
	CollectionDate time.Time       `gorm:"column:collection_date" json:"collection_date"`
	Amount         decimal.Decimal `gorm:"column:amount;type:numeric(14,2)" json:"amount"`
	PaymentMethod  string          `gorm:"column:payment_method;size:20" json:"payment_method"`
	BankName       string          `gorm:"column:bank_name;size:100" json:"bank_name"`
	BankAccount    string          `gorm:"column:bank_account;size:50" json:"bank_account"`
	TransactionNo  string          `gorm:"column:transaction_no;size:100" json:"transaction_no"`
	InvoiceID      *uint64         `gorm:"column:invoice_id" json:"invoice_id,omitempty"`
	Confirmed      bool            `gorm:"column:confirmed" json:"confirmed"`
	ConfirmedByID  *uint64         `gorm:"column:confirmed_by_id" json:"confirmed_by_id,omitempty"`
	ConfirmedAt    *time.Time      `gorm:"column:confirmed_at" json:"confirmed_at,omitempty"`
	Notes          string          `gorm:"column:notes" json:"notes"`
}

func (CollectionRecord) TableName() string { return "collection_record" }
