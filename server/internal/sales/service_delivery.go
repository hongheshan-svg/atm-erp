package sales

import "context"

func (s *Service) ListDeliveries(ctx context.Context, q ListQuery, offset, limit int) ([]DeliveryOrder, int64, error) {
	return s.repo.ListDeliveries(ctx, q, offset, limit)
}

func (s *Service) GetDelivery(ctx context.Context, id uint64) (*DeliveryOrder, error) {
	v, err := s.repo.GetDelivery(ctx, id)
	if err != nil {
		return nil, notFoundOr(err)
	}
	return v, nil
}

func (s *Service) CreateDelivery(ctx context.Context, in DeliveryCreateInput) (*DeliveryOrder, error) {
	d := &DeliveryOrder{
		SOID:            in.SOID,
		WarehouseID:     in.WarehouseID,
		DeliveryDate:    in.DeliveryDate,
		Status:          "DRAFT",
		ReceiverName:    in.ReceiverName,
		ReceiverPhone:   in.ReceiverPhone,
		ReceiverAddress: in.ReceiverAddress,
		PackagingType:   orDefault(in.PackagingType, "STANDARD"),
		Notes:           in.Notes,
	}
	if err := createWithCodeRetry(
		func() { d.DeliveryNo = genCode("DO") },
		func() error { return s.repo.CreateDelivery(ctx, d) },
	); err != nil {
		return nil, err
	}
	lines := make([]DeliveryOrderLine, 0, len(in.Lines))
	for _, l := range in.Lines {
		lines = append(lines, DeliveryOrderLine{
			DeliveryID: d.ID,
			SOLineID:   l.SOLineID,
			ItemID:     l.ItemID,
			Qty:        l.Qty,
			Notes:      l.Notes,
		})
	}
	if err := s.repo.CreateDeliveryLines(ctx, lines); err != nil {
		return nil, err
	}
	// TODO(port): Django 发货流程在审批通过/确认各环节回写 SalesOrderLine.delivered_qty 与
	// 订单 PARTIAL/COMPLETED 状态,并联动 inventory 出库。本轮仅建单,未回写发货数量与库存。
	return d, nil
}

func (s *Service) UpdateDelivery(ctx context.Context, id uint64, in DeliveryUpdateInput) (*DeliveryOrder, error) {
	d, err := s.GetDelivery(ctx, id)
	if err != nil {
		return nil, err
	}
	if in.WarehouseID != nil {
		d.WarehouseID = *in.WarehouseID
	}
	if in.DeliveryDate != nil {
		d.DeliveryDate = in.DeliveryDate
	}
	if in.ReceiverName != nil {
		d.ReceiverName = *in.ReceiverName
	}
	if in.ReceiverPhone != nil {
		d.ReceiverPhone = *in.ReceiverPhone
	}
	if in.ReceiverAddress != nil {
		d.ReceiverAddress = *in.ReceiverAddress
	}
	if in.PackagingType != nil {
		d.PackagingType = *in.PackagingType
	}
	if in.Status != nil {
		d.Status = *in.Status
	}
	if in.Notes != nil {
		d.Notes = *in.Notes
	}
	if err := s.repo.SaveDelivery(ctx, d); err != nil {
		return nil, err
	}
	return d, nil
}

func (s *Service) DeleteDelivery(ctx context.Context, id uint64) error {
	if _, err := s.GetDelivery(ctx, id); err != nil {
		return err
	}
	return s.repo.DeleteDelivery(ctx, id)
}

// SubmitDelivery 提交发货单进入审批流程。对齐 Django: 仅 DRAFT 可提交,置 PENDING。
//
// TODO(port): Django 发货审批由 core.workflow 流程配置驱动多步状态机
// (PREPARING→LOGISTICS_BOOKING→CUSTOMER_SIGNING→...→COMPLETED),
// 各 confirm_* 动作未在本轮迁移;待 workflow 模块就绪后补全完整状态机。
func (s *Service) SubmitDelivery(ctx context.Context, id uint64) (*DeliveryOrder, error) {
	d, err := s.GetDelivery(ctx, id)
	if err != nil {
		return nil, err
	}
	if d.Status != "DRAFT" {
		return nil, errWrap(ErrInvalidState, "只能提交草稿状态的发货单")
	}
	d.Status = "PENDING"
	if err := s.repo.SaveDelivery(ctx, d); err != nil {
		return nil, err
	}
	return d, nil
}
