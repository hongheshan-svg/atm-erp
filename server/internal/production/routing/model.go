// Package routing 移植 Django apps.production.routing.RoutingTemplate(工艺路线模板)。
package routing

import "github.com/atm-erp/server/internal/platform/model"

// 工艺路线状态(对齐 Django RoutingTemplate.status choices)。
const (
	StatusDraft    = "DRAFT"    // 草稿
	StatusApproved = "APPROVED" // 已批准
	StatusObsolete = "OBSOLETE" // 已废弃
)

// Routing 工艺路线模板,忠实映射 Django RoutingTemplate(Meta.db_table='production_routing_template')。
type Routing struct {
	model.Base
	Code string `gorm:"column:code;size:50;uniqueIndex" json:"code"`
	Name string `gorm:"column:name;size:200" json:"name"`

	// 外键 ID 直存(SET_NULL → 可空),不跨模块 import。
	ProductCategoryID *uint64 `gorm:"column:product_category_id" json:"product_category_id,omitempty"` // TODO(port): masterdata.ItemCategory
	ItemID            *uint64 `gorm:"column:item_id" json:"item_id,omitempty"`                         // TODO(port): masterdata.Item

	// 版本控制
	Version   string `gorm:"column:version;size:20;default:1.0" json:"version"`
	IsCurrent bool   `gorm:"column:is_current;default:true" json:"is_current"`

	// 工艺参数(由工序合计回写,见 service.RecalcTotals)。
	TotalStandardHours float64 `gorm:"column:total_standard_hours;type:decimal(10,2);default:0" json:"total_standard_hours"`
	TotalSetupHours    float64 `gorm:"column:total_setup_hours;type:decimal(10,2);default:0" json:"total_setup_hours"`

	Status      string `gorm:"column:status;size:20;default:DRAFT" json:"status"`
	Description string `gorm:"column:description;type:text" json:"description"`
	IsActive    bool   `gorm:"column:is_active;default:true" json:"is_active"`
}

// TableName 对齐 Django Meta.db_table。
func (Routing) TableName() string { return "production_routing_template" }
