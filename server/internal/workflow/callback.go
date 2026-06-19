package workflow

import (
	"context"
	"fmt"
	"sync"
)

// ApprovalCallback 是业务域向引擎注册的审批结果回调,取代 Django
// WorkflowService._on_workflow_complete 的巨型 if/elif 反向 import。
//
// 引擎完成审批/拒绝/撤回后,按 instance.BusinessType 查表分发到对应 callback,
// 由业务包自行更新业务对象状态(如 SALES_ORDER 置 CONFIRMED、PR 通过联动
// 生成 ProjectBOM 等)。引擎零业务 import,依赖方向倒置为「业务→引擎」。
//
// 实现约定:回调内的业务事务与引擎审批事务的边界本轮按「事务后同步调用」处理
// (见 service.go transition);若需强一致同事务,后续可改造为传入 *gorm.DB。
type ApprovalCallback interface {
	OnApproved(ctx context.Context, instance *WorkflowInstance) error
	OnRejected(ctx context.Context, instance *WorkflowInstance) error
	OnWithdrawn(ctx context.Context, instance *WorkflowInstance) error
}

// CallbackRegistry 按 business_type 持有 ApprovalCallback。并发安全。
type CallbackRegistry struct {
	mu sync.RWMutex
	m  map[string]ApprovalCallback
}

// NewCallbackRegistry 创建空注册表。
func NewCallbackRegistry() *CallbackRegistry {
	return &CallbackRegistry{m: make(map[string]ApprovalCallback)}
}

// Register 注册某业务类型的回调(业务包在 wire 阶段调用)。重复注册以最后一次为准。
func (r *CallbackRegistry) Register(businessType string, cb ApprovalCallback) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.m[businessType] = cb
}

// Get 取某业务类型的回调。
func (r *CallbackRegistry) Get(businessType string) (ApprovalCallback, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	cb, ok := r.m[businessType]
	return cb, ok
}

// dispatch 在审批完成后分发结果到业务 callback。
//
// 对齐设计文档风险条目:某 business_type 未注册 callback 时不能静默失败——
// 这里返回 error 由调用方记录/告警(不阻断审批本身,因实例状态已落库)。
func (r *CallbackRegistry) dispatch(ctx context.Context, instance *WorkflowInstance, result string) error {
	cb, ok := r.Get(instance.BusinessType)
	if !ok {
		// TODO(verify): 接 audit/notify 后改为写审计 + 告警;当前返回 error 供上层 log。
		return fmt.Errorf("workflow: business_type %q 未注册 ApprovalCallback,业务状态未联动更新", instance.BusinessType)
	}
	switch result {
	case ResultApproved:
		return cb.OnApproved(ctx, instance)
	case ResultRejected:
		return cb.OnRejected(ctx, instance)
	case ResultWithdrawn:
		return cb.OnWithdrawn(ctx, instance)
	default:
		return fmt.Errorf("workflow: 未知审批结果 %q", result)
	}
}

// AssigneeResolver 解析步骤审批人,取代 Django _get_step_assignee 的跨模块反查。
//
// USER 类型由引擎直接用 step.ApproverUserID;ROLE/DEPARTMENT_MANAGER/SUPERIOR
// 走 IAM;PROJECT_MANAGER 需业务上下文,由业务侧通过实现该接口提供
// (而非引擎反查业务表)。本轮提供一个默认空实现,真实接线时注入。
//
// 返回 (0, nil) 表示未解析到审批人,引擎据 _create_next_task 语义跳过/兜底。
type AssigneeResolver interface {
	// Resolve 返回该步骤在此实例下的审批人用户 ID(单人审批 APPROVE/REVIEW)。
	Resolve(ctx context.Context, step *WorkflowStep, instance *WorkflowInstance) (uint64, error)
	// ResolveAll 返回会签(COUNTERSIGN)步骤的全部审批人(每人一条 task,全 APPROVED 才推进)。
	ResolveAll(ctx context.Context, step *WorkflowStep, instance *WorkflowInstance) ([]uint64, error)
}

// defaultResolver 兜底解析器:仅处理 USER 类型(读 step.ApproverUserID)。
//
// TODO(port): ROLE/DEPARTMENT_MANAGER/PROJECT_MANAGER/SUPERIOR 需注入真实
// IAM/业务上下文解析器替换本实现;Django 末位兜底到 superuser 的越权风险见设计文档,
// 迁移时再决定是否保留(见 docs 待定问题)。
type defaultResolver struct{}

func (defaultResolver) Resolve(_ context.Context, step *WorkflowStep, _ *WorkflowInstance) (uint64, error) {
	if step.ApproverType == ApproverTypeUser && step.ApproverUserID != nil {
		return *step.ApproverUserID, nil
	}
	// 非 USER 类型本轮无法解析:返回 0,引擎按「无审批人」处理。
	return 0, nil
}

// ResolveAll 默认仅支持 USER 单人(会签需注入能返回多人的 resolver,如按角色取全部用户)。
func (r defaultResolver) ResolveAll(ctx context.Context, step *WorkflowStep, inst *WorkflowInstance) ([]uint64, error) {
	id, err := r.Resolve(ctx, step, inst)
	if err != nil || id == 0 {
		return nil, err
	}
	return []uint64{id}, nil
}
