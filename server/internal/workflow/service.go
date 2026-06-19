package workflow

import (
	"context"
	"errors"
	"time"

	"github.com/atm-erp/server/internal/iam"
	"github.com/atm-erp/server/internal/platform/model"
	"gorm.io/gorm"
)

// 领域错误。
var (
	ErrDefinitionNotFound = errors.New("审批流程定义不存在")
	ErrStepNotFound       = errors.New("审批步骤不存在")
	ErrInstanceNotFound   = errors.New("审批实例不存在")
	ErrTaskNotFound       = errors.New("审批任务不存在")

	ErrNoWorkflow       = errors.New("未找到适用的审批流程")
	ErrAlreadyActive    = errors.New("该单据已有进行中的审批流程")
	ErrTaskHandled      = errors.New("该任务已处理")
	ErrNoPermission     = errors.New("您没有权限处理此任务")
	ErrNotPending       = errors.New("只能撤回进行中的审批")
	ErrNotSubmitter     = errors.New("只有提交人可以撤回")
	ErrRejectNeedReason = errors.New("拒绝时必须填写原因")
)

// Service 是工作流引擎核心。零业务 import:业务联动经 CallbackRegistry 分发。
type Service struct {
	db        *gorm.DB
	defs      *DefinitionRepo
	steps     *StepRepo
	instances *InstanceRepo
	tasks     *TaskRepo
	registry  *CallbackRegistry
	resolver  AssigneeResolver
}

// NewService 装配引擎。registry/resolver 允许为 nil(用默认空实现)。
func NewService(db *gorm.DB, registry *CallbackRegistry, resolver AssigneeResolver) *Service {
	if registry == nil {
		registry = NewCallbackRegistry()
	}
	if resolver == nil {
		resolver = defaultResolver{}
	}
	return &Service{
		db:        db,
		defs:      NewDefinitionRepo(db),
		steps:     NewStepRepo(db),
		instances: NewInstanceRepo(db),
		tasks:     NewTaskRepo(db),
		registry:  registry,
		resolver:  resolver,
	}
}

// Registry 暴露注册表给业务包在 wire 阶段 Register callback。
func (s *Service) Registry() *CallbackRegistry { return s.registry }

func currentUserID(ctx context.Context) uint64 {
	if u, ok := iam.AuthUserFrom(ctx); ok {
		return u.ID
	}
	return 0
}

func isSuperuser(ctx context.Context) bool {
	if u, ok := iam.AuthUserFrom(ctx); ok {
		return u.IsSuperuser
	}
	return false
}

// ── 选流 / 启流 ──────────────────────────────────────────────────

// StartResult 启流结果。AutoApproved=true 表示无启用流程,调用方据此置已批准终态
// (对齐 Django start_workflow_or_auto_approve 兜底)。
type StartResult struct {
	Instance     *WorkflowInstance
	AutoApproved bool
}

// Start 为业务对象启动审批实例,对齐 WorkflowService.start_workflow。
//
// 与 Django 不同:找不到流程时不报错,返回 AutoApproved=true 兜底(设计文档要求)。
func (s *Service) Start(ctx context.Context, in StartInput) (*StartResult, error) {
	def, err := s.defs.SelectForBusiness(ctx, in.BusinessType, in.Amount)
	if err != nil {
		return nil, err
	}
	if def == nil {
		// 无启用流程:自动批准兜底。
		return &StartResult{AutoApproved: true}, nil
	}

	var created *WorkflowInstance
	err = s.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		txCtx := withTx(ctx, tx)

		// 去重:已有 PENDING 实例则拒绝(Django select_for_update)。
		existing, ferr := s.findActiveTx(txCtx, in.BusinessType, in.BusinessID)
		if ferr != nil {
			return ferr
		}
		if existing != nil {
			return ErrAlreadyActive
		}

		submitter := currentUserID(ctx)
		inst := &WorkflowInstance{
			WorkflowID:   def.ID,
			BusinessType: in.BusinessType,
			BusinessID:   in.BusinessID,
			BusinessNo:   in.BusinessNo,
			SubmitterID:  submitter,
			SubmitTime:   time.Now(),
			Status:       InstanceStatusPending,
			CurrentStep:  1,
			Amount:       in.Amount,
		}
		if err := tx.WithContext(txCtx).Create(inst).Error; err != nil {
			return err
		}

		// 创建第一个任务(可能直接走完所有步骤而 APPROVED)。
		if err := s.createNextTask(txCtx, tx, inst); err != nil {
			return err
		}
		created = inst
		return nil
	})
	if err != nil {
		return nil, err
	}

	// 若启流过程中已直接完成(全部步骤被跳过),事务后分发 callback。
	if created != nil && created.Status == InstanceStatusApproved {
		_ = s.registry.dispatch(ctx, created, ResultApproved)
	}
	return &StartResult{Instance: created}, nil
}

