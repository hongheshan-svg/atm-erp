package purchase

import (
	"context"

	"github.com/atm-erp/server/internal/iam"
	"gorm.io/gorm"
)

// scopeModule 标识该资源所属权限/数据范围模块。
const scopeModule = "purchase"

// Repo 采购模块统一数据访问层(单仓覆盖四个主实体及其明细)。
type Repo struct{ db *gorm.DB }

func NewRepo(db *gorm.DB) *Repo { return &Repo{db: db} }

// scopedPR 等:返回已套用数据范围过滤的查询(软删除由 gorm.DeletedAt 默认过滤)。
// 单据归属人列统一用 created_by(对齐 BaseModel 与 iam.ApplyScope 约定)。
func (r *Repo) scoped(ctx context.Context, model any) *gorm.DB {
	q := r.db.WithContext(ctx).Model(model)
	if u, ok := iam.AuthUserFrom(ctx); ok {
		q = iam.ApplyScope(q, u, scopeModule, "created_by")
	}
	return q
}

// ---------------------------- 采购申请 ----------------------------

func (r *Repo) ListPR(ctx context.Context, q ListQuery, offset, limit int) ([]PurchaseRequest, int64, error) {
	tx := r.scoped(ctx, &PurchaseRequest{})
	if q.Keyword != "" {
		tx = tx.Where("request_no LIKE ?", "%"+q.Keyword+"%")
	}
	if q.Status != "" {
		tx = tx.Where("status = ?", q.Status)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var rows []PurchaseRequest
	if err := tx.Order("id DESC").Offset(offset).Limit(limit).Find(&rows).Error; err != nil {
		return nil, 0, err
	}
	return rows, total, nil
}

func (r *Repo) GetPR(ctx context.Context, id uint64) (*PurchaseRequest, error) {
	var pr PurchaseRequest
	if err := r.scoped(ctx, &PurchaseRequest{}).Where("id = ?", id).First(&pr).Error; err != nil {
		return nil, err
	}
	if err := r.db.WithContext(ctx).Where("pr_id = ?", id).Order("id").Find(&pr.Lines).Error; err != nil {
		return nil, err
	}
	return &pr, nil
}

func (r *Repo) CreatePR(ctx context.Context, pr *PurchaseRequest, lines []PurchaseRequestLine) error {
	return r.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		if err := tx.Create(pr).Error; err != nil {
			return err
		}
		for i := range lines {
			lines[i].PRID = pr.ID
		}
		if len(lines) > 0 {
			if err := tx.Create(&lines).Error; err != nil {
				return err
			}
		}
		pr.Lines = lines
		return nil
	})
}

func (r *Repo) SavePR(ctx context.Context, pr *PurchaseRequest) error {
	return r.db.WithContext(ctx).Save(pr).Error
}

func (r *Repo) SoftDeletePR(ctx context.Context, id uint64) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&PurchaseRequest{}).Error
}

// ---------------------------- 采购订单 ----------------------------

func (r *Repo) ListPO(ctx context.Context, q ListQuery, offset, limit int) ([]PurchaseOrder, int64, error) {
	tx := r.scoped(ctx, &PurchaseOrder{})
	if q.Keyword != "" {
		tx = tx.Where("order_no LIKE ?", "%"+q.Keyword+"%")
	}
	if q.Status != "" {
		tx = tx.Where("status = ?", q.Status)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var rows []PurchaseOrder
	if err := tx.Order("id DESC").Offset(offset).Limit(limit).Find(&rows).Error; err != nil {
		return nil, 0, err
	}
	return rows, total, nil
}

func (r *Repo) GetPO(ctx context.Context, id uint64) (*PurchaseOrder, error) {
	var po PurchaseOrder
	if err := r.scoped(ctx, &PurchaseOrder{}).Where("id = ?", id).First(&po).Error; err != nil {
		return nil, err
	}
	if err := r.db.WithContext(ctx).Where("po_id = ?", id).Order("id").Find(&po.Lines).Error; err != nil {
		return nil, err
	}
	return &po, nil
}

func (r *Repo) CreatePO(ctx context.Context, po *PurchaseOrder, lines []PurchaseOrderLine) error {
	return r.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		if err := tx.Create(po).Error; err != nil {
			return err
		}
		for i := range lines {
			lines[i].POID = po.ID
		}
		if len(lines) > 0 {
			if err := tx.Create(&lines).Error; err != nil {
				return err
			}
		}
		po.Lines = lines
		return nil
	})
}

func (r *Repo) SavePO(ctx context.Context, po *PurchaseOrder) error {
	return r.db.WithContext(ctx).Save(po).Error
}

func (r *Repo) SoftDeletePO(ctx context.Context, id uint64) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&PurchaseOrder{}).Error
}

// POLines 取某订单未删除明细(供收货校验)。
func (r *Repo) POLines(ctx context.Context, poID uint64) ([]PurchaseOrderLine, error) {
	var lines []PurchaseOrderLine
	err := r.db.WithContext(ctx).Where("po_id = ?", poID).Order("id").Find(&lines).Error
	return lines, err
}

// GetPOLine 取单条订单明细。
func (r *Repo) GetPOLine(ctx context.Context, id uint64) (*PurchaseOrderLine, error) {
	var l PurchaseOrderLine
	if err := r.db.WithContext(ctx).Where("id = ?", id).First(&l).Error; err != nil {
		return nil, err
	}
	return &l, nil
}

