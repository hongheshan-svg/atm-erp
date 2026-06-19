package projects

import "time"

// ===========================================================================
// Project DTO
// ===========================================================================

// ProjectCreateInput 新建项目入参。code 可缺省(由编号规则生成)。
type ProjectCreateInput struct {
	Code           string     `json:"code"`
	Name           string     `json:"name" binding:"required"`
	CustomerID     uint64     `json:"customer_id" binding:"required"`
	SalesOrderID   *uint64    `json:"sales_order_id"`
	ManagerID      uint64     `json:"manager_id" binding:"required"`
	StartDate      *time.Time `json:"start_date"`
	EndDate        *time.Time `json:"end_date"`
	Status         string     `json:"status"`
	BudgetTotal    float64    `json:"budget_total"`
	BudgetMaterial float64    `json:"budget_material"`
	BudgetLabor    float64    `json:"budget_labor"`
	BudgetExpense  float64    `json:"budget_expense"`
	Description    string     `json:"description"`
	Notes          string     `json:"notes"`
}

// ProjectUpdateInput 局部更新项目入参。
type ProjectUpdateInput struct {
	Name           *string    `json:"name"`
	CustomerID     *uint64    `json:"customer_id"`
	SalesOrderID   *uint64    `json:"sales_order_id"`
	ManagerID      *uint64    `json:"manager_id"`
	StartDate      *time.Time `json:"start_date"`
	EndDate        *time.Time `json:"end_date"`
	Status         *string    `json:"status"`
	BudgetTotal    *float64   `json:"budget_total"`
	BudgetMaterial *float64   `json:"budget_material"`
	BudgetLabor    *float64   `json:"budget_labor"`
	BudgetExpense  *float64   `json:"budget_expense"`
	Description    *string    `json:"description"`
	Notes          *string    `json:"notes"`
}

// ProjectListQuery 项目列表筛选(对齐 Django filterset_fields/search_fields)。
type ProjectListQuery struct {
	Keyword    string // code / name 模糊
	CustomerID uint64
	ManagerID  uint64
	Status     string
}

// ChangeStatusInput change_status 动作入参。
type ChangeStatusInput struct {
	Status string `json:"status" binding:"required"`
}

// ===========================================================================
// ProjectTask DTO
// ===========================================================================

// TaskCreateInput 新建任务入参。
type TaskCreateInput struct {
	ProjectID    uint64     `json:"project_id" binding:"required"`
	ParentID     *uint64    `json:"parent_id"`
	Code         string     `json:"code" binding:"required"`
	Name         string     `json:"name" binding:"required"`
	AssigneeID   *uint64    `json:"assignee_id"`
	PlannedHours float64    `json:"planned_hours"`
	ActualHours  float64    `json:"actual_hours"`
	Status       string     `json:"status"`
	StartDate    *time.Time `json:"start_date"`
	EndDate      *time.Time `json:"end_date"`
	Description  string     `json:"description"`
	SortOrder    int        `json:"sort_order"`
}

// TaskUpdateInput 局部更新任务入参。
type TaskUpdateInput struct {
	ParentID     *uint64    `json:"parent_id"`
	Code         *string    `json:"code"`
	Name         *string    `json:"name"`
	AssigneeID   *uint64    `json:"assignee_id"`
	PlannedHours *float64   `json:"planned_hours"`
	ActualHours  *float64   `json:"actual_hours"`
	Status       *string    `json:"status"`
	StartDate    *time.Time `json:"start_date"`
	EndDate      *time.Time `json:"end_date"`
	Description  *string    `json:"description"`
	SortOrder    *int       `json:"sort_order"`
}

// TaskListQuery 任务列表筛选。
type TaskListQuery struct {
	Keyword    string
	ProjectID  uint64
	AssigneeID uint64
	Status     string
}

// UpdateProgressInput update_progress 动作入参。
type UpdateProgressInput struct {
	ProgressPercent *int     `json:"progress_percent"`
	ActualHours     *float64 `json:"actual_hours"`
}

// ===========================================================================
// ProjectBOM DTO（字段众多,Create 仅强约束核心键,其余可选）
// ===========================================================================

