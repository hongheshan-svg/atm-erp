package kanban

import (
	"context"
	"errors"
	"fmt"

	"gorm.io/gorm"
)

var (
	ErrNotFound  = errors.New("WIP 规则不存在")
	ErrDuplicate = errors.New("该工序的 WIP 规则已存在")
)

type Service struct{ repo *Repo }

func NewService(repo *Repo) *Service { return &Service{repo: repo} }

func (s *Service) List(ctx context.Context, q ListQuery, offset, limit int) ([]KanbanWIPRule, int64, error) {
	return s.repo.List(ctx, q, offset, limit)
}

func (s *Service) Get(ctx context.Context, id uint64) (*KanbanWIPRule, error) {
	k, err := s.repo.Get(ctx, id)
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, ErrNotFound
	}
	return k, err
}

func (s *Service) Create(ctx context.Context, in CreateInput) (*KanbanWIPRule, error) {
	if exists, err := s.repo.ExistsProcessName(ctx, in.ProcessName, 0); err != nil {
		return nil, err
	} else if exists {
		return nil, fmt.Errorf("%w:%s", ErrDuplicate, in.ProcessName)
	}
	k := &KanbanWIPRule{
		ProcessName:      in.ProcessName,
		WIPLimit:         in.WIPLimit,
		WarningThreshold: 80,
		IsActive:         true,
	}
	if in.WarningThreshold != nil {
		k.WarningThreshold = *in.WarningThreshold
	}
	if in.IsActive != nil {
		k.IsActive = *in.IsActive
	}
	if err := s.repo.Create(ctx, k); err != nil {
		return nil, err
	}
	return k, nil
}

func (s *Service) Update(ctx context.Context, id uint64, in UpdateInput) (*KanbanWIPRule, error) {
	k, err := s.Get(ctx, id)
	if err != nil {
		return nil, err
	}
	if in.ProcessName != nil && *in.ProcessName != k.ProcessName {
		if exists, err := s.repo.ExistsProcessName(ctx, *in.ProcessName, k.ID); err != nil {
			return nil, err
		} else if exists {
			return nil, fmt.Errorf("%w:%s", ErrDuplicate, *in.ProcessName)
		}
		k.ProcessName = *in.ProcessName
	}
	if in.WIPLimit != nil {
		k.WIPLimit = *in.WIPLimit
	}
	if in.WarningThreshold != nil {
		k.WarningThreshold = *in.WarningThreshold
	}
	if in.IsActive != nil {
		k.IsActive = *in.IsActive
	}
	if err := s.repo.Update(ctx, k); err != nil {
		return nil, err
	}
	return k, nil
}

func (s *Service) Delete(ctx context.Context, id uint64) error {
	if _, err := s.Get(ctx, id); err != nil {
		return err
	}
	return s.repo.SoftDelete(ctx, id)
}
