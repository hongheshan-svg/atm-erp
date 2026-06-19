// Package workorder 移植 Django apps.production.aps.ScheduleOrder(排程工单/工单)。
package workorder

import (
	"time"

	"github.com/atm-erp/server/internal/platform/model"
)

// 工单状态机(对齐 Django ScheduleOrder.STATUS_CHOICES)。
const (
	StatusPending    = "PENDING"     // 待排程
	StatusScheduled  = "SCHEDULED"   // 已排程
	StatusInProgress = "IN_PROGRESS" // 生产中
	StatusCompleted  = "COMPLETED"   // 已完成
	StatusCancelled  = "CANCELLED"   // 已取消
)

// WorkOrder 排程工单,忠实映射 Django ScheduleOrder(Meta.db_table='mes_schedule_order')。
// 外键(project/sales_order/item/work_center)在本轮以可空 *uint64 列保留,
// 不跨模块 import;关联展开留待集成阶段补全。
type WorkOrder struct {
	model.Base
	OrderNo string `gorm:"column:order_no;size:50;uniqueIndex" json:"order_no"`

	// 来源 / 产品(外键 ID 直存,SET_NULL → 可空)。
	ProjectID    *uint64 `gorm:"column:project_id" json:"project_id,omitempty"`         // TODO(port): projects.Project
	SalesOrderID *uint64 `gorm:"column:sales_order_id" json:"sales_order_id,omitempty"` // TODO(port): sales.SalesOrder
	ItemID       *uint64 `gorm:"column:item_id" json:"item_id,omitempty"`               // TODO(port): masterdata.Item

	Quantity float64 `gorm:"column:quantity;type:decimal(18,4)" json:"quantity"`

	// 时间要求
	RequiredDate  time.Time  `gorm:"column:required_date;type:date" json:"required_date"`
	EarliestStart *time.Time `gorm:"column:earliest_start;type:date" json:"earliest_start,omitempty"`

	// 排程结果
	WorkCenterID *uint64    `gorm:"column:work_center_id" json:"work_center_id,omitempty"`
	PlannedStart *time.Time `gorm:"column:planned_start" json:"planned_start,omitempty"`
	PlannedEnd   *time.Time `gorm:"column:planned_end" json:"planned_end,omitempty"`
	PlannedHours *float64   `gorm:"column:planned_hours;type:decimal(10,2)" json:"planned_hours,omitempty"`

	// 实际
	ActualStart  *time.Time `gorm:"column:actual_start" json:"actual_start,omitempty"`
	ActualEnd    *time.Time `gorm:"column:actual_end" json:"actual_end,omitempty"`
	CompletedQty float64    `gorm:"column:completed_qty;type:decimal(18,4);default:0" json:"completed_qty"`

	Priority int    `gorm:"column:priority;default:3" json:"priority"` // 1最高..5最低
	Status   string `gorm:"column:status;size:20;default:PENDING" json:"status"`

	Remarks string `gorm:"column:remarks;type:text" json:"remarks"`
}

// TableName 对齐 Django Meta.db_table。
func (WorkOrder) TableName() string { return "mes_schedule_order" }
