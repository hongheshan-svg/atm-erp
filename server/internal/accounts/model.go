// Package accounts 实现账户/用户/角色/部门/权限模块,忠实迁移 Django apps.accounts
// 与 apps.core 的 RBAC 实体。结构与 masterdata/item 参考切片同构。
package accounts

import (
	"time"

	"github.com/atm-erp/server/internal/platform/model"
	"gorm.io/gorm"
)

// SoftBase 对应 Django TimeStampedModel + SoftDeleteModel(无 created_by/updated_by)。
// User/Role/Department 继承的是这两个抽象类,故其表无操作人列;不可直接用 model.Base
// (model.Base 含 created_by/updated_by,会与现有表结构不符)。
// BeforeDelete 复刻软删除互认:UPDATE 时同步写 is_deleted=true(对齐 ADR-006)。
type SoftBase struct {
	ID        uint64         `gorm:"primaryKey;column:id" json:"id"`
	CreatedAt time.Time      `gorm:"column:created_at" json:"created_at"`
	UpdatedAt time.Time      `gorm:"column:updated_at" json:"updated_at"`
	IsDeleted bool           `gorm:"column:is_deleted;index" json:"is_deleted"`
	DeletedAt gorm.DeletedAt `gorm:"column:deleted_at;index" json:"-"`
}

// BeforeDelete 在软删除 UPDATE 中同步 is_deleted=true(与 Django soft_delete 互认)。
func (b *SoftBase) BeforeDelete(tx *gorm.DB) error {
	tx.Statement.SetColumn("is_deleted", true)
	return nil
}

// Department 部门(层级树),对齐 Django Department / db_table=department。
type Department struct {
	SoftBase
	Name        string  `gorm:"column:name;size:100" json:"name"`
	Code        string  `gorm:"column:code;size:50;uniqueIndex" json:"code"`
	ParentID    *uint64 `gorm:"column:parent_id" json:"parent_id,omitempty"`
	ManagerID   *uint64 `gorm:"column:manager_id" json:"manager_id,omitempty"`
	Description string  `gorm:"column:description" json:"description"`
	SortOrder   int     `gorm:"column:sort_order;default:0" json:"sort_order"`
}

// TableName 对齐 Django Meta.db_table。
func (Department) TableName() string { return "department" }

// Role 角色,对齐 Django Role / db_table=role。
// Permissions 为 JSON 旧字段({"menu_ids":[...],"permissions":[...]});结构化权限走
// core_role_permission(见 RolePermission),数据范围走 core_data_scope(见 DataScope)。
type Role struct {
	SoftBase
	Name        string `gorm:"column:name;size:100;uniqueIndex" json:"name"`
	Code        string `gorm:"column:code;size:50;uniqueIndex" json:"code"`
	Description string `gorm:"column:description" json:"description"`
	// DataScope 旧粗粒度数据范围(ALL/DEPARTMENT/SELF),细粒度按模块见 core_data_scope。
	DataScope string `gorm:"column:data_scope;size:20;default:ALL" json:"data_scope"`
	// Permissions 旧 JSONField,GORM 读为原始 JSON 字符串(序列化器侧解析)。
	// TODO(verify): Postgres jsonb 列;如需结构化访问可换 datatypes.JSON(本轮不引入新依赖)。
	Permissions string `gorm:"column:permissions;type:jsonb;default:'{}'" json:"permissions"`
	IsActive    bool   `gorm:"column:is_active;default:true" json:"is_active"`
	SortOrder   int    `gorm:"column:sort_order;default:0" json:"sort_order"`
}

// TableName 对齐 Django Meta.db_table。
func (Role) TableName() string { return "role" }

