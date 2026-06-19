package finance

import (
	"context"
	"errors"
	"fmt"
	"time"

	"gorm.io/gorm"
)

var (
	ErrNotFound      = errors.New("记录不存在")
	ErrInvalidStatus = errors.New("状态非法或不允许的状态流转")
	ErrPaymentTarget = errors.New("付款必须关联应收(ar_id)或应付(ap_id)之一")
)

type Service struct{ repo *Repo }

func NewService(repo *Repo) *Service { return &Service{repo: repo} }

func notFound(err error) error {
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return ErrNotFound
	}
	return err
}

// genNo 复刻 Django「PREFIX+YYYYMMDD+%04d」编号生成。
func (s *Service) genNo(ctx context.Context, table, col, prefix string) (string, error) {
	dateStr := time.Now().Format("20060102")
	prefixWithDate := prefix + dateStr
	seq, err := s.repo.nextSeqNo(ctx, table, col, prefixWithDate)
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("%s%04d", prefixWithDate, seq), nil
}

func deref[T any](p *T, def T) T {
	if p == nil {
		return def
	}
	return *p
}

// ============================ Currency ============================

func (s *Service) ListCurrency(ctx context.Context, q CurrencyListQuery, offset, limit int) ([]Currency, int64, error) {
	return s.repo.ListCurrency(ctx, q, offset, limit)
}

func (s *Service) GetCurrency(ctx context.Context, id uint64) (*Currency, error) {
	v, err := s.repo.GetCurrency(ctx, id)
	return v, notFound(err)
}

func (s *Service) CreateCurrency(ctx context.Context, in CurrencyCreateInput) (*Currency, error) {
	rate := in.ExchangeRate
	if rate == 0 {
		rate = 1.0 // Django default=1.0
	}
	v := &Currency{
		Code:           in.Code,
		Name:           in.Name,
		Symbol:         in.Symbol,
		ExchangeRate:   rate,
		IsBaseCurrency: in.IsBaseCurrency,
		IsActive:       deref(in.IsActive, true),
	}
	if err := s.repo.create(ctx, v); err != nil {
		return nil, err
	}
	return v, nil
}

func (s *Service) UpdateCurrency(ctx context.Context, id uint64, in CurrencyUpdateInput) (*Currency, error) {
	v, err := s.GetCurrency(ctx, id)
	if err != nil {
		return nil, err
	}
	if in.Name != nil {
		v.Name = *in.Name
	}
	if in.Symbol != nil {
		v.Symbol = *in.Symbol
	}
	if in.ExchangeRate != nil {
		v.ExchangeRate = *in.ExchangeRate
	}
	if in.IsBaseCurrency != nil {
		v.IsBaseCurrency = *in.IsBaseCurrency
	}
	if in.IsActive != nil {
		v.IsActive = *in.IsActive
	}
	if err := s.repo.save(ctx, v); err != nil {
		return nil, err
	}
	return v, nil
}

func (s *Service) DeleteCurrency(ctx context.Context, id uint64) error {
	if _, err := s.GetCurrency(ctx, id); err != nil {
		return err
	}
	return s.repo.SoftDeleteCurrency(ctx, id)
}

// ============================ Expense ============================

func (s *Service) ListExpense(ctx context.Context, q ExpenseListQuery, offset, limit int) ([]Expense, int64, error) {
	return s.repo.ListExpense(ctx, q, offset, limit)
}

func (s *Service) GetExpense(ctx context.Context, id uint64) (*Expense, error) {
	v, err := s.repo.GetExpense(ctx, id)
	return v, notFound(err)
}