// createNextTask 复刻 WorkflowService._create_next_task(同事务内)。
//
// 选取 step_order >= current_step 的首个未跳过步骤;按金额跳步;无审批人时
// 跳过并前进(带步数上限防死循环);无更多步骤则置 APPROVED + completed_at。
func (s *Service) createNextTask(ctx context.Context, tx *gorm.DB, inst *WorkflowInstance) error {
	steps, err := s.stepsByWorkflowTx(ctx, tx, inst.WorkflowID)
	if err != nil {
		return err
	}

	var current *WorkflowStep
	for i := range steps {
		st := &steps[i]
		if st.StepOrder >= inst.CurrentStep {
			// 按金额跳步(skip_amount_threshold)。
			if st.SkipAmountThreshold != nil && inst.Amount != nil {
				if *inst.Amount < *st.SkipAmountThreshold {
					continue
				}
			}
			current = st
			break
		}
	}

	if current == nil {
		// 无更多步骤:流程通过。
		return s.completeTx(ctx, tx, inst, InstanceStatusApproved)
	}

	assignee, err := s.resolver.Resolve(ctx, current, inst)
	if err != nil {
		return err
	}
	if assignee == 0 {
		// 无审批人:跳过本步并前进(对齐 Django,带步数上限防死循环)。
		inst.CurrentStep = current.StepOrder + 1
		if err := tx.WithContext(ctx).Save(inst).Error; err != nil {
			return err
		}
		if inst.CurrentStep > len(steps) {
			return s.completeTx(ctx, tx, inst, InstanceStatusApproved)
		}
		return s.createNextTask(ctx, tx, inst)
	}

	timeoutHours := current.TimeoutHours
	if timeoutHours <= 0 {
		timeoutHours = 24
	}
	deadline := time.Now().Add(time.Duration(timeoutHours) * time.Hour)

	// TODO(verify): COUNTERSIGN 会签——Django 声明未实现。按设计文档应在
	// action_type=COUNTERSIGN 时一步生成多 task(多审批人全 APPROVED 才进下一步)。
	// 当前 resolver 仅返回单审批人,会签留待 resolver 扩展为多人后补齐。
	task := &WorkflowTask{
		InstanceID: inst.ID,
		StepID:     current.ID,
		AssigneeID: assignee,
		Status:     TaskStatusPending,
		Deadline:   &deadline,
	}
	if err := tx.WithContext(ctx).Create(task).Error; err != nil {
		return err
	}
	// TODO(port): _notify_assignee —— 站内信 + 钉钉/企微,依赖 notification 服务。
	return nil
}

// completeTx 在事务内置实例终态(同步 completed_at)。callback 分发在事务后由调用方触发。
func (s *Service) completeTx(ctx context.Context, tx *gorm.DB, inst *WorkflowInstance, status string) error {
	now := time.Now()
	inst.Status = status
	inst.CompletedAt = &now
	return tx.WithContext(ctx).Save(inst).Error
}

// ── 审批 / 拒绝 / 撤回 ────────────────────────────────────────────

// ApproveTask 审批通过,对齐 WorkflowService.approve_task。
//
// skipAssigneeCheck=true 时跳过 assignee 校验(供业务 ViewSet 自带权限检查时用)。
func (s *Service) ApproveTask(ctx context.Context, taskID uint64, comment string, skipAssigneeCheck bool) error {
	return s.transition(ctx, taskID, comment, skipAssigneeCheck, false)
}

// RejectTask 审批拒绝,对齐 WorkflowService.reject_task。
func (s *Service) RejectTask(ctx context.Context, taskID uint64, comment string, skipAssigneeCheck bool) error {
	if comment == "" {
		return ErrRejectNeedReason
	}
	return s.transition(ctx, taskID, comment, skipAssigneeCheck, true)
}

