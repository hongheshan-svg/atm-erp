package workorder

import "time"

// CreateInput 新建工单入参。order_no 留空则由 service 生成(对齐 Django save() 自动编号)。
type CreateInput struct {
	OrderNo       string     `json:"order_no"`
	ProjectID     *uint64    `json:"project_id"`
	SalesOrderID  *uint64    `json:"sales_order_id"`
	ItemID        *uint64    `json:"item_id"`
	Quantity      float64    `json:"quantity" binding:"required"`
	RequiredDate  time.Time  `json:"required_date" binding:"required"`
	EarliestStart *time.Time `json:"earliest_start"`
	WorkCenterID  *uint64    `json:"work_center_id"`
	Priority      *int       `json:"priority"`
	Remarks       string     `json:"remarks"`
}

// UpdateInput 局部更新(指针区分“未传”与“置零值”)。
type UpdateInput struct {
	ProjectID     *uint64    `json:"project_id"`
	SalesOrderID  *uint64    `json:"sales_order_id"`
	ItemID        *uint64    `json:"item_id"`
	Quantity      *float64   `json:"quantity"`
	RequiredDate  *time.Time `json:"required_date"`
	EarliestStart *time.Time `json:"earliest_start"`
	WorkCenterID  *uint64    `json:"work_center_id"`
	PlannedStart  *time.Time `json:"planned_start"`
	PlannedEnd    *time.Time `json:"planned_end"`
	PlannedHours  *float64   `json:"planned_hours"`
	Priority      *int       `json:"priority"`
	Remarks       *string    `json:"remarks"`
}

// CompleteInput 完成生产入参(对齐 Django complete action)。
type CompleteInput struct {
	CompletedQty *float64 `json:"completed_qty"`
}

// ListQuery 列表筛选(对齐 Django filterset_fields=['status','priority','work_center','project']
// + search_fields=['order_no'])。
type ListQuery struct {
	Keyword      string
	Status       string
	Priority     *int
	WorkCenterID *uint64
	ProjectID    *uint64
}