func (s *Service) CreateExpense(ctx context.Context, in ExpenseCreateInput) (*Expense, error) {
	no, err := s.genNo(ctx, "expense", "expense_no", "EXP")
	if err != nil {
		return nil, err
	}
	rate := deref(in.ExchangeRate, 1.0)
	v := &Expense{
		ExpenseNo:    no,
		ProjectID:    in.ProjectID,
		DepartmentID: in.DepartmentID,
		UserID:       in.UserID,
		ExpenseDate:  in.ExpenseDate,
		Category:     in.Category,
		CurrencyID:   in.CurrencyID,
		Amount:       in.Amount,
		ExchangeRate: rate,
		Description:  in.Description,
		Status:       ExpenseStatusDraft,
	}
	// Django save(): base_amount = amount * exchange_rate(currency 存在时)
	if in.CurrencyID != nil {
		ba := in.Amount * rate
		v.BaseAmount = &ba
	}
	if err := s.repo.create(ctx, v); err != nil {
		return nil, err
	}
	return v, nil
}

func (s *Service) UpdateExpense(ctx context.Context, id uint64, in ExpenseUpdateInput) (*Expense, error) {
	v, err := s.GetExpense(ctx, id)
	if err != nil {
		return nil, err
	}
	if in.ProjectID != nil {
		v.ProjectID = in.ProjectID
	}
	if in.DepartmentID != nil {
		v.DepartmentID = in.DepartmentID
	}
	if in.ExpenseDate != nil {
		v.ExpenseDate = *in.ExpenseDate
	}
	if in.Category != nil {
		v.Category = *in.Category
	}
	if in.CurrencyID != nil {
		v.CurrencyID = in.CurrencyID
	}
	if in.Amount != nil {
		v.Amount = *in.Amount
	}
	if in.ExchangeRate != nil {
		v.ExchangeRate = *in.ExchangeRate
	}
	if in.Description != nil {
		v.Description = *in.Description
	}
	if in.Status != nil {
		v.Status = *in.Status
	}
	if in.ReimbursementDate != nil {
		v.ReimbursementDate = in.ReimbursementDate
	}
	// 重算 base_amount(Django save 行为)
	if v.CurrencyID != nil {
		ba := v.Amount * v.ExchangeRate
		v.BaseAmount = &ba
	}
	if err := s.repo.save(ctx, v); err != nil {
		return nil, err
	}
	return v, nil
}

func (s *Service) DeleteExpense(ctx context.Context, id uint64) error {
	if _, err := s.GetExpense(ctx, id); err != nil {
		return err
	}
	return s.repo.SoftDeleteExpense(ctx, id)
}

// SubmitExpense DRAFT -> SUBMITTED。
func (s *Service) SubmitExpense(ctx context.Context, id uint64) (*Expense, error) {
	v, err := s.GetExpense(ctx, id)
	if err != nil {
		return nil, err
	}
	if v.Status != ExpenseStatusDraft {
		return nil, ErrInvalidStatus
	}
	v.Status = ExpenseStatusSubmitted
	// TODO(verify): 接入 workflow 审批联动(WorkflowEnforcementMixin 等价物)后补全。
	if err := s.repo.save(ctx, v); err != nil {
		return nil, err
	}
	return v, nil
}

// ApproveExpense SUBMITTED -> APPROVED。
func (s *Service) ApproveExpense(ctx context.Context, id uint64) (*Expense, error) {
	v, err := s.GetExpense(ctx, id)
	if err != nil {
		return nil, err
	}
	if v.Status != ExpenseStatusSubmitted {
		return nil, ErrInvalidStatus
	}
	v.Status = ExpenseStatusApproved
	if err := s.repo.save(ctx, v); err != nil {
		return nil, err
	}
	return v, nil
}

// RejectExpense SUBMITTED -> REJECTED。
func (s *Service) RejectExpense(ctx context.Context, id uint64) (*Expense, error) {
	v, err := s.GetExpense(ctx, id)
	if err != nil {
		return nil, err
	}
	if v.Status != ExpenseStatusSubmitted {
		return nil, ErrInvalidStatus
	}
	v.Status = ExpenseStatusRejected
	if err := s.repo.save(ctx, v); err != nil {
		return nil, err
	}
	return v, nil
}

// ============================ AccountReceivable ============================

