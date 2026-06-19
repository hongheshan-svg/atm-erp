// Package workflow 是审批工作流引擎的 Go 重写(对齐 Django apps.core.workflow)。
//
// 设计要点(见 docs/go-rewrite/20-module-designs.md「审批工作流引擎」):
//   - 四模型 1:1 保留:WorkflowDefinition/WorkflowStep/WorkflowInstance/WorkflowTask,
//     内嵌 model.Base(软删除 + created_by 钩子),TableName 对齐 Django Meta.db_table。
//   - 反转依赖:废弃 Django _on_workflow_complete 巨型 if/elif。引擎只持有
//     ApprovalCallback 接口 + CallbackRegistry(见 callback.go),各业务包在 wire 时
//     注册自己的 callback;引擎零业务 import。
//   - 选流:按 business_type 过滤 is_active,按 amount_threshold DESC 取首个
//     threshold<=amount(或 threshold IS NULL)者(见 service.go)。
//   - 状态机:task 仅 PENDING 可 approve/reject;审批/拒绝/撤回三入口统一经 service。
package workflow

import (
	"time"

	"github.com/atm-erp/server/internal/platform/model"
)

// ── 枚举常量(忠实迁移 Django choices)──────────────────────────────

// WorkflowInstance / WorkflowTask 状态。
const (
	InstanceStatusPending   = "PENDING"   // 审批中
	InstanceStatusApproved  = "APPROVED"  // 已通过
	InstanceStatusRejected  = "REJECTED"  // 已拒绝
	InstanceStatusCancelled = "CANCELLED" // 已取消
	InstanceStatusWithdrawn = "WITHDRAWN" // 已撤回

	TaskStatusPending  = "PENDING"  // 待处理
	TaskStatusApproved = "APPROVED" // 已通过
	TaskStatusRejected = "REJECTED" // 已拒绝
	TaskStatusSkipped  = "SKIPPED"  // 已跳过
	TaskStatusTimeout  = "TIMEOUT"  // 已超时
)

// WorkflowStep.approver_type。
const (
	ApproverTypeUser              = "USER"
	ApproverTypeRole              = "ROLE"
	ApproverTypeDepartmentManager = "DEPARTMENT_MANAGER"
	ApproverTypeProjectManager    = "PROJECT_MANAGER"
	ApproverTypeSuperior          = "SUPERIOR"
)

// WorkflowStep.action_type。
const (
	ActionTypeApprove     = "APPROVE"
	ActionTypeReview      = "REVIEW"
	ActionTypeCountersign = "COUNTERSIGN"
)

// 审批结果(传给 callback / _on_workflow_complete 等价物)。
const (
	ResultApproved  = "APPROVED"
	ResultRejected  = "REJECTED"
	ResultWithdrawn = "WITHDRAWN"
)

// ── 模型 ─────────────────────────────────────────────────────────

// WorkflowDefinition 审批流程定义(模板)。db_table=workflow_definition。
type WorkflowDefinition struct {
	model.Base
	Name         string `gorm:"column:name;size:100" json:"name"`
	Code         string `gorm:"column:code;size:50;uniqueIndex" json:"code"`
	BusinessType string `gorm:"column:business_type;size:30" json:"business_type"`
	Description  string `gorm:"column:description" json:"description"`
	IsActive     bool   `gorm:"column:is_active" json:"is_active"`
	// AmountThreshold 金额阈值:超过此金额时使用此流程(nullable)。
	AmountThreshold *float64 `gorm:"column:amount_threshold" json:"amount_threshold"`

	// Steps 关联步骤(列表/详情按需 Preload)。
	Steps []WorkflowStep `gorm:"foreignKey:WorkflowID" json:"steps,omitempty"`
}

// TableName 对齐 Django Meta.db_table。
func (WorkflowDefinition) TableName() string { return "workflow_definition" }

