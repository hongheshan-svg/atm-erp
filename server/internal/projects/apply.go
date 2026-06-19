package projects

// applyBOMUpdate 把 BOMUpdateInput 中非 nil 字段套用到实体(指针区分未传/置零)。
func applyBOMUpdate(b *ProjectBOM, in BOMUpdateInput) {
	if in.ItemCode != nil {
		b.ItemCode = *in.ItemCode
	}
	if in.ItemProperty != nil {
		b.ItemProperty = *in.ItemProperty
	}
	if in.Status != nil {
		b.Status = *in.Status
	}
	if in.Priority != nil {
		b.Priority = *in.Priority
	}
	if in.PlannedQty != nil {
		b.PlannedQty = *in.PlannedQty
	}
	if in.ActualQty != nil {
		b.ActualQty = *in.ActualQty
	}
	if in.UnitQty != nil {
		b.UnitQty = *in.UnitQty
	}
	if in.ScrapRate != nil {
		b.ScrapRate = *in.ScrapRate
	}
	if in.EstimatedCost != nil {
		b.EstimatedCost = *in.EstimatedCost
	}
	if in.TargetCost != nil {
		b.TargetCost = in.TargetCost
	}
	if in.ActualCost != nil {
		b.ActualCost = *in.ActualCost
	}
	if in.VersionBrand != nil {
		b.VersionBrand = *in.VersionBrand
	}
	if in.HasDrawing != nil {
		b.HasDrawing = *in.HasDrawing
	}
	if in.DrawingID != nil {
		b.DrawingID = in.DrawingID
	}
	if in.DrawingNo != nil {
		b.DrawingNo = *in.DrawingNo
	}
	if in.DrawingVersion != nil {
		b.DrawingVersion = *in.DrawingVersion
	}
	if in.MaterialSpec != nil {
		b.MaterialSpec = *in.MaterialSpec
	}
	if in.SurfaceTreatment != nil {
		b.SurfaceTreatment = *in.SurfaceTreatment
	}
	if in.TechnicalRequirement != nil {
		b.TechnicalRequirement = *in.TechnicalRequirement
	}
	if in.WorkCenterID != nil {
		b.WorkCenterID = in.WorkCenterID
	}
	if in.ProcessID != nil {
		b.ProcessID = in.ProcessID
	}
	if in.AssemblySequence != nil {
		b.AssemblySequence = *in.AssemblySequence
	}
	if in.AssemblyInstruction != nil {
		b.AssemblyInstruction = *in.AssemblyInstruction
	}
	if in.RequirementIDRef != nil {
		b.RequirementIDRef = in.RequirementIDRef
	}
	if in.FunctionModule != nil {
		b.FunctionModule = *in.FunctionModule
	}
	if in.RequiredDate != nil {
		b.RequiredDate = in.RequiredDate
	}
	if in.RequesterID != nil {
		b.RequesterID = in.RequesterID
	}
	if in.Description != nil {
		b.Description = *in.Description
	}
	if in.Notes != nil {
		b.Notes = *in.Notes
	}
	if in.OrderStatus != nil {
		b.OrderStatus = *in.OrderStatus
	}
	if in.SupplierID != nil {
		b.SupplierID = in.SupplierID
	}
	if in.OrderedQty != nil {
		b.OrderedQty = *in.OrderedQty
	}
	if in.ReceivedQty != nil {
		b.ReceivedQty = *in.ReceivedQty
	}
	if in.IssuedQty != nil {
		b.IssuedQty = *in.IssuedQty
	}
	if in.ReservedQty != nil {
		b.ReservedQty = *in.ReservedQty
	}
	if in.ShippedQty != nil {
		b.ShippedQty = *in.ShippedQty
	}
	if in.ReturnedQty != nil {
		b.ReturnedQty = *in.ReturnedQty
	}
	if in.InspectionRequired != nil {
		b.InspectionRequired = *in.InspectionRequired
	}
	if in.InspectionPassed != nil {
		b.InspectionPassed = in.InspectionPassed
	}
	if in.InspectionNotes != nil {
		b.InspectionNotes = *in.InspectionNotes
	}
	if in.ParentID != nil {
		b.ParentID = in.ParentID
	}
	if in.Level != nil {
		b.Level = *in.Level
	}
	if in.SortOrder != nil {
		b.SortOrder = *in.SortOrder
	}
	if in.IsCritical != nil {
		b.IsCritical = *in.IsCritical
	}
	if in.IsLongLead != nil {
		b.IsLongLead = *in.IsLongLead
	}
	if in.AssemblyCode != nil {
		b.AssemblyCode = *in.AssemblyCode
	}
	if in.IsCustomPart != nil {
		b.IsCustomPart = *in.IsCustomPart
	}
	if in.CustomPartType != nil {
		b.CustomPartType = *in.CustomPartType
	}
	if in.CadFileName != nil {
		b.CadFileName = *in.CadFileName
	}
	if in.CadSoftware != nil {
		b.CadSoftware = *in.CadSoftware
	}
	if in.QuoteStatus != nil {
		b.QuoteStatus = *in.QuoteStatus
	}
	if in.QuoteSupplierID != nil {
		b.QuoteSupplierID = in.QuoteSupplierID
	}
	if in.PriceWithTax != nil {
		b.PriceWithTax = in.PriceWithTax
	}
	if in.PriceWithoutTax != nil {
		b.PriceWithoutTax = in.PriceWithoutTax
	}
	if in.TaxRate != nil {
		b.TaxRate = in.TaxRate
	}
	if in.QuoteDeliveryDays != nil {
		b.QuoteDeliveryDays = in.QuoteDeliveryDays
	}
	if in.QuoteDate != nil {
		b.QuoteDate = in.QuoteDate
	}
	if in.QuoteNotes != nil {
		b.QuoteNotes = *in.QuoteNotes
	}
	if in.ExtraFields != nil {
		b.ExtraFields = *in.ExtraFields
	}
}

