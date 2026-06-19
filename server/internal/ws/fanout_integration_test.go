//go:build integration

package ws

import (
	"context"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/atm-erp/server/internal/iam"
	"github.com/coder/websocket"
	"github.com/gin-gonic/gin"
	"github.com/redis/go-redis/v9"
)

const fanoutRedisAddr = "127.0.0.1:56390"

// 多实例扇出:客户端连实例 A,实例 B(模拟另一进程 / worker)经 SendToUser 发布到 Redis,
// 实例 A 订阅后投递给本地连接。验证跨实例推送 + 按 uid 隔离。
func TestRedisFanoutCrossInstance(t *testing.T) {
	ctx := context.Background()
	rdbA := redis.NewClient(&redis.Options{Addr: fanoutRedisAddr})
	rdbB := redis.NewClient(&redis.Options{Addr: fanoutRedisAddr})
	defer rdbA.Close()
	defer rdbB.Close()
	if err := rdbA.Ping(ctx).Err(); err != nil {
		t.Fatalf("redis 不可用: %v", err)
	}
	const channel = "ws:test:fanout"

	hubA, err := NewHubWithRedis(ctx, rdbA, channel) // 带订阅 + WS 端点
	if err != nil {
		t.Fatalf("hubA: %v", err)
	}
	defer hubA.Close()                     // 终止 consume goroutine
	hubB := NewHubPublisher(rdbB, channel) // 只发布(另一进程 / worker)

	gin.SetMode(gin.TestMode)
	tm := iam.NewTokenManager("test-secret-0123456789abcdefghij", 60, 7)
	const uid = uint64(42)
	tok, err := tm.Access(uid)
	if err != nil {
		t.Fatalf("签 token: %v", err)
	}

	r := gin.New()
	r.GET("/ws/notifications", hubA.Handler(tm))
	srv := httptest.NewServer(r)
	defer srv.Close()

	wsURL := "ws" + strings.TrimPrefix(srv.URL, "http") + "/ws/notifications"
	c, _, err := websocket.Dial(ctx, wsURL, &websocket.DialOptions{
		Subprotocols: []string{wsAuthSubprotocol, tok}, // 子协议鉴权:["access_token", <jwt>]
	})
	if err != nil {
		t.Fatalf("dial: %v", err)
	}
	defer c.Close(websocket.StatusNormalClosure, "")

	// 等连接在 hubA 注册(Accept 后 add 是异步的)
	ok := false
	for i := 0; i < 100; i++ {
		if hubA.connCount() == 1 {
			ok = true
			break
		}
		time.Sleep(20 * time.Millisecond)
	}
	if !ok {
		t.Fatal("WS 连接未注册到 hubA")
	}

	// 实例 B 发布给 uid → 经 Redis → 实例 A 投递给客户端
	hubB.SendToUser(ctx, uid, []byte(`{"type":"notification","data":{"id":1}}`))

	rctx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()
	_, data, err := c.Read(rctx)
	if err != nil {
		t.Fatalf("跨实例消息未送达: %v", err)
	}
	if !strings.Contains(string(data), `"id":1`) {
		t.Errorf("收到 %q,期望含 id:1", string(data))
	}

	// 隔离:发给别的 uid 不应送到本客户端
	hubB.SendToUser(ctx, 99, []byte(`{"x":1}`))
	rctx2, cancel2 := context.WithTimeout(ctx, 800*time.Millisecond)
	defer cancel2()
	if _, _, err := c.Read(rctx2); err == nil {
		t.Error("不应收到发给他人的消息(uid 隔离失效)")
	}
}
