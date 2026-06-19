package warehouse

// CreateInput 新建仓库入参。code 为必填(Django unique,无自动生成)。
type CreateInput struct {
	Code          string  `json:"code" binding:"required"`
	Name          string  `json:"name" binding:"required"`
	WarehouseType string  `json:"warehouse_type"`
	Address       string  `json:"address"`
	ManagerID     *uint64 `json:"manager_id"`
	ContactPhone  string  `json:"contact_phone"`
	IsActive      *bool   `json:"is_active"`
	Notes         string  `json:"notes"`
}

// UpdateInput 局部更新入参。
type UpdateInput struct {
	Name          *string `json:"name"`
	WarehouseType *string `json:"warehouse_type"`
	Address       *string `json:"address"`
	ManagerID     *uint64 `json:"manager_id"`
	ContactPhone  *string `json:"contact_phone"`
	IsActive      *bool   `json:"is_active"`
	Notes         *string `json:"notes"`
}

// ListQuery 列表筛选条件。
type ListQuery struct {
	Keyword       string
	WarehouseType string
	IsActive      *bool
}
