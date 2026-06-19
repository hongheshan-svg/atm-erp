package routing

// CreateInput 新建工艺路线模板入参。
type CreateInput struct {
	Code              string  `json:"code" binding:"required"`
	Name              string  `json:"name" binding:"required"`
	ProductCategoryID *uint64 `json:"product_category_id"`
	ItemID            *uint64 `json:"item_id"`
	Version           string  `json:"version"`
	Description       string  `json:"description"`
}

// UpdateInput 局部更新。状态/工时合计为只读派生字段,不在此处直接更新
// (对齐 Django:status 经 approve 动作迁移,total_*hours 由 calculate_totals 回写)。
type UpdateInput struct {
	Name              *string `json:"name"`
	ProductCategoryID *uint64 `json:"product_category_id"`
	ItemID            *uint64 `json:"item_id"`
	Version           *string `json:"version"`
	IsCurrent         *bool   `json:"is_current"`
	Description       *string `json:"description"`
	IsActive          *bool   `json:"is_active"`
}

// ListQuery 列表筛选(对齐 Django filterset_fields=['status','product_category','is_active','is_current']
// + search_fields=['code','name'])。
type ListQuery struct {
	Keyword           string
	Status            string
	ProductCategoryID *uint64
	IsActive          *bool
	IsCurrent         *bool
}
