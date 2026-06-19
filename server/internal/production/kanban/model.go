// Package kanban 移植 Django apps.production.kanban_wip.KanbanWIPRule(看板 WIP 规则)。
// 看板大屏只读聚合视图(ProductionKanbanView)依赖工单/工作中心实时聚合,
// 跨模块且无独立表,本轮以 // TODO(port) 标注,不在此实现。
package kanban

import "github.com/atm-erp/server/internal/platform/model"

// KanbanWIPRule 看板在制品(WIP)上限规则,
// 忠实映射 Django KanbanWIPRule(Meta.db_table='production_kanban_wip_rule')。
type KanbanWIPRule struct {
	model.Base
	ProcessName      string `gorm:"column:process_name;size:200;uniqueIndex" json:"process_name"`
	WIPLimit         int    `gorm:"column:wip_limit" json:"wip_limit"`
	WarningThreshold int    `gorm:"column:warning_threshold;default:80" json:"warning_threshold"` // 预警阈值(%)
	IsActive         bool   `gorm:"column:is_active;default:true" json:"is_active"`
}

// TableName 对齐 Django Meta.db_table。
func (KanbanWIPRule) TableName() string { return "production_kanban_wip_rule" }