// WorkflowStep 审批步骤。db_table=workflow_step。
//
// 注意:cc_users / cc_roles 是 Django ManyToManyField(中间表
// workflow_step_cc_users / workflow_step_cc_roles),本轮先不映射多对多关系
// (留 TODO),五件套聚焦主表字段。
type WorkflowStep struct {
	model.Base
	WorkflowID   uint64 `gorm:"column:workflow_id" json:"workflow"`
	StepOrder    int    `gorm:"column:step_order" json:"step_order"`
	Name         string `gorm:"column:name;size:100" json:"name"`
	ApproverType string `gorm:"column:approver_type;size:30" json:"approver_type"`
	// ApproverUserID USER 类型审批人(nullable, on_delete=SET_NULL)。
	ApproverUserID *uint64 `gorm:"column:approver_user_id" json:"approver_user"`
	// ApproverRoleID ROLE 类型审批角色(nullable, on_delete=SET_NULL)。
	ApproverRoleID *uint64 `gorm:"column:approver_role_id" json:"approver_role"`
	ActionType     string  `gorm:"column:action_type;size:20" json:"action_type"`
	TimeoutHours   int     `gorm:"column:timeout_hours" json:"timeout_hours"`
	// SkipAmountThreshold 低于此金额时跳过此步骤(nullable)。
	SkipAmountThreshold *float64 `gorm:"column:skip_amount_threshold" json:"skip_amount_threshold"`
	CanReject           bool     `gorm:"column:can_reject" json:"can_reject"`

	// TODO(port): cc_users(workflow_step_cc_users)、cc_roles(workflow_step_cc_roles)
	// 多对多抄送关系本轮未映射;抄送派发依赖 notification 服务,留待接线。
}

// TableName 对齐 Django Meta.db_table。
func (WorkflowStep) TableName() string { return "workflow_step" }

// WorkflowInstance 审批实例(某业务对象的一次运行)。db_table=workflow_instance。
type WorkflowInstance struct {
	model.Base
	WorkflowID   uint64 `gorm:"column:workflow_id" json:"workflow"`
	BusinessType string `gorm:"column:business_type;size:30" json:"business_type"`
	BusinessID   int64  `gorm:"column:business_id" json:"business_id"`
	BusinessNo   string `gorm:"column:business_no;size:50" json:"business_no"`
	SubmitterID  uint64 `gorm:"column:submitter_id" json:"submitter"`
	// SubmitTime Django auto_now_add;Go 由应用层在创建时赋值。
	SubmitTime  time.Time `gorm:"column:submit_time" json:"submit_time"`
	Status      string    `gorm:"column:status;size:20" json:"status"`
	CurrentStep int       `gorm:"column:current_step" json:"current_step"`
	// Amount 金额(用于阈值判断,nullable)。
	Amount      *float64   `gorm:"column:amount" json:"amount"`
	CompletedAt *time.Time `gorm:"column:completed_at" json:"completed_at"`

	// Workflow / Tasks 关联(按需 Preload)。
	Workflow *WorkflowDefinition `gorm:"foreignKey:WorkflowID" json:"workflow_detail,omitempty"`
	Tasks    []WorkflowTask      `gorm:"foreignKey:InstanceID" json:"tasks,omitempty"`
}

// TableName 对齐 Django Meta.db_table。
func (WorkflowInstance) TableName() string { return "workflow_instance" }

// WorkflowTask 审批任务(每步的待办)。db_table=workflow_task。
type WorkflowTask struct {
	model.Base
	InstanceID uint64 `gorm:"column:instance_id" json:"instance"`
	StepID     uint64 `gorm:"column:step_id" json:"step"`
	AssigneeID uint64 `gorm:"column:assignee_id" json:"assignee"`
	Status     string `gorm:"column:status;size:20" json:"status"`
	// ActionTime 处理时间(nullable)。
	ActionTime *time.Time `gorm:"column:action_time" json:"action_time"`
	Comment    string     `gorm:"column:comment" json:"comment"`
	// Deadline 截止时间(nullable)。
	Deadline *time.Time `gorm:"column:deadline" json:"deadline"`

	// Instance / Step 关联(按需 Preload)。
	Instance *WorkflowInstance `gorm:"foreignKey:InstanceID" json:"-"`
	Step     *WorkflowStep     `gorm:"foreignKey:StepID" json:"step_detail,omitempty"`
}

// TableName 对齐 Django Meta.db_table。
func (WorkflowTask) TableName() string { return "workflow_task" }
