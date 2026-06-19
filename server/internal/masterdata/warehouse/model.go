// Package warehouse 是仓库主数据(masterdata.Warehouse)的 Go 实现,
// 忠实映射 Django apps.masterdata.models.Warehouse。
package warehouse

import "github.com/atm-erp/server/internal/platform/model"

// Warehouse 仓库主数据。字段对齐 Django Meta.db_table='warehouse'。
type Warehouse struct {
	model.Base
	Code          string `gorm:"column:code;size:50;uniqueIndex" json:"code"`
	Name          string `gorm:"column:name;size:200" json:"name"`
	WarehouseType string `gorm:"column:warehouse_type;size:20" json:"warehouse_type"`
	Address       string `gorm:"column:address" json:"address"`
	// ManagerID 对应 Django manager FK -> accounts.User(on_delete=SET_NULL,可空)。
	// TODO(port): accounts 用户模块迁移后,补充窄接口校验 manager 是否存在。
	ManagerID    *uint64 `gorm:"column:manager_id" json:"manager_id,omitempty"`
	ContactPhone string  `gorm:"column:contact_phone;size:50" json:"contact_phone"`
	IsActive     bool    `gorm:"column:is_active" json:"is_active"`
	Notes        string  `gorm:"column:notes" json:"notes"`
}

// TableName 对齐 Django Meta.db_table。
func (Warehouse) TableName() string { return "warehouse" }

// warehouseTypes 对齐 Django TYPE_CHOICES。
var warehouseTypes = map[string]bool{
	"MAIN": true, "BRANCH": true, "TRANSIT": true, "VIRTUAL": true,
}