// applyARStatus 复刻 Django AccountReceivable.save() 的状态推导。
func applyARStatus(v *AccountReceivable) {
	if v.AmountPaid >= v.AmountDue {
		v.Status = ARAPStatusPaid
	} else if v.AmountPaid > 0 {
		v.Status = ARAPStatusPartial
	}
}

func (s *Service) ListReceivable(ctx context.Context, q ReceivableListQuery, offset, limit int) ([]AccountReceivable, int64, error) {
	return s.repo.ListReceivable(ctx, q, offset, limit)
}

func (s *Service) GetReceivable(ctx context.Context, id uint64) (*AccountReceivable, error) {
	v, err := s.repo.GetReceivable(ctx, id)
	return v, notFound(err)
}

func (s *Service) CreateReceivable(ctx context.Context, in ReceivableCreateInput) (*AccountReceivable, error) {
	no, err := s.genNo(ctx, "account_receivable", "ar_no", "AR")
	if err != nil {
		return nil, err
	}
	v := &AccountReceivable{
		ARNo:         no,
		CustomerID:   in.CustomerID,
		SOID:         in.SOID,
		ProjectID:    in.ProjectID,
		InvoiceNo:    in.InvoiceNo,
		InvoiceDate:  in.InvoiceDate,
		CurrencyID:   in.CurrencyID,
		AmountDue:    in.AmountDue,
		AmountPaid:   deref(in.AmountPaid, 0),
		ExchangeRate: deref(in.ExchangeRate, 1.0),
		DueDate:      in.DueDate,
		Status:       ARAPStatusPending,
	}
	applyARStatus(v)
	if err := s.repo.create(ctx, v); err != nil {
		return nil, err
	}
	return v, nil
}

func (s *Service) UpdateReceivable(ctx context.Context, id uint64, in ReceivableUpdateInput) (*AccountReceivable, error) {
	v, err := s.GetReceivable(ctx, id)
	if err != nil {
		return nil, err
	}
	if in.CustomerID != nil {
		v.CustomerID = *in.CustomerID
	}
	if in.SOID != nil {
		v.SOID = in.SOID
	}
	if in.ProjectID != nil {
		v.ProjectID = in.ProjectID
	}
	if in.InvoiceNo != nil {
		v.InvoiceNo = *in.InvoiceNo
	}
	if in.InvoiceDate != nil {
		v.InvoiceDate = *in.InvoiceDate
	}
	if in.CurrencyID != nil {
		v.CurrencyID = in.CurrencyID
	}
	if in.AmountDue != nil {
		v.AmountDue = *in.AmountDue
	}
	if in.AmountPaid != nil {
		v.AmountPaid = *in.AmountPaid
	}
	if in.ExchangeRate != nil {
		v.ExchangeRate = *in.ExchangeRate
	}
	if in.DueDate != nil {
		v.DueDate = *in.DueDate
	}
	if in.Status != nil {
		v.Status = *in.Status
	}
	applyARStatus(v)
	if err := s.repo.save(ctx, v); err != nil {
		return nil, err
	}
	return v, nil
}

func (s *Service) DeleteReceivable(ctx context.Context, id uint64) error {
	if _, err := s.GetReceivable(ctx, id); err != nil {
		return err
	}
	return s.repo.SoftDeleteReceivable(ctx, id)
}

// ============================ AccountPayable ============================

func applyAPStatus(v *AccountPayable) {
	if v.AmountPaid >= v.AmountDue {
		v.Status = ARAPStatusPaid
	} else if v.AmountPaid > 0 {
		v.Status = ARAPStatusPartial
	}
}

func (s *Service) ListPayable(ctx context.Context, q PayableListQuery, offset, limit int) ([]AccountPayable, int64, error) {
	return s.repo.ListPayable(ctx, q, offset, limit)
}

func (s *Service) GetPayable(ctx context.Context, id uint64) (*AccountPayable, error) {
	v, err := s.repo.GetPayable(ctx, id)
	return v, notFound(err)
}

