// Package ws 提供 WebSocket Hub(coder/websocket),替代 Django Channels。
// 本期为单实例内存 Hub;多实例扇出需接 Redis Pub/Sub(TODO)。
package ws

import (
	"context"
	"net/http"
	"strings"
	"sync"

	"github.com/atm-erp/server/internal/iam"
	"github.com/coder/websocket"
	"github.com/gin-gonic/gin"
)

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

// Hub 管理活动连接(单实例内存)。
type Hub struct {
	mu    sync.RWMutex
	conns map[*websocket.Conn]uint64 // conn -> userID
}

func NewHub() *Hub { return &Hub{conns: make(map[*websocket.Conn]uint64)} }

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

// SendToUser 仅向指定用户的连接推送(按 uid 过滤),避免跨用户数据泄露。
func (h *Hub) SendToUser(ctx context.Context, uid uint64, msg []byte) {
	h.mu.RLock()
	defer h.mu.RUnlock()
	for c, u := range h.conns {
		if u == uid {
			_ = c.Write(ctx, websocket.MessageText, msg)
		}
	}
}

// BroadcastPublic 向所有连接推送——仅限真正面向全员的公开消息(如系统公告);
// 严禁用于用户私有数据(用户态数据请用 SendToUser)。
// TODO(port): group(user_{id}/dashboard/upgrade_{job})定向 + Redis Pub/Sub 多实例扇出。
func (h *Hub) BroadcastPublic(ctx context.Context, msg []byte) {
	h.mu.RLock()
	defer h.mu.RUnlock()
	for c := range h.conns {
		_ = c.Write(ctx, websocket.MessageText, msg)
	}
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
