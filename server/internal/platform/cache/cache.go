// Package cache 提供 Redis 缓存(go-redis),复用现有 Redis 7。
package cache

import (
	"context"
	"encoding/json"
	"time"

	"github.com/redis/go-redis/v9"
)

// Cache 是缓存抽象,便于测试替身与未来多级缓存。
type Cache interface {
	GetJSON(ctx context.Context, key string, dest any) (bool, error)
	SetJSON(ctx context.Context, key string, val any, ttl time.Duration) error
	Del(ctx context.Context, keys ...string) error
}

type Redis struct{ c *redis.Client }

// NewRedis 解析 REDIS_URL 并 Ping 校验连通;不可用时返回错误(调用方可降级)。
func NewRedis(url string) (*Redis, error) {
	opt, err := redis.ParseURL(url)
	if err != nil {
		return nil, err
	}
	c := redis.NewClient(opt)
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	if err := c.Ping(ctx).Err(); err != nil {
		_ = c.Close()
		return nil, err
	}
	return &Redis{c: c}, nil
}

func (r *Redis) GetJSON(ctx context.Context, key string, dest any) (bool, error) {
	b, err := r.c.Get(ctx, key).Bytes()
	if err == redis.Nil {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	return true, json.Unmarshal(b, dest)
}

func (r *Redis) SetJSON(ctx context.Context, key string, val any, ttl time.Duration) error {
	b, err := json.Marshal(val)
	if err != nil {
		return err
	}
	return r.c.Set(ctx, key, b, ttl).Err()
}

func (r *Redis) Del(ctx context.Context, keys ...string) error {
	return r.c.Del(ctx, keys...).Err()
}

// Client 暴露底层客户端供 asynq/redsync 等复用。
func (r *Redis) Client() *redis.Client { return r.c }
