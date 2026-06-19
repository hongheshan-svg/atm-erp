package accounts

import (
	"context"

	"github.com/atm-erp/server/internal/iam"
	"gorm.io/gorm"
)

// scopeModule 标识该资源所属权限/数据范围模块(对齐 Django 模块名)。
const scopeModule = "accounts"

type Repo struct{ db *gorm.DB }

func NewRepo(db *gorm.DB) *Repo { return &Repo{db: db} }

// db 直通(写操作用,软删除互认靠各 model 的 BeforeDelete 钩子)。
func (r *Repo) raw(ctx context.Context) *gorm.DB { return r.db.WithContext(ctx) }

// ---------------- Department ----------------
// 说明:User/Role/Department 表无 created_by 列(继承 TimeStampedModel+SoftDeleteModel),
// 故不套 iam.ApplyScope("created_by_id");这些为系统管理实体,访问由权限码 accounts:* 控制。
// TODO(verify): 若后续要按 dept 维度做数据范围,需引入专门的 owner 列或部门归属逻辑。

func (r *Repo) ListDepartments(ctx context.Context, q DeptListQuery, offset, limit int) ([]Department, int64, error) {
	tx := r.raw(ctx).Model(&Department{})
	if q.Keyword != "" {
		kw := "%" + q.Keyword + "%"
		tx = tx.Where("name LIKE ? OR code LIKE ?", kw, kw)
	}
	if q.ParentID != nil {
		tx = tx.Where("parent_id = ?", *q.ParentID)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var rows []Department
	if err := tx.Order("sort_order ASC, code ASC").Offset(offset).Limit(limit).Find(&rows).Error; err != nil {
		return nil, 0, err
	}
	return rows, total, nil
}

func (r *Repo) GetDepartment(ctx context.Context, id uint64) (*Department, error) {
	var d Department
	if err := r.raw(ctx).First(&d, id).Error; err != nil {
		return nil, err
	}
	return &d, nil
}

func (r *Repo) CreateDepartment(ctx context.Context, d *Department) error {
	return r.raw(ctx).Create(d).Error
}

func (r *Repo) SaveDepartment(ctx context.Context, d *Department) error {
	return r.raw(ctx).Save(d).Error
}

func (r *Repo) DeleteDepartment(ctx context.Context, id uint64) error {
	return r.raw(ctx).Delete(&Department{}, id).Error
}

// CountDeptChildren 统计直接子部门数(删除前校验用)。
func (r *Repo) CountDeptChildren(ctx context.Context, id uint64) (int64, error) {
	var n int64
	err := r.raw(ctx).Model(&Department{}).Where("parent_id = ?", id).Count(&n).Error
	return n, err
}

// CountDeptUsers 统计部门下用户数(删除前校验用)。
func (r *Repo) CountDeptUsers(ctx context.Context, id uint64) (int64, error) {
	var n int64
	err := r.raw(ctx).Model(&User{}).Where("department_id = ?", id).Count(&n).Error
	return n, err
}

// ---------------- Role ----------------

func (r *Repo) ListRoles(ctx context.Context, q RoleListQuery, offset, limit int) ([]Role, int64, error) {
	tx := r.raw(ctx).Model(&Role{})
	if q.Keyword != "" {
		kw := "%" + q.Keyword + "%"
		tx = tx.Where("name LIKE ? OR code LIKE ?", kw, kw)
	}
	if q.IsActive != nil {
		tx = tx.Where("is_active = ?", *q.IsActive)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var rows []Role
	if err := tx.Order("sort_order ASC, code ASC").Offset(offset).Limit(limit).Find(&rows).Error; err != nil {
		return nil, 0, err
	}
	return rows, total, nil
}

func (r *Repo) GetRole(ctx context.Context, id uint64) (*Role, error) {
	var role Role
	if err := r.raw(ctx).First(&role, id).Error; err != nil {
		return nil, err
	}
	return &role, nil
}

func (r *Repo) CreateRole(ctx context.Context, role *Role) error {
	return r.raw(ctx).Create(role).Error
}

func (r *Repo) SaveRole(ctx context.Context, role *Role) error {
	return r.raw(ctx).Save(role).Error
}

func (r *Repo) DeleteRole(ctx context.Context, id uint64) error {
	return r.raw(ctx).Delete(&Role{}, id).Error
}

// CountRoleUsers 统计绑定该角色的用户数(删除前校验用,含旧单角色 role_id)。
func (r *Repo) CountRoleUsers(ctx context.Context, id uint64) (int64, error) {
	var n int64
	err := r.raw(ctx).Model(&User{}).Where("role_id = ?", id).Count(&n).Error
	return n, err
}

// ---------------- User ----------------

func (r *Repo) ListUsers(ctx context.Context, q UserListQuery, offset, limit int) ([]User, int64, error) {
	tx := r.raw(ctx).Model(&User{})
	if q.Keyword != "" {
		kw := "%" + q.Keyword + "%"
		tx = tx.Where(
			"username LIKE ? OR employee_id LIKE ? OR email LIKE ? OR first_name LIKE ? OR last_name LIKE ?",
			kw, kw, kw, kw, kw,
		)
	}
	if q.DepartmentID != nil {
		tx = tx.Where("department_id = ?", *q.DepartmentID)
	}
	if q.RoleID != nil {
		tx = tx.Where("role_id = ?", *q.RoleID)
	}
	if q.IsActive != nil {
		tx = tx.Where("is_active = ?", *q.IsActive)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var rows []User
	if err := tx.Order("created_at DESC").Offset(offset).Limit(limit).Find(&rows).Error; err != nil {
		return nil, 0, err
	}
	return rows, total, nil
}

func (r *Repo) GetUser(ctx context.Context, id uint64) (*User, error) {
	var u User
	if err := r.raw(ctx).First(&u, id).Error; err != nil {
		return nil, err
	}
	return &u, nil
}

func (r *Repo) CreateUser(ctx context.Context, u *User) error {
	return r.raw(ctx).Create(u).Error
}

func (r *Repo) SaveUser(ctx context.Context, u *User) error {
	return r.raw(ctx).Save(u).Error
}

func (r *Repo) DeleteUser(ctx context.Context, id uint64) error {
	return r.raw(ctx).Delete(&User{}, id).Error
}

// UsernameExists 唯一性校验(排除指定 id;0 表示新建)。
func (r *Repo) UsernameExists(ctx context.Context, username string, excludeID uint64) (bool, error) {
	var n int64
	tx := r.raw(ctx).Model(&User{}).Where("username = ?", username)
	if excludeID != 0 {
		tx = tx.Where("id <> ?", excludeID)
	}
	err := tx.Count(&n).Error
	return n > 0, err
}

// EmployeeIDExists 工号唯一性校验。
func (r *Repo) EmployeeIDExists(ctx context.Context, empID string, excludeID uint64) (bool, error) {
	var n int64
	tx := r.raw(ctx).Model(&User{}).Where("employee_id = ?", empID)
	if excludeID != 0 {
		tx = tx.Where("id <> ?", excludeID)
	}
	err := tx.Count(&n).Error
	return n > 0, err
}

// MaxEmployeeIDNum 取现有工号最大序号(用于自动生成,见 service)。
// TODO(verify): Django 端工号生成规则需确认;此处提供一个朴素自增基础。
func (r *Repo) CountUsers(ctx context.Context) (int64, error) {
	var n int64
	err := r.raw(ctx).Model(&User{}).Count(&n).Error
	return n, err
}

// ---------------- Permission ----------------
// Permission 继承 BaseModel,有 created_by 列;但权限树为全局系统数据,通常不按个人范围过滤。
// 这里保留 scoped 能力但默认对超管/系统管理放行(由 accounts:permission:* 权限码把关)。

func (r *Repo) permScoped(ctx context.Context) *gorm.DB {
	q := r.raw(ctx).Model(&Permission{})
	if u, ok := iam.AuthUserFrom(ctx); ok && !u.IsSuperuser {
		// 非超管时仍按数据范围控制(created_by);超管查看全部权限树。
		q = iam.ApplyScope(q, u, scopeModule, "created_by_id")
	}
	return q
}

func (r *Repo) ListPermissions(ctx context.Context, q PermissionListQuery, offset, limit int) ([]Permission, int64, error) {
	tx := r.permScoped(ctx)
	if q.Keyword != "" {
		kw := "%" + q.Keyword + "%"
		tx = tx.Where("code LIKE ? OR name LIKE ?", kw, kw)
	}
	if q.Type != "" {
		tx = tx.Where("type = ?", q.Type)
	}
	if q.Resource != "" {
		tx = tx.Where("resource = ?", q.Resource)
	}
	if q.IsActive != nil {
		tx = tx.Where("is_active = ?", *q.IsActive)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var rows []Permission
	if err := tx.Order("sort_order ASC, id ASC").Offset(offset).Limit(limit).Find(&rows).Error; err != nil {
		return nil, 0, err
	}
	return rows, total, nil
}

func (r *Repo) GetPermission(ctx context.Context, id uint64) (*Permission, error) {
	var p Permission
	if err := r.permScoped(ctx).Where("id = ?", id).First(&p).Error; err != nil {
		return nil, err
	}
	return &p, nil
}

func (r *Repo) CreatePermission(ctx context.Context, p *Permission) error {
	return r.raw(ctx).Create(p).Error
}

func (r *Repo) SavePermission(ctx context.Context, p *Permission) error {
	return r.raw(ctx).Save(p).Error
}

func (r *Repo) DeletePermission(ctx context.Context, id uint64) error {
	return r.raw(ctx).Delete(&Permission{}, id).Error
}

// PermissionCodeExists 权限码唯一性校验。
func (r *Repo) PermissionCodeExists(ctx context.Context, code string, excludeID uint64) (bool, error) {
	var n int64
	tx := r.raw(ctx).Model(&Permission{}).Where("code = ?", code)
	if excludeID != 0 {
		tx = tx.Where("id <> ?", excludeID)
	}
	err := tx.Count(&n).Error
	return n > 0, err
}
