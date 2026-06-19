package workflow

import (
	"context"

	"github.com/atm-erp/server/internal/iam"
	"gorm.io/gorm"
)

// scopeModule 标识工作流资源所属权限/数据范围模块。
//
// 注意:Django 端 WorkflowInstance/Task 的 ViewSet permission_module='system'
// 且 allow_authenticated_read=True(已登录即可读)。这里数据范围以 created_by
// 兜底过滤;实例待办的 assignee 越权在 service 层手写校验(见 service.go)。
const scopeModule = "workflow"

// ── DefinitionRepo ───────────────────────────────────────────────

type DefinitionRepo struct{ db *gorm.DB }

func NewDefinitionRepo(db *gorm.DB) *DefinitionRepo { return &DefinitionRepo{db: db} }

func (r *DefinitionRepo) scoped(ctx context.Context) *gorm.DB {
	q := r.db.WithContext(ctx).Model(&WorkflowDefinition{})
	if u, ok := iam.AuthUserFrom(ctx); ok {
		q = iam.ApplyScope(q, u, scopeModule, "created_by")
	}
	return q
}

func (r *DefinitionRepo) List(ctx context.Context, q DefinitionListQuery, offset, limit int) ([]WorkflowDefinition, int64, error) {
	tx := r.scoped(ctx)
	if q.BusinessType != "" {
		tx = tx.Where("business_type = ?", q.BusinessType)
	}
	if q.IsActive != nil {
		tx = tx.Where("is_active = ?", *q.IsActive)
	}
	if q.Keyword != "" {
		kw := "%" + q.Keyword + "%"
		tx = tx.Where("name LIKE ? OR code LIKE ?", kw, kw)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var items []WorkflowDefinition
	if err := tx.Order("business_type, amount_threshold").Offset(offset).Limit(limit).Find(&items).Error; err != nil {
		return nil, 0, err
	}
	return items, total, nil
}

func (r *DefinitionRepo) Get(ctx context.Context, id uint64) (*WorkflowDefinition, error) {
	var d WorkflowDefinition
	if err := r.scoped(ctx).Preload("Steps", func(db *gorm.DB) *gorm.DB {
		return db.Order("step_order")
	}).Where("id = ?", id).First(&d).Error; err != nil {
		return nil, err
	}
	return &d, nil
}

func (r *DefinitionRepo) Create(ctx context.Context, d *WorkflowDefinition) error {
	return r.db.WithContext(ctx).Create(d).Error
}

func (r *DefinitionRepo) Update(ctx context.Context, d *WorkflowDefinition) error {
	return r.db.WithContext(ctx).Save(d).Error
}

func (r *DefinitionRepo) SoftDelete(ctx context.Context, id uint64) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&WorkflowDefinition{}).Error
}

// SelectForBusiness 选流:business_type 过滤 is_active,按 amount_threshold DESC
// 取首个 threshold<=amount(或 threshold IS NULL)者。对齐
// WorkflowService.get_workflow_for_business。不套数据范围(系统级选流)。
func (r *DefinitionRepo) SelectForBusiness(ctx context.Context, businessType string, amount *float64) (*WorkflowDefinition, error) {
	var defs []WorkflowDefinition
	if err := r.db.WithContext(ctx).
		Where("business_type = ? AND is_active = ?", businessType, true).
		Order("amount_threshold DESC").
		Find(&defs).Error; err != nil {
		return nil, err
	}
	if len(defs) == 0 {
		return nil, nil
	}
	if amount != nil {
		for i := range defs {
			d := &defs[i]
			if d.AmountThreshold == nil || *amount >= *d.AmountThreshold {
				return d, nil
			}
		}
	}
	// 无金额或无匹配阈值:返回第一个(order by amount_threshold DESC)。
	return &defs[0], nil
}

// ── StepRepo ─────────────────────────────────────────────────────

type StepRepo struct{ db *gorm.DB }

func NewStepRepo(db *gorm.DB) *StepRepo { return &StepRepo{db: db} }

func (r *StepRepo) scoped(ctx context.Context) *gorm.DB {
	q := r.db.WithContext(ctx).Model(&WorkflowStep{})
	if u, ok := iam.AuthUserFrom(ctx); ok {
		q = iam.ApplyScope(q, u, scopeModule, "created_by")
	}
	return q
}

