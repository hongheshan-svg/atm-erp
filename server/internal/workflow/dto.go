package workflow

// ── WorkflowDefinition DTO ───────────────────────────────────────

// DefinitionCreateInput 新建流程定义入参。
type DefinitionCreateInput struct {
	Name            string   `json:"name" binding:"required"`
	Code            string   `json:"code" binding:"required"`
	BusinessType    string   `json:"business_type" binding:"required"`
	Description     string   `json:"description"`
	IsActive        *bool    `json:"is_active"`
	AmountThreshold *float64 `json:"amount_threshold"`
}

// DefinitionUpdateInput 局部更新流程定义(指针区分未传/置零)。
type DefinitionUpdateInput struct {
	Name            *string  `json:"name"`
	Code            *string  `json:"code"`
	BusinessType    *string  `json:"business_type"`
	Description     *string  `json:"description"`
	IsActive        *bool    `json:"is_active"`
	AmountThreshold *float64 `json:"amount_threshold"`
}

// DefinitionListQuery 流程定义列表筛选(对齐 filterset_fields/search_fields)。
type DefinitionListQuery struct {
	BusinessType string
	IsActive     *bool
	Keyword      string // name / code 模糊
}

// ── WorkflowStep DTO ─────────────────────────────────────────────

// StepCreateInput 新建审批步骤入参。
type StepCreateInput struct {
	WorkflowID          uint64   `json:"workflow" binding:"required"`
	StepOrder           int      `json:"step_order" binding:"required"`
	Name                string   `json:"name" binding:"required"`
	ApproverType        string   `json:"approver_type"`
	ApproverUserID      *uint64  `json:"approver_user"`
	ApproverRoleID      *uint64  `json:"approver_role"`
	ActionType          string   `json:"action_type"`
	TimeoutHours        *int     `json:"timeout_hours"`
	SkipAmountThreshold *float64 `json:"skip_amount_threshold"`
	CanReject           *bool    `json:"can_reject"`
}

// StepUpdateInput 局部更新审批步骤。
type StepUpdateInput struct {
	StepOrder           *int     `json:"step_order"`
	Name                *string  `json:"name"`
	ApproverType        *string  `json:"approver_type"`
	ApproverUserID      *uint64  `json:"approver_user"`
	ApproverRoleID      *uint64  `json:"approver_role"`
	ActionType          *string  `json:"action_type"`
	TimeoutHours        *int     `json:"timeout_hours"`
	SkipAmountThreshold *float64 `json:"skip_amount_threshold"`
	CanReject           *bool    `json:"can_reject"`
}

// StepListQuery 步骤列表筛选(对齐 filterset_fields=[workflow, approver_type])。
type StepListQuery struct {
	WorkflowID   *uint64
	ApproverType string
}

// ReorderInput 交换两步骤顺序(对齐 WorkflowStepViewSet.reorder)。
type ReorderInput struct {
	StepID   uint64 `json:"step_id" binding:"required"`
	TargetID uint64 `json:"target_id" binding:"required"`
}

// ── WorkflowInstance DTO ─────────────────────────────────────────

// InstanceListQuery 实例列表筛选(对齐 filterset_fields/search_fields)。
type InstanceListQuery struct {
	BusinessType string
	Status       string
	SubmitterID  *uint64
	Keyword      string // business_no 模糊
}

// StartInput 启动审批实例入参(对齐 WorkflowService.start_workflow)。
type StartInput struct {
	BusinessType string   `json:"business_type" binding:"required"`
	BusinessID   int64    `json:"business_id" binding:"required"`
	BusinessNo   string   `json:"business_no"`
	Amount       *float64 `json:"amount"`
}

// WithdrawInput 撤回入参(可选携带说明)。
type WithdrawInput struct {
	Comment string `json:"comment"`
}

// ── WorkflowTask DTO ─────────────────────────────────────────────

// TaskListQuery 任务列表筛选(对齐 filterset_fields=[instance, assignee, status])。
type TaskListQuery struct {
	InstanceID *uint64
	AssigneeID *uint64
	Status     string
}

// TaskActionInput 审批/拒绝入参(对齐 approve/reject 的 comment)。
type TaskActionInput struct {
	Comment string `json:"comment"`
}
