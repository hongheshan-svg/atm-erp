package customer

import (
	"context"
	"errors"
	"fmt"
	"time"

	"gorm.io/gorm"
)

var (
	ErrNotFound      = errors.New("客户不存在")
	ErrCodeExists    = errors.New("客户编码已存在")
	ErrInvalidStatus = errors.New("无效的客户状态")
)

type Service struct{ repo *Repo }

func NewService(repo *Repo) *Service { return &Service{repo: repo} }

func validStatus(s string) bool {
	switch s {
	case StatusActive, StatusInactive, StatusPotential:
		return true
	}
	return false
}

func (s *Service) List(ctx context.Context, q ListQuery, offset, limit int) ([]Customer, int64, error) {
	return s.repo.List(ctx, q, offset, limit)
}

func (s *Service) Get(ctx context.Context, id uint64) (*Customer, error) {
	row, err := s.repo.Get(ctx, id)
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, ErrNotFound
	}
	return row, err
}

// generateCode 生成客户编码。
// TODO(verify): Django 走 apps.core.utils.generate_code('C', rule_type='CUSTOMER'),
// 由 CodeRule 模型动态配置前缀/序号格式;此处暂以 C+yyMM+6位流水 近似,待 CodeRule 移植后对齐。
func (s *Service) generateCode(ctx context.Context) (string, error) {
	prefix := "C" + time.Now().Format("0601")
	max, err := s.repo.MaxCodeLike(ctx, prefix)
	if err != nil {
		return "", err
	}
	seq := 1
	if len(max) == len(prefix)+6 {
		var cur int
		if _, e := fmt.Sscanf(max[len(prefix):], "%06d", &cur); e == nil {
			seq = cur + 1
		}
	}
	return fmt.Sprintf("%s%06d", prefix, seq), nil
}

func (s *Service) Create(ctx context.Context, in CreateInput) (*Customer, error) {
	if in.Status == "" {
		in.Status = StatusActive
	}
	if !validStatus(in.Status) {
		return nil, ErrInvalidStatus
	}
	code := in.Code
	if code == "" {
		c, err := s.generateCode(ctx)
		if err != nil {
			return nil, err
		}
		code = c
	}
	exists, err := s.repo.ExistsByCode(ctx, code)
	if err != nil {
		return nil, err
	}
	if exists {
		return nil, ErrCodeExists
	}
	row := &Customer{
		Code:           code,
		Name:           in.Name,
		ShortName:      in.ShortName,
		ContactPerson:  in.ContactPerson,
		Phone:          in.Phone,
		Email:          in.Email,
		Address:        in.Address,
		CreditLimit:    in.CreditLimit,
		PaymentTerms:   in.PaymentTerms,
		InvoiceTitle:   in.InvoiceTitle,
		TaxNumber:      in.TaxNumber,
		BankName:       in.BankName,
		BankAccount:    in.BankAccount,
		RegisteredAddr: in.RegisteredAddr,
		RegisteredTel:  in.RegisteredTel,
		Status:         in.Status,
		Notes:          in.Notes,
	}
	if err := s.repo.Create(ctx, row); err != nil {
		return nil, err
	}
	// TODO(port): Django 在 perform_create 中自动为新客户建立 CustomerCredit 信用档案
	// (初始额度取 credit_limit)。信用管理属另一限界上下文,本轮以占位标注,待 credit 模块落地后联动。
	return row, nil
}

func (s *Service) Update(ctx context.Context, id uint64, in UpdateInput) (*Customer, error) {
	row, err := s.Get(ctx, id)
	if err != nil {
		return nil, err
	}
	if in.Name != nil {
		row.Name = *in.Name
	}
	if in.ShortName != nil {
		row.ShortName = *in.ShortName
	}
	if in.ContactPerson != nil {
		row.ContactPerson = *in.ContactPerson
	}
	if in.Phone != nil {
		row.Phone = *in.Phone
	}
	if in.Email != nil {
		row.Email = *in.Email
	}
	if in.Address != nil {
		row.Address = *in.Address
	}
	if in.CreditLimit != nil {
		row.CreditLimit = *in.CreditLimit
	}
	if in.PaymentTerms != nil {
		row.PaymentTerms = *in.PaymentTerms
	}
	if in.InvoiceTitle != nil {
		row.InvoiceTitle = *in.InvoiceTitle
	}
	if in.TaxNumber != nil {
		row.TaxNumber = *in.TaxNumber
	}
	if in.BankName != nil {
		row.BankName = *in.BankName
	}
	if in.BankAccount != nil {
		row.BankAccount = *in.BankAccount
	}
	if in.RegisteredAddr != nil {
		row.RegisteredAddr = *in.RegisteredAddr
	}
	if in.RegisteredTel != nil {
		row.RegisteredTel = *in.RegisteredTel
	}
	if in.Status != nil {
		if !validStatus(*in.Status) {
			return nil, ErrInvalidStatus
		}
		row.Status = *in.Status
	}
	if in.Notes != nil {
		row.Notes = *in.Notes
	}
	if err := s.repo.Update(ctx, row); err != nil {
		return nil, err
	}
	return row, nil
}

// ChangeStatus 状态流转。
func (s *Service) ChangeStatus(ctx context.Context, id uint64, status string) (*Customer, error) {
	if !validStatus(status) {
		return nil, ErrInvalidStatus
	}
	row, err := s.Get(ctx, id)
	if err != nil {
		return nil, err
	}
	row.Status = status
	if err := s.repo.Update(ctx, row); err != nil {
		return nil, err
	}
	return row, nil
}

func (s *Service) Delete(ctx context.Context, id uint64) error {
	if _, err := s.Get(ctx, id); err != nil {
		return err
	}
	return s.repo.SoftDelete(ctx, id)
}
