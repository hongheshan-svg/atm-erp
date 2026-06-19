// Package item 是物料主数据切片。字段已按**真实 Django `item` 表**列对齐(共库):
// sku(非 code)、specification(非 spec)、category_id(FK,非 category 字符串)、
// standard_cost/purchase_price/sale_price(真表无 price 列)。
package item

import "github.com/atm-erp/server/internal/platform/model"

// Item 物料主数据(对齐 Django masterdata.Item / db_table=item 的核心列子集)。
type Item struct {
	model.Base
	Sku           string  `gorm:"column:sku;size:64;uniqueIndex" json:"sku"`
	Name          string  `gorm:"column:name;size:255" json:"name"`
	Specification string  `gorm:"column:specification;size:255" json:"specification"`
	Brand         string  `gorm:"column:brand;size:100" json:"brand"`
	Model         string  `gorm:"column:model;size:100" json:"model"`
	CategoryID    *uint64 `gorm:"column:category_id" json:"category_id,omitempty"`
	Unit          string  `gorm:"column:unit;size:32" json:"unit"`
	StandardCost  float64 `gorm:"column:standard_cost" json:"standard_cost"`
	PurchasePrice float64 `gorm:"column:purchase_price" json:"purchase_price"`
	SalePrice     float64 `gorm:"column:sale_price" json:"sale_price"`
	IsActive      bool    `gorm:"column:is_active" json:"is_active"`
}

func (Item) TableName() string { return "item" }
