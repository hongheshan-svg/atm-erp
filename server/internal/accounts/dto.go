package accounts

// ---------------- Department ----------------

type DeptCreateInput struct {
	Name        string  `json:"name" binding:"required"`
	Code        string  `json:"code" binding:"required"`
	ParentID    *uint64 `json:"parent_id"`
	ManagerID   *uint64 `json:"manager_id"`
	Description string  `json:"description"`
	SortOrder   int     `json:"sort_order"`
}

type DeptUpdateInput struct {
	Name        *string `json:"name"`
	Code        *string `json:"code"`
	ParentID    *uint64 `json:"parent_id"`
	ManagerID   *uint64 `json:"manager_id"`
	Description *string `json:"description"`
	SortOrder   *int    `json:"sort_order"`
}

type DeptListQuery struct {
	Keyword  string
	ParentID *uint64
}

// ---------------- Role ----------------

type RoleCreateInput struct {
	Name        string `json:"name" binding:"required"`
	Code        string `json:"code" binding:"required"`
	Description string `json:"description"`
	DataScope   string `json:"data_scope"`
	Permissions string `json:"permissions"`
	IsActive    *bool  `json:"is_active"`
	SortOrder   int    `json:"sort_order"`
}

type RoleUpdateInput struct {
	Name        *string `json:"name"`
	Code        *string `json:"code"`
	Description *string `json:"description"`
	DataScope   *string `json:"data_scope"`
	Permissions *string `json:"permissions"`
	IsActive    *bool   `json:"is_active"`
	SortOrder   *int    `json:"sort_order"`
}

type RoleListQuery struct {
	Keyword  string
	IsActive *bool
}

// ---------------- User ----------------

type UserCreateInput struct {
	Username     string  `json:"username" binding:"required"`
	Password     string  `json:"password" binding:"required"`
	EmployeeID   string  `json:"employee_id"`
	Email        string  `json:"email"`
	FirstName    string  `json:"first_name"`
	LastName     string  `json:"last_name"`
	Phone        string  `json:"phone"`
	Gender       string  `json:"gender"`
	Position     string  `json:"position"`
	DepartmentID *uint64 `json:"department_id"`
	RoleID       *uint64 `json:"role_id"`
	IsActive     *bool   `json:"is_active"`
	IsStaff      *bool   `json:"is_staff"`
}

type UserUpdateInput struct {
	Email        *string `json:"email"`
	FirstName    *string `json:"first_name"`
	LastName     *string `json:"last_name"`
	Phone        *string `json:"phone"`
	Gender       *string `json:"gender"`
	Position     *string `json:"position"`
	DepartmentID *uint64 `json:"department_id"`
	RoleID       *uint64 `json:"role_id"`
	IsActive     *bool   `json:"is_active"`
	IsStaff      *bool   `json:"is_staff"`
}

type UserListQuery struct {
	Keyword      string
	DepartmentID *uint64
	RoleID       *uint64
	IsActive     *bool
}

// ChangePasswordInput 对应 Django change_password action。
type ChangePasswordInput struct {
	OldPassword string `json:"old_password" binding:"required"`
	NewPassword string `json:"new_password" binding:"required"`
}

// ResetPasswordInput 对应 Django reset_password(管理员)action。
type ResetPasswordInput struct {
	NewPassword string `json:"new_password" binding:"required"`
}

// ---------------- Permission ----------------

type PermissionCreateInput struct {
	ParentID  *uint64 `json:"parent_id"`
	Code      string  `json:"code" binding:"required"`
	Name      string  `json:"name" binding:"required"`
	Type      string  `json:"type" binding:"required"` // menu/operation/field
	Resource  string  `json:"resource"`
	FieldName string  `json:"field_name"`
	RoutePath string  `json:"route_path"`
	Icon      string  `json:"icon"`
	SortOrder int     `json:"sort_order"`
	IsActive  *bool   `json:"is_active"`
}

type PermissionUpdateInput struct {
	ParentID  *uint64 `json:"parent_id"`
	Code      *string `json:"code"`
	Name      *string `json:"name"`
	Type      *string `json:"type"`
	Resource  *string `json:"resource"`
	FieldName *string `json:"field_name"`
	RoutePath *string `json:"route_path"`
	Icon      *string `json:"icon"`
	SortOrder *int    `json:"sort_order"`
	IsActive  *bool   `json:"is_active"`
}

type PermissionListQuery struct {
	Keyword  string
	Type     string
	Resource string
	IsActive *bool
}
