// Package projects 实现「项目与工程」限界上下文的 Go 重写,
// 忠实移植自 backend/apps/projects(Project / ProjectBOM / Drawing / ProjectTask 等)。
// 与样板 masterdata/item 同构:model→dto→repo→service→handler,统一 model.Base 内嵌、
// iam.ApplyScope 数据范围、httpx.Page 分页信封、Handler.Register(rg, perm)。
package projects

import (
	"time"

	"github.com/atm-erp/server/internal/platform/model"
)

// ---------------------------------------------------------------------------
// Project 项目(Django Meta.db_table = "project")
// ---------------------------------------------------------------------------

// Project 项目主数据 —— 业务核心枢纽。
type Project struct {
	model.Base
	Code       string `gorm:"column:code;size:50;uniqueIndex" json:"code"`
	Name       string `gorm:"column:name;size:200" json:"name"`
	CustomerID uint64 `gorm:"column:customer_id" json:"customer_id"`
	// TODO(port): sales_order_id 指向 sales.SalesOrder,本轮不跨模块 import,仅存外键列。
	SalesOrderID *uint64    `gorm:"column:sales_order_id" json:"sales_order_id,omitempty"`
	ManagerID    uint64     `gorm:"column:manager_id" json:"manager_id"`
	StartDate    *time.Time `gorm:"column:start_date" json:"start_date"`
	EndDate      *time.Time `gorm:"column:end_date" json:"end_date"`
	Status       string     `gorm:"column:status;size:20;default:DRAFT" json:"status"`

	BudgetTotal    float64 `gorm:"column:budget_total" json:"budget_total"`
	BudgetMaterial float64 `gorm:"column:budget_material" json:"budget_material"`
	BudgetLabor    float64 `gorm:"column:budget_labor" json:"budget_labor"`
	BudgetExpense  float64 `gorm:"column:budget_expense" json:"budget_expense"`

	Description string `gorm:"column:description" json:"description"`
	Notes       string `gorm:"column:notes" json:"notes"`
}

func (Project) TableName() string { return "project" }

// Project 状态常量(对齐 Django STATUS_CHOICES)。
const (
	ProjectStatusDraft      = "DRAFT"
	ProjectStatusPlanning   = "PLANNING"
	ProjectStatusPending    = "PENDING"
	ProjectStatusRejected   = "REJECTED"
	ProjectStatusInProgress = "IN_PROGRESS"
	ProjectStatusActive     = "ACTIVE" // 保留兼容
	ProjectStatusPaused     = "PAUSED"
	ProjectStatusCompleted  = "COMPLETED"
	ProjectStatusCancelled  = "CANCELLED"
	ProjectStatusArchived   = "ARCHIVED"
)

// ---------------------------------------------------------------------------
// ProjectTask 项目任务(Django Meta.db_table = "project_task",支持 WBS)
// ---------------------------------------------------------------------------

// ProjectTask 项目任务。
type ProjectTask struct {
	model.Base
	ProjectID       uint64     `gorm:"column:project_id" json:"project_id"`
	ParentID        *uint64    `gorm:"column:parent_id" json:"parent_id,omitempty"`
	Code            string     `gorm:"column:code;size:50" json:"code"`
	Name            string     `gorm:"column:name;size:200" json:"name"`
	AssigneeID      *uint64    `gorm:"column:assignee_id" json:"assignee_id,omitempty"`
	PlannedHours    float64    `gorm:"column:planned_hours" json:"planned_hours"`
	ActualHours     float64    `gorm:"column:actual_hours" json:"actual_hours"`
	ProgressPercent int        `gorm:"column:progress_percent" json:"progress_percent"`
	Status          string     `gorm:"column:status;size:20;default:TODO" json:"status"`
	StartDate       *time.Time `gorm:"column:start_date" json:"start_date"`
	EndDate         *time.Time `gorm:"column:end_date" json:"end_date"`
	Description     string     `gorm:"column:description" json:"description"`
	SortOrder       int        `gorm:"column:sort_order" json:"sort_order"`
}

func (ProjectTask) TableName() string { return "project_task" }

// ProjectTask 状态常量。
const (
	TaskStatusTodo       = "TODO"
	TaskStatusInProgress = "IN_PROGRESS"
	TaskStatusCompleted  = "COMPLETED"
	TaskStatusCancelled  = "CANCELLED"
)

