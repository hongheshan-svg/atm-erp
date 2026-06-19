package workflow

import (
	"context"
	"errors"

	"gorm.io/gorm"
)

// 本文件承载流程定义/步骤的 CRUD 与实例/任务的只读查询(配置类 + 待办聚合),
// 与 service.go 的引擎状态机分离。

// ── Definition CRUD ──────────────────────────────────────────────

func (s *Service) ListDefinitions(ctx context.Context, q DefinitionListQuery, offset, limit int) ([]WorkflowDefinition, int64, error) {
	return s.defs.List(ctx, q, offset, limit)
}

func (s *Service) GetDefinition(ctx context.Context, id uint64) (*WorkflowDefinition, error) {
	d, err := s.defs.Get(ctx, id)
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, ErrDefinitionNotFound
	}
	return d, err
}

func (s *Service) CreateDefinition(ctx context.Context, in DefinitionCreateInput) (*WorkflowDefinition, error) {
	d := &WorkflowDefinition{
		Name:            in.Name,
		Code:            in.Code,
		BusinessType:    in.BusinessType,
		Description:     in.Description,
		IsActive:        true,
		AmountThreshold: in.AmountThreshold,
	}
	if in.IsActive != nil {
		d.IsActive = *in.IsActive
	}
	if err := s.defs.Create(ctx, d); err != nil {
		return nil, err
	}
	return d, nil
}

func (s *Service) UpdateDefinition(ctx context.Context, id uint64, in DefinitionUpdateInput) (*WorkflowDefinition, error) {
	d, err := s.GetDefinition(ctx, id)
	if err != nil {
		return nil, err
	}
	if in.Name != nil {
		d.Name = *in.Name
	}
	if in.Code != nil {
		d.Code = *in.Code
	}
	if in.BusinessType != nil {
		d.BusinessType = *in.BusinessType
	}
	if in.Description != nil {
		d.Description = *in.Description
	}
	if in.IsActive != nil {
		d.IsActive = *in.IsActive
	}
	if in.AmountThreshold != nil {
		d.AmountThreshold = in.AmountThreshold
	}
	if err := s.defs.Update(ctx, d); err != nil {
		return nil, err
	}
	return d, nil
}

func (s *Service) DeleteDefinition(ctx context.Context, id uint64) error {
	if _, err := s.GetDefinition(ctx, id); err != nil {
		return err
	}
	return s.defs.SoftDelete(ctx, id)
}

// ── Step CRUD ────────────────────────────────────────────────────

func (s *Service) ListSteps(ctx context.Context, q StepListQuery, offset, limit int) ([]WorkflowStep, int64, error) {
	return s.steps.List(ctx, q, offset, limit)
}

func (s *Service) GetStep(ctx context.Context, id uint64) (*WorkflowStep, error) {
	st, err := s.steps.Get(ctx, id)
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, ErrStepNotFound
	}
	return st, err
}

func (s *Service) CreateStep(ctx context.Context, in StepCreateInput) (*WorkflowStep, error) {
	st := &WorkflowStep{
		WorkflowID:          in.WorkflowID,
		StepOrder:           in.StepOrder,
		Name:                in.Name,
		ApproverType:        in.ApproverType,
		ApproverUserID:      in.ApproverUserID,
		ApproverRoleID:      in.ApproverRoleID,
		ActionType:          in.ActionType,
		TimeoutHours:        24,
		SkipAmountThreshold: in.SkipAmountThreshold,
		CanReject:           true,
	}
	if st.ApproverType == "" {
		st.ApproverType = ApproverTypeUser
	}
	if st.ActionType == "" {
		st.ActionType = ActionTypeApprove
	}
	if in.TimeoutHours != nil {
		st.TimeoutHours = *in.TimeoutHours
	}
	if in.CanReject != nil {
		st.CanReject = *in.CanReject
	}
	if err := s.steps.Create(ctx, st); err != nil {
		return nil, err
	}
	return st, nil
}