// BOMCreateInput 新建 BOM 行入参。
type BOMCreateInput struct {
	ProjectID    uint64  `json:"project_id" binding:"required"`
	ItemID       uint64  `json:"item_id" binding:"required"`
	ItemCode     string  `json:"item_code"`
	ItemProperty string  `json:"item_property"`
	Status       string  `json:"status"`
	Priority     string  `json:"priority"`
	PlannedQty   float64 `json:"planned_qty"`
	ActualQty    float64 `json:"actual_qty"`
	UnitQty      float64 `json:"unit_qty"`
	ScrapRate    float64 `json:"scrap_rate"`

	EstimatedCost float64  `json:"estimated_cost"`
	TargetCost    *float64 `json:"target_cost"`
	ActualCost    float64  `json:"actual_cost"`

	VersionBrand   string  `json:"version_brand"`
	HasDrawing     string  `json:"has_drawing"`
	DrawingID      *uint64 `json:"drawing_id"`
	DrawingNo      string  `json:"drawing_no"`
	DrawingVersion string  `json:"drawing_version"`

	MaterialSpec         string `json:"material_spec"`
	SurfaceTreatment     string `json:"surface_treatment"`
	TechnicalRequirement string `json:"technical_requirement"`

	WorkCenterID        *uint64 `json:"work_center_id"`
	ProcessID           *uint64 `json:"process_id"`
	AssemblySequence    int     `json:"assembly_sequence"`
	AssemblyInstruction string  `json:"assembly_instruction"`

	RequirementIDRef *int   `json:"requirement_id_ref"`
	FunctionModule   string `json:"function_module"`

	RequiredDate *time.Time `json:"required_date"`
	RequesterID  *uint64    `json:"requester_id"`

	Description string `json:"description"`
	Notes       string `json:"notes"`

	SupplierID  *uint64 `json:"supplier_id"`
	ReservedQty float64 `json:"reserved_qty"`

	InspectionRequired *bool `json:"inspection_required"`

	ParentID  *uint64 `json:"parent_id"`
	Level     int     `json:"level"`
	SortOrder int     `json:"sort_order"`

	IsCritical bool `json:"is_critical"`
	IsLongLead bool `json:"is_long_lead"`

	AssemblyCode   string `json:"assembly_code"`
	IsCustomPart   bool   `json:"is_custom_part"`
	CustomPartType string `json:"custom_part_type"`
	CadFileName    string `json:"cad_file_name"`
	CadSoftware    string `json:"cad_software"`

	ExtraFields string `json:"extra_fields"`
}

// BOMUpdateInput 局部更新 BOM 行入参(指针区分未传/置零)。
type BOMUpdateInput struct {
	ItemCode     *string  `json:"item_code"`
	ItemProperty *string  `json:"item_property"`
	Status       *string  `json:"status"`
	Priority     *string  `json:"priority"`
	PlannedQty   *float64 `json:"planned_qty"`
	ActualQty    *float64 `json:"actual_qty"`
	UnitQty      *float64 `json:"unit_qty"`
	ScrapRate    *float64 `json:"scrap_rate"`

	EstimatedCost *float64 `json:"estimated_cost"`
	TargetCost    *float64 `json:"target_cost"`
	ActualCost    *float64 `json:"actual_cost"`

	VersionBrand   *string `json:"version_brand"`
	HasDrawing     *string `json:"has_drawing"`
	DrawingID      *uint64 `json:"drawing_id"`
	DrawingNo      *string `json:"drawing_no"`
	DrawingVersion *string `json:"drawing_version"`

	MaterialSpec         *string `json:"material_spec"`
	SurfaceTreatment     *string `json:"surface_treatment"`
	TechnicalRequirement *string `json:"technical_requirement"`

	WorkCenterID        *uint64 `json:"work_center_id"`
	ProcessID           *uint64 `json:"process_id"`
	AssemblySequence    *int    `json:"assembly_sequence"`
	AssemblyInstruction *string `json:"assembly_instruction"`

	RequirementIDRef *int    `json:"requirement_id_ref"`
	FunctionModule   *string `json:"function_module"`

	RequiredDate *time.Time `json:"required_date"`
	RequesterID  *uint64    `json:"requester_id"`

	Description *string `json:"description"`
	Notes       *string `json:"notes"`

	OrderStatus *string  `json:"order_status"`
	SupplierID  *uint64  `json:"supplier_id"`
	OrderedQty  *float64 `json:"ordered_qty"`
	ReceivedQty *float64 `json:"received_qty"`
	IssuedQty   *float64 `json:"issued_qty"`
	ReservedQty *float64 `json:"reserved_qty"`
	ShippedQty  *float64 `json:"shipped_qty"`
	ReturnedQty *float64 `json:"returned_qty"`

	InspectionRequired *bool   `json:"inspection_required"`
	InspectionPassed   *bool   `json:"inspection_passed"`
	InspectionNotes    *string `json:"inspection_notes"`

	ParentID  *uint64 `json:"parent_id"`
	Level     *int    `json:"level"`
	SortOrder *int    `json:"sort_order"`

	IsCritical *bool `json:"is_critical"`
	IsLongLead *bool `json:"is_long_lead"`

	AssemblyCode   *string `json:"assembly_code"`
	IsCustomPart   *bool   `json:"is_custom_part"`
	CustomPartType *string `json:"custom_part_type"`
	CadFileName    *string `json:"cad_file_name"`
	CadSoftware    *string `json:"cad_software"`

	// 询价信息
	QuoteStatus       *string    `json:"quote_status"`
	QuoteSupplierID   *uint64    `json:"quote_supplier_id"`
	PriceWithTax      *float64   `json:"price_with_tax"`
	PriceWithoutTax   *float64   `json:"price_without_tax"`
	TaxRate           *float64   `json:"tax_rate"`
	QuoteDeliveryDays *int       `json:"quote_delivery_days"`
	QuoteDate         *time.Time `json:"quote_date"`
	QuoteNotes        *string    `json:"quote_notes"`

	ExtraFields *string `json:"extra_fields"`
}

