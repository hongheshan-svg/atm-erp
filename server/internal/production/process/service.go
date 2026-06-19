package process

import (
	"context"
	"errors"
	"fmt"

	"gorm.io/gorm"
)

var (
	ErrNotFound    = errors.New("工序不存在")
	ErrSeqConflict = errors.New("同一工艺路线下工序号已存在")
)

type Service struct{ repo *Repo }

func NewService(repo *Repo) *Service { return &Service{repo: repo} }

func (s *Service) List(ctx context.Context, q ListQuery, offset, limit int) ([]Process, int64, error) {
	return s.repo.List(ctx, q, offset, limit)
}

func (s *Service) Get(ctx context.Context, id uint64) (*Process, error) {
	p, err := s.repo.Get(ctx, id)
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, ErrNotFound
	}
	return p, err
}

func (s *Service) Create(ctx context.Context, in CreateInput) (*Process, error) {
	if exists, err := s.repo.ExistsSequence(ctx, in.RoutingID, in.Sequence, 0); err != nil {
		return nil, err
	} else if exists {
		return nil, fmt.Errorf("%w:%d", ErrSeqConflict, in.Sequence)
	}
	p := &Process{
		RoutingID:         in.RoutingID,
		Sequence:          in.Sequence,
		OperationCode:     in.OperationCode,
		OperationName:     in.OperationName,
		OperationType:     in.OperationType,
		WorkStationID:     in.WorkStationID,
		WorkCenterID:      in.WorkCenterID,
		SetupHours:        in.SetupHours,
		StandardHours:     in.StandardHours,
		CycleTime:         in.CycleTime,
		SkillRequirements: in.SkillRequirements,
		EquipmentRequired: in.EquipmentRequired,
		ToolsRequired:     in.ToolsRequired,
		WorkInstruction:   in.WorkInstruction,
		SafetyNotes:       in.SafetyNotes,
		BatchSize:         1,
		OperatorsRequired: 1,
	}
	if in.OperationType == "" {
		p.OperationType = TypeOther
	}
	if in.OperatorsRequired != nil {
		p.OperatorsRequired = *in.OperatorsRequired
	}
	if in.InspectionRequired != nil {
		p.InspectionRequired = *in.InspectionRequired
	}
	if in.IsOutsourced != nil {
		p.IsOutsourced = *in.IsOutsourced
	}
	if err := s.repo.Create(ctx, p); err != nil {
		return nil, err
	}
	// 工时合计联动(对齐 Django perform_create)。
	_ = s.repo.RecalcRoutingTotals(ctx, p.RoutingID)
	return p, nil
}

func (s *Service) Update(ctx context.Context, id uint64, in UpdateInput) (*Process, error) {
	p, err := s.Get(ctx, id)
	if err != nil {
		return nil, err
	}
	if in.Sequence != nil && *in.Sequence != p.Sequence {
		if exists, err := s.repo.ExistsSequence(ctx, p.RoutingID, *in.Sequence, p.ID); err != nil {
			return nil, err
		} else if exists {
			return nil, fmt.Errorf("%w:%d", ErrSeqConflict, *in.Sequence)
		}
		p.Sequence = *in.Sequence
	}
	if in.OperationCode != nil {
		p.OperationCode = *in.OperationCode
	}
	if in.OperationName != nil {
		p.OperationName = *in.OperationName
	}
	if in.OperationType != nil {
		p.OperationType = *in.OperationType
	}
	if in.WorkStationID != nil {
		p.WorkStationID = in.WorkStationID
	}
	if in.WorkCenterID != nil {
		p.WorkCenterID = in.WorkCenterID
	}
	if in.SetupHours != nil {
		p.SetupHours = *in.SetupHours
	}
	if in.StandardHours != nil {
		p.StandardHours = *in.StandardHours
	}
	if in.CycleTime != nil {
		p.CycleTime = *in.CycleTime
	}
	if in.OperatorsRequired != nil {
		p.OperatorsRequired = *in.OperatorsRequired
	}
	if in.SkillRequirements != nil {
		p.SkillRequirements = *in.SkillRequirements
	}
	if in.EquipmentRequired != nil {
		p.EquipmentRequired = *in.EquipmentRequired
	}
	if in.ToolsRequired != nil {
		p.ToolsRequired = *in.ToolsRequired
	}
	if in.InspectionRequired != nil {
		p.InspectionRequired = *in.InspectionRequired
	}
	if in.WorkInstruction != nil {
		p.WorkInstruction = *in.WorkInstruction
	}
	if in.SafetyNotes != nil {
		p.SafetyNotes = *in.SafetyNotes
	}
	if in.IsOutsourced != nil {
		p.IsOutsourced = *in.IsOutsourced
	}
	if err := s.repo.Update(ctx, p); err != nil {
		return nil, err
	}
	_ = s.repo.RecalcRoutingTotals(ctx, p.RoutingID)
	return p, nil
}

func (s *Service) Delete(ctx context.Context, id uint64) error {
	p, err := s.Get(ctx, id)
	if err != nil {
		return err
	}
	if err := s.repo.SoftDelete(ctx, id); err != nil {
		return err
	}
	_ = s.repo.RecalcRoutingTotals(ctx, p.RoutingID)
	return nil
}
