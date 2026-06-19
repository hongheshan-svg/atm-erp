package sales

import (
	"context"

	"github.com/atm-erp/server/internal/iam"
	"gorm.io/gorm"
)

// scopeModule 标识该上下文所属权限/数据范围模块(对齐 Django permission_module='sales')。
const scopeModule = "sales"

// Repo 承载 sales 上下文所有实体的持久化。数据范围按 created_by 归属过滤
// (Django 现状以 created_by/owner 作归属;owner 维度待 IAM 部门树落地后细化)。
type Repo struct{ db *gorm.DB }

func NewRepo(db *gorm.DB) *Repo { return &Repo{db: db} }

// scoped 套用数据范围过滤;软删除由 gorm.DeletedAt 默认过滤。
func (r *Repo) scoped(ctx context.Context, dest any) *gorm.DB {
	q := r.db.WithContext(ctx).Model(dest)
	if u, ok := iam.AuthUserFrom(ctx); ok {
		q = iam.ApplyScope(q, u, scopeModule, "created_by")
	}
	return q
}

func (r *Repo) DB() *gorm.DB { return r.db }

// ---- 通用 CRUD 辅助(按表泛型化) ----

func (r *Repo) create(ctx context.Context, v any) error {
	return r.db.WithContext(ctx).Create(v).Error
}

func (r *Repo) save(ctx context.Context, v any) error {
	return r.db.WithContext(ctx).Save(v).Error
}

// ===== Quotation =====

func (r *Repo) ListQuotations(ctx context.Context, q ListQuery, offset, limit int) ([]Quotation, int64, error) {
	tx := r.scoped(ctx, &Quotation{})
	if q.Keyword != "" {
		tx = tx.Where("quote_no LIKE ?", "%"+q.Keyword+"%")
	}
	if q.Status != "" {
		tx = tx.Where("status = ?", q.Status)
	}
	if q.CustomerID != "" {
		tx = tx.Where("customer_id = ?", q.CustomerID)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var out []Quotation
	err := tx.Order("id DESC").Offset(offset).Limit(limit).Find(&out).Error
	return out, total, err
}

func (r *Repo) GetQuotation(ctx context.Context, id uint64) (*Quotation, error) {
	var v Quotation
	if err := r.scoped(ctx, &Quotation{}).Where("id = ?", id).First(&v).Error; err != nil {
		return nil, err
	}
	return &v, nil
}

func (r *Repo) CreateQuotation(ctx context.Context, v *Quotation) error { return r.create(ctx, v) }
func (r *Repo) SaveQuotation(ctx context.Context, v *Quotation) error   { return r.save(ctx, v) }
func (r *Repo) DeleteQuotation(ctx context.Context, id uint64) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&Quotation{}).Error
}

func (r *Repo) CreateQuotationLines(ctx context.Context, lines []QuotationLine) error {
	if len(lines) == 0 {
		return nil
	}
	return r.db.WithContext(ctx).Create(&lines).Error
}

func (r *Repo) ListQuotationLines(ctx context.Context, quotationID uint64) ([]QuotationLine, error) {
	var out []QuotationLine
	err := r.db.WithContext(ctx).Where("quotation_id = ?", quotationID).Order("id").Find(&out).Error
	return out, err
}

// ===== SalesOrder =====

func (r *Repo) ListSalesOrders(ctx context.Context, q ListQuery, offset, limit int) ([]SalesOrder, int64, error) {
	tx := r.scoped(ctx, &SalesOrder{})
	if q.Keyword != "" {
		kw := "%" + q.Keyword + "%"
		tx = tx.Where("order_no LIKE ? OR customer_order_no LIKE ?", kw, kw)
	}
	if q.Status != "" {
		tx = tx.Where("status = ?", q.Status)
	}
	if q.CustomerID != "" {
		tx = tx.Where("customer_id = ?", q.CustomerID)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var out []SalesOrder
	err := tx.Order("id DESC").Offset(offset).Limit(limit).Find(&out).Error
	return out, total, err
}

func (r *Repo) GetSalesOrder(ctx context.Context, id uint64) (*SalesOrder, error) {
	var v SalesOrder
	if err := r.scoped(ctx, &SalesOrder{}).Where("id = ?", id).First(&v).Error; err != nil {
		return nil, err
	}
	return &v, nil
}

func (r *Repo) CreateSalesOrder(ctx context.Context, v *SalesOrder) error { return r.create(ctx, v) }
func (r *Repo) SaveSalesOrder(ctx context.Context, v *SalesOrder) error   { return r.save(ctx, v) }
func (r *Repo) DeleteSalesOrder(ctx context.Context, id uint64) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&SalesOrder{}).Error
}

func (r *Repo) CreateSalesOrderLines(ctx context.Context, lines []SalesOrderLine) error {
	if len(lines) == 0 {
		return nil
	}
	return r.db.WithContext(ctx).Create(&lines).Error
}

func (r *Repo) ListSalesOrderLines(ctx context.Context, soID uint64) ([]SalesOrderLine, error) {
	var out []SalesOrderLine
	err := r.db.WithContext(ctx).Where("so_id = ?", soID).Order("id").Find(&out).Error
	return out, err
}