func (r *StepRepo) List(ctx context.Context, q StepListQuery, offset, limit int) ([]WorkflowStep, int64, error) {
	tx := r.scoped(ctx)
	if q.WorkflowID != nil {
		tx = tx.Where("workflow_id = ?", *q.WorkflowID)
	}
	if q.ApproverType != "" {
		tx = tx.Where("approver_type = ?", q.ApproverType)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var items []WorkflowStep
	if err := tx.Order("workflow_id, step_order").Offset(offset).Limit(limit).Find(&items).Error; err != nil {
		return nil, 0, err
	}
	return items, total, nil
}

// ListByWorkflow 取某流程的全部步骤(按 step_order 升序),供引擎选步。
func (r *StepRepo) ListByWorkflow(ctx context.Context, workflowID uint64) ([]WorkflowStep, error) {
	var steps []WorkflowStep
	if err := r.db.WithContext(ctx).
		Where("workflow_id = ?", workflowID).
		Order("step_order").
		Find(&steps).Error; err != nil {
		return nil, err
	}
	return steps, nil
}

func (r *StepRepo) Get(ctx context.Context, id uint64) (*WorkflowStep, error) {
	var s WorkflowStep
	if err := r.scoped(ctx).Where("id = ?", id).First(&s).Error; err != nil {
		return nil, err
	}
	return &s, nil
}

func (r *StepRepo) Create(ctx context.Context, s *WorkflowStep) error {
	return r.db.WithContext(ctx).Create(s).Error
}

func (r *StepRepo) Update(ctx context.Context, s *WorkflowStep) error {
	return r.db.WithContext(ctx).Save(s).Error
}

func (r *StepRepo) SoftDelete(ctx context.Context, id uint64) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&WorkflowStep{}).Error
}

// MaxStepOrder 返回某流程现有最大 step_order(含软删除,对齐 reorder 用 all_objects)。
func (r *StepRepo) MaxStepOrder(ctx context.Context, workflowID uint64) (int, error) {
	var max *int
	// Unscoped 绕过软删除全局过滤,等价 Django all_objects。
	err := r.db.WithContext(ctx).Unscoped().Model(&WorkflowStep{}).
		Where("workflow_id = ?", workflowID).
		Select("MAX(step_order)").Scan(&max).Error
	if err != nil {
		return 0, err
	}
	if max == nil {
		return 0, nil
	}
	return *max, nil
}

// ── InstanceRepo ─────────────────────────────────────────────────

type InstanceRepo struct{ db *gorm.DB }

func NewInstanceRepo(db *gorm.DB) *InstanceRepo { return &InstanceRepo{db: db} }

func (r *InstanceRepo) scoped(ctx context.Context) *gorm.DB {
	// allow_authenticated_read:实例对已登录用户可读,这里不强制 created_by 过滤
	// (Django ViewSet 也未按 owner 限制读)。保留 model 过滤软删除。
	return r.db.WithContext(ctx).Model(&WorkflowInstance{})
}

func (r *InstanceRepo) List(ctx context.Context, q InstanceListQuery, offset, limit int) ([]WorkflowInstance, int64, error) {
	tx := r.scoped(ctx)
	if q.BusinessType != "" {
		tx = tx.Where("business_type = ?", q.BusinessType)
	}
	if q.Status != "" {
		tx = tx.Where("status = ?", q.Status)
	}
	if q.SubmitterID != nil {
		tx = tx.Where("submitter_id = ?", *q.SubmitterID)
	}
	if q.Keyword != "" {
		tx = tx.Where("business_no LIKE ?", "%"+q.Keyword+"%")
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var items []WorkflowInstance
	if err := tx.Order("submit_time DESC").Offset(offset).Limit(limit).Find(&items).Error; err != nil {
		return nil, 0, err
	}
	return items, total, nil
}

func (r *InstanceRepo) Get(ctx context.Context, id uint64) (*WorkflowInstance, error) {
	var inst WorkflowInstance
	if err := r.scoped(ctx).
		Preload("Workflow").
		Preload("Tasks", func(db *gorm.DB) *gorm.DB { return db.Order("step_id") }).
		Where("id = ?", id).First(&inst).Error; err != nil {
		return nil, err
	}
	return &inst, nil
}

func (r *InstanceRepo) Create(ctx context.Context, inst *WorkflowInstance) error {
	return r.db.WithContext(ctx).Create(inst).Error
}

func (r *InstanceRepo) Update(ctx context.Context, inst *WorkflowInstance) error {
	return r.db.WithContext(ctx).Save(inst).Error
}

func (r *InstanceRepo) SoftDelete(ctx context.Context, id uint64) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&WorkflowInstance{}).Error
}