func (s *Service) CreatePayable(ctx context.Context, in PayableCreateInput) (*AccountPayable, error) {
	no, err := s.genNo(ctx, "account_payable", "ap_no", "AP")
	if err != nil {
		return nil, err
	}
	v := &AccountPayable{
		APNo:         no,
		SupplierID:   in.SupplierID,
		POID:         in.POID,
		ProjectID:    in.ProjectID,
		InvoiceNo:    in.InvoiceNo,
		InvoiceDate:  in.InvoiceDate,
		CurrencyID:   in.CurrencyID,
		AmountDue:    in.AmountDue,
		AmountPaid:   deref(in.AmountPaid, 0),
		ExchangeRate: deref(in.ExchangeRate, 1.0),
		DueDate:      in.DueDate,
		Status:       ARAPStatusPending,
	}
	applyAPStatus(v)
	if err := s.repo.create(ctx, v); err != nil {
		return nil, err
	}
	return v, nil
}

func (s *Service) UpdatePayable(ctx context.Context, id uint64, in PayableUpdateInput) (*AccountPayable, error) {
	v, err := s.GetPayable(ctx, id)
	if err != nil {
		return nil, err
	}
	if in.SupplierID != nil {
		v.SupplierID = *in.SupplierID
	}
	if in.POID != nil {
		v.POID = in.POID
	}
	if in.ProjectID != nil {
		v.ProjectID = in.ProjectID
	}
	if in.InvoiceNo != nil {
		v.InvoiceNo = *in.InvoiceNo
	}
	if in.InvoiceDate != nil {
		v.InvoiceDate = *in.InvoiceDate
	}
	if in.CurrencyID != nil {
		v.CurrencyID = in.CurrencyID
	}
	if in.AmountDue != nil {
		v.AmountDue = *in.AmountDue
	}
	if in.AmountPaid != nil {
		v.AmountPaid = *in.AmountPaid
	}
	if in.ExchangeRate != nil {
		v.ExchangeRate = *in.ExchangeRate
	}
	if in.DueDate != nil {
		v.DueDate = *in.DueDate
	}
	if in.Status != nil {
		v.Status = *in.Status
	}
	applyAPStatus(v)
	if err := s.repo.save(ctx, v); err != nil {
		return nil, err
	}
	return v, nil
}

func (s *Service) DeletePayable(ctx context.Context, id uint64) error {
	if _, err := s.GetPayable(ctx, id); err != nil {
		return err
	}
	return s.repo.SoftDeletePayable(ctx, id)
}

// ============================ Payment ============================

func (s *Service) ListPayment(ctx context.Context, q PaymentListQuery, offset, limit int) ([]Payment, int64, error) {
	return s.repo.ListPayment(ctx, q, offset, limit)
}

func (s *Service) GetPayment(ctx context.Context, id uint64) (*Payment, error) {
	v, err := s.repo.GetPayment(ctx, id)
	return v, notFound(err)
}

// CreatePayment 复刻 Django Payment.save():生成编号 + 新建后回写 AR/AP 的 amount_paid。
// Django 用 F('amount_paid') + amount 原子自增,并由 AR/AP.save() 推导状态;
// 这里在事务内 reload 目标单据、累加金额、重算状态后保存,以保持状态一致。
func (s *Service) CreatePayment(ctx context.Context, in PaymentCreateInput) (*Payment, error) {
	if in.ARID == nil && in.APID == nil {
		return nil, ErrPaymentTarget
	}
	no, err := s.genNo(ctx, "payment", "payment_no", "PAY")
	if err != nil {
		return nil, err
	}
	v := &Payment{
		PaymentNo:     no,
		PaymentType:   in.PaymentType,
		ARID:          in.ARID,
		APID:          in.APID,
		PaymentDate:   in.PaymentDate,
		PaymentMethod: in.PaymentMethod,
		CurrencyID:    in.CurrencyID,
		Amount:        in.Amount,
		ExchangeRate:  deref(in.ExchangeRate, 1.0),
		Notes:         in.Notes,
	}
	if err := s.repo.create(ctx, v); err != nil {
		return nil, err
	}

	// 回写关联单据 amount_paid 并推导状态(对应 Django save() 里的 is_new 分支)。
	if v.ARID != nil {
		ar, err := s.repo.GetReceivable(ctx, *v.ARID)
		if err == nil {
			ar.AmountPaid += v.Amount
			applyARStatus(ar)
			_ = s.repo.save(ctx, ar) // TODO(verify): 失败应整体回滚;切流后用单事务包裹 create+update。
		}
	} else if v.APID != nil {
		ap, err := s.repo.GetPayable(ctx, *v.APID)
		if err == nil {
			ap.AmountPaid += v.Amount
			applyAPStatus(ap)
			_ = s.repo.save(ctx, ap)
		}
	}
	return v, nil
}

