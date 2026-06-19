package sales

import (
	"context"
	"time"
)

func (s *Service) ListLeads(ctx context.Context, q ListQuery, offset, limit int) ([]Lead, int64, error) {
	return s.repo.ListLeads(ctx, q, offset, limit)
}

func (s *Service) GetLead(ctx context.Context, id uint64) (*Lead, error) {
	v, err := s.repo.GetLead(ctx, id)
	if err != nil {
		return nil, notFoundOr(err)
	}
	return v, nil
}

func (s *Service) CreateLead(ctx context.Context, in LeadCreateInput) (*Lead, error) {
	l := &Lead{
		CompanyName:     in.CompanyName,
		ContactName:     in.ContactName,
		ContactPhone:    in.ContactPhone,
		ContactEmail:    in.ContactEmail,
		ContactPosition: in.ContactPosition,
		Industry:        in.Industry,
		CompanySize:     in.CompanySize,
		Address:         in.Address,
		Website:         in.Website,
		Requirement:     in.Requirement,
		ProductInterest: in.ProductInterest,
		BudgetRange:     in.BudgetRange,
		ExpectedDate:    in.ExpectedDate,
		SourceID:        in.SourceID,
		SourceDetail:    in.SourceDetail,
		Status:          "NEW",
		OwnerID:         in.OwnerID,
		Score:           in.Score,
		Notes:           in.Notes,
	}
	if err := createWithCodeRetry(
		func() { l.LeadNo = genCode("LEAD") },
		func() error { return s.repo.CreateLead(ctx, l) },
	); err != nil {
		return nil, err
	}
	return l, nil
}

func (s *Service) UpdateLead(ctx context.Context, id uint64, in LeadUpdateInput) (*Lead, error) {
	l, err := s.GetLead(ctx, id)
	if err != nil {
		return nil, err
	}
	setStr(&l.CompanyName, in.CompanyName)
	setStr(&l.ContactName, in.ContactName)
	setStr(&l.ContactPhone, in.ContactPhone)
	setStr(&l.ContactEmail, in.ContactEmail)
	setStr(&l.ContactPosition, in.ContactPosition)
	setStr(&l.Industry, in.Industry)
	setStr(&l.CompanySize, in.CompanySize)
	setStr(&l.Address, in.Address)
	setStr(&l.Website, in.Website)
	setStr(&l.Requirement, in.Requirement)
	setStr(&l.ProductInterest, in.ProductInterest)
	setStr(&l.BudgetRange, in.BudgetRange)
	setStr(&l.SourceDetail, in.SourceDetail)
	setStr(&l.Status, in.Status)
	setStr(&l.Notes, in.Notes)
	if in.ExpectedDate != nil {
		l.ExpectedDate = in.ExpectedDate
	}
	if in.SourceID != nil {
		l.SourceID = in.SourceID
	}
	if in.OwnerID != nil {
		l.OwnerID = in.OwnerID
	}
	if in.Score != nil {
		l.Score = *in.Score
	}
	if err := s.repo.SaveLead(ctx, l); err != nil {
		return nil, err
	}
	return l, nil
}

func (s *Service) DeleteLead(ctx context.Context, id uint64) error {
	if _, err := s.GetLead(ctx, id); err != nil {
		return err
	}
	return s.repo.DeleteLead(ctx, id)
}

// ConvertLead 转化线索(忠实迁移 Django Lead.convert 的状态机部分)。
// 规则: 已 CONVERTED 不可重复转化;转化后置 CONVERTED 并记录 converted_at。
//
// TODO(port): Django convert 会跨模块创建 masterdata.Customer 并(可选)创建 Opportunity,
// 再回填 converted_customer/converted_opportunity。Customer 创建跨模块,本轮不实现;
// 此处仅: 若入参带 customer_id 则回填;若 create_opportunity 则在本上下文内创建 Opportunity 并回填。
func (s *Service) ConvertLead(ctx context.Context, id uint64, in LeadConvertInput) (*Lead, *Opportunity, error) {
	l, err := s.GetLead(ctx, id)
	if err != nil {
		return nil, nil, err
	}
	if l.Status == "CONVERTED" {
		return nil, nil, errWrap(ErrInvalidState, "线索已转化")
	}

	createCustomer := in.CreateCustomer == nil || *in.CreateCustomer
	if !createCustomer && in.CustomerID == nil {
		return nil, nil, errWrap(ErrValidation, "请创建新客户或选择已有客户")
	}

	var customerID *uint64
	if in.CustomerID != nil {
		customerID = in.CustomerID
	}
	// TODO(port): createCustomer=true 时应调用 masterdata 创建 Customer 并取回 ID。

	var opp *Opportunity
	createOpp := in.CreateOpportunity == nil || *in.CreateOpportunity
	if createOpp && customerID != nil {
		name := in.OpportunityName
		if name == "" {
			name = l.CompanyName + "商机"
		}
		opp = &Opportunity{
			Name:            name,
			CustomerID:      *customerID,
			ContactName:     l.ContactName,
			ContactPhone:    l.ContactPhone,
			Stage:           "QUALIFICATION",
			Priority:        "MEDIUM",
			Probability:     20,
			EstimatedAmount: in.EstimatedAmount,
			Requirement:     l.Requirement,
			OwnerID:         l.OwnerID,
		}
		opp.WeightedAmount = opp.EstimatedAmount * float64(opp.Probability) / 100
		if err := createWithCodeRetry(
			func() { opp.OpportunityNo = genCode("OPP") },
			func() error { return s.repo.CreateOpportunity(ctx, opp) },
		); err != nil {
			return nil, nil, err
		}
	}

	l.Status = "CONVERTED"
	l.ConvertedCustomerID = customerID
	if opp != nil {
		l.ConvertedOpportunityID = &opp.ID
	}
	now := time.Now().Format(time.RFC3339)
	l.ConvertedAt = &now
	if err := s.repo.SaveLead(ctx, l); err != nil {
		return nil, nil, err
	}
	return l, opp, nil
}

// setStr 在指针非空时把值写入目标(局部更新用)。
func setStr(dst *string, v *string) {
	if v != nil {
		*dst = *v
	}
}
