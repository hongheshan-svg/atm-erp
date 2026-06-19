// Package process 移植 Django apps.production.routing.RoutingOperation(工艺工序)。
package process

import "github.com/atm-erp/server/internal/platform/model"

// 工序类型(对齐 Django RoutingOperation.OPERATION_TYPE_CHOICES)。
const (
	TypeMachining = "MACHINING"
	TypeAssembly  = "ASSEMBLY"
	TypeWelding   = "WELDING"
	TypePainting  = "PAINTING"
	TypeTesting   = "TESTING"
	TypeOther     = "OTHER"
)

// Process 工艺工序,忠实映射 Django RoutingOperation(Meta.db_table='production_routing_operation')。
// Django 有 unique_together=['routing','sequence']。
type Process struct {
	model.Base
	RoutingID uint64 `gorm:"column:routing_id;index:idx_routing_seq,unique" json:"routing_id"`

	Sequence      int    `gorm:"column:sequence;index:idx_routing_seq,unique" json:"sequence"`
	OperationCode string `gorm:"column:operation_code;size:50" json:"operation_code"`
	OperationName string `gorm:"column:operation_name;size:200" json:"operation_name"`
	OperationType string `gorm:"column:operation_type;size:20;default:OTHER" json:"operation_type"`

	// 工位/工作中心(外键 ID 直存,SET_NULL → 可空)。
	WorkStationID *uint64 `gorm:"column:work_station_id" json:"work_station_id,omitempty"`
	WorkCenterID  *uint64 `gorm:"column:work_center_id" json:"work_center_id,omitempty"`

	// 工时标准
	SetupHours    float64 `gorm:"column:setup_hours;type:decimal(10,2);default:0" json:"setup_hours"`
	StandardHours float64 `gorm:"column:standard_hours;type:decimal(10,2);default:0" json:"standard_hours"`
	MinHours      float64 `gorm:"column:min_hours;type:decimal(10,2);default:0" json:"min_hours"`
	MaxHours      float64 `gorm:"column:max_hours;type:decimal(10,2);default:0" json:"max_hours"`

	// 产能参数
	CycleTime float64 `gorm:"column:cycle_time;type:decimal(10,2);default:0" json:"cycle_time"`
	BatchSize int     `gorm:"column:batch_size;default:1" json:"batch_size"`

	// 人员配置
	OperatorsRequired int    `gorm:"column:operators_required;default:1" json:"operators_required"`
	SkillRequirements string `gorm:"column:skill_requirements;size:200" json:"skill_requirements"`

	// 设备/工具
	EquipmentRequired string `gorm:"column:equipment_required;size:500" json:"equipment_required"`
	ToolsRequired     string `gorm:"column:tools_required;size:500" json:"tools_required"`

	// 质量控制
	InspectionRequired bool   `gorm:"column:inspection_required;default:false" json:"inspection_required"`
	InspectionMethod   string `gorm:"column:inspection_method;size:200" json:"inspection_method"`
	QualityStandard    string `gorm:"column:quality_standard;type:text" json:"quality_standard"`

	// 操作说明
	WorkInstruction string `gorm:"column:work_instruction;type:text" json:"work_instruction"`
	SafetyNotes     string `gorm:"column:safety_notes;type:text" json:"safety_notes"`

	// 外协
	IsOutsourced      bool    `gorm:"column:is_outsourced;default:false" json:"is_outsourced"`
	OutsourceSupplier *uint64 `gorm:"column:outsource_supplier_id" json:"outsource_supplier_id,omitempty"` // TODO(port): masterdata.Supplier
	OutsourceCost     float64 `gorm:"column:outsource_cost;type:decimal(10,2);default:0" json:"outsource_cost"`

	// drawings/documents 为 Django JSONField(default=list);本轮以 text 存原始 JSON,
	// 关联展开/类型化留待集成阶段。
	Drawings  string `gorm:"column:drawings;type:text" json:"drawings"`
	Documents string `gorm:"column:documents;type:text" json:"documents"`
}

// TableName 对齐 Django Meta.db_table。
func (Process) TableName() string { return "production_routing_operation" }
