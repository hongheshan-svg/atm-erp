package purchase

import (
	"context"
	"errors"
	"fmt"
	"strconv"
	"time"

	"gorm.io/gorm"
)

var (
	ErrNotFound  = errors.New("记录不存在")
	ErrBadStatus = errors.New("当前状态不允许该操作")
	ErrValidate  = errors.New("校验失败")
)

// Service 采购模块业务逻辑层。
type Service struct{ repo *Repo }

func NewService(repo *Repo) *Service { return &Service{repo: repo} }

// notFound 把 gorm.ErrRecordNotFound 归一化为 ErrNotFound。
func notFound(err error) error {
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return ErrNotFound
	}
	return err
}

// genDailyNo 生成 <prefix><yyyymmdd><4位序号> 形式编号。
// 对齐 Django RFQ/SupplierQuotation/QuotationComparison 的 save() 逻辑。
// TODO(verify): Django PR/PO/GR 走 generate_code(CodeRule),格式可配置;
// 本轮共库前先用日序号占位,切流前须接 CodeRule 以免与 Django 既有序号冲突。
func (s *Service) genDailyNo(ctx context.Context, m any, col, prefix string) (string, error) {
	dateStr := time.Now().Format("20060102")
	full := prefix + dateStr
	last, err := s.repo.MaxNoLike(ctx, m, col, full)
	if err != nil {
		return "", err
	}
	seq := 1
	if last != "" && len(last) >= 4 {
		if n, e := strconv.Atoi(last[len(last)-4:]); e == nil {
			seq = n + 1
		}
	}
	return fmt.Sprintf("%s%04d", full, seq), nil
}

// recalcAmounts 依据税率与不含税金额计算税额与含税总额(Django 一致:整数税率/100)。
func recalcAmounts(total float64, taxRate int) (tax, withTax float64) {
	tax = total * float64(taxRate) / 100
	return tax, total + tax
}

// ============================ 采购申请 ============================

func (s *Service) ListPR(ctx context.Context, q ListQuery, offset, limit int) ([]PurchaseRequest, int64, error) {
	return s.repo.ListPR(ctx, q, offset, limit)
}

func (s *Service) GetPR(ctx context.Context, id uint64) (*PurchaseRequest, error) {
	pr, err := s.repo.GetPR(ctx, id)
	return pr, notFound(err)
}

func (s *Service) CreatePR(ctx context.Context, in PRCreateInput) (*PurchaseRequest, error) {
	taxRate := 13
	if in.TaxRate != nil {
		taxRate = *in.TaxRate
	}
	pr := &PurchaseRequest{
		ProjectID:    in.ProjectID,
		SupplierID:   in.SupplierID,
		RequestorID:  in.RequestorID,
		RequestDate:  time.Now(),
		RequiredDate: in.RequiredDate,
		Status:       "DRAFT",
		TaxRate:      taxRate,
		Notes:        in.Notes,
	}
	no, err := s.genDailyNo(ctx, &PurchaseRequest{}, "request_no", "PR")
	if err != nil {
		return nil, err
	}
	pr.RequestNo = no

	lines := make([]PurchaseRequestLine, 0, len(in.Lines))
	var total float64
	for _, li := range in.Lines {
		amt := li.Qty * li.EstimatedPrice // 对齐 Django PurchaseRequestLine.save() line_amount = qty*estimated_price
		total += amt
		lines = append(lines, PurchaseRequestLine{
			ItemID:         li.ItemID,
			Qty:            li.Qty,
			EstimatedPrice: li.EstimatedPrice,
			LineAmount:     amt,
			RequiredDate:   li.RequiredDate,
			ProjectID:      li.ProjectID,
			BOMItemID:      li.BOMItemID,
			IsCritical:     li.IsCritical,
			IsLongLead:     li.IsLongLead,
			FunctionModule: li.FunctionModule,
			Notes:          li.Notes,
		})
	}
	pr.TotalAmount = total
	pr.TaxAmount, pr.TotalWithTax = recalcAmounts(total, taxRate)

	if err := s.repo.CreatePR(ctx, pr, lines); err != nil {
		return nil, err
	}
	return pr, nil
}

