package process

// CreateInput 新建工序入参。
type CreateInput struct {
	RoutingID          uint64  `json:"routing_id" binding:"required"`
	Sequence           int     `json:"sequence" binding:"required"`
	OperationCode      string  `json:"operation_code"`
	OperationName      string  `json:"operation_name" binding:"required"`
	OperationType      string  `json:"operation_type"`
	WorkStationID      *uint64 `json:"work_station_id"`
	WorkCenterID       *uint64 `json:"work_center_id"`
	SetupHours         float64 `json:"setup_hours"`
	StandardHours      float64 `json:"standard_hours"`
	CycleTime          float64 `json:"cycle_time"`
	OperatorsRequired  *int    `json:"operators_required"`
	SkillRequirements  string  `json:"skill_requirements"`
	EquipmentRequired  string  `json:"equipment_required"`
	ToolsRequired      string  `json:"tools_required"`
	InspectionRequired *bool   `json:"inspection_required"`
	WorkInstruction    string  `json:"work_instruction"`
	SafetyNotes        string  `json:"safety_notes"`
	IsOutsourced       *bool   `json:"is_outsourced"`
}

// UpdateInput 局部更新。
type UpdateInput struct {
	Sequence           *int     `json:"sequence"`
	OperationCode      *string  `json:"operation_code"`
	OperationName      *string  `json:"operation_name"`
	OperationType      *string  `json:"operation_type"`
	WorkStationID      *uint64  `json:"work_station_id"`
	WorkCenterID       *uint64  `json:"work_center_id"`
	SetupHours         *float64 `json:"setup_hours"`
	StandardHours      *float64 `json:"standard_hours"`
	CycleTime          *float64 `json:"cycle_time"`
	OperatorsRequired  *int     `json:"operators_required"`
	SkillRequirements  *string  `json:"skill_requirements"`
	EquipmentRequired  *string  `json:"equipment_required"`
	ToolsRequired      *string  `json:"tools_required"`
	InspectionRequired *bool    `json:"inspection_required"`
	WorkInstruction    *string  `json:"work_instruction"`
	SafetyNotes        *string  `json:"safety_notes"`
	IsOutsourced       *bool    `json:"is_outsourced"`
}

// ListQuery 列表筛选(对齐 Django filterset_fields=['routing','operation_type','work_station','is_outsourced'])。
type ListQuery struct {
	RoutingID     *uint64
	OperationType string
	WorkStationID *uint64
	IsOutsourced  *bool
}
