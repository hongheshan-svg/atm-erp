package accounts

import (
	"context"
	"fmt"
	"time"

	"github.com/atm-erp/server/internal/iam"
	"github.com/atm-erp/server/internal/platform/cache"
)

// CachedPermissionService 在 GormPermissionService 外加一层 Redis 缓存(对齐性能设计:
// 权限/数据范围缓存,复刻旧 user_permissions:{id} 键)。TTL 5 分钟。
// TODO(verify): 角色授权/权限变更时需主动失效 erp:perm:<uid>(待 Role 授权接口落地后接入)。
type CachedPermissionService struct {
	base  *GormPermissionService
	cache cache.Cache
	ttl   time.Duration
}

func NewCachedPermissionService(base *GormPermissionService, c cache.Cache) *CachedPermissionService {
	return &CachedPermissionService{base: base, cache: c, ttl: 5 * time.Minute}
}

var _ iam.PermissionService = (*CachedPermissionService)(nil)

func (s *CachedPermissionService) Load(ctx context.Context, uid uint64) (*iam.AuthUser, error) {
	key := fmt.Sprintf("erp:perm:%d", uid)
	var cached iam.AuthUser
	if ok, _ := s.cache.GetJSON(ctx, key, &cached); ok {
		return &cached, nil
	}
	au, err := s.base.Load(ctx, uid)
	if err != nil {
		return nil, err
	}
	_ = s.cache.SetJSON(ctx, key, au, s.ttl)
	return au, nil
}