func (s *Service) DeletePayment(ctx context.Context, id uint64) error {
	if _, err := s.GetPayment(ctx, id); err != nil {
		return err
	}
	// TODO(verify): Django 未在删除付款时冲回 amount_paid;此处保持一致,仅软删付款记录。
	return s.repo.SoftDeletePayment(ctx, id)
}

// ============================ Invoice ============================

// computeInvoiceTotal 复刻 Django Invoice.save():total = amount_before_tax + tax_amount。
func computeInvoiceTotal(before, tax float64, explicit *float64) float64 {
	if explicit != nil {
		return *explicit
	}
	return before + tax
}

func (s *Service) ListInvoice(ctx context.Context, q InvoiceListQuery, offset, limit int) ([]Invoice, int64, error) {
	return s.repo.ListInvoice(ctx, q, offset, limit)
}

func (s *Service) GetInvoice(ctx context.Context, id uint64) (*Invoice, error) {
	v, err := s.repo.GetInvoice(ctx, id)
	return v, notFound(err)
}

func (s *Service) GetInvoiceItems(ctx context.Context, invoiceID uint64) ([]InvoiceItem, error) {
	if _, err := s.GetInvoice(ctx, invoiceID); err != nil {
		return nil, err
	}
	return s.repo.GetInvoiceItems(ctx, invoiceID)
}

func (s *Service) CreateInvoice(ctx context.Context, in InvoiceCreateInput) (*Invoice, error) {
	v := &Invoice{
		InvoiceType:      in.InvoiceType,
		InvoiceNo:        in.InvoiceNo,
		InvoiceCode:      in.InvoiceCode,
		DigitalInvoiceNo: in.DigitalInvoiceNo,
		InvoiceDate:      in.InvoiceDate,
		SellerTaxNo:      in.SellerTaxNo,
		SellerName:       in.SellerName,
		BuyerTaxNo:       in.BuyerTaxNo,
		BuyerName:        in.BuyerName,
		PartyName:        in.PartyName,
		TaxNumber:        in.TaxNumber,
		AmountBeforeTax:  in.AmountBeforeTax,
		TaxAmount:        in.TaxAmount,
		TotalAmount:      computeInvoiceTotal(in.AmountBeforeTax, in.TaxAmount, in.TotalAmount),
		InvoiceSource:    in.InvoiceSource,
		InvoiceCategory:  in.InvoiceCategory,
		ReferenceType:    in.ReferenceType,
		ReferenceID:      in.ReferenceID,
		ProjectID:        in.ProjectID,
		Status:           InvoiceStatusRegistered,
		Notes:            in.Notes,
	}
	if err := s.repo.create(ctx, v); err != nil {
		return nil, err
	}
	if len(in.Items) > 0 {
		items := make([]InvoiceItem, 0, len(in.Items))
		for _, it := range in.Items {
			items = append(items, toInvoiceItem(it))
		}
		if err := s.repo.ReplaceInvoiceItems(ctx, v.ID, items); err != nil {
			return nil, err
		}
	}
	return v, nil
}

