package routing

import (
	"context"
	"errors"
	"fmt"

	"gorm.io/gorm"
)

var (
	ErrNotFound      = errors.New("工艺路线不存在")
	ErrCodeExists    = errors.New("工艺编码已存在")
	ErrBadTransition = errors.New("只能审批草稿状态的工艺")
)

type Service struct{ repo *Repo }

func NewService(repo *Repo) *Service { return &Service{repo: repo} }

func (s *Service) List(ctx context.Context, q ListQuery, offset, limit int) ([]Routing, int64, error) {
	return s.repo.List(ctx, q, offset, limit)
}

func (s *Service) Get(ctx context.Context, id uint64) (*Routing, error) {
	rt, err := s.repo.Get(ctx, id)
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, ErrNotFound
	}
	return rt, err
}

func (s *Service) Create(ctx context.Context, in CreateInput) (*Routing, error) {
	if exists, err := s.repo.ExistsCode(ctx, in.Code); err != nil {
		return nil, err
	} else if exists {
		return nil, fmt.Errorf("%w:%s", ErrCodeExists, in.Code)
	}
	rt := &Routing{
		Code:              in.Code,
		Name:              in.Name,
		ProductCategoryID: in.ProductCategoryID,
		ItemID:            in.ItemID,
		Version:           in.Version,
		Description:       in.Description,
		IsCurrent:         true,
		IsActive:          true,
		Status:            StatusDraft,
	}
	if rt.Version == "" {
		rt.Version = "1.0"
	}
	if err := s.repo.Create(ctx, rt); err != nil {
		return nil, err
	}
	return rt, nil
}

func (s *Service) Update(ctx context.Context, id uint64, in UpdateInput) (*Routing, error) {
	rt, err := s.Get(ctx, id)
	if err != nil {
		return nil, err
	}
	if in.Name != nil {
		rt.Name = *in.Name
	}
	if in.ProductCategoryID != nil {
		rt.ProductCategoryID = in.ProductCategoryID
	}
	if in.ItemID != nil {
		rt.ItemID = in.ItemID
	}
	if in.Version != nil {
		rt.Version = *in.Version
	}
	if in.IsCurrent != nil {
		rt.IsCurrent = *in.IsCurrent
	}
	if in.Description != nil {
		rt.Description = *in.Description
	}
	if in.IsActive != nil {
		rt.IsActive = *in.IsActive
	}
	if err := s.repo.Update(ctx, rt); err != nil {
		return nil, err
	}
	return rt, nil
}

func (s *Service) Delete(ctx context.Context, id uint64) error {
	if _, err := s.Get(ctx, id); err != nil {
		return err
	}
	return s.repo.SoftDelete(ctx, id)
}

// Approve 审批工艺路线:仅 DRAFT→APPROVED,并重算工时合计
// (忠实迁移 Django RoutingTemplateViewSet.approve)。
func (s *Service) Approve(ctx context.Context, id uint64) (*Routing, error) {
	rt, err := s.Get(ctx, id)
	if err != nil {
		return nil, err
	}
	if rt.Status != StatusDraft {
		return nil, ErrBadTransition
	}
	rt.Status = StatusApproved
	if err := s.repo.Update(ctx, rt); err != nil {
		return nil, err
	}
	return s.recalcTotals(ctx, rt)
}

// recalcTotals 汇总工序工时回写到路线(对齐 Django calculate_totals)。
func (s *Service) recalcTotals(ctx context.Context, rt *Routing) (*Routing, error) {
	std, setup, err := s.repo.SumOperationHours(ctx, rt.ID)
	if err != nil {
		return nil, err
	}
	rt.TotalStandardHours = std
	rt.TotalSetupHours = setup
	if err := s.repo.Update(ctx, rt); err != nil {
		return nil, err
	}
	return rt, nil
}

// RecalcTotals 暴露给工序变更后联动调用(对齐 Django RoutingOperationViewSet.perform_create/update)。
func (s *Service) RecalcTotals(ctx context.Context, id uint64) (*Routing, error) {
	rt, err := s.Get(ctx, id)
	if err != nil {
		return nil, err
	}
	return s.recalcTotals(ctx, rt)
}
