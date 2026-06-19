package sales

import "context"

func (s *Service) ListOpportunities(ctx context.Context, q ListQuery, offset, limit int) ([]Opportunity, int64, error) {
	return s.repo.ListOpportunities(ctx, q, offset, limit)
}

func (s *Service) GetOpportunity(ctx context.Context, id uint64) (*Opportunity, error) {
	v, err := s.repo.GetOpportunity(ctx, id)
	if err != nil {
		return nil, notFoundOr(err)
	}
	return v, nil
}

func (s *Service) CreateOpportunity(ctx context.Context, in OpportunityCreateInput) (*Opportunity, error) {
	probability := 20
	if in.Probability != nil {
		probability = *in.Probability
	}
	o := &Opportunity{
		OpportunityNo:         genCode("OPP"),
		Name:                  in.Name,
		CustomerID:            in.CustomerID,
		ContactName:           in.ContactName,
		ContactPhone:          in.ContactPhone,
		Stage:                 orDefault(in.Stage, "QUALIFICATION"),
		Priority:              orDefault(in.Priority, "MEDIUM"),
		Probability:           probability,
		EstimatedAmount:       in.EstimatedAmount,
		ProductType:           in.ProductType,
		Requirement:           in.Requirement,
		TechnicalRequirements: in.TechnicalRequirements,
		ExpectedCloseDate:     in.ExpectedCloseDate,
		ExpectedDeliveryDate:  in.ExpectedDeliveryDate,
		OwnerID:               in.OwnerID,
		Competitors:           in.Competitors,
		CompetitiveAdvantage:  in.CompetitiveAdvantage,
		Notes:                 in.Notes,
	}
	// 加权金额 = 预估金额 * 概率 / 100(对齐 Django Opportunity.save)。
	o.WeightedAmount = o.EstimatedAmount * float64(o.Probability) / 100
	if err := s.repo.CreateOpportunity(ctx, o); err != nil {
		return nil, err
	}
	return o, nil
}

func (s *Service) UpdateOpportunity(ctx context.Context, id uint64, in OpportunityUpdateInput) (*Opportunity, error) {
	o, err := s.GetOpportunity(ctx, id)
	if err != nil {
		return nil, err
	}
	setStr(&o.Name, in.Name)
	if in.CustomerID != nil {
		o.CustomerID = *in.CustomerID
	}
	setStr(&o.ContactName, in.ContactName)
	setStr(&o.ContactPhone, in.ContactPhone)
	setStr(&o.Stage, in.Stage)
	setStr(&o.Priority, in.Priority)
	if in.Probability != nil {
		o.Probability = *in.Probability
	}
	if in.EstimatedAmount != nil {
		o.EstimatedAmount = *in.EstimatedAmount
	}
	setStr(&o.ProductType, in.ProductType)
	setStr(&o.Requirement, in.Requirement)
	setStr(&o.TechnicalRequirements, in.TechnicalRequirements)
	if in.ExpectedCloseDate != nil {
		o.ExpectedCloseDate = in.ExpectedCloseDate
	}
	if in.ExpectedDeliveryDate != nil {
		o.ExpectedDeliveryDate = in.ExpectedDeliveryDate
	}
	if in.OwnerID != nil {
		o.OwnerID = in.OwnerID
	}
	setStr(&o.Competitors, in.Competitors)
	setStr(&o.CompetitiveAdvantage, in.CompetitiveAdvantage)
	setStr(&o.LostReason, in.LostReason)
	setStr(&o.Notes, in.Notes)
	// 概率或金额变化后回算加权金额。
	o.WeightedAmount = o.EstimatedAmount * float64(o.Probability) / 100
	if err := s.repo.SaveOpportunity(ctx, o); err != nil {
		return nil, err
	}
	return o, nil
}

func (s *Service) DeleteOpportunity(ctx context.Context, id uint64) error {
	if _, err := s.GetOpportunity(ctx, id); err != nil {
		return err
	}
	return s.repo.DeleteOpportunity(ctx, id)
}