// ---------------------------------------------------------------------------
// ProjectBOM 项目 BOM(Django Meta.db_table = "project_bom")
// 针对非标自动化行业,字段较多,忠实映射。
// ---------------------------------------------------------------------------

// ProjectBOM 项目物料清单。
type ProjectBOM struct {
	model.Base
	ProjectID uint64 `gorm:"column:project_id" json:"project_id"`
	ItemID    uint64 `gorm:"column:item_id" json:"item_id"`

	ItemCode     string `gorm:"column:item_code;size:50" json:"item_code"`
	ItemProperty string `gorm:"column:item_property;size:20" json:"item_property"`
	Status       string `gorm:"column:status;size:20;default:DRAFT" json:"status"`
	Priority     string `gorm:"column:priority;size:20;default:NORMAL" json:"priority"`

	// 数量信息
	PlannedQty float64 `gorm:"column:planned_qty" json:"planned_qty"`
	ActualQty  float64 `gorm:"column:actual_qty" json:"actual_qty"`
	UnitQty    float64 `gorm:"column:unit_qty;default:1" json:"unit_qty"`
	ScrapRate  float64 `gorm:"column:scrap_rate" json:"scrap_rate"`

	// 成本信息
	EstimatedCost float64  `gorm:"column:estimated_cost" json:"estimated_cost"`
	TargetCost    *float64 `gorm:"column:target_cost" json:"target_cost,omitempty"`
	ActualCost    float64  `gorm:"column:actual_cost" json:"actual_cost"`
	TotalCost     float64  `gorm:"column:total_cost" json:"total_cost"`

	// 图纸与技术资料
	VersionBrand   string  `gorm:"column:version_brand;size:100" json:"version_brand"`
	HasDrawing     string  `gorm:"column:has_drawing;size:10;default:PENDING" json:"has_drawing"`
	DrawingID      *uint64 `gorm:"column:drawing_id" json:"drawing_id,omitempty"`
	DrawingNo      string  `gorm:"column:drawing_no;size:100" json:"drawing_no"`
	DrawingVersion string  `gorm:"column:drawing_version;size:50" json:"drawing_version"`

	MaterialSpec         string `gorm:"column:material_spec;size:200" json:"material_spec"`
	SurfaceTreatment     string `gorm:"column:surface_treatment;size:100" json:"surface_treatment"`
	TechnicalRequirement string `gorm:"column:technical_requirement" json:"technical_requirement"`

	// 装配与工艺
	// TODO(port): work_center_id / process_id 指向 production 模块,仅存外键列。
	WorkCenterID        *uint64 `gorm:"column:work_center_id" json:"work_center_id,omitempty"`
	ProcessID           *uint64 `gorm:"column:process_id" json:"process_id,omitempty"`
	AssemblySequence    int     `gorm:"column:assembly_sequence" json:"assembly_sequence"`
	AssemblyInstruction string  `gorm:"column:assembly_instruction" json:"assembly_instruction"`

	// 需求追溯
	RequirementIDRef *int   `gorm:"column:requirement_id_ref" json:"requirement_id_ref,omitempty"`
	FunctionModule   string `gorm:"column:function_module;size:100" json:"function_module"`

	// 日期与时间
	RequiredDate    *time.Time `gorm:"column:required_date" json:"required_date"`
	LatestOrderDate *time.Time `gorm:"column:latest_order_date" json:"latest_order_date"`
	RequesterID     *uint64    `gorm:"column:requester_id" json:"requester_id,omitempty"`

	Description string `gorm:"column:description" json:"description"`
	Notes       string `gorm:"column:notes" json:"notes"`

	// 采购与库存跟踪
	OrderStatus string `gorm:"column:order_status;size:20;default:NOT_ORDERED" json:"order_status"`
	// TODO(port): supplier_id 指向 masterdata.Supplier。
	SupplierID         *uint64    `gorm:"column:supplier_id" json:"supplier_id,omitempty"`
	DeliveryDate       *time.Time `gorm:"column:delivery_date" json:"delivery_date"`
	ActualDeliveryDate *time.Time `gorm:"column:actual_delivery_date" json:"actual_delivery_date"`

	OrderedQty  float64 `gorm:"column:ordered_qty" json:"ordered_qty"`
	ReceivedQty float64 `gorm:"column:received_qty" json:"received_qty"`
	IssuedQty   float64 `gorm:"column:issued_qty" json:"issued_qty"`
	ReservedQty float64 `gorm:"column:reserved_qty" json:"reserved_qty"`

	// TODO(port): purchase_request_id / purchase_order_id 指向 purchase 模块。
	PurchaseRequestID *uint64 `gorm:"column:purchase_request_id" json:"purchase_request_id,omitempty"`
	PrQty             float64 `gorm:"column:pr_qty" json:"pr_qty"`
	PurchaseOrderID   *uint64 `gorm:"column:purchase_order_id" json:"purchase_order_id,omitempty"`

	ShippedQty  float64 `gorm:"column:shipped_qty" json:"shipped_qty"`
	ReturnedQty float64 `gorm:"column:returned_qty" json:"returned_qty"`

	// 质量与检验
	InspectionRequired bool   `gorm:"column:inspection_required;default:true" json:"inspection_required"`
	InspectionPassed   *bool  `gorm:"column:inspection_passed" json:"inspection_passed,omitempty"`
	InspectionNotes    string `gorm:"column:inspection_notes" json:"inspection_notes"`

	// 多级 BOM 结构
	ParentID  *uint64 `gorm:"column:parent_id" json:"parent_id,omitempty"`
	Level     int     `gorm:"column:level" json:"level"`
	SortOrder int     `gorm:"column:sort_order" json:"sort_order"`

	IsCritical bool `gorm:"column:is_critical" json:"is_critical"`
	IsLongLead bool `gorm:"column:is_long_lead" json:"is_long_lead"`

	// 非标自动化行业增强
	AssemblyCode   string `gorm:"column:assembly_code;size:100" json:"assembly_code"`
	IsCustomPart   bool   `gorm:"column:is_custom_part" json:"is_custom_part"`
	CustomPartType string `gorm:"column:custom_part_type;size:20" json:"custom_part_type"`
	CadFileName    string `gorm:"column:cad_file_name;size:200" json:"cad_file_name"`
	CadSoftware    string `gorm:"column:cad_software;size:50" json:"cad_software"`

	// 询价信息
	QuoteStatus       string     `gorm:"column:quote_status;size:20;default:NOT_QUOTED" json:"quote_status"`
	QuoteSupplierID   *uint64    `gorm:"column:quote_supplier_id" json:"quote_supplier_id,omitempty"`
	PriceWithTax      *float64   `gorm:"column:price_with_tax" json:"price_with_tax,omitempty"`
	PriceWithoutTax   *float64   `gorm:"column:price_without_tax" json:"price_without_tax,omitempty"`
	TaxRate           *float64   `gorm:"column:tax_rate" json:"tax_rate,omitempty"`
	QuoteDeliveryDays *int       `gorm:"column:quote_delivery_days" json:"quote_delivery_days,omitempty"`
	QuoteDate         *time.Time `gorm:"column:quote_date" json:"quote_date"`
	QuoteNotes        string     `gorm:"column:quote_notes" json:"quote_notes"`

	// 扩展字段(Django JSONField);GORM 用 datatypes.JSON 需额外依赖,这里以字符串承载原始 JSON。
	// TODO(verify): 共库切流时确认 PostgreSQL 列类型为 jsonb,可改用 datatypes.JSON(需引入 gorm.io/datatypes)。
	ExtraFields string `gorm:"column:extra_fields;type:jsonb" json:"extra_fields"`
}

