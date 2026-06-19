// Package ws 提供 WebSocket Hub(coder/websocket),替代 Django Channels。
// 单实例时本地直投;注入 Redis 后经 Pub/Sub 跨实例扇出(任一实例/worker 产生的推送发布到频道,
// 各 serve 实例订阅后投递给本地对应连接),支持多副本部署。
package ws

import (
	"context"
	"encoding/json"
	"net/http"
	"strings"
	"sync"
	"time"

	"github.com/atm-erp/server/internal/iam"
	"github.com/coder/websocket"
	"github.com/gin-gonic/gin"
	"github.com/redis/go-redis/v9"
)

// FanoutChannel 是跨实例 WS 扇出的 Redis 频道名。
const FanoutChannel = "ws:fanout"

// wsAuthSubprotocol 是承载 access token 的鉴权子协议哨兵。
// 客户端按 ["access_token", <jwt>] 发起握手;服务端只回选哨兵本身(绝不回显 token)。
const wsAuthSubprotocol = "access_token"

// bearerSubprotocol 从 Sec-WebSocket-Protocol 取 access token(约定客户端发送
// ["access_token", <jwt>]),令 token 走握手头而非 URL,避免进 access log / 代理日志 / 浏览器历史。
// JWT(base64url + '.')是合法的子协议 token 字符,无需额外编码。
func bearerSubprotocol(r *http.Request) (string, bool) {
	for _, header := range r.Header.Values("Sec-WebSocket-Protocol") {
		parts := strings.Split(header, ",")
		for i := range parts {
			parts[i] = strings.TrimSpace(parts[i])
		}
		for i, p := range parts {
			if p == wsAuthSubprotocol && i+1 < len(parts) && parts[i+1] != "" {
				return parts[i+1], true
			}
		}
	}
	return "", false
}

// Hub 管理活动 WebSocket 连接。rdb 为 nil 时单实例本地直投;非 nil 时推送经 Redis Pub/Sub
// 发布到频道,各实例(含本实例)订阅后投递给本地对应连接,实现多副本跨实例扇出。
type Hub struct {
	mu      sync.RWMutex
	conns   map[*websocket.Conn]uint64 // conn -> userID
	rdb     *redis.Client              // 非 nil 时启用 Redis 扇出
	channel string
	sub     *redis.PubSub // 仅 NewHubWithRedis 设置;Close() 用其终止 consume goroutine
}

// NewHub 创建单实例内存 Hub(无跨实例扇出),用于测试或 Redis 不可用时降级。
func NewHub() *Hub { return &Hub{conns: make(map[*websocket.Conn]uint64)} }

// NewHubWithRedis 创建带 Redis Pub/Sub 扇出的 Hub(serve 实例用:发布 + 订阅 + 本地投递)。
// 阻塞至订阅确认建立后返回,确保返回后发布的消息不会因订阅未就绪而丢失;之后由后台 goroutine 消费。
func NewHubWithRedis(ctx context.Context, rdb *redis.Client, channel string) (*Hub, error) {
	h := &Hub{conns: make(map[*websocket.Conn]uint64), rdb: rdb, channel: channel}
	sub := rdb.Subscribe(ctx, channel)
	if _, err := sub.Receive(ctx); err != nil { // 等订阅确认
		_ = sub.Close()
		return nil, err
	}
	h.sub = sub
	go h.consume(sub.Channel())
	return h, nil
}

// Close 关闭 Redis 订阅,终止 consume goroutine(优雅关停 / 测试清理);无订阅时为 no-op。
func (h *Hub) Close() error {
	if h.sub != nil {
		return h.sub.Close()
	}
	return nil
}

// NewHubPublisher 创建只发布的 Hub(worker 用:无 WS 端点、不订阅,仅把推送发布到 Redis 由 serve 实例投递)。
func NewHubPublisher(rdb *redis.Client, channel string) *Hub {
	return &Hub{conns: make(map[*websocket.Conn]uint64), rdb: rdb, channel: channel}
}

// hubEnvelope 是 Redis 频道上的消息信封。
type hubEnvelope struct {
	UserID    uint64          `json:"user_id"`
	Broadcast bool            `json:"broadcast"`
	Data      json.RawMessage `json:"data"`
}

func (h *Hub) add(c *websocket.Conn, uid uint64) {
	h.mu.Lock()
	h.conns[c] = uid
	h.mu.Unlock()
}

func (h *Hub) remove(c *websocket.Conn) {
	h.mu.Lock()
	delete(h.conns, c)
	h.mu.Unlock()
}

