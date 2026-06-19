package workcenter

// CreateInput 新建工作中心入参。
type CreateInput struct {
	Code           string   `json:"code" binding:"required"`
	Name           string   `json:"name" binding:"required"`
	CapacityPerDay *float64 `json:"capacity_per_day"`
	Efficiency     *float64 `json:"efficiency"`
	ManagerID      *uint64  `json:"manager_id"`
	IsActive       *bool    `json:"is_active"`
	Description    string   `json:"description"`
}

// UpdateInput 局部更新。
type UpdateInput struct {
	Name           *string  `json:"name"`
	CapacityPerDay *float64 `json:"capacity_per_day"`
	Efficiency     *float64 `json:"efficiency"`
	ManagerID      *uint64  `json:"manager_id"`
	IsActive       *bool    `json:"is_active"`
	Description    *string  `json:"description"`
}

// ListQuery 列表筛选(对齐 Django filterset_fields=['is_active'])。
type ListQuery struct {
	Keyword  string
	IsActive *bool
}