// User 用户。Django 继承 AbstractUser,故含 username/password/email 等内建字段,
// 这里逐一映射到 auth 字段;db_table=user。
//
// 注意:Django AbstractUser 的 PK 仍是 BigAutoField id(model.Base 已含);
// password 是 PBKDF2 编码串(算法$迭代$盐$哈希)。
type User struct {
	SoftBase
	// --- Django AbstractUser 内建字段 ---
	Password    string     `gorm:"column:password;size:128" json:"-"`
	LastLogin   *time.Time `gorm:"column:last_login" json:"last_login,omitempty"`
	IsSuperuser bool       `gorm:"column:is_superuser;default:false" json:"is_superuser"`
	Username    string     `gorm:"column:username;size:150;uniqueIndex" json:"username"`
	FirstName   string     `gorm:"column:first_name;size:150" json:"first_name"`
	LastName    string     `gorm:"column:last_name;size:150" json:"last_name"`
	Email       string     `gorm:"column:email;size:254" json:"email"`
	IsStaff     bool       `gorm:"column:is_staff;default:false" json:"is_staff"`
	IsActive    bool       `gorm:"column:is_active;default:true" json:"is_active"`
	DateJoined  time.Time  `gorm:"column:date_joined" json:"date_joined"`

	// --- 自定义扩展字段 ---
	EmployeeID   string     `gorm:"column:employee_id;size:50;uniqueIndex" json:"employee_id"`
	Phone        string     `gorm:"column:phone;size:20" json:"phone"`
	Avatar       string     `gorm:"column:avatar;size:255" json:"avatar"`
	Gender       string     `gorm:"column:gender;size:1" json:"gender"`
	BirthDate    *time.Time `gorm:"column:birth_date" json:"birth_date,omitempty"`
	WechatWorkID string     `gorm:"column:wechat_work_id;size:100" json:"wechat_work_id"`
	DingtalkID   string     `gorm:"column:dingtalk_id;size:100" json:"dingtalk_id"`
	DepartmentID *uint64    `gorm:"column:department_id" json:"department_id,omitempty"`
	RoleID       *uint64    `gorm:"column:role_id" json:"role_id,omitempty"`
	Position     string     `gorm:"column:position;size:100" json:"position"`
	HireDate     *time.Time `gorm:"column:hire_date" json:"hire_date,omitempty"`
}

// TableName 对齐 Django Meta.db_table。
func (User) TableName() string { return "user" }

// FullName 复刻 Django User.get_full_name():姓(last_name)+名(first_name),空则用 username。
func (u *User) FullName() string {
	name := u.LastName + u.FirstName
	if name == "" {
		return u.Username
	}
	return name
}

// Permission 权限(树形:菜单/操作/字段),对齐 core.Permission / db_table=core_permission。
type Permission struct {
	model.Base
	ParentID  *uint64 `gorm:"column:parent_id" json:"parent_id,omitempty"`
	Code      string  `gorm:"column:code;size:100;uniqueIndex" json:"code"`
	Name      string  `gorm:"column:name;size:100" json:"name"`
	Type      string  `gorm:"column:type;size:20" json:"type"` // menu/operation/field
	Resource  string  `gorm:"column:resource;size:100" json:"resource"`
	FieldName string  `gorm:"column:field_name;size:100" json:"field_name"`
	RoutePath string  `gorm:"column:route_path;size:200" json:"route_path"`
	Icon      string  `gorm:"column:icon;size:100" json:"icon"`
	SortOrder int     `gorm:"column:sort_order;default:0" json:"sort_order"`
	IsActive  bool    `gorm:"column:is_active;default:true" json:"is_active"`
}

// TableName 对齐 Django Meta.db_table。
func (Permission) TableName() string { return "core_permission" }

// RolePermission 角色-权限关联(不软删除),对齐 core.RolePermission / db_table=core_role_permission。
// TODO(port): 维护接口待 Role 详情/授权页面对接,本轮仅提供 model 与表名。
type RolePermission struct {
	ID           uint64    `gorm:"primaryKey;column:id" json:"id"`
	RoleID       uint64    `gorm:"column:role_id;index" json:"role_id"`
	PermissionID uint64    `gorm:"column:permission_id;index" json:"permission_id"`
	CreatedAt    time.Time `gorm:"column:created_at" json:"created_at"`
}

// TableName 对齐 Django Meta.db_table。
func (RolePermission) TableName() string { return "core_role_permission" }

// DataScopeRule 角色-模块数据范围(不软删除),对齐 core.DataScope / db_table=core_data_scope。
// 命名加 Rule 后缀以避免与 iam.DataScope 概念混淆。
// TODO(port): 与 iam.ApplyScope 打通的真实 PermissionService 见 task #43。
type DataScopeRule struct {
	ID        uint64    `gorm:"primaryKey;column:id" json:"id"`
	RoleID    uint64    `gorm:"column:role_id;index" json:"role_id"`
	Module    string    `gorm:"column:module;size:50" json:"module"`
	ScopeType string    `gorm:"column:scope_type;size:30" json:"scope_type"` // all/dept/dept_tree/self/custom
	CreatedAt time.Time `gorm:"column:created_at" json:"created_at"`
	UpdatedAt time.Time `gorm:"column:updated_at" json:"updated_at"`
}

// TableName 对齐 Django Meta.db_table。
func (DataScopeRule) TableName() string { return "core_data_scope" }
