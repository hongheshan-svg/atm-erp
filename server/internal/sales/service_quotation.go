package sales

import "context"

func (s *Service) ListQuotations(ctx context.Context, q ListQuery, offset, limit int) ([]Quotation, int64, error) {
	return s.repo.ListQuotations(ctx, q, offset, limit)
}

func (s *Service) GetQuotation(ctx context.Context, id uint64) (*Quotation, error) {
	v, err := s.repo.GetQuotation(ctx, id)
	if err != nil {
		return nil, notFoundOr(err)
	}
	return v, nil
}

func (s *Service) CreateQuotation(ctx context.Context, in QuotationCreateInput) (*Quotation, error) {
	taxRate := defaultTaxRate
	if in.TaxRate != nil {
		taxRate = *in.TaxRate
	}
	q := &Quotation{
		CustomerID: in.CustomerID,
		ProjectID:  in.ProjectID,
		ValidUntil: in.ValidUntil,
		Status:     "DRAFT",
		Version:    1,
		TaxRate:    taxRate,
		Notes:      in.Notes,
	}
	if err := createWithCodeRetry(
		func() { q.QuoteNo = genCode("QT") },
		func() error { return s.repo.CreateQuotation(ctx, q) },
	); err != nil {
		return nil, err
	}
	// 明细 + 金额回算(line_amount = qty*unit_price,对齐 Django Line.save)。
	var total float64
	lines := make([]QuotationLine, 0, len(in.Lines))
	for _, l := range in.Lines {
		amt := l.Qty * l.UnitPrice
		total += amt
		lines = append(lines, QuotationLine{
			QuotationID: q.ID,
			ItemID:      l.ItemID,
			CustomName:  l.CustomName,
			CustomSpec:  l.CustomSpec,
			CustomUnit:  l.CustomUnit,
			Qty:         l.Qty,
			UnitPrice:   l.UnitPrice,
			LineAmount:  amt,
			Notes:       l.Notes,
		})
	}
	if err := s.repo.CreateQuotationLines(ctx, lines); err != nil {
		return nil, err
	}
	q.TotalAmount = total
	q.TaxAmount, q.TotalWithTax = computeTotals(total, q.TaxRate)
	if err := s.repo.SaveQuotation(ctx, q); err != nil {
		return nil, err
	}
	return q, nil
}

func (s *Service) UpdateQuotation(ctx context.Context, id uint64, in QuotationUpdateInput) (*Quotation, error) {
	q, err := s.GetQuotation(ctx, id)
	if err != nil {
		return nil, err
	}
	if in.CustomerID != nil {
		q.CustomerID = *in.CustomerID
	}
	if in.ProjectID != nil {
		q.ProjectID = in.ProjectID
	}
	if in.ValidUntil != nil {
		q.ValidUntil = in.ValidUntil
	}
	if in.TaxRate != nil {
		q.TaxRate = *in.TaxRate
		q.TaxAmount, q.TotalWithTax = computeTotals(q.TotalAmount, q.TaxRate)
	}
	if in.Status != nil {
		q.Status = *in.Status
	}
	if in.Notes != nil {
		q.Notes = *in.Notes
	}
	if err := s.repo.SaveQuotation(ctx, q); err != nil {
		return nil, err
	}
	return q, nil
}

func (s *Service) DeleteQuotation(ctx context.Context, id uint64) error {
	if _, err := s.GetQuotation(ctx, id); err != nil {
		return err
	}
	return s.repo.DeleteQuotation(ctx, id)
}

// SubmitQuotation 提交报价审批。对齐 Django: 仅 DRAFT/REJECTED 可提交。
//
// TODO(port): Django 通过 core.workflow.WorkflowService.start_workflow 启动审批,
// 有流程则置 PENDING,无流程则直接 APPROVED;工作流异常须 fail-closed(返回 503,不自动通过)。
// 本轮无 workflow 包依赖,保守置为 PENDING(等待审批中心);待 workflow 模块就绪后回填判定。
func (s *Service) SubmitQuotation(ctx context.Context, id uint64) (*Quotation, error) {
	q, err := s.GetQuotation(ctx, id)
	if err != nil {
		return nil, err
	}
	if q.Status != "DRAFT" && q.Status != "REJECTED" {
		return nil, ErrInvalidState
	}
	q.Status = "PENDING"
	if err := s.repo.SaveQuotation(ctx, q); err != nil {
		return nil, err
	}
	return q, nil
}

// ConvertToSO 报价转销售订单(忠实迁移 Django convert_to_so)。
// 规则: 仅 APPROVED/SENT 可转;必须关联项目;交货日期取入参回退报价有效期;
// 复制明细并回算订单金额;成功后报价置 ACCEPTED 防重复转换。
func (s *Service) ConvertToSO(ctx context.Context, id uint64, in ConvertToSOInput) (*SalesOrder, error) {
	q, err := s.GetQuotation(ctx, id)
	if err != nil {
		return nil, err
	}
	if q.Status != "APPROVED" && q.Status != "SENT" {
		return nil, ErrInvalidState
	}
	if q.ProjectID == nil {
		return nil, ErrProjectNeeded
	}
	deliveryDate := in.DeliveryDate
	if deliveryDate == nil {
		deliveryDate = q.ValidUntil
	}
	if deliveryDate == nil {
		return nil, errWrap(ErrValidation, "请指定交货日期")
	}

	srcLines, err := s.repo.ListQuotationLines(ctx, q.ID)
	if err != nil {
		return nil, err
	}

	so := &SalesOrder{
		CustomerID:    q.CustomerID,
		ProjectID:     q.ProjectID,
		DeliveryDate:  deliveryDate,
		Status:        "DRAFT",
		TaxRate:       q.TaxRate,
		PaymentTerms:  "M_30_30_30_10",
		PaymentMethod: "WIRE",
	}
	// TODO(verify): Django convert_to_so 未用显式事务包裹本 Go 实现的多步写;
	// 接入 db 事务封装后改为 r.db.Transaction(...) 保证原子性。
	if err := createWithCodeRetry(
		func() { so.OrderNo = genCode("SO") },
		func() error { return s.repo.CreateSalesOrder(ctx, so) },
	); err != nil {
		return nil, err
	}
	var total float64
	dstLines := make([]SalesOrderLine, 0, len(srcLines))
	for _, l := range srcLines {
		amt := l.Qty * l.UnitPrice
		total += amt
		dstLines = append(dstLines, SalesOrderLine{
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
	if err := s.repo.CreateSalesOrderLines(ctx, dstLines); err != nil {
		return nil, err
	}
	so.TotalAmount = total
	so.TaxAmount, so.TotalWithTax = computeTotals(total, so.TaxRate)
	if err := s.repo.SaveSalesOrder(ctx, so); err != nil {
		return nil, err
	}

	q.Status = "ACCEPTED"
	if err := s.repo.SaveQuotation(ctx, q); err != nil {
		return nil, err
	}
	return so, nil
}
