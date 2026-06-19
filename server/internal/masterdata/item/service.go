package item

import (
	"context"
	"errors"

	"gorm.io/gorm"
)

var ErrNotFound = errors.New("物料不存在")

type Service struct{ repo *Repo }

func NewService(repo *Repo) *Service { return &Service{repo: repo} }

func (s *Service) List(ctx context.Context, q ListQuery, offset, limit int) ([]Item, int64, error) {
	return s.repo.List(ctx, q, offset, limit)
}

func (s *Service) Get(ctx context.Context, id uint64) (*Item, error) {
	it, err := s.repo.Get(ctx, id)
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, ErrNotFound
	}
	return it, err
}

func (s *Service) Create(ctx context.Context, in CreateInput) (*Item, error) {
	it := &Item{
		Code:     in.Code,
		Name:     in.Name,
		Spec:     in.Spec,
		Unit:     in.Unit,
		Category: in.Category,
		Price:    in.Price,
	}
	if err := s.repo.Create(ctx, it); err != nil {
		return nil, err
	}
	return it, nil
}

func (s *Service) Update(ctx context.Context, id uint64, in UpdateInput) (*Item, error) {
	it, err := s.Get(ctx, id)
	if err != nil {
		return nil, err
	}
	if in.Name != nil {
		it.Name = *in.Name
	}
	if in.Spec != nil {
		it.Spec = *in.Spec
	}
	if in.Unit != nil {
		it.Unit = *in.Unit
	}
	if in.Category != nil {
		it.Category = *in.Category
	}
	if in.Price != nil {
		it.Price = *in.Price
	}
	if err := s.repo.Update(ctx, it); err != nil {
		return nil, err
	}
	return it, nil
}

func (s *Service) Delete(ctx context.Context, id uint64) error {
	if _, err := s.Get(ctx, id); err != nil {
		return err
	}
	return s.repo.SoftDelete(ctx, id)
}