// FindActiveByBusiness 查某业务对象的进行中(PENDING)实例,对齐 start_workflow
// 的 select_for_update 去重检查。
func (r *InstanceRepo) FindActiveByBusiness(ctx context.Context, businessType string, businessID int64) (*WorkflowInstance, error) {
	var inst WorkflowInstance
	err := r.db.WithContext(ctx).
		Where("business_type = ? AND business_id = ? AND status = ?", businessType, businessID, InstanceStatusPending).
		First(&inst).Error
	if err != nil {
		return nil, err
	}
	return &inst, nil
}

// HistoryByBusiness 取某业务对象的全部实例(对齐 get_workflow_history)。
func (r *InstanceRepo) HistoryByBusiness(ctx context.Context, businessType string, businessID int64) ([]WorkflowInstance, error) {
	var items []WorkflowInstance
	err := r.db.WithContext(ctx).
		Preload("Workflow").
		Preload("Tasks", func(db *gorm.DB) *gorm.DB { return db.Order("step_id") }).
		Where("business_type = ? AND business_id = ?", businessType, businessID).
		Order("submit_time DESC").
		Find(&items).Error
	return items, err
}

// SubmittedBy 取某用户提交的全部实例(对齐 get_submitted_workflows)。
func (r *InstanceRepo) SubmittedBy(ctx context.Context, userID uint64) ([]WorkflowInstance, error) {
	var items []WorkflowInstance
	err := r.db.WithContext(ctx).
		Preload("Workflow").
		Where("submitter_id = ?", userID).
		Order("submit_time DESC").
		Find(&items).Error
	return items, err
}

// ── TaskRepo ─────────────────────────────────────────────────────

type TaskRepo struct{ db *gorm.DB }

func NewTaskRepo(db *gorm.DB) *TaskRepo { return &TaskRepo{db: db} }

func (r *TaskRepo) scoped(ctx context.Context) *gorm.DB {
	return r.db.WithContext(ctx).Model(&WorkflowTask{})
}

func (r *TaskRepo) List(ctx context.Context, q TaskListQuery, offset, limit int) ([]WorkflowTask, int64, error) {
	tx := r.scoped(ctx)
	if q.InstanceID != nil {
		tx = tx.Where("instance_id = ?", *q.InstanceID)
	}
	if q.AssigneeID != nil {
		tx = tx.Where("assignee_id = ?", *q.AssigneeID)
	}
	if q.Status != "" {
		tx = tx.Where("status = ?", q.Status)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var items []WorkflowTask
	if err := tx.Order("instance_id, step_id").Offset(offset).Limit(limit).Find(&items).Error; err != nil {
		return nil, 0, err
	}
	return items, total, nil
}

func (r *TaskRepo) Get(ctx context.Context, id uint64) (*WorkflowTask, error) {
	var t WorkflowTask
	if err := r.scoped(ctx).
		Preload("Step").
		Preload("Instance").
		Where("id = ?", id).First(&t).Error; err != nil {
		return nil, err
	}
	return &t, nil
}

func (r *TaskRepo) Create(ctx context.Context, t *WorkflowTask) error {
	return r.db.WithContext(ctx).Create(t).Error
}

func (r *TaskRepo) Update(ctx context.Context, t *WorkflowTask) error {
	return r.db.WithContext(ctx).Save(t).Error
}

func (r *TaskRepo) SoftDelete(ctx context.Context, id uint64) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&WorkflowTask{}).Error
}

// PendingByAssignee 取某用户的全部待处理任务(对齐 get_pending_tasks)。
func (r *TaskRepo) PendingByAssignee(ctx context.Context, userID uint64) ([]WorkflowTask, error) {
	var items []WorkflowTask
	err := r.db.WithContext(ctx).
		Preload("Step").
		Preload("Instance").
		Preload("Instance.Workflow").
		Where("assignee_id = ? AND status = ?", userID, TaskStatusPending).
		Order("created_at DESC").
		Find(&items).Error
	return items, err
}

// CountPendingByAssignee 待办计数(对齐 pending_count)。
func (r *TaskRepo) CountPendingByAssignee(ctx context.Context, userID uint64) (int64, error) {
	var n int64
	err := r.db.WithContext(ctx).Model(&WorkflowTask{}).
		Where("assignee_id = ? AND status = ?", userID, TaskStatusPending).
		Count(&n).Error
	return n, err
}

// CancelPendingByInstance 撤回时把实例下所有 PENDING 任务置 SKIPPED
// (对齐 withdraw_workflow)。
func (r *TaskRepo) CancelPendingByInstance(ctx context.Context, tx *gorm.DB, instanceID uint64, actionTime any) error {
	return tx.WithContext(ctx).Model(&WorkflowTask{}).
		Where("instance_id = ? AND status = ?", instanceID, TaskStatusPending).
		Updates(map[string]any{"status": TaskStatusSkipped, "action_time": actionTime}).Error
}