func (ProjectBOM) TableName() string { return "project_bom" }

// ProjectBOM 状态常量。
const (
	BOMStatusDraft     = "DRAFT"
	BOMStatusConfirmed = "CONFIRMED"
	BOMStatusReleased  = "RELEASED"
	BOMStatusCompleted = "COMPLETED"
	BOMStatusCancelled = "CANCELLED"
)

// ---------------------------------------------------------------------------
// Drawing 图纸(Django Meta.db_table = "project_drawing")
// ---------------------------------------------------------------------------

// Drawing 图纸管理。
type Drawing struct {
	model.Base
	DrawingNo string `gorm:"column:drawing_no;size:100" json:"drawing_no"`
	Name      string `gorm:"column:name;size:200" json:"name"`
	Version   string `gorm:"column:version;size:20;default:A0" json:"version"`
	Revision  int    `gorm:"column:revision;default:1" json:"revision"`
	PartType  string `gorm:"column:part_type;size:20;default:PART" json:"part_type"`

	ProjectID       *uint64 `gorm:"column:project_id" json:"project_id,omitempty"`
	ItemID          *uint64 `gorm:"column:item_id" json:"item_id,omitempty"`
	BomItemID       *uint64 `gorm:"column:bom_item_id" json:"bom_item_id,omitempty"`
	ParentDrawingID *uint64 `gorm:"column:parent_drawing_id" json:"parent_drawing_id,omitempty"`

	Material         string   `gorm:"column:material;size:100" json:"material"`
	Weight           *float64 `gorm:"column:weight" json:"weight,omitempty"`
	SurfaceTreatment string   `gorm:"column:surface_treatment;size:100" json:"surface_treatment"`
	HeatTreatment    string   `gorm:"column:heat_treatment;size:100" json:"heat_treatment"`
	ToleranceGrade   string   `gorm:"column:tolerance_grade;size:50" json:"tolerance_grade"`
	Roughness        string   `gorm:"column:roughness;size:50" json:"roughness"`

	CadFileName string `gorm:"column:cad_file_name;size:200" json:"cad_file_name"`
	CadSoftware string `gorm:"column:cad_software;size:50" json:"cad_software"`

	FileType        string `gorm:"column:file_type;size:20;default:PDF" json:"file_type"`
	FilePath        string `gorm:"column:file_path;size:500" json:"file_path"`
	FileSize        int64  `gorm:"column:file_size" json:"file_size"`
	PublicSharePath string `gorm:"column:public_share_path;size:500" json:"public_share_path"`

	Status string `gorm:"column:status;size:20;default:DRAFT" json:"status"`

	DesignerID *uint64    `gorm:"column:designer_id" json:"designer_id,omitempty"`
	ReviewerID *uint64    `gorm:"column:reviewer_id" json:"reviewer_id,omitempty"`
	ApproverID *uint64    `gorm:"column:approver_id" json:"approver_id,omitempty"`
	ApprovedAt *time.Time `gorm:"column:approved_at" json:"approved_at"`
	ReleasedAt *time.Time `gorm:"column:released_at" json:"released_at"`

	ChangeDescription string `gorm:"column:change_description" json:"change_description"`
	Notes             string `gorm:"column:notes" json:"notes"`
}