func (s *Service) UpdatePR(ctx context.Context, id uint64, in PRUpdateInput) (*PurchaseRequest, error) {
	pr, err := s.GetPR(ctx, id)
	if err != nil {
		return nil, err
	}
	// 对齐 Django:仅 DRAFT/REJECTED 可编辑(views.update 校验)。
	if pr.Status != "DRAFT" && pr.Status != "REJECTED" {
		return nil, fmt.Errorf("%w: 只能编辑草稿或已拒绝状态的采购申请", ErrBadStatus)
	}
	if in.ProjectID != nil {
		pr.ProjectID = in.ProjectID
	}
	if in.SupplierID != nil {
		pr.SupplierID = in.SupplierID
	}
	if in.RequiredDate != nil {
		pr.RequiredDate = *in.RequiredDate
	}
	if in.TaxRate != nil {
		pr.TaxRate = *in.TaxRate
		pr.TaxAmount, pr.TotalWithTax = recalcAmounts(pr.TotalAmount, pr.TaxRate)
	}
	if in.Notes != nil {
		pr.Notes = *in.Notes
	}
	if err := s.repo.SavePR(ctx, pr); err != nil {
		return nil, err
	}
	return pr, nil
}

func (s *Service) DeletePR(ctx context.Context, id uint64) error {
	pr, err := s.GetPR(ctx, id)
	if err != nil {
		return err
	}
	// 对齐 Django perform_destroy:只能删除草稿或已拒绝。
	if pr.Status != "DRAFT" && pr.Status != "REJECTED" {
		return fmt.Errorf("%w: 只能删除草稿或已拒绝状态的采购申请", ErrBadStatus)
	}
	return s.repo.SoftDeletePR(ctx, id)
}

// SubmitPR 提交采购申请。Django:DRAFT->SUBMITTED(走审批)或直批 APPROVED;
// 这里忠实迁移“提交即进入已提交”,审批联动(WorkflowEnforcement)留 TODO。
func (s *Service) SubmitPR(ctx context.Context, id uint64) (*PurchaseRequest, error) {
	pr, err := s.GetPR(ctx, id)
	if err != nil {
		return nil, err
	}
	if pr.Status != "DRAFT" && pr.Status != "REJECTED" {
		return nil, fmt.Errorf("%w: 只有草稿或已拒绝的申请可提交", ErrBadStatus)
	}
	// TODO(port): 预算校验 BudgetService.validate_purchase_request(project,total) 跨 projects/inventory 模块。
	// TODO(port): 审批流 WorkflowEnforcement —— 有审批配置时置 SUBMITTED,否则直接 APPROVED。
	pr.Status = "SUBMITTED"
	if err := s.repo.SavePR(ctx, pr); err != nil {
		return nil, err
	}
	return pr, nil
}

// ApprovePR 批准。Django:SUBMITTED/PENDING -> APPROVED。
func (s *Service) ApprovePR(ctx context.Context, id uint64) (*PurchaseRequest, error) {
	pr, err := s.GetPR(ctx, id)
	if err != nil {
		return nil, err
	}
	if pr.Status != "SUBMITTED" {
		return nil, fmt.Errorf("%w: 只有已提交的申请可批准", ErrBadStatus)
	}
	pr.Status = "APPROVED"
	if err := s.repo.SavePR(ctx, pr); err != nil {
		return nil, err
	}
	return pr, nil
}

// RejectPR 拒绝。
func (s *Service) RejectPR(ctx context.Context, id uint64) (*PurchaseRequest, error) {
	pr, err := s.GetPR(ctx, id)
	if err != nil {
		return nil, err
	}
	if pr.Status != "SUBMITTED" {
		return nil, fmt.Errorf("%w: 只有已提交的申请可拒绝", ErrBadStatus)
	}
	pr.Status = "REJECTED"
	if err := s.repo.SavePR(ctx, pr); err != nil {
		return nil, err
	}
	return pr, nil
}

