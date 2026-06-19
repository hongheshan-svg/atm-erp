package item

// CreateInput 新建物料入参(validator/v10 标签由 gin binding 驱动)。
type CreateInput struct {
	Code     string  `json:"code" binding:"required"`
	Name     string  `json:"name" binding:"required"`
	Spec     string  `json:"spec"`
	Unit     string  `json:"unit"`
	Category string  `json:"category"`
	Price    float64 `json:"price"`
}

// UpdateInput 局部更新入参(指针区分“未传”与“置零值”)。
type UpdateInput struct {
	Name     *string  `json:"name"`
	Spec     *string  `json:"spec"`
	Unit     *string  `json:"unit"`
	Category *string  `json:"category"`
	Price    *float64 `json:"price"`
}

// ListQuery 列表筛选条件(对应前端可选筛选,生产可换 Squirrel 动态拼装)。
type ListQuery struct {
	Keyword  string
	Category string
}
