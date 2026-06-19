package accounts

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"

	"gorm.io/gorm"
)

var (
	ErrDeptNotFound       = errors.New("部门不存在")
	ErrRoleNotFound       = errors.New("角色不存在")
	ErrUserNotFound       = errors.New("用户不存在")
	ErrPermissionNotFound = errors.New("权限不存在")

	ErrValidation = errors.New("校验失败")
)

type Service struct{ repo *Repo }

func NewService(repo *Repo) *Service { return &Service{repo: repo} }

func wrapNotFound(err error, nf error) error {
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nf
	}
	return err
}

// ===================== Department =====================

func (s *Service) ListDepartments(ctx context.Context, q DeptListQuery, offset, limit int) ([]Department, int64, error) {
	return s.repo.ListDepartments(ctx, q, offset, limit)
}

func (s *Service) GetDepartment(ctx context.Context, id uint64) (*Department, error) {
	d, err := s.repo.GetDepartment(ctx, id)
	return d, wrapNotFound(err, ErrDeptNotFound)
}

func (s *Service) CreateDepartment(ctx context.Context, in DeptCreateInput) (*Department, error) {
	d := &Department{
		Name:        in.Name,
		Code:        in.Code,
		ParentID:    in.ParentID,
		ManagerID:   in.ManagerID,
		Description: in.Description,
		SortOrder:   in.SortOrder,
	}
	if err := s.repo.CreateDepartment(ctx, d); err != nil {
		return nil, err
	}
	return d, nil
}

func (s *Service) UpdateDepartment(ctx context.Context, id uint64, in DeptUpdateInput) (*Department, error) {
	d, err := s.GetDepartment(ctx, id)
	if err != nil {
		return nil, err
	}
	if in.Name != nil {
		d.Name = *in.Name
	}
	if in.Code != nil {
		d.Code = *in.Code
	}
	if in.ParentID != nil {
		// 禁止自引用为上级。
		if *in.ParentID == id {
			return nil, fmt.Errorf("%w: 部门不能将自身设为上级", ErrValidation)
		}
		d.ParentID = in.ParentID
	}
	if in.ManagerID != nil {
		d.ManagerID = in.ManagerID
	}
	if in.Description != nil {
		d.Description = *in.Description
	}
	if in.SortOrder != nil {
		d.SortOrder = *in.SortOrder
	}
	if err := s.repo.SaveDepartment(ctx, d); err != nil {
		return nil, err
	}
	return d, nil
}

func (s *Service) DeleteDepartment(ctx context.Context, id uint64) error {
	if _, err := s.GetDepartment(ctx, id); err != nil {
		return err
	}
	// 有子部门或在岗用户时禁止删除(忠实迁移常见删除保护)。
	if n, err := s.repo.CountDeptChildren(ctx, id); err != nil {
		return err
	} else if n > 0 {
		return fmt.Errorf("%w: 该部门下存在子部门,无法删除", ErrValidation)
	}
	if n, err := s.repo.CountDeptUsers(ctx, id); err != nil {
		return err
	} else if n > 0 {
		return fmt.Errorf("%w: 该部门下存在用户,无法删除", ErrValidation)
	}
	return s.repo.DeleteDepartment(ctx, id)
}

// ===================== Role =====================

func (s *Service) ListRoles(ctx context.Context, q RoleListQuery, offset, limit int) ([]Role, int64, error) {
	return s.repo.ListRoles(ctx, q, offset, limit)
}

func (s *Service) GetRole(ctx context.Context, id uint64) (*Role, error) {
	r, err := s.repo.GetRole(ctx, id)
	return r, wrapNotFound(err, ErrRoleNotFound)
}

func (s *Service) CreateRole(ctx context.Context, in RoleCreateInput) (*Role, error) {
	scope := strings.TrimSpace(in.DataScope)
	if scope == "" {
		scope = "ALL"
	}
	perms := in.Permissions
	if perms == "" {
		perms = "{}"
	}
	role := &Role{
		Name:        in.Name,
		Code:        in.Code,
		Description: in.Description,
		DataScope:   scope,
		Permissions: perms,
		IsActive:    boolOr(in.IsActive, true),
		SortOrder:   in.SortOrder,
	}
	if err := s.repo.CreateRole(ctx, role); err != nil {
		return nil, err
	}
	return role, nil
}

func (s *Service) UpdateRole(ctx context.Context, id uint64, in RoleUpdateInput) (*Role, error) {
	role, err := s.GetRole(ctx, id)
	if err != nil {
		return nil, err
	}
	if in.Name != nil {
		role.Name = *in.Name
	}
	if in.Code != nil {
		role.Code = *in.Code
	}
	if in.Description != nil {
		role.Description = *in.Description
	}
	if in.DataScope != nil {
		role.DataScope = *in.DataScope
	}
	if in.Permissions != nil {
		role.Permissions = *in.Permissions
	}
	if in.IsActive != nil {
		role.IsActive = *in.IsActive
	}
	if in.SortOrder != nil {
		role.SortOrder = *in.SortOrder
	}
	if err := s.repo.SaveRole(ctx, role); err != nil {
		return nil, err
	}
	return role, nil
}

