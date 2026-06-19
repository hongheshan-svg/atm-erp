package finance

import (
	"context"

	"github.com/atm-erp/server/internal/iam"
	"gorm.io/gorm"
)

// Repo 封装本上下文所有实体的数据访问;按 scopeModule 套用数据范围,软删除走 gorm.DeletedAt。
type Repo struct{ db *gorm.DB }

func NewRepo(db *gorm.DB) *Repo { return &Repo{db: db} }

// scoped 返回已套用数据范围过滤的查询(model 由调用方在 Model() 指定)。
func (r *Repo) scoped(ctx context.Context, model any) *gorm.DB {
	q := r.db.WithContext(ctx).Model(model)
	if u, ok := iam.AuthUserFrom(ctx); ok {
		q = iam.ApplyScope(q, u, scopeModule, "created_by_id")
	}
	return q
}

// nextSeqNo 复刻 Django save() 里的「PREFIX+YYYYMMDD+4位序号」自增逻辑。
// 取当天同前缀最大编号末 4 位 +1;以 created_by 数据范围外的全量为基准(编号唯一性应全局成立)。
// 注意:并发下存在竞态,Django 原实现亦然;切流后建议改用 CodeRule + 行锁(见 todos)。
func (r *Repo) nextSeqNo(ctx context.Context, table, col, prefixWithDate string) (int, error) {
	var last string
	err := r.db.WithContext(ctx).
		Table(table).
		Where(col+" LIKE ?", prefixWithDate+"%").
		Order(col+" DESC").
		Limit(1).
		Pluck(col, &last).Error
	if err != nil {
		return 0, err
	}
	if last == "" {
		return 1, nil
	}
	// 末 4 位为序号
	if len(last) < 4 {
		return 1, nil
	}
	seq := 0
	for _, ch := range last[len(last)-4:] {
		if ch < '0' || ch > '9' {
			return 1, nil
		}
		seq = seq*10 + int(ch-'0')
	}
	return seq + 1, nil
}

// ---- 通用 CRUD(GORM Model 已带 TableName,软删除自动) ----

func (r *Repo) create(ctx context.Context, v any) error {
	return r.db.WithContext(ctx).Create(v).Error
}

func (r *Repo) save(ctx context.Context, v any) error {
	return r.db.WithContext(ctx).Save(v).Error
}

// ---- Currency ----

func (r *Repo) ListCurrency(ctx context.Context, q CurrencyListQuery, offset, limit int) ([]Currency, int64, error) {
	tx := r.scoped(ctx, &Currency{})
	if q.Keyword != "" {
		kw := "%" + q.Keyword + "%"
		tx = tx.Where("code LIKE ? OR name LIKE ?", kw, kw)
	}
	if q.IsActive != nil {
		tx = tx.Where("is_active = ?", *q.IsActive)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var rows []Currency
	if err := tx.Order("code ASC").Offset(offset).Limit(limit).Find(&rows).Error; err != nil {
		return nil, 0, err
	}
	return rows, total, nil
}

func (r *Repo) GetCurrency(ctx context.Context, id uint64) (*Currency, error) {
	var v Currency
	if err := r.scoped(ctx, &Currency{}).Where("id = ?", id).First(&v).Error; err != nil {
		return nil, err
	}
	return &v, nil
}

func (r *Repo) SoftDeleteCurrency(ctx context.Context, id uint64) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&Currency{}).Error
}

// ---- Expense ----

func (r *Repo) ListExpense(ctx context.Context, q ExpenseListQuery, offset, limit int) ([]Expense, int64, error) {
	tx := r.scoped(ctx, &Expense{})
	if q.Keyword != "" {
		kw := "%" + q.Keyword + "%"
		tx = tx.Where("expense_no LIKE ? OR description LIKE ?", kw, kw)
	}
	if q.Status != "" {
		tx = tx.Where("status = ?", q.Status)
	}
	if q.Category != "" {
		tx = tx.Where("category = ?", q.Category)
	}
	if q.ProjectID != nil {
		tx = tx.Where("project_id = ?", *q.ProjectID)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var rows []Expense
	if err := tx.Order("expense_date DESC, id DESC").Offset(offset).Limit(limit).Find(&rows).Error; err != nil {
		return nil, 0, err
	}
	return rows, total, nil
}

func (r *Repo) GetExpense(ctx context.Context, id uint64) (*Expense, error) {
	var v Expense
	if err := r.scoped(ctx, &Expense{}).Where("id = ?", id).First(&v).Error; err != nil {
		return nil, err
	}
	return &v, nil
}

func (r *Repo) SoftDeleteExpense(ctx context.Context, id uint64) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&Expense{}).Error
}

// ---- AccountReceivable ----

func (r *Repo) ListReceivable(ctx context.Context, q ReceivableListQuery, offset, limit int) ([]AccountReceivable, int64, error) {
	tx := r.scoped(ctx, &AccountReceivable{})
	if q.Keyword != "" {
		kw := "%" + q.Keyword + "%"
		tx = tx.Where("ar_no LIKE ? OR invoice_no LIKE ?", kw, kw)
	}
	if q.Status != "" {
		tx = tx.Where("status = ?", q.Status)
	}
	if q.CustomerID != nil {
		tx = tx.Where("customer_id = ?", *q.CustomerID)
	}
	if q.ProjectID != nil {
		tx = tx.Where("project_id = ?", *q.ProjectID)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var rows []AccountReceivable
	if err := tx.Order("invoice_date DESC, id DESC").Offset(offset).Limit(limit).Find(&rows).Error; err != nil {
		return nil, 0, err
	}
	return rows, total, nil
}

func (r *Repo) GetReceivable(ctx context.Context, id uint64) (*AccountReceivable, error) {
	var v AccountReceivable
	if err := r.scoped(ctx, &AccountReceivable{}).Where("id = ?", id).First(&v).Error; err != nil {
		return nil, err
	}
	return &v, nil
}

func (r *Repo) SoftDeleteReceivable(ctx context.Context, id uint64) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&AccountReceivable{}).Error
}

