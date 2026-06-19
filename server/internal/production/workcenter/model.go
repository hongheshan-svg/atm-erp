// Package workcenter 移植 Django apps.production.scheduling.WorkCenter(工作中心)。
// 工单(WorkOrder)、工序(Process)、看板均以 work_center_id 关联本实体。
package workcenter

import "github.com/atm-erp/server/internal/platform/model"

// WorkCenter 工作中心,忠实映射 Django WorkCenter(Meta.db_table='mes_work_center')。
// equipment(M2M)、manager(FK)关联在本轮以 ID/占位保留,不跨模块 import。
type WorkCenter struct {
	model.Base
	Code string `gorm:"column:code;size:50;uniqueIndex" json:"code"`
	Name string `gorm:"column:name;size:100" json:"name"`

	// 产能参数
	CapacityPerDay float64 `gorm:"column:capacity_per_day;type:decimal(10,2);default:8" json:"capacity_per_day"`
	Efficiency     float64 `gorm:"column:efficiency;type:decimal(5,2);default:100" json:"efficiency"`

	ManagerID *uint64 `gorm:"column:manager_id" json:"manager_id,omitempty"` // TODO(port): accounts.User

	IsActive    bool   `gorm:"column:is_active;default:true" json:"is_active"`
	Description string `gorm:"column:description;type:text" json:"description"`
}

// TableName 对齐 Django Meta.db_table。
func (WorkCenter) TableName() string { return "mes_work_center" }