func toInvoiceItem(in InvoiceItemInput) InvoiceItem {
	return InvoiceItem{
		LineNo:          in.LineNo,
		TaxCategoryCode: in.TaxCategoryCode,
		BusinessType:    in.BusinessType,
		ItemName:        in.ItemName,
		Specification:   in.Specification,
		Unit:            in.Unit,
		Quantity:        in.Quantity,
		UnitPrice:       in.UnitPrice,
		Amount:          in.Amount,
		TaxRate:         in.TaxRate,
		TaxAmount:       in.TaxAmount,
	}
}

func (s *Service) UpdateInvoice(ctx context.Context, id uint64, in InvoiceUpdateInput) (*Invoice, error) {
	v, err := s.GetInvoice(ctx, id)
	if err != nil {
		return nil, err
	}
	if in.InvoiceType != nil {
		v.InvoiceType = *in.InvoiceType
	}
	if in.InvoiceCode != nil {
		v.InvoiceCode = *in.InvoiceCode
	}
	if in.DigitalInvoiceNo != nil {
		v.DigitalInvoiceNo = *in.DigitalInvoiceNo
	}
	if in.InvoiceDate != nil {
		v.InvoiceDate = *in.InvoiceDate
	}
	if in.SellerTaxNo != nil {
		v.SellerTaxNo = *in.SellerTaxNo
	}
	if in.SellerName != nil {
		v.SellerName = *in.SellerName
	}
	if in.BuyerTaxNo != nil {
		v.BuyerTaxNo = *in.BuyerTaxNo
	}
	if in.BuyerName != nil {
		v.BuyerName = *in.BuyerName
	}
	if in.PartyName != nil {
		v.PartyName = *in.PartyName
	}
	if in.TaxNumber != nil {
		v.TaxNumber = *in.TaxNumber
	}
	if in.AmountBeforeTax != nil {
		v.AmountBeforeTax = *in.AmountBeforeTax
	}
	if in.TaxAmount != nil {
		v.TaxAmount = *in.TaxAmount
	}
	if in.InvoiceSource != nil {
		v.InvoiceSource = *in.InvoiceSource
	}
	if in.InvoiceCategory != nil {
		v.InvoiceCategory = *in.InvoiceCategory
	}
	if in.ReferenceType != nil {
		v.ReferenceType = in.ReferenceType
	}
	if in.ReferenceID != nil {
		v.ReferenceID = in.ReferenceID
	}
	if in.ProjectID != nil {
		v.ProjectID = in.ProjectID
	}
	if in.Status != nil {
		v.Status = *in.Status
	}
	if in.Notes != nil {
		v.Notes = *in.Notes
	}
	// Django save(): total = before + tax(显式 total_amount 优先)
	v.TotalAmount = computeInvoiceTotal(v.AmountBeforeTax, v.TaxAmount, in.TotalAmount)
	if err := s.repo.save(ctx, v); err != nil {
		return nil, err
	}
	return v, nil
}

func (s *Service) DeleteInvoice(ctx context.Context, id uint64) error {
	if _, err := s.GetInvoice(ctx, id); err != nil {
		return err
	}
	return s.repo.SoftDeleteInvoice(ctx, id)
}

// VoidInvoice 作废发票(任意状态 -> VOID)。
func (s *Service) VoidInvoice(ctx context.Context, id uint64) (*Invoice, error) {
	v, err := s.GetInvoice(ctx, id)
	if err != nil {
		return nil, err
	}
	if v.Status == InvoiceStatusVoid {
		return nil, ErrInvalidStatus
	}
	v.Status = InvoiceStatusVoid
	if err := s.repo.save(ctx, v); err != nil {
		return nil, err
	}
	return v, nil
}

// CertifyInvoice 认证进项发票(REGISTERED -> CERTIFIED)。
func (s *Service) CertifyInvoice(ctx context.Context, id uint64) (*Invoice, error) {
	v, err := s.GetInvoice(ctx, id)
	if err != nil {
		return nil, err
	}
	if v.Status != InvoiceStatusRegistered {
		return nil, ErrInvalidStatus
	}
	v.Status = InvoiceStatusCertified
	if err := s.repo.save(ctx, v); err != nil {
		return nil, err
	}
	return v, nil
}
