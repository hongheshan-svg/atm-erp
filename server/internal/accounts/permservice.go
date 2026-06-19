package accounts

import (
	"context"
	"encoding/json"

	"github.com/atm-erp/server/internal/iam"
	"gorm.io/gorm"
)

// GormPermissionService 是 iam.PermissionService 的生产实现:
// 从现有 RBAC 表(user / role / core_permission / core_role_permission / core_data_scope)
// 解析用户的权限码与数据范围,替代仅供本地的 StaticPermissionService(task #43)。
type GormPermissionService struct{ db *gorm.DB }

func NewGormPermissionService(db *gorm.DB) *GormPermissionService {
	return &GormPermissionService{db: db}
}

var _ iam.PermissionService = (*GormPermissionService)(nil)

func (s *GormPermissionService) Load(ctx context.Context, userID uint64) (*iam.AuthUser, error) {
	var u User
	if err := s.db.WithContext(ctx).Where("id = ? AND is_active = ?", userID, true).First(&u).Error; err != nil {
		return nil, err
	}
	au := &iam.AuthUser{
		ID:          u.ID,
		Username:    u.Username,
		IsSuperuser: u.IsSuperuser,
		Permissions: []string{},
		DataScopes:  map[string]string{},
	}
	if u.DepartmentID != nil {
		au.DeptIDs = []uint64{*u.DepartmentID}
	}
	if u.IsSuperuser {
		return au, nil // 超管放行,无需解析权限
	}

	roleIDs := s.roleIDs(ctx, &u)
	if len(roleIDs) == 0 {
		return au, nil
	}
	au.Permissions = s.permissions(ctx, roleIDs)
	au.DataScopes = s.dataScopes(ctx, roleIDs)
	return au, nil
}

// roleIDs 收集用户角色:单 role_id FK + M2M user_roles(尽力;表不存在则忽略)。
// TODO(verify): 多角色(user_roles)是 Django 的扩展;若现网以 M2M 为准需对齐去重口径。
func (s *GormPermissionService) roleIDs(ctx context.Context, u *User) []uint64 {
	set := map[uint64]struct{}{}
	if u.RoleID != nil {
		set[*u.RoleID] = struct{}{}
	}
	var m2m []uint64
	_ = s.db.WithContext(ctx).Table("user_roles").
		Where("user_id = ?", u.ID).Pluck("role_id", &m2m).Error
	for _, id := range m2m {
		set[id] = struct{}{}
	}
	out := make([]uint64, 0, len(set))
	for id := range set {
		out = append(out, id)
	}
	return out
}

// permissions 取角色授予的权限码:core_role_permission JOIN core_permission(active)
// 并入 role.permissions(jsonb {"permissions":[...]})两个来源的并集。
func (s *GormPermissionService) permissions(ctx context.Context, roleIDs []uint64) []string {
	set := map[string]struct{}{}

	var codes []string
	_ = s.db.WithContext(ctx).
		Table("core_role_permission AS rp").
		Joins("JOIN core_permission AS p ON p.id = rp.permission_id").
		Where("rp.role_id IN ? AND p.is_active = ? AND p.deleted_at IS NULL", roleIDs, true).
		Pluck("p.code", &codes).Error
	for _, c := range codes {
		if c != "" {
			set[c] = struct{}{}
		}
	}

	var roles []Role
	_ = s.db.WithContext(ctx).Where("id IN ?", roleIDs).Find(&roles).Error
	for _, r := range roles {
		if r.Permissions == "" {
			continue
		}
		var blob struct {
			Permissions []string `json:"permissions"`
		}
		if json.Unmarshal([]byte(r.Permissions), &blob) == nil {
			for _, c := range blob.Permissions {
				if c != "" {
					set[c] = struct{}{}
				}
			}
		}
	}

	out := make([]string, 0, len(set))
	for c := range set {
		out = append(out, c)
	}
	return out
}

// dataScopes 取每模块最宽数据范围(core_data_scope:role_id, module, scope_type)。
func (s *GormPermissionService) dataScopes(ctx context.Context, roleIDs []uint64) map[string]string {
	var rules []DataScopeRule
	_ = s.db.WithContext(ctx).Where("role_id IN ?", roleIDs).Find(&rules).Error
	out := map[string]string{}
	for _, r := range rules {
		if cur, ok := out[r.Module]; !ok || scopeRank(r.ScopeType) > scopeRank(cur) {
			out[r.Module] = r.ScopeType
		}
	}
	return out
}

// scopeRank 数据范围宽窄:all > dept_tree > dept > self > custom。
func scopeRank(s string) int {
	switch s {
	case "all":
		return 5
	case "dept_tree":
		return 4
	case "dept":
		return 3
	case "self":
		return 2
	case "custom":
		return 1
	default:
		return 0
	}
}
