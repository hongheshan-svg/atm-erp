package warehouse

import (
	"context"
	"errors"

	"gorm.io/gorm"
)

var (
	ErrNotFound     = errors.New("仓库不存在")
	ErrCodeExists   = errors.New("仓库编码已存在")
	ErrInvalidType  = errors.New("无效的仓库类型")
	ErrCodeRequired = errors.New("仓库编码不能为空")
)

type Service struct{ repo *Repo }

func NewService(repo *Repo) *Service { return &Service{repo: repo} }

func (s *Service) List(ctx context.Context, q ListQuery, offset, limit int) ([]Warehouse, int64, error) {
	return s.repo.List(ctx, q, offset, limit)
}

func (s *Service) Get(ctx context.Context, id uint64) (*Warehouse, error) {
	row, err := s.repo.Get(ctx, id)
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, ErrNotFound
	}
	return row, err
}

func (s *Service) Create(ctx context.Context, in CreateInput) (*Warehouse, error) {
	if in.Code == "" {
		return nil, ErrCodeRequired
	}
	wtype := in.WarehouseType
	if wtype == "" {
		wtype = "MAIN"
	}
	if !warehouseTypes[wtype] {
		return nil, ErrInvalidType
	}
	exists, err := s.repo.ExistsByCode(ctx, in.Code)
	if err != nil {
		return nil, err
	}
	if exists {
		return nil, ErrCodeExists
	}
	isActive := true
	if in.IsActive != nil {
		isActive = *in.IsActive
	}
	row := &Warehouse{
		Code:          in.Code,
		Name:          in.Name,
		WarehouseType: wtype,
		Address:       in.Address,
		ManagerID:     in.ManagerID,
		ContactPhone:  in.ContactPhone,
		IsActive:      isActive,
		Notes:         in.Notes,
	}
	if err := s.repo.Create(ctx, row); err != nil {
		return nil, err
	}
	return row, nil
}

func (s *Service) Update(ctx context.Context, id uint64, in UpdateInput) (*Warehouse, error) {
	row, err := s.Get(ctx, id)
	if err != nil {
		return nil, err
	}
	if in.Name != nil {
		row.Name = *in.Name
	}
	if in.WarehouseType != nil {
		if !warehouseTypes[*in.WarehouseType] {
			return nil, ErrInvalidType
		}
		row.WarehouseType = *in.WarehouseType
	}
	if in.Address != nil {
		row.Address = *in.Address
	}
	if in.ManagerID != nil {
		row.ManagerID = in.ManagerID
	}
	if in.ContactPhone != nil {
		row.ContactPhone = *in.ContactPhone
	}
	if in.IsActive != nil {
		row.IsActive = *in.IsActive
	}
	if in.Notes != nil {
		row.Notes = *in.Notes
	}
	if err := s.repo.Update(ctx, row); err != nil {
		return nil, err
	}
	return row, nil
}

func (s *Service) Delete(ctx context.Context, id uint64) error {
	if _, err := s.Get(ctx, id); err != nil {
		return err
	}
	// TODO(port): Django 仓库删除前应校验是否存在关联库存/库位(inventory 模块),本轮以软删除直接处理。
	return s.repo.SoftDelete(ctx, id)
}