// BOMListQuery BOM 列表筛选。
type BOMListQuery struct {
	Keyword     string
	ProjectID   uint64
	ItemID      uint64
	QuoteStatus string
	OrderStatus string
	HasDrawing  string
}

// ===========================================================================
// Drawing DTO
// ===========================================================================

// DrawingCreateInput 新建图纸入参。drawing_no 可缺省(由编号规则生成)。
type DrawingCreateInput struct {
	DrawingNo         string   `json:"drawing_no"`
	Name              string   `json:"name"`
	Version           string   `json:"version"`
	Revision          int      `json:"revision"`
	PartType          string   `json:"part_type"`
	ProjectID         *uint64  `json:"project_id"`
	ItemID            *uint64  `json:"item_id"`
	BomItemID         *uint64  `json:"bom_item_id"`
	ParentDrawingID   *uint64  `json:"parent_drawing_id"`
	Material          string   `json:"material"`
	Weight            *float64 `json:"weight"`
	SurfaceTreatment  string   `json:"surface_treatment"`
	HeatTreatment     string   `json:"heat_treatment"`
	ToleranceGrade    string   `json:"tolerance_grade"`
	Roughness         string   `json:"roughness"`
	CadFileName       string   `json:"cad_file_name"`
	CadSoftware       string   `json:"cad_software"`
	FileType          string   `json:"file_type"`
	FilePath          string   `json:"file_path"`
	FileSize          int64    `json:"file_size"`
	PublicSharePath   string   `json:"public_share_path"`
	DesignerID        *uint64  `json:"designer_id"`
	ReviewerID        *uint64  `json:"reviewer_id"`
	ChangeDescription string   `json:"change_description"`
	Notes             string   `json:"notes"`
}

// DrawingUpdateInput 局部更新图纸入参。
type DrawingUpdateInput struct {
	Name              *string  `json:"name"`
	Version           *string  `json:"version"`
	Revision          *int     `json:"revision"`
	PartType          *string  `json:"part_type"`
	ProjectID         *uint64  `json:"project_id"`
	ItemID            *uint64  `json:"item_id"`
	BomItemID         *uint64  `json:"bom_item_id"`
	ParentDrawingID   *uint64  `json:"parent_drawing_id"`
	Material          *string  `json:"material"`
	Weight            *float64 `json:"weight"`
	SurfaceTreatment  *string  `json:"surface_treatment"`
	HeatTreatment     *string  `json:"heat_treatment"`
	ToleranceGrade    *string  `json:"tolerance_grade"`
	Roughness         *string  `json:"roughness"`
	CadFileName       *string  `json:"cad_file_name"`
	CadSoftware       *string  `json:"cad_software"`
	FileType          *string  `json:"file_type"`
	FilePath          *string  `json:"file_path"`
	FileSize          *int64   `json:"file_size"`
	PublicSharePath   *string  `json:"public_share_path"`
	DesignerID        *uint64  `json:"designer_id"`
	ReviewerID        *uint64  `json:"reviewer_id"`
	ChangeDescription *string  `json:"change_description"`
	Notes             *string  `json:"notes"`
}

// DrawingListQuery 图纸列表筛选。
type DrawingListQuery struct {
	Keyword   string
	ProjectID uint64
	ItemID    uint64
	Status    string
	PartType  string
}

// RejectInput 驳回动作入参(图纸 reject 附评论)。
type RejectInput struct {
	Comment string `json:"comment"`
}