// ============================ 采购订单 ============================

func (s *Service) ListPO(ctx context.Context, q ListQuery, offset, limit int) ([]PurchaseOrder, int64, error) {
	return s.repo.ListPO(ctx, q, offset, limit)
}

func (s *Service) GetPO(ctx context.Context, id uint64) (*PurchaseOrder, error) {
	po, err := s.repo.GetPO(ctx, id)
	return po, notFound(err)
}

func (s *Service) CreatePO(ctx context.Context, in POCreateInput) (*PurchaseOrder, error) {
	// TODO(port): 供应商黑名单校验(masterdata.Supplier.is_blacklisted)跨模块,本轮略。
	taxRate := 13
	if in.TaxRate != nil {
		taxRate = *in.TaxRate
	}
	po := &PurchaseOrder{
		SupplierID:         in.SupplierID,
		ProjectID:          in.ProjectID,
		OrderDate:          time.Now(),
		DeliveryDate:       in.DeliveryDate,
		Status:             "DRAFT",
		TaxRate:            taxRate,
		PaymentTerms:       orDefault(in.PaymentTerms, "NET30"),
		PaymentMethod:      orDefault(in.PaymentMethod, "WIRE"),
		PaymentTermsDetail: in.PaymentTermsDetail,
		Notes:              in.Notes,
	}
	no, err := s.genDailyNo(ctx, &PurchaseOrder{}, "order_no", "PO")
	if err != nil {
		return nil, err
	}
	po.OrderNo = no

	lines := make([]PurchaseOrderLine, 0, len(in.Lines))
	var total float64
	for _, li := range in.Lines {
		amt := li.Qty * li.UnitPrice // 对齐 Django PurchaseOrderLine.save() line_amount = qty*unit_price
		total += amt
		lines = append(lines, PurchaseOrderLine{
			ItemID:               li.ItemID,
			Qty:                  li.Qty,
			UnitPrice:            li.UnitPrice,
			LineAmount:           amt,
			BOMItemID:            li.BOMItemID,
			IsCritical:           li.IsCritical,
			IsLongLead:           li.IsLongLead,
			FunctionModule:       li.FunctionModule,
			DrawingNo:            li.DrawingNo,
			TechnicalRequirement: li.TechnicalRequirement,
			Notes:                li.Notes,
		})
	}
	po.TotalAmount = total
	po.TaxAmount, po.TotalWithTax = recalcAmounts(total, taxRate)

	if err := s.repo.CreatePO(ctx, po, lines); err != nil {
		return nil, err
	}
	return po, nil
}

func (s *Service) UpdatePO(ctx context.Context, id uint64, in POUpdateInput) (*PurchaseOrder, error) {
	po, err := s.GetPO(ctx, id)
	if err != nil {
		return nil, err
	}
	// 对齐 Django:仅 DRAFT/REJECTED 可编辑。
	if po.Status != "DRAFT" && po.Status != "REJECTED" {
		return nil, fmt.Errorf("%w: 只能编辑草稿或已拒绝状态的采购订单", ErrBadStatus)
	}
	if in.SupplierID != nil {
		po.SupplierID = *in.SupplierID
	}
	if in.ProjectID != nil {
		po.ProjectID = in.ProjectID
	}
	if in.DeliveryDate != nil {
		po.DeliveryDate = *in.DeliveryDate
	}
	if in.TaxRate != nil {
		po.TaxRate = *in.TaxRate
		po.TaxAmount, po.TotalWithTax = recalcAmounts(po.TotalAmount, po.TaxRate)
	}
	if in.PaymentTerms != nil {
		po.PaymentTerms = *in.PaymentTerms
	}
	if in.PaymentMethod != nil {
		po.PaymentMethod = *in.PaymentMethod
	}
	if in.PaymentTermsDetail != nil {
		po.PaymentTermsDetail = *in.PaymentTermsDetail
	}
	if in.Notes != nil {
		po.Notes = *in.Notes
	}
	if err := s.repo.SavePO(ctx, po); err != nil {
		return nil, err
	}
	return po, nil
}

