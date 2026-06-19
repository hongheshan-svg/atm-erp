package sales

import "context"

func (s *Service) ListSalesOrders(ctx context.Context, q ListQuery, offset, limit int) ([]SalesOrder, int64, error) {
	return s.repo.ListSalesOrders(ctx, q, offset, limit)
}

func (s *Service) GetSalesOrder(ctx context.Context, id uint64) (*SalesOrder, error) {
	v, err := s.repo.GetSalesOrder(ctx, id)
	if err != nil {
		return nil, notFoundOr(err)
	}
	return v, nil
}

func (s *Service) CreateSalesOrder(ctx context.Context, in SalesOrderCreateInput) (*SalesOrder, error) {
	taxRate := defaultTaxRate
	if in.TaxRate != nil {
		taxRate = *in.TaxRate
	}
	so := &SalesOrder{
		OrderNo:         genCode("SO"),
		CustomerOrderNo: in.CustomerOrderNo,
		CustomerID:      in.CustomerID,
		ProjectID:       in.ProjectID,
		DeliveryDate:    in.DeliveryDate,
		Status:          "DRAFT",
		TaxRate:         taxRate,
		PaymentTerms:    orDefault(in.PaymentTerms, "M_30_30_30_10"),
		PaymentMethod:   orDefault(in.PaymentMethod, "WIRE"),
		Notes:           in.Notes,
	}
	if err := s.repo.CreateSalesOrder(ctx, so); err != nil {
		return nil, err
	}
	var total float64
	lines := make([]SalesOrderLine, 0, len(in.Lines))
	for _, l := range in.Lines {
		amt := l.Qty * l.UnitPrice
		total += amt
		lines = append(lines, SalesOrderLine{
			SOID:       so.ID,
			ItemID:     l.ItemID,
			CustomName: l.CustomName,
			CustomSpec: l.CustomSpec,
			CustomUnit: l.CustomUnit,
			Qty:        l.Qty,
			UnitPrice:  l.UnitPrice,
			LineAmount: amt,
			Notes:      l.Notes,
		})
	}
	if err := s.repo.CreateSalesOrderLines(ctx, lines); err != nil {
		return nil, err
	}
	so.TotalAmount = total
	so.TaxAmount, so.TotalWithTax = computeTotals(total, so.TaxRate)
	if err := s.repo.SaveSalesOrder(ctx, so); err != nil {
		return nil, err
	}
	return so, nil
}

func (s *Service) UpdateSalesOrder(ctx context.Context, id uint64, in SalesOrderUpdateInput) (*SalesOrder, error) {
	so, err := s.GetSalesOrder(ctx, id)
	if err != nil {
		return nil, err
	}
	if in.CustomerID != nil {
		so.CustomerID = *in.CustomerID
	}
	if in.ProjectID != nil {
		so.ProjectID = in.ProjectID
	}
	if in.CustomerOrderNo != nil {
		so.CustomerOrderNo = *in.CustomerOrderNo
	}
	if in.DeliveryDate != nil {
		so.DeliveryDate = in.DeliveryDate
	}
	if in.TaxRate != nil {
		so.TaxRate = *in.TaxRate
		so.TaxAmount, so.TotalWithTax = computeTotals(so.TotalAmount, so.TaxRate)
	}
	if in.PaymentTerms != nil {
		so.PaymentTerms = *in.PaymentTerms
	}
	if in.PaymentMethod != nil {
		so.PaymentMethod = *in.PaymentMethod
	}
	if in.Status != nil {
		so.Status = *in.Status
	}
	if in.Notes != nil {
		so.Notes = *in.Notes
	}
	if err := s.repo.SaveSalesOrder(ctx, so); err != nil {
		return nil, err
	}
	return so, nil
}

func (s *Service) DeleteSalesOrder(ctx context.Context, id uint64) error {
	if _, err := s.GetSalesOrder(ctx, id); err != nil {
		return err
	}
	return s.repo.DeleteSalesOrder(ctx, id)
}