// ---- AccountPayable ----

func (r *Repo) ListPayable(ctx context.Context, q PayableListQuery, offset, limit int) ([]AccountPayable, int64, error) {
	tx := r.scoped(ctx, &AccountPayable{})
	if q.Keyword != "" {
		kw := "%" + q.Keyword + "%"
		tx = tx.Where("ap_no LIKE ? OR invoice_no LIKE ?", kw, kw)
	}
	if q.Status != "" {
		tx = tx.Where("status = ?", q.Status)
	}
	if q.SupplierID != nil {
		tx = tx.Where("supplier_id = ?", *q.SupplierID)
	}
	if q.ProjectID != nil {
		tx = tx.Where("project_id = ?", *q.ProjectID)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var rows []AccountPayable
	if err := tx.Order("invoice_date DESC, id DESC").Offset(offset).Limit(limit).Find(&rows).Error; err != nil {
		return nil, 0, err
	}
	return rows, total, nil
}

func (r *Repo) GetPayable(ctx context.Context, id uint64) (*AccountPayable, error) {
	var v AccountPayable
	if err := r.scoped(ctx, &AccountPayable{}).Where("id = ?", id).First(&v).Error; err != nil {
		return nil, err
	}
	return &v, nil
}

func (r *Repo) SoftDeletePayable(ctx context.Context, id uint64) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&AccountPayable{}).Error
}

// ---- Payment ----

func (r *Repo) ListPayment(ctx context.Context, q PaymentListQuery, offset, limit int) ([]Payment, int64, error) {
	tx := r.scoped(ctx, &Payment{})
	if q.Keyword != "" {
		kw := "%" + q.Keyword + "%"
		tx = tx.Where("payment_no LIKE ?", kw)
	}
	if q.PaymentType != "" {
		tx = tx.Where("payment_type = ?", q.PaymentType)
	}
	if q.ARID != nil {
		tx = tx.Where("ar_id = ?", *q.ARID)
	}
	if q.APID != nil {
		tx = tx.Where("ap_id = ?", *q.APID)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var rows []Payment
	if err := tx.Order("payment_date DESC, id DESC").Offset(offset).Limit(limit).Find(&rows).Error; err != nil {
		return nil, 0, err
	}
	return rows, total, nil
}

func (r *Repo) GetPayment(ctx context.Context, id uint64) (*Payment, error) {
	var v Payment
	if err := r.scoped(ctx, &Payment{}).Where("id = ?", id).First(&v).Error; err != nil {
		return nil, err
	}
	return &v, nil
}

func (r *Repo) SoftDeletePayment(ctx context.Context, id uint64) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&Payment{}).Error
}

// ---- Invoice ----

func (r *Repo) ListInvoice(ctx context.Context, q InvoiceListQuery, offset, limit int) ([]Invoice, int64, error) {
	tx := r.scoped(ctx, &Invoice{})
	if q.Keyword != "" {
		kw := "%" + q.Keyword + "%"
		tx = tx.Where("invoice_no LIKE ? OR party_name LIKE ? OR seller_name LIKE ? OR buyer_name LIKE ?", kw, kw, kw, kw)
	}
	if q.InvoiceType != "" {
		tx = tx.Where("invoice_type = ?", q.InvoiceType)
	}
	if q.Status != "" {
		tx = tx.Where("status = ?", q.Status)
	}
	if q.ProjectID != nil {
		tx = tx.Where("project_id = ?", *q.ProjectID)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var rows []Invoice
	if err := tx.Order("invoice_date DESC, id DESC").Offset(offset).Limit(limit).Find(&rows).Error; err != nil {
		return nil, 0, err
	}
	return rows, total, nil
}

func (r *Repo) GetInvoice(ctx context.Context, id uint64) (*Invoice, error) {
	var v Invoice
	if err := r.scoped(ctx, &Invoice{}).Where("id = ?", id).First(&v).Error; err != nil {
		return nil, err
	}
	return &v, nil
}

func (r *Repo) GetInvoiceItems(ctx context.Context, invoiceID uint64) ([]InvoiceItem, error) {
	var rows []InvoiceItem
	if err := r.db.WithContext(ctx).Where("invoice_id = ?", invoiceID).Order("line_no ASC").Find(&rows).Error; err != nil {
		return nil, err
	}
	return rows, nil
}

func (r *Repo) ReplaceInvoiceItems(ctx context.Context, invoiceID uint64, items []InvoiceItem) error {
	return r.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		if err := tx.Where("invoice_id = ?", invoiceID).Delete(&InvoiceItem{}).Error; err != nil {
			return err
		}
		for i := range items {
			items[i].InvoiceID = invoiceID
			if err := tx.Create(&items[i]).Error; err != nil {
				return err
			}
		}
		return nil
	})
}

func (r *Repo) SoftDeleteInvoice(ctx context.Context, id uint64) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&Invoice{}).Error
}
