package item

// CreateInput 新建物料入参(sku 业务编码,对齐真实列)。
type CreateInput struct {
	Sku           string  `json:"sku" binding:"required"`
	Name          string  `json:"name" binding:"required"`
	Specification string  `json:"specification"`
	Brand         string  `json:"brand"`
	Model         string  `json:"model"`
	CategoryID    *uint64 `json:"category_id"`
	Unit          string  `json:"unit"`
	StandardCost  float64 `json:"standard_cost"`
	PurchasePrice float64 `json:"purchase_price"`
	SalePrice     float64 `json:"sale_price"`
}

// UpdateInput 局部更新(指针区分未传与置零值)。
type UpdateInput struct {
	Name          *string  `json:"name"`
	Specification *string  `json:"specification"`
	Brand         *string  `json:"brand"`
	Model         *string  `json:"model"`
	CategoryID    *uint64  `json:"category_id"`
	Unit          *string  `json:"unit"`
	StandardCost  *float64 `json:"standard_cost"`
	PurchasePrice *float64 `json:"purchase_price"`
	SalePrice     *float64 `json:"sale_price"`
}

// ListQuery 列表筛选(keyword 命中 sku/name)。
type ListQuery struct {
	Keyword    string
	CategoryID string
}
