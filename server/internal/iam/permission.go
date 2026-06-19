package iam

import "context"

// PermissionService 加载用户的权限码与数据范围。
// 生产实现应查询现有 RBAC 表(role/role_user/permission + data_scope),并叠加 Redis 缓存。
type PermissionService interface {
	Load(ctx context.Context, userID uint64) (*AuthUser, error)
}

// StaticPermissionService 是脚手架起步用的默认实现:把已认证用户视为给定权限集。
// 注意:Superuser=true 仅用于本地起步演示;接入真实 RBAC 前不可用于生产。
// TODO(iam): 替换为查询 accounts/core 权限表的 GORM 实现(Phase 1)。
type StaticPermissionService struct {
	Superuser bool
	Perms     []string
	Scopes    map[string]string
}

func (s *StaticPermissionService) Load(_ context.Context, uid uint64) (*AuthUser, error) {
	return &AuthUser{
		ID:          uid,
		IsSuperuser: s.Superuser,
		Permissions: s.Perms,
		DataScopes:  s.Scopes,
	}, nil
}