// HasReceipts 订单是否已有收货记录(删除/撤回校验)。
func (r *Repo) HasReceipts(ctx context.Context, poID uint64, confirmedOnly bool) (bool, error) {
	q := r.db.WithContext(ctx).Model(&GoodsReceipt{}).Where("po_id = ?", poID)
	if confirmedOnly {
		q = q.Where("status = ?", "CONFIRMED")
	}
	var n int64
	err := q.Count(&n).Error
	return n > 0, err
}

// ---------------------------- 收货 ----------------------------

func (r *Repo) ListGR(ctx context.Context, q ListQuery, offset, limit int) ([]GoodsReceipt, int64, error) {
	tx := r.scoped(ctx, &GoodsReceipt{})
	if q.Keyword != "" {
		tx = tx.Where("receipt_no LIKE ?", "%"+q.Keyword+"%")
	}
	if q.Status != "" {
		tx = tx.Where("status = ?", q.Status)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var rows []GoodsReceipt
	if err := tx.Order("id DESC").Offset(offset).Limit(limit).Find(&rows).Error; err != nil {
		return nil, 0, err
	}
	return rows, total, nil
}

func (r *Repo) GetGR(ctx context.Context, id uint64) (*GoodsReceipt, error) {
	var gr GoodsReceipt
	if err := r.scoped(ctx, &GoodsReceipt{}).Where("id = ?", id).First(&gr).Error; err != nil {
		return nil, err
	}
	if err := r.db.WithContext(ctx).Where("receipt_id = ?", id).Order("id").Find(&gr.Lines).Error; err != nil {
		return nil, err
	}
	return &gr, nil
}

func (r *Repo) CreateGR(ctx context.Context, gr *GoodsReceipt, lines []GoodsReceiptLine) error {
	return r.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		if err := tx.Create(gr).Error; err != nil {
			return err
		}
		for i := range lines {
			lines[i].ReceiptID = gr.ID
		}
		if len(lines) > 0 {
			if err := tx.Create(&lines).Error; err != nil {
				return err
			}
		}
		gr.Lines = lines
		return nil
	})
}

func (r *Repo) SaveGR(ctx context.Context, gr *GoodsReceipt) error {
	return r.db.WithContext(ctx).Save(gr).Error
}

func (r *Repo) SoftDeleteGR(ctx context.Context, id uint64) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&GoodsReceipt{}).Error
}

// ConfirmGRTx 在事务内确认收货:回写 PO 行已收量、刷新收货单与订单状态。
// 库存移动(InventoryMovement)与 BOM 联动属其他模块,本轮以 TODO(port) 占位。
func (r *Repo) ConfirmGRTx(ctx context.Context, fn func(tx *gorm.DB) error) error {
	return r.db.WithContext(ctx).Transaction(fn)
}

// ---------------------------- 询价 RFQ ----------------------------

func (r *Repo) ListRFQ(ctx context.Context, q ListQuery, offset, limit int) ([]RFQ, int64, error) {
	tx := r.scoped(ctx, &RFQ{})
	if q.Keyword != "" {
		tx = tx.Where("rfq_no LIKE ?", "%"+q.Keyword+"%")
	}
	if q.Status != "" {
		tx = tx.Where("status = ?", q.Status)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var rows []RFQ
	if err := tx.Order("id DESC").Offset(offset).Limit(limit).Find(&rows).Error; err != nil {
		return nil, 0, err
	}
	return rows, total, nil
}

func (r *Repo) GetRFQ(ctx context.Context, id uint64) (*RFQ, error) {
	var rfq RFQ
	if err := r.scoped(ctx, &RFQ{}).Where("id = ?", id).First(&rfq).Error; err != nil {
		return nil, err
	}
	if err := r.db.WithContext(ctx).Where("rfq_id = ?", id).Order("id").Find(&rfq.Lines).Error; err != nil {
		return nil, err
	}
	if err := r.db.WithContext(ctx).Where("rfq_id = ?", id).Find(&rfq.SupplierRFQs).Error; err != nil {
		return nil, err
	}
	return &rfq, nil
}

func (r *Repo) CreateRFQ(ctx context.Context, rfq *RFQ, lines []RFQLine, suppliers []RFQSupplier) error {
	return r.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		if err := tx.Create(rfq).Error; err != nil {
			return err
		}
		for i := range lines {
			lines[i].RFQID = rfq.ID
		}
		if len(lines) > 0 {
			if err := tx.Create(&lines).Error; err != nil {
				return err
			}
		}
		for i := range suppliers {
			suppliers[i].RFQID = rfq.ID
		}
		if len(suppliers) > 0 {
			if err := tx.Create(&suppliers).Error; err != nil {
				return err
			}
		}
		rfq.Lines = lines
		rfq.SupplierRFQs = suppliers
		return nil
	})
}

func (r *Repo) SaveRFQ(ctx context.Context, rfq *RFQ) error {
	return r.db.WithContext(ctx).Save(rfq).Error
}

func (r *Repo) SoftDeleteRFQ(ctx context.Context, id uint64) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&RFQ{}).Error
}

// MaxNoLike 取某前缀下最大单号(用于按日序号生成 rfq_no/quotation_no 等)。
func (r *Repo) MaxNoLike(ctx context.Context, model any, col, prefix string) (string, error) {
	var max string
	err := r.db.WithContext(ctx).Model(model).
		Where(col+" LIKE ?", prefix+"%").
		Order(col+" DESC").
		Limit(1).
		Pluck(col, &max).Error
	if err != nil {
		return "", err
	}
	return max, nil
}
