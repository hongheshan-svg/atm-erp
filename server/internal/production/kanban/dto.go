package kanban

// CreateInput 新建 WIP 规则入参。
type CreateInput struct {
	ProcessName      string `json:"process_name" binding:"required"`
	WIPLimit         int    `json:"wip_limit" binding:"required"`
	WarningThreshold *int   `json:"warning_threshold"`
	IsActive         *bool  `json:"is_active"`
}

// UpdateInput 局部更新。
type UpdateInput struct {
	ProcessName      *string `json:"process_name"`
	WIPLimit         *int    `json:"wip_limit"`
	WarningThreshold *int    `json:"warning_threshold"`
	IsActive         *bool   `json:"is_active"`
}

// ListQuery 列表筛选。
type ListQuery struct {
	Keyword  string
	IsActive *bool
}
