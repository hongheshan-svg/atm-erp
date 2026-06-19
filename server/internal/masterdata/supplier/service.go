package supplier

import (
	"context"
	"errors"
	"fmt"
	"time"

	"gorm.io/gorm"
)

var (
	ErrNotFound          = errors.New("供应商不存在")
	ErrCodeExists        = errors.New("供应商编码已存在")
	ErrInvalidStatus     = errors.New("无效的供应商状态")
	ErrInvalidSettlement = errors.New("无效的结款方式")
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

func (s *Service) List(ctx context.Context, q ListQuery, offset, limit int) ([]Supplier, int64, error) {
	return s.repo.List(ctx, q, offset, limit)
}

func (s *Service) Get(ctx context.Context, id uint64) (*Supplier, error) {
	row, err := s.repo.Get(ctx, id)
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, ErrNotFound
	}
	return row, err
}

// generateCode 生成供应商编码。
// TODO(verify): Django 走 generate_code('S', rule_type='SUPPLIER'),由 CodeRule 配置;
// 此处暂以 S+yyMM+6位流水 近似,待 CodeRule 移植后对齐。
func (s *Service) generateCode(ctx context.Context) (string, error) {
	prefix := "S" + time.Now().Format("0601")
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

func (s *Service) Create(ctx context.Context, in CreateInput) (*Supplier, error) {
	if in.Status == "" {
		in.Status = StatusActive
	}
	if !validStatus(in.Status) {
		return nil, ErrInvalidStatus
	}
	if in.SettlementMethod != "" && !settlementMethods[in.SettlementMethod] {
		return nil, ErrInvalidSettlement
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
	row := &Supplier{
		Code:             code,
		Name:             in.Name,
		ShortName:        in.ShortName,
		ContactPerson:    in.ContactPerson,
		Phone:            in.Phone,
		Email:            in.Email,
		Address:          in.Address,
		PaymentTerms:     in.PaymentTerms,
		SettlementMethod: in.SettlementMethod,
		InvoiceTitle:     in.InvoiceTitle,
		TaxNumber:        in.TaxNumber,
		BankName:         in.BankName,
		BankAccount:      in.BankAccount,
		RegisteredAddr:   in.RegisteredAddr,
		RegisteredTel:    in.RegisteredTel,
		Status:           in.Status,
		Notes:            in.Notes,
	}
	if err := s.repo.Create(ctx, row); err != nil {
		return nil, err
	}
	return row, nil
}

func (s *Service) Update(ctx context.Context, id uint64, in UpdateInput) (*Supplier, error) {
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
	if in.PaymentTerms != nil {
		row.PaymentTerms = *in.PaymentTerms
	}
	if in.SettlementMethod != nil {
		if *in.SettlementMethod != "" && !settlementMethods[*in.SettlementMethod] {
			return nil, ErrInvalidSettlement
		}
		row.SettlementMethod = *in.SettlementMethod
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

func (s *Service) ChangeStatus(ctx context.Context, id uint64, status string) (*Supplier, error) {
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