func (s *Service) DeletePO(ctx context.Context, id uint64) error {
	po, err := s.GetPO(ctx, id)
	if err != nil {
		return err
	}
	// 对齐 Django perform_destroy:仅 DRAFT/REJECTED/CANCELLED 且无收货记录可删。
	if po.Status != "DRAFT" && po.Status != "REJECTED" && po.Status != "CANCELLED" {
		return fmt.Errorf("%w: 只能删除草稿、已拒绝或已取消状态的采购订单", ErrBadStatus)
	}
	has, err := s.repo.HasReceipts(ctx, id, false)
	if err != nil {
		return err
	}
	if has {
		return fmt.Errorf("%w: 该订单已有收货记录,不能删除", ErrValidate)
	}
	// TODO(port): 应付账款联动校验(finance.AccountPayable)跨模块,本轮略。
	return s.repo.SoftDeletePO(ctx, id)
}

// SubmitPO 提交订单待审批。Django:DRAFT->PENDING(有审批)或直接 CONFIRMED。
func (s *Service) SubmitPO(ctx context.Context, id uint64) (*PurchaseOrder, error) {
	po, err := s.GetPO(ctx, id)
	if err != nil {
		return nil, err
	}
	if po.Status != "DRAFT" && po.Status != "REJECTED" {
		return nil, fmt.Errorf("%w: 只有草稿或已拒绝订单可提交", ErrBadStatus)
	}
	// TODO(port): 审批流 —— 有审批配置置 PENDING,否则走 confirm 副作用。本轮置 PENDING。
	po.Status = "PENDING"
	if err := s.repo.SavePO(ctx, po); err != nil {
		return nil, err
	}
	return po, nil
}

// ConfirmPO 确认订单。Django _apply_confirm_side_effects:状态->CONFIRMED、生成应付、BOM 联动。
func (s *Service) ConfirmPO(ctx context.Context, id uint64) (*PurchaseOrder, error) {
	po, err := s.GetPO(ctx, id)
	if err != nil {
		return nil, err
	}
	if po.Status != "PENDING" && po.Status != "APPROVED" && po.Status != "DRAFT" {
		return nil, fmt.Errorf("%w: 当前状态不可确认", ErrBadStatus)
	}
	po.Status = "CONFIRMED"
	// TODO(port): 生成应付账款(finance.AccountPayable)、BOM order_status=ORDERED 联动,跨模块。
	if err := s.repo.SavePO(ctx, po); err != nil {
		return nil, err
	}
	return po, nil
}

// CancelPO 取消订单。Django:无已确认收货时 CONFIRMED/PENDING/APPROVED -> CANCELLED。
func (s *Service) CancelPO(ctx context.Context, id uint64) (*PurchaseOrder, error) {
	po, err := s.GetPO(ctx, id)
	if err != nil {
		return nil, err
	}
	if po.Status == "COMPLETED" || po.Status == "CANCELLED" {
		return nil, fmt.Errorf("%w: 已完成或已取消的订单不可取消", ErrBadStatus)
	}
	has, err := s.repo.HasReceipts(ctx, id, true)
	if err != nil {
		return nil, err
	}
	if has {
		return nil, fmt.Errorf("%w: 该订单已有确认收货,不能取消", ErrValidate)
	}
	po.Status = "CANCELLED"
	// TODO(port): BOM order_status 回退为 CANCELLED,跨模块。
	if err := s.repo.SavePO(ctx, po); err != nil {
		return nil, err
	}
	return po, nil
}

// ============================ 收货 ============================

func (s *Service) ListGR(ctx context.Context, q ListQuery, offset, limit int) ([]GoodsReceipt, int64, error) {
	return s.repo.ListGR(ctx, q, offset, limit)
}

func (s *Service) GetGR(ctx context.Context, id uint64) (*GoodsReceipt, error) {
	gr, err := s.repo.GetGR(ctx, id)
	return gr, notFound(err)
}

