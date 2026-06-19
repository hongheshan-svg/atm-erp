// Package item 是物料主数据的参考垂直切片(model→repo→service→handler→权限→API),
// 作为后续 14 个限界上下文逐模块移植的样板。
package item

import "github.com/atm-erp/server/internal/platform/model"

// Item 物料主数据(现有 masterdata 表的子集,作参考用)。
type Item struct {
	model.Base
	Code     string  `gorm:"column:code;size:64;uniqueIndex" json:"code"`
	Name     string  `gorm:"column:name;size:255" json:"name"`
	Spec     string  `gorm:"column:spec;size:255" json:"spec"`
	Unit     string  `gorm:"column:unit;size:32" json:"unit"`
	Category string  `gorm:"column:category;size:64" json:"category"`
	Price    float64 `gorm:"column:price" json:"price"`
}

// TableName 显式对齐 Django Meta.db_table(ADR-004,禁 AutoMigrate)。
// 注意:确切表名须在共库切流前与 Django 模型 Meta.db_table 核对。
func (Item) TableName() string { return "item" }