// consume 消费 Redis 频道消息并投递给本实例的本地连接(跨实例扇出的接收端)。
func (h *Hub) consume(ch <-chan *redis.Message) {
	for msg := range ch {
		var env hubEnvelope
		if err := json.Unmarshal([]byte(msg.Payload), &env); err != nil {
			continue
		}
		if env.Broadcast {
			h.broadcastLocal(env.Data)
		} else {
			h.deliverLocal(env.UserID, env.Data)
		}
	}
}

func (h *Hub) publish(ctx context.Context, env hubEnvelope) {
	b, err := json.Marshal(env)
	if err != nil {
		return
	}
	_ = h.rdb.Publish(ctx, h.channel, b).Err()
}

// SendToUser 仅向指定用户的连接推送(按 uid 过滤,避免跨用户数据泄露)。
// 注入 Redis 后改为发布到频道,由各实例订阅后本地投递,实现多实例扇出。
func (h *Hub) SendToUser(ctx context.Context, uid uint64, msg []byte) {
	if h.rdb != nil {
		h.publish(ctx, hubEnvelope{UserID: uid, Data: msg})
		return
	}
	h.deliverLocal(uid, msg)
}

// BroadcastPublic 向所有连接推送——仅限真正面向全员的公开消息(如系统公告);
// 严禁用于用户私有数据(用户态数据请用 SendToUser)。
func (h *Hub) BroadcastPublic(ctx context.Context, msg []byte) {
	if h.rdb != nil {
		h.publish(ctx, hubEnvelope{Broadcast: true, Data: msg})
		return
	}
	h.broadcastLocal(msg)
}

// deliverLocal 把消息写给本实例中属于 uid 的连接(锁内快照目标 + 锁外并发写)。
func (h *Hub) deliverLocal(uid uint64, msg []byte) {
	h.mu.RLock()
	targets := make([]*websocket.Conn, 0, 4)
	for c, u := range h.conns {
		if u == uid {
			targets = append(targets, c)
		}
	}
	h.mu.RUnlock()
	h.writeAll(targets, msg)
}

func (h *Hub) broadcastLocal(msg []byte) {
	h.mu.RLock()
	targets := make([]*websocket.Conn, 0, len(h.conns))
	for c := range h.conns {
		targets = append(targets, c)
	}
	h.mu.RUnlock()
	h.writeAll(targets, msg)
}

// writeAll 为每个目标连接起独立 goroutine 写(各自 5s 超时),避免单个慢/死连接串行阻塞
// consume 消费循环——否则一条 Redis 消息的投递会卡住后续所有消息(go-redis Channel buffer 满后丢弃)。
func (h *Hub) writeAll(targets []*websocket.Conn, msg []byte) {
	for _, c := range targets {
		go func() {
			wctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
			defer cancel()
			_ = c.Write(wctx, websocket.MessageText, msg)
		}()
	}
}

// connCount 返回当前本地连接数(测试辅助)。
func (h *Hub) connCount() int {
	h.mu.RLock()
	defer h.mu.RUnlock()
	return len(h.conns)
}

// Handler 升级 WS 连接,经 Sec-WebSocket-Protocol 子协议(["access_token", <jwt>])做 JWT 鉴权,
// 令 token 不进 URL(避免 access log / 代理日志 / 浏览器历史泄漏)。握手只回选哨兵子协议,绝不回显 token。
func (h *Hub) Handler(tm *iam.TokenManager) gin.HandlerFunc {
	return func(g *gin.Context) {
		token, ok := bearerSubprotocol(g.Request)
		if !ok {
			g.AbortWithStatus(http.StatusUnauthorized)
			return
		}
		claims, err := tm.Parse(token)
		if err != nil || claims.TokenType != "access" {
			g.AbortWithStatus(http.StatusUnauthorized)
			return
		}
		// 只声明哨兵子协议:浏览器要求服务端回选其所提供的某个子协议,这里回 "access_token"(非 token 值)。
		c, err := websocket.Accept(g.Writer, g.Request, &websocket.AcceptOptions{
			Subprotocols: []string{wsAuthSubprotocol},
		})
		if err != nil {
			return
		}
		h.add(c, claims.UserID)
		defer h.remove(c)
		defer func() { _ = c.Close(websocket.StatusNormalClosure, "") }()

		// 连接生命周期不超过 token 有效期:到期自动断开(对齐安全评审建议)。
		ctx := g.Request.Context()
		if claims.ExpiresAt != nil {
			var cancel context.CancelFunc
			ctx, cancel = context.WithDeadline(ctx, claims.ExpiresAt.Time)
			defer cancel()
		}
		for { // 读循环保持连接;收到错误(断开/到期)即退出
			if _, _, err := c.Read(ctx); err != nil {
				return
			}
		}
	}
}