func (s *Service) CreateGR(ctx context.Context, in GRCreateInput) (*GoodsReceipt, error) {
	// 校验所属订单存在且状态允许收货。
	po, err := s.GetPO(ctx, in.POID)
	if err != nil {
		return nil, err
	}
	if po.Status != "CONFIRMED" && po.Status != "PARTIAL" {
		return nil, fmt.Errorf("%w: 只有已确认或部分收货的订单可收货", ErrBadStatus)
	}
	gr := &GoodsReceipt{
		POID:        in.POID,
		WarehouseID: in.WarehouseID,
		ReceiptDate: in.ReceiptDate,
		Status:      "DRAFT",
		Notes:       in.Notes,
	}
	no, err := s.genDailyNo(ctx, &GoodsReceipt{}, "receipt_no", "GR")
	if err != nil {
		return nil, err
	}
	gr.ReceiptNo = no

	lines := make([]GoodsReceiptLine, 0, len(in.Lines))
	for _, li := range in.Lines {
		lines = append(lines, GoodsReceiptLine{
			POLineID:      li.POLineID,
			ItemID:        li.ItemID,
			Qty:           li.Qty,
			QualityStatus: orDefault(li.QualityStatus, "PENDING"),
			Notes:         li.Notes,
		})
	}
	if err := s.repo.CreateGR(ctx, gr, lines); err != nil {
		return nil, err
	}
	return gr, nil
}

func (s *Service) UpdateGR(ctx context.Context, id uint64, in GRUpdateInput) (*GoodsReceipt, error) {
	gr, err := s.GetGR(ctx, id)
	if err != nil {
		return nil, err
	}
	if gr.Status != "DRAFT" {
		return nil, fmt.Errorf("%w: 只能编辑草稿状态的收货单", ErrBadStatus)
	}
	if in.WarehouseID != nil {
		gr.WarehouseID = *in.WarehouseID
	}
	if in.ReceiptDate != nil {
		gr.ReceiptDate = *in.ReceiptDate
	}
	if in.Notes != nil {
		gr.Notes = *in.Notes
	}
	if err := s.repo.SaveGR(ctx, gr); err != nil {
		return nil, err
	}
	return gr, nil
}

func (s *Service) DeleteGR(ctx context.Context, id uint64) error {
	gr, err := s.GetGR(ctx, id)
	if err != nil {
		return err
	}
	// 对齐 Django:只能删除草稿状态。
	if gr.Status != "DRAFT" {
		return fmt.Errorf("%w: 只能删除草稿状态的收货单,已确认收货单请先退货冲销", ErrBadStatus)
	}
	return s.repo.SoftDeleteGR(ctx, id)
}