// SubmitSalesOrder 提交订单审批。对齐 Django: 仅 DRAFT/REJECTED 可提交。
//
// TODO(port): 同 Quotation — 接入 core.workflow 后区分「有流程→PENDING / 无流程→直接 confirm」。
func (s *Service) SubmitSalesOrder(ctx context.Context, id uint64) (*SalesOrder, error) {
	so, err := s.GetSalesOrder(ctx, id)
	if err != nil {
		return nil, err
	}
	if so.Status != "DRAFT" && so.Status != "REJECTED" {
		return nil, ErrInvalidState
	}
	so.Status = "PENDING"
	if err := s.repo.SaveSalesOrder(ctx, so); err != nil {
		return nil, err
	}
	return so, nil
}

// ConfirmSalesOrder 直接确认订单(忠实迁移 Django confirm/_do_confirm 的状态机部分)。
// 规则: 仅 DRAFT/PENDING 可确认,置 CONFIRMED。
//
// TODO(port): Django 在确认前调用 masterdata.check_customer_credit_for_order 做信用/客户状态校验,
// 确认后调用 sales.services.create_sales_order_receivables 生成应收账款+付款计划。
// 二者均跨模块(masterdata/finance),本轮未迁移;切流前必须补齐,否则确认不产生应收。
func (s *Service) ConfirmSalesOrder(ctx context.Context, id uint64) (*SalesOrder, error) {
	so, err := s.GetSalesOrder(ctx, id)
	if err != nil {
		return nil, err
	}
	if so.Status != "DRAFT" && so.Status != "PENDING" {
		return nil, ErrInvalidState
	}
	so.Status = "CONFIRMED"
	if err := s.repo.SaveSalesOrder(ctx, so); err != nil {
		return nil, err
	}
	return so, nil
}

// CancelSalesOrder 取消订单(忠实迁移 Django cancel)。
// 规则: COMPLETED/CANCELLED 不可取消;存在已提交/在途发货单时禁止取消。
//
// TODO(port): Django 取消时还会撤销关联应收账款/未收款付款计划、作废草稿发货单、
// 撤回活跃审批工作流(均跨 finance/workflow 模块),本轮仅迁移状态机与发货校验。
func (s *Service) CancelSalesOrder(ctx context.Context, id uint64) (*SalesOrder, error) {
	so, err := s.GetSalesOrder(ctx, id)
	if err != nil {
		return nil, err
	}
	if so.Status == "COMPLETED" || so.Status == "CANCELLED" {
		return nil, errWrap(ErrInvalidState, "无法取消已完成或已取消的订单")
	}
	active, err := s.repo.HasActiveDeliveries(ctx, so.ID)
	if err != nil {
		return nil, err
	}
	if active {
		return nil, errWrap(ErrInvalidState, "该订单存在已提交/在途的发货单，请先拒绝或退货后再取消")
	}
	so.Status = "CANCELLED"
	if err := s.repo.SaveSalesOrder(ctx, so); err != nil {
		return nil, err
	}
	return so, nil
}

// ReturnSalesOrderToDraft 已确认订单退回草稿(忠实迁移 Django return_to_draft)。
// 规则: 仅 CONFIRMED 可退回;已有发货记录则禁止。
func (s *Service) ReturnSalesOrderToDraft(ctx context.Context, id uint64) (*SalesOrder, error) {
	so, err := s.GetSalesOrder(ctx, id)
	if err != nil {
		return nil, err
	}
	if so.Status != "CONFIRMED" {
		return nil, errWrap(ErrInvalidState, "只能将已确认状态的订单退回草稿")
	}
	has, err := s.repo.HasAnyDeliveries(ctx, so.ID)
	if err != nil {
		return nil, err
	}
	if has {
		return nil, errWrap(ErrInvalidState, "订单已有发货记录，无法退回草稿")
	}
	so.Status = "DRAFT"
	if err := s.repo.SaveSalesOrder(ctx, so); err != nil {
		return nil, err
	}
	return so, nil
}

func orDefault(v, def string) string {
	if v == "" {
		return def
	}
	return v
}