// applyDrawingUpdate 把 DrawingUpdateInput 中非 nil 字段套用到实体。
func applyDrawingUpdate(d *Drawing, in DrawingUpdateInput) {
	if in.Name != nil {
		d.Name = *in.Name
	}
	if in.Version != nil {
		d.Version = *in.Version
	}
	if in.Revision != nil {
		d.Revision = *in.Revision
	}
	if in.PartType != nil {
		d.PartType = *in.PartType
	}
	if in.ProjectID != nil {
		d.ProjectID = in.ProjectID
	}
	if in.ItemID != nil {
		d.ItemID = in.ItemID
	}
	if in.BomItemID != nil {
		d.BomItemID = in.BomItemID
	}
	if in.ParentDrawingID != nil {
		d.ParentDrawingID = in.ParentDrawingID
	}
	if in.Material != nil {
		d.Material = *in.Material
	}
	if in.Weight != nil {
		d.Weight = in.Weight
	}
	if in.SurfaceTreatment != nil {
		d.SurfaceTreatment = *in.SurfaceTreatment
	}
	if in.HeatTreatment != nil {
		d.HeatTreatment = *in.HeatTreatment
	}
	if in.ToleranceGrade != nil {
		d.ToleranceGrade = *in.ToleranceGrade
	}
	if in.Roughness != nil {
		d.Roughness = *in.Roughness
	}
	if in.CadFileName != nil {
		d.CadFileName = *in.CadFileName
	}
	if in.CadSoftware != nil {
		d.CadSoftware = *in.CadSoftware
	}
	if in.FileType != nil {
		d.FileType = *in.FileType
	}
	if in.FilePath != nil {
		d.FilePath = *in.FilePath
	}
	if in.FileSize != nil {
		d.FileSize = *in.FileSize
	}
	if in.PublicSharePath != nil {
		d.PublicSharePath = *in.PublicSharePath
	}
	if in.DesignerID != nil {
		d.DesignerID = in.DesignerID
	}
	if in.ReviewerID != nil {
		d.ReviewerID = in.ReviewerID
	}
	if in.ChangeDescription != nil {
		d.ChangeDescription = *in.ChangeDescription
	}
	if in.Notes != nil {
		d.Notes = *in.Notes
	}
}