// ConfirmGR 确认收货。忠实迁移 Django GoodsReceiptViewSet.confirm 的核心校验与回写:
//   - 草稿才能确认;质检 FAILED 行不入库不计收;超收拦截;
//   - 回写 PO 行 received_qty += qty;
//   - 全部行收满 -> PO COMPLETED,否则 PARTIAL;收货单 -> CONFIRMED。
//
// 库存移动(inventory.InventoryMovement)与 BOM received_qty 联动跨模块,标 TODO(port)。
func (s *Service) ConfirmGR(ctx context.Context, id uint64) (*GoodsReceipt, error) {
	gr, err := s.GetGR(ctx, id)
	if err != nil {
		return nil, err
	}
	if gr.Status != "DRAFT" {
		return nil, fmt.Errorf("%w: 只有草稿状态的收货单可确认", ErrBadStatus)
	}
	if len(gr.Lines) == 0 {
		return nil, fmt.Errorf("%w: 收货单无明细", ErrValidate)
	}

	err = s.repo.ConfirmGRTx(ctx, func(tx *gorm.DB) error {
		// 取订单全部明细做超收校验与完成判定。
		poLines, e := s.repo.POLines(ctx, gr.POID)
		if e != nil {
			return e
		}
		byID := make(map[uint64]*PurchaseOrderLine, len(poLines))
		for i := range poLines {
			byID[poLines[i].ID] = &poLines[i]
		}

		for _, gl := range gr.Lines {
			if gl.QualityStatus == "FAILED" {
				continue // 不合格不计收、不入库
			}
			pl, ok := byID[gl.POLineID]
			if !ok {
				return fmt.Errorf("%w: 收货行对应的订单明细不存在", ErrValidate)
			}
			remaining := pl.Qty - pl.ReceivedQty
			if gl.Qty > remaining {
				return fmt.Errorf("%w: 物料超收:剩余可收 %.2f,本次 %.2f", ErrValidate, remaining, gl.Qty)
			}
			// 回写已收量(并发安全用表达式自增)。
			if e := tx.Model(&PurchaseOrderLine{}).Where("id = ?", pl.ID).
				UpdateColumn("received_qty", gorm.Expr("received_qty + ?", gl.Qty)).Error; e != nil {
				return e
			}
			pl.ReceivedQty += gl.Qty
			// TODO(port): 写 inventory.InventoryMovement(IN);BOM received_qty 与 order_status 联动。
		}

		// 判定订单是否全部收满。
		allReceived := true
		for _, pl := range poLines {
			if pl.ReceivedQty < pl.Qty {
				allReceived = false
				break
			}
		}
		newPOStatus := "PARTIAL"
		if allReceived {
			newPOStatus = "COMPLETED"
		}
		if e := tx.Model(&PurchaseOrder{}).Where("id = ?", gr.POID).
			UpdateColumn("status", newPOStatus).Error; e != nil {
			return e
		}

		gr.Status = "CONFIRMED"
		return tx.Model(&GoodsReceipt{}).Where("id = ?", gr.ID).
			UpdateColumn("status", "CONFIRMED").Error
	})
	if err != nil {
		return nil, err
	}
	return gr, nil
}

// ============================ 询价 RFQ ============================

func (s *Service) ListRFQ(ctx context.Context, q ListQuery, offset, limit int) ([]RFQ, int64, error) {
	return s.repo.ListRFQ(ctx, q, offset, limit)
}

func (s *Service) GetRFQ(ctx context.Context, id uint64) (*RFQ, error) {
	rfq, err := s.repo.GetRFQ(ctx, id)
	return rfq, notFound(err)
}

func (s *Service) CreateRFQ(ctx context.Context, in RFQCreateInput) (*RFQ, error) {
	rfq := &RFQ{
		ProjectID:             in.ProjectID,
		RequestDate:           time.Now(),
		ResponseDeadline:      in.ResponseDeadline,
		Status:                "DRAFT",
		RFQType:               orDefault(in.RFQType, "NORMAL"),
		Priority:              orDefault(in.Priority, "NORMAL"),
		TemplateID:            in.TemplateID,
		TechnicalRequirements: in.TechnicalRequirements,
		QualityRequirements:   in.QualityRequirements,
		PackagingRequirements: in.PackagingRequirements,
		DeliveryRequirements:  in.DeliveryRequirements,
		Notes:                 in.Notes,
	}
	no, err := s.genDailyNo(ctx, &RFQ{}, "rfq_no", "RFQ")
	if err != nil {
		return nil, err
	}
	rfq.RFQNo = no

	lines := make([]RFQLine, 0, len(in.Lines))
	for _, li := range in.Lines {
		specs := li.TechnicalSpecs
		if specs == "" {
			specs = "{}" // JSONField default=dict
		}
		lines = append(lines, RFQLine{
			ItemID:         li.ItemID,
			Qty:            li.Qty,
			RequiredDate:   li.RequiredDate,
			Specifications: li.Specifications,
			BOMItemID:      li.BOMItemID,
			DrawingID:      li.DrawingID,
			DrawingNo:      li.DrawingNo,
			DrawingVersion: li.DrawingVersion,
			TechnicalSpecs: specs,
			IsCritical:     li.IsCritical,
			IsLongLead:     li.IsLongLead,
			IsCustom:       li.IsCustom,
			TargetPrice:    li.TargetPrice,
		})
	}
	suppliers := make([]RFQSupplier, 0, len(in.SupplierIDs))
	for _, sid := range in.SupplierIDs {
		suppliers = append(suppliers, RFQSupplier{SupplierID: sid})
	}
	if err := s.repo.CreateRFQ(ctx, rfq, lines, suppliers); err != nil {
		return nil, err
	}
	return rfq, nil
}