// SumSalesOrderLineAmount 汇总订单明细行金额(用于回算 total)。
func (r *Repo) SumSalesOrderLineAmount(ctx context.Context, soID uint64) (float64, error) {
	var total float64
	err := r.db.WithContext(ctx).Model(&SalesOrderLine{}).
		Where("so_id = ?", soID).
		Select("COALESCE(SUM(line_amount),0)").Scan(&total).Error
	return total, err
}

// HasActiveDeliveries 是否存在已提交/在途发货单(排除 DRAFT/REJECTED)。
func (r *Repo) HasActiveDeliveries(ctx context.Context, soID uint64) (bool, error) {
	var cnt int64
	err := r.db.WithContext(ctx).Model(&DeliveryOrder{}).
		Where("so_id = ? AND status NOT IN ?", soID, []string{"DRAFT", "REJECTED"}).
		Count(&cnt).Error
	return cnt > 0, err
}

// HasAnyDeliveries 是否存在任何未删除发货单(退回草稿用)。
func (r *Repo) HasAnyDeliveries(ctx context.Context, soID uint64) (bool, error) {
	var cnt int64
	err := r.db.WithContext(ctx).Model(&DeliveryOrder{}).Where("so_id = ?", soID).Count(&cnt).Error
	return cnt > 0, err
}

// ===== DeliveryOrder =====

func (r *Repo) ListDeliveries(ctx context.Context, q ListQuery, offset, limit int) ([]DeliveryOrder, int64, error) {
	tx := r.scoped(ctx, &DeliveryOrder{})
	if q.Keyword != "" {
		tx = tx.Where("delivery_no LIKE ?", "%"+q.Keyword+"%")
	}
	if q.Status != "" {
		tx = tx.Where("status = ?", q.Status)
	}
	if q.SOID != "" {
		tx = tx.Where("so_id = ?", q.SOID)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var out []DeliveryOrder
	err := tx.Order("id DESC").Offset(offset).Limit(limit).Find(&out).Error
	return out, total, err
}

func (r *Repo) GetDelivery(ctx context.Context, id uint64) (*DeliveryOrder, error) {
	var v DeliveryOrder
	if err := r.scoped(ctx, &DeliveryOrder{}).Where("id = ?", id).First(&v).Error; err != nil {
		return nil, err
	}
	return &v, nil
}

func (r *Repo) CreateDelivery(ctx context.Context, v *DeliveryOrder) error { return r.create(ctx, v) }
func (r *Repo) SaveDelivery(ctx context.Context, v *DeliveryOrder) error   { return r.save(ctx, v) }
func (r *Repo) DeleteDelivery(ctx context.Context, id uint64) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&DeliveryOrder{}).Error
}

func (r *Repo) CreateDeliveryLines(ctx context.Context, lines []DeliveryOrderLine) error {
	if len(lines) == 0 {
		return nil
	}
	return r.db.WithContext(ctx).Create(&lines).Error
}

// ===== Lead =====

func (r *Repo) ListLeads(ctx context.Context, q ListQuery, offset, limit int) ([]Lead, int64, error) {
	tx := r.scoped(ctx, &Lead{})
	if q.Keyword != "" {
		kw := "%" + q.Keyword + "%"
		tx = tx.Where("lead_no LIKE ? OR company_name LIKE ? OR contact_name LIKE ?", kw, kw, kw)
	}
	if q.Status != "" {
		tx = tx.Where("status = ?", q.Status)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var out []Lead
	err := tx.Order("id DESC").Offset(offset).Limit(limit).Find(&out).Error
	return out, total, err
}

func (r *Repo) GetLead(ctx context.Context, id uint64) (*Lead, error) {
	var v Lead
	if err := r.scoped(ctx, &Lead{}).Where("id = ?", id).First(&v).Error; err != nil {
		return nil, err
	}
	return &v, nil
}

func (r *Repo) CreateLead(ctx context.Context, v *Lead) error { return r.create(ctx, v) }
func (r *Repo) SaveLead(ctx context.Context, v *Lead) error   { return r.save(ctx, v) }
func (r *Repo) DeleteLead(ctx context.Context, id uint64) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&Lead{}).Error
}

// ===== Opportunity =====

func (r *Repo) ListOpportunities(ctx context.Context, q ListQuery, offset, limit int) ([]Opportunity, int64, error) {
	tx := r.scoped(ctx, &Opportunity{})
	if q.Keyword != "" {
		kw := "%" + q.Keyword + "%"
		tx = tx.Where("opportunity_no LIKE ? OR name LIKE ?", kw, kw)
	}
	if q.Stage != "" {
		tx = tx.Where("stage = ?", q.Stage)
	}
	if q.CustomerID != "" {
		tx = tx.Where("customer_id = ?", q.CustomerID)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var out []Opportunity
	err := tx.Order("id DESC").Offset(offset).Limit(limit).Find(&out).Error
	return out, total, err
}

func (r *Repo) GetOpportunity(ctx context.Context, id uint64) (*Opportunity, error) {
	var v Opportunity
	if err := r.scoped(ctx, &Opportunity{}).Where("id = ?", id).First(&v).Error; err != nil {
		return nil, err
	}
	return &v, nil
}

func (r *Repo) CreateOpportunity(ctx context.Context, v *Opportunity) error { return r.create(ctx, v) }
func (r *Repo) SaveOpportunity(ctx context.Context, v *Opportunity) error   { return r.save(ctx, v) }
func (r *Repo) DeleteOpportunity(ctx context.Context, id uint64) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&Opportunity{}).Error
}