func (Drawing) TableName() string { return "project_drawing" }

// Drawing 状态常量。
const (
	DrawingStatusDraft     = "DRAFT"
	DrawingStatusReviewing = "REVIEWING"
	DrawingStatusApproved  = "APPROVED"
	DrawingStatusReleased  = "RELEASED"
	DrawingStatusObsolete  = "OBSOLETE"
)

// ---------------------------------------------------------------------------
// DrawingChangeNotice 图纸变更通知(Django Meta.db_table = "project_drawing_change_notice")
// release 动作联动创建。M2M notified_users 暂未迁移(TODO)。
// ---------------------------------------------------------------------------

// DrawingChangeNotice 图纸变更通知。
type DrawingChangeNotice struct {
	model.Base
	DrawingID         uint64     `gorm:"column:drawing_id" json:"drawing_id"`
	ChangeType        string     `gorm:"column:change_type;size:20;default:NEW" json:"change_type"`
	OldVersion        string     `gorm:"column:old_version;size:20" json:"old_version"`
	NewVersion        string     `gorm:"column:new_version;size:20" json:"new_version"`
	ChangeDescription string     `gorm:"column:change_description" json:"change_description"`
	EmailSent         bool       `gorm:"column:email_sent" json:"email_sent"`
	EmailSentAt       *time.Time `gorm:"column:email_sent_at" json:"email_sent_at"`
	// TODO(port): notified_users 是 M2M(project_drawing_change_notice <-> accounts.User),需独立连接表迁移。
}

func (DrawingChangeNotice) TableName() string { return "project_drawing_change_notice" }
