package workcenter

import (
	"context"
	"errors"
	"fmt"

	"gorm.io/gorm"
)

var (
	ErrNotFound   = errors.New("工作中心不存在")
	ErrCodeExists = errors.New("工作中心编码已存在")
)

type Service struct{ repo *Repo }

func NewService(repo *Repo) *Service { return &Service{repo: repo} }

func (s *Service) List(ctx context.Context, q ListQuery, offset, limit int) ([]WorkCenter, int64, error) {
	return s.repo.List(ctx, q, offset, limit)
}

func (s *Service) Get(ctx context.Context, id uint64) (*WorkCenter, error) {
	wc, err := s.repo.Get(ctx, id)
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, ErrNotFound
	}
	return wc, err
}

func (s *Service) Create(ctx context.Context, in CreateInput) (*WorkCenter, error) {
	if exists, err := s.repo.ExistsCode(ctx, in.Code); err != nil {
		return nil, err
	} else if exists {
		return nil, fmt.Errorf("%w:%s", ErrCodeExists, in.Code)
	}
	wc := &WorkCenter{
		Code:           in.Code,
		Name:           in.Name,
		CapacityPerDay: 8,
		Efficiency:     100,
		ManagerID:      in.ManagerID,
		IsActive:       true,
		Description:    in.Description,
	}
	if in.CapacityPerDay != nil {
		wc.CapacityPerDay = *in.CapacityPerDay
	}
	if in.Efficiency != nil {
		wc.Efficiency = *in.Efficiency
	}
	if in.IsActive != nil {
		wc.IsActive = *in.IsActive
	}
	if err := s.repo.Create(ctx, wc); err != nil {
		return nil, err
	}
	return wc, nil
}

func (s *Service) Update(ctx context.Context, id uint64, in UpdateInput) (*WorkCenter, error) {
	wc, err := s.Get(ctx, id)
	if err != nil {
		return nil, err
	}
	if in.Name != nil {
		wc.Name = *in.Name
	}
	if in.CapacityPerDay != nil {
		wc.CapacityPerDay = *in.CapacityPerDay
	}
	if in.Efficiency != nil {
		wc.Efficiency = *in.Efficiency
	}
	if in.ManagerID != nil {
		wc.ManagerID = in.ManagerID
	}
	if in.IsActive != nil {
		wc.IsActive = *in.IsActive
	}
	if in.Description != nil {
		wc.Description = *in.Description
	}
	if err := s.repo.Update(ctx, wc); err != nil {
		return nil, err
	}
	return wc, nil
}

func (s *Service) Delete(ctx context.Context, id uint64) error {
	if _, err := s.Get(ctx, id); err != nil {
		return err
	}
	return s.repo.SoftDelete(ctx, id)
}