func (s *Service) DeleteRole(ctx context.Context, id uint64) error {
	if _, err := s.GetRole(ctx, id); err != nil {
		return err
	}
	if n, err := s.repo.CountRoleUsers(ctx, id); err != nil {
		return err
	} else if n > 0 {
		return fmt.Errorf("%w: 该角色已分配给用户,无法删除", ErrValidation)
	}
	return s.repo.DeleteRole(ctx, id)
}

// ===================== User =====================

func (s *Service) ListUsers(ctx context.Context, q UserListQuery, offset, limit int) ([]User, int64, error) {
	return s.repo.ListUsers(ctx, q, offset, limit)
}

func (s *Service) GetUser(ctx context.Context, id uint64) (*User, error) {
	u, err := s.repo.GetUser(ctx, id)
	return u, wrapNotFound(err, ErrUserNotFound)
}

func (s *Service) CreateUser(ctx context.Context, in UserCreateInput) (*User, error) {
	if exists, err := s.repo.UsernameExists(ctx, in.Username, 0); err != nil {
		return nil, err
	} else if exists {
		return nil, fmt.Errorf("%w: 用户名已存在", ErrValidation)
	}

	empID := strings.TrimSpace(in.EmployeeID)
	if empID == "" {
		// 自动生成工号(简易规则:EMP+时间戳尾段)。
		// TODO(verify): Django 端若有 CodeRule 工号规则,需对齐前缀/序号格式。
		empID = fmt.Sprintf("EMP%d", time.Now().UnixNano()%1_000_000_0)
	}
	if exists, err := s.repo.EmployeeIDExists(ctx, empID, 0); err != nil {
		return nil, err
	} else if exists {
		return nil, fmt.Errorf("%w: 工号已存在", ErrValidation)
	}

	hashed, err := hashPassword(in.Password)
	if err != nil {
		return nil, err
	}
	now := time.Now()
	u := &User{
		Username:     in.Username,
		Password:     hashed,
		EmployeeID:   empID,
		Email:        in.Email,
		FirstName:    in.FirstName,
		LastName:     in.LastName,
		Phone:        in.Phone,
		Gender:       in.Gender,
		Position:     in.Position,
		DepartmentID: in.DepartmentID,
		RoleID:       in.RoleID,
		IsActive:     boolOr(in.IsActive, true),
		IsStaff:      boolOr(in.IsStaff, false),
		DateJoined:   now,
	}
	if err := s.repo.CreateUser(ctx, u); err != nil {
		return nil, err
	}
	return u, nil
}

func (s *Service) UpdateUser(ctx context.Context, id uint64, in UserUpdateInput) (*User, error) {
	u, err := s.GetUser(ctx, id)
	if err != nil {
		return nil, err
	}
	if in.Email != nil {
		u.Email = *in.Email
	}
	if in.FirstName != nil {
		u.FirstName = *in.FirstName
	}
	if in.LastName != nil {
		u.LastName = *in.LastName
	}
	if in.Phone != nil {
		u.Phone = *in.Phone
	}
	if in.Gender != nil {
		u.Gender = *in.Gender
	}
	if in.Position != nil {
		u.Position = *in.Position
	}
	if in.DepartmentID != nil {
		u.DepartmentID = in.DepartmentID
	}
	if in.RoleID != nil {
		u.RoleID = in.RoleID
	}
	if in.IsActive != nil {
		u.IsActive = *in.IsActive
	}
	if in.IsStaff != nil {
		u.IsStaff = *in.IsStaff
	}
	if err := s.repo.SaveUser(ctx, u); err != nil {
		return nil, err
	}
	return u, nil
}

// DeleteUser 软删除。复刻 Django User.soft_delete():释放 username/email/employee_id 唯一约束
// (追加 _deleted_<rand> 后缀)、置 is_active=false,再走软删除。
func (s *Service) DeleteUser(ctx context.Context, id uint64) error {
	u, err := s.GetUser(ctx, id)
	if err != nil {
		return err
	}
	suffix, err := randomSalt(8)
	if err != nil {
		return err
	}
	suffix = "_deleted_" + suffix
	u.Username += suffix
	u.Email += suffix
	u.EmployeeID += suffix
	u.IsActive = false
	if err := s.repo.SaveUser(ctx, u); err != nil {
		return err
	}
	return s.repo.DeleteUser(ctx, id)
}

