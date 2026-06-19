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
		Sku:           in.Sku,
		Name:          in.Name,
		Specification: in.Specification,
		Brand:         in.Brand,
		Model:         in.Model,
		CategoryID:    in.CategoryID,
		Unit:          in.Unit,
		StandardCost:  in.StandardCost,
		PurchasePrice: in.PurchasePrice,
		SalePrice:     in.SalePrice,
		IsActive:      true,
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
	if in.Specification != nil {
		it.Specification = *in.Specification
	}
	if in.Brand != nil {
		it.Brand = *in.Brand
	}
	if in.Model != nil {
		it.Model = *in.Model
	}
	if in.CategoryID != nil {
		it.CategoryID = in.CategoryID
	}
	if in.Unit != nil {
		it.Unit = *in.Unit
	}
	if in.StandardCost != nil {
		it.StandardCost = *in.StandardCost
	}
	if in.PurchasePrice != nil {
		it.PurchasePrice = *in.PurchasePrice
	}
	if in.SalePrice != nil {
		it.SalePrice = *in.SalePrice
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