// transition 统一审批/拒绝入口。reject=true 拒绝整个流程,否则进下一步。
func (s *Service) transition(ctx context.Context, taskID uint64, comment string, skipAssigneeCheck, reject bool) error {
	uid := currentUserID(ctx)
	var (
		completedInst  *WorkflowInstance
		completeResult string
	)

	err := s.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		txCtx := withTx(ctx, tx)

		task, err := s.getTaskTx(txCtx, tx, taskID)
		if err != nil {
			return err
		}
		if task.Status != TaskStatusPending {
			return ErrTaskHandled
		}
		// Guard:assignee 越权校验(Casbin 不覆盖,手写)。superuser 放行。
		if !skipAssigneeCheck && task.AssigneeID != uid && !isSuperuser(ctx) {
			return ErrNoPermission
		}

		now := time.Now()
		task.ActionTime = &now
		task.Comment = comment

		inst, err := s.getInstanceTx(txCtx, tx, task.InstanceID)
		if err != nil {
			return err
		}

		if reject {
			task.Status = TaskStatusRejected
			if err := tx.WithContext(txCtx).Save(task).Error; err != nil {
				return err
			}
			if err := s.completeTx(txCtx, tx, inst, InstanceStatusRejected); err != nil {
				return err
			}
			completedInst, completeResult = inst, ResultRejected
			return nil
		}

		// 通过:进下一步。
		task.Status = TaskStatusApproved
		if err := tx.WithContext(txCtx).Save(task).Error; err != nil {
			return err
		}
		// 取该任务所属步骤的 step_order 以推进 current_step。
		step, err := s.getStepTx(txCtx, tx, task.StepID)
		if err != nil {
			return err
		}
		inst.CurrentStep = step.StepOrder + 1
		if err := tx.WithContext(txCtx).Save(inst).Error; err != nil {
			return err
		}
		if err := s.createNextTask(txCtx, tx, inst); err != nil {
			return err
		}
		if inst.Status == InstanceStatusApproved {
			completedInst, completeResult = inst, ResultApproved
		}
		return nil
	})
	if err != nil {
		return err
	}

	// 事务提交后分发业务 callback(松耦合,避免长事务/跨域死锁,见设计文档待定)。
	if completedInst != nil {
		_ = s.registry.dispatch(ctx, completedInst, completeResult)
		// TODO(port): _notify_submitter —— 依赖 notification 服务。
	}
	return nil
}

// Withdraw 撤回实例(提交人或超管),对齐 WorkflowService.withdraw_workflow。
func (s *Service) Withdraw(ctx context.Context, instanceID uint64) error {
	uid := currentUserID(ctx)
	var withdrawn *WorkflowInstance

	err := s.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		txCtx := withTx(ctx, tx)
		inst, err := s.getInstanceTx(txCtx, tx, instanceID)
		if err != nil {
			return err
		}
		if inst.Status != InstanceStatusPending {
			return ErrNotPending
		}
		if inst.SubmitterID != uid && !isSuperuser(ctx) {
			return ErrNotSubmitter
		}
		now := time.Now()
		if err := s.tasks.CancelPendingByInstance(txCtx, tx, inst.ID, now); err != nil {
			return err
		}
		if err := s.completeTx(txCtx, tx, inst, InstanceStatusWithdrawn); err != nil {
			return err
		}
		withdrawn = inst
		return nil
	})
	if err != nil {
		return err
	}
	if withdrawn != nil {
		_ = s.registry.dispatch(ctx, withdrawn, ResultWithdrawn)
	}
	return nil
}

// ── tx 内的轻量读取(套 BeforeCreate/Update 操作人钩子需 model.WithUserID)──

type txCtxKey struct{}

func withTx(ctx context.Context, tx *gorm.DB) context.Context {
	// 注入操作人到 ctx,使 GORM 钩子写 created_by/updated_by。
	if u, ok := iam.AuthUserFrom(ctx); ok {
		ctx = model.WithUserID(ctx, u.ID)
	}
	return context.WithValue(ctx, txCtxKey{}, tx)
}

func (s *Service) findActiveTx(ctx context.Context, businessType string, businessID int64) (*WorkflowInstance, error) {
	tx := ctx.Value(txCtxKey{}).(*gorm.DB)
	var inst WorkflowInstance
	err := tx.WithContext(ctx).
		Where("business_type = ? AND business_id = ? AND status = ?", businessType, businessID, InstanceStatusPending).
		First(&inst).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &inst, nil
}

func (s *Service) stepsByWorkflowTx(ctx context.Context, tx *gorm.DB, workflowID uint64) ([]WorkflowStep, error) {
	var steps []WorkflowStep
	err := tx.WithContext(ctx).Where("workflow_id = ?", workflowID).Order("step_order").Find(&steps).Error
	return steps, err
}

func (s *Service) getTaskTx(ctx context.Context, tx *gorm.DB, id uint64) (*WorkflowTask, error) {
	var t WorkflowTask
	if err := tx.WithContext(ctx).Where("id = ?", id).First(&t).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil, ErrTaskNotFound
		}
		return nil, err
	}
	return &t, nil
}

func (s *Service) getInstanceTx(ctx context.Context, tx *gorm.DB, id uint64) (*WorkflowInstance, error) {
	var inst WorkflowInstance
	if err := tx.WithContext(ctx).Where("id = ?", id).First(&inst).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil, ErrInstanceNotFound
		}
		return nil, err
	}
	return &inst, nil
}

func (s *Service) getStepTx(ctx context.Context, tx *gorm.DB, id uint64) (*WorkflowStep, error) {
	var st WorkflowStep
	if err := tx.WithContext(ctx).Where("id = ?", id).First(&st).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil, ErrStepNotFound
		}
		return nil, err
	}
	return &st, nil
}