func (s *Service) UpdateStep(ctx context.Context, id uint64, in StepUpdateInput) (*WorkflowStep, error) {
	st, err := s.GetStep(ctx, id)
	if err != nil {
		return nil, err
	}
	if in.StepOrder != nil {
		st.StepOrder = *in.StepOrder
	}
	if in.Name != nil {
		st.Name = *in.Name
	}
	if in.ApproverType != nil {
		st.ApproverType = *in.ApproverType
	}
	if in.ApproverUserID != nil {
		st.ApproverUserID = in.ApproverUserID
	}
	if in.ApproverRoleID != nil {
		st.ApproverRoleID = in.ApproverRoleID
	}
	if in.ActionType != nil {
		st.ActionType = *in.ActionType
	}
	if in.TimeoutHours != nil {
		st.TimeoutHours = *in.TimeoutHours
	}
	if in.SkipAmountThreshold != nil {
		st.SkipAmountThreshold = in.SkipAmountThreshold
	}
	if in.CanReject != nil {
		st.CanReject = *in.CanReject
	}
	if err := s.steps.Update(ctx, st); err != nil {
		return nil, err
	}
	return st, nil
}

func (s *Service) DeleteStep(ctx context.Context, id uint64) error {
	if _, err := s.GetStep(ctx, id); err != nil {
		return err
	}
	return s.steps.SoftDelete(ctx, id)
}

// ReorderSteps 交换两步骤顺序,对齐 WorkflowStepViewSet.reorder。
//
// 在单事务内用「临时序号 = 该流程最大序号+1」规避 unique(workflow, step_order)冲突。
func (s *Service) ReorderSteps(ctx context.Context, stepID, targetID uint64) error {
	return s.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		txCtx := withTx(ctx, tx)
		step, err := s.getStepTx(txCtx, tx, stepID)
		if err != nil {
			return err
		}
		target, err := s.getStepTx(txCtx, tx, targetID)
		if err != nil {
			return err
		}
		if step.WorkflowID != target.WorkflowID {
			return errors.New("只能在同一工作流内调整顺序")
		}
		max, err := s.steps.MaxStepOrder(txCtx, step.WorkflowID)
		if err != nil {
			return err
		}
		tempOrder := max + 1
		stepOrder, targetOrder := step.StepOrder, target.StepOrder

		step.StepOrder = tempOrder
		if err := tx.WithContext(txCtx).Save(step).Error; err != nil {
			return err
		}
		target.StepOrder = stepOrder
		if err := tx.WithContext(txCtx).Save(target).Error; err != nil {
			return err
		}
		step.StepOrder = targetOrder
		return tx.WithContext(txCtx).Save(step).Error
	})
}

// ── Instance 只读 ────────────────────────────────────────────────

func (s *Service) ListInstances(ctx context.Context, q InstanceListQuery, offset, limit int) ([]WorkflowInstance, int64, error) {
	return s.instances.List(ctx, q, offset, limit)
}

func (s *Service) GetInstance(ctx context.Context, id uint64) (*WorkflowInstance, error) {
	inst, err := s.instances.Get(ctx, id)
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, ErrInstanceNotFound
	}
	return inst, err
}

func (s *Service) MySubmitted(ctx context.Context) ([]WorkflowInstance, error) {
	return s.instances.SubmittedBy(ctx, currentUserID(ctx))
}

func (s *Service) History(ctx context.Context, businessType string, businessID int64) ([]WorkflowInstance, error) {
	return s.instances.HistoryByBusiness(ctx, businessType, businessID)
}

func (s *Service) DeleteInstance(ctx context.Context, id uint64) error {
	if _, err := s.GetInstance(ctx, id); err != nil {
		return err
	}
	return s.instances.SoftDelete(ctx, id)
}

// ── Task 只读 ────────────────────────────────────────────────────

func (s *Service) ListTasks(ctx context.Context, q TaskListQuery, offset, limit int) ([]WorkflowTask, int64, error) {
	return s.tasks.List(ctx, q, offset, limit)
}

func (s *Service) GetTask(ctx context.Context, id uint64) (*WorkflowTask, error) {
	t, err := s.tasks.Get(ctx, id)
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, ErrTaskNotFound
	}
	return t, err
}

func (s *Service) MyPending(ctx context.Context) ([]WorkflowTask, error) {
	return s.tasks.PendingByAssignee(ctx, currentUserID(ctx))
}

func (s *Service) PendingCount(ctx context.Context) (int64, error) {
	return s.tasks.CountPendingByAssignee(ctx, currentUserID(ctx))
}