func (s *Service) UpdateRFQ(ctx context.Context, id uint64, in RFQUpdateInput) (*RFQ, error) {
	rfq, err := s.GetRFQ(ctx, id)
	if err != nil {
		return nil, err
	}
	if rfq.Status != "DRAFT" {
		return nil, fmt.Errorf("%w: 只能编辑草稿状态的询价单", ErrBadStatus)
	}
	if in.ProjectID != nil {
		rfq.ProjectID = in.ProjectID
	}
	if in.ResponseDeadline != nil {
		rfq.ResponseDeadline = *in.ResponseDeadline
	}
	if in.RFQType != nil {
		rfq.RFQType = *in.RFQType
	}
	if in.Priority != nil {
		rfq.Priority = *in.Priority
	}
	if in.TechnicalRequirements != nil {
		rfq.TechnicalRequirements = *in.TechnicalRequirements
	}
	if in.QualityRequirements != nil {
		rfq.QualityRequirements = *in.QualityRequirements
	}
	if in.PackagingRequirements != nil {
		rfq.PackagingRequirements = *in.PackagingRequirements
	}
	if in.DeliveryRequirements != nil {
		rfq.DeliveryRequirements = *in.DeliveryRequirements
	}
	if in.Notes != nil {
		rfq.Notes = *in.Notes
	}
	if err := s.repo.SaveRFQ(ctx, rfq); err != nil {
		return nil, err
	}
	return rfq, nil
}

func (s *Service) DeleteRFQ(ctx context.Context, id uint64) error {
	rfq, err := s.GetRFQ(ctx, id)
	if err != nil {
		return err
	}
	if rfq.Status != "DRAFT" {
		return fmt.Errorf("%w: 只能删除草稿状态的询价单", ErrBadStatus)
	}
	return s.repo.SoftDeleteRFQ(ctx, id)
}

// SendRFQ 发送询价给供应商。Django send_to_suppliers:DRAFT->SENT,标记发送时间。
// 入参 supplierIDs 为空则发给创建时已挂的供应商。
func (s *Service) SendRFQ(ctx context.Context, id uint64, supplierIDs []uint64) (*RFQ, error) {
	rfq, err := s.GetRFQ(ctx, id)
	if err != nil {
		return nil, err
	}
	if rfq.Status != "DRAFT" {
		return nil, fmt.Errorf("%w: 只有草稿状态的询价单可发送", ErrBadStatus)
	}
	if len(rfq.SupplierRFQs) == 0 && len(supplierIDs) == 0 {
		return nil, fmt.Errorf("%w: 请先添加询价供应商", ErrValidate)
	}
	err = s.repo.ConfirmGRTx(ctx, func(tx *gorm.DB) error {
		now := time.Now()
		// 追加本次传入但尚未挂接的供应商。
		exist := make(map[uint64]bool)
		for _, rs := range rfq.SupplierRFQs {
			exist[rs.SupplierID] = true
		}
		for _, sid := range supplierIDs {
			if !exist[sid] {
				if e := tx.Create(&RFQSupplier{RFQID: rfq.ID, SupplierID: sid, SentDate: &now}).Error; e != nil {
					return e
				}
			}
		}
		// 已挂接的标记发送时间。
		if e := tx.Model(&RFQSupplier{}).Where("rfq_id = ?", rfq.ID).
			UpdateColumn("sent_date", now).Error; e != nil {
			return e
		}
		rfq.Status = "SENT"
		return tx.Model(&RFQ{}).Where("id = ?", rfq.ID).UpdateColumn("status", "SENT").Error
	})
	if err != nil {
		return nil, err
	}
	// TODO(port): 通知供应商(core.Notification / supplier_portal),跨模块。
	return rfq, nil
}

func orDefault(v, def string) string {
	if v == "" {
		return def
	}
	return v
}