// ChangePassword 复刻 Django change_password:校验旧密码,新密码 >=6 位。
func (s *Service) ChangePassword(ctx context.Context, id uint64, in ChangePasswordInput) error {
	u, err := s.GetUser(ctx, id)
	if err != nil {
		return err
	}
	if !checkPassword(in.OldPassword, u.Password) {
		return fmt.Errorf("%w: 旧密码不正确", ErrValidation)
	}
	if len(in.NewPassword) < 6 {
		return fmt.Errorf("%w: 新密码长度不能少于6位", ErrValidation)
	}
	hashed, err := hashPassword(in.NewPassword)
	if err != nil {
		return err
	}
	u.Password = hashed
	return s.repo.SaveUser(ctx, u)
}

// ResetPassword 复刻 Django reset_password(管理员):新密码 >=6 位,不校验旧密码。
func (s *Service) ResetPassword(ctx context.Context, id uint64, in ResetPasswordInput) error {
	u, err := s.GetUser(ctx, id)
	if err != nil {
		return err
	}
	if len(in.NewPassword) < 6 {
		return fmt.Errorf("%w: 新密码长度不能少于6位", ErrValidation)
	}
	hashed, err := hashPassword(in.NewPassword)
	if err != nil {
		return err
	}
	u.Password = hashed
	return s.repo.SaveUser(ctx, u)
}

// ===================== Permission =====================

func (s *Service) ListPermissions(ctx context.Context, q PermissionListQuery, offset, limit int) ([]Permission, int64, error) {
	return s.repo.ListPermissions(ctx, q, offset, limit)
}

func (s *Service) GetPermission(ctx context.Context, id uint64) (*Permission, error) {
	p, err := s.repo.GetPermission(ctx, id)
	return p, wrapNotFound(err, ErrPermissionNotFound)
}

func (s *Service) CreatePermission(ctx context.Context, in PermissionCreateInput) (*Permission, error) {
	if err := validatePermission(in.Type, in.FieldName, in.Resource); err != nil {
		return nil, err
	}
	if exists, err := s.repo.PermissionCodeExists(ctx, in.Code, 0); err != nil {
		return nil, err
	} else if exists {
		return nil, fmt.Errorf("%w: 权限编码已存在", ErrValidation)
	}
	p := &Permission{
		ParentID:  in.ParentID,
		Code:      in.Code,
		Name:      in.Name,
		Type:      in.Type,
		Resource:  in.Resource,
		FieldName: in.FieldName,
		RoutePath: in.RoutePath,
		Icon:      in.Icon,
		SortOrder: in.SortOrder,
		IsActive:  boolOr(in.IsActive, true),
	}
	if err := s.repo.CreatePermission(ctx, p); err != nil {
		return nil, err
	}
	return p, nil
}

func (s *Service) UpdatePermission(ctx context.Context, id uint64, in PermissionUpdateInput) (*Permission, error) {
	p, err := s.GetPermission(ctx, id)
	if err != nil {
		return nil, err
	}
	if in.ParentID != nil {
		if *in.ParentID == id {
			return nil, fmt.Errorf("%w: 权限不能将自身设为父权限", ErrValidation)
		}
		p.ParentID = in.ParentID
	}
	if in.Code != nil {
		p.Code = *in.Code
	}
	if in.Name != nil {
		p.Name = *in.Name
	}
	if in.Type != nil {
		p.Type = *in.Type
	}
	if in.Resource != nil {
		p.Resource = *in.Resource
	}
	if in.FieldName != nil {
		p.FieldName = *in.FieldName
	}
	if in.RoutePath != nil {
		p.RoutePath = *in.RoutePath
	}
	if in.Icon != nil {
		p.Icon = *in.Icon
	}
	if in.SortOrder != nil {
		p.SortOrder = *in.SortOrder
	}
	if in.IsActive != nil {
		p.IsActive = *in.IsActive
	}
	// 类型/资源/字段联动校验(复刻 Permission.clean)。
	if err := validatePermission(p.Type, p.FieldName, p.Resource); err != nil {
		return nil, err
	}
	if err := s.repo.SavePermission(ctx, p); err != nil {
		return nil, err
	}
	return p, nil
}

func (s *Service) DeletePermission(ctx context.Context, id uint64) error {
	if _, err := s.GetPermission(ctx, id); err != nil {
		return err
	}
	return s.repo.DeletePermission(ctx, id)
}

// validatePermission 复刻 Django Permission.clean 的类型联动校验。
func validatePermission(typ, fieldName, resource string) error {
	switch typ {
	case "field":
		if fieldName == "" {
			return fmt.Errorf("%w: 字段权限必须指定 field_name", ErrValidation)
		}
	case "operation":
		if resource == "" {
			return fmt.Errorf("%w: 操作权限必须指定 resource", ErrValidation)
		}
	case "menu":
		// 菜单权限无额外约束。
	default:
		return fmt.Errorf("%w: 权限类型必须为 menu/operation/field 之一", ErrValidation)
	}
	return nil
}

func boolOr(p *bool, def bool) bool {
	if p == nil {
		return def
	}
	return *p
}
