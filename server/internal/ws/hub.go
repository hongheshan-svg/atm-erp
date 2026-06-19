// Package ws 提供 WebSocket Hub(coder/websocket),替代 Django Channels。
// 本期为单实例内存 Hub;多实例扇出需接 Redis Pub/Sub(TODO)。
package ws

import (
	"context"
	"net/http"
	"sync"

	"github.com/atm-erp/server/internal/iam"
	"github.com/coder/websocket"
	"github.com/gin-gonic/gin"
)

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

// Broadcast 向所有连接推送文本消息(信封 {type,data} 由调用方序列化)。
// TODO(port): 按 group(user_{id}/dashboard/upgrade_{job})定向 + Redis Pub/Sub 多实例扇出。
func (h *Hub) Broadcast(ctx context.Context, msg []byte) {
	h.mu.RLock()
	defer h.mu.RUnlock()
	for c := range h.conns {
		_ = c.Write(ctx, websocket.MessageText, msg)
	}
}

// Handler 升级 WS 连接,?token= 用 JWT 鉴权(对齐旧 consumer 的 query token)。
// TODO(security): 评审建议改 Sec-WebSocket-Protocol 子协议鉴权,避免 token 进 access log。
func (h *Hub) Handler(tm *iam.TokenManager) gin.HandlerFunc {
	return func(g *gin.Context) {
		claims, err := tm.Parse(g.Query("token"))
		if err != nil || claims.TokenType != "access" {
			g.AbortWithStatus(http.StatusUnauthorized)
			return
		}
		c, err := websocket.Accept(g.Writer, g.Request, nil)
		if err != nil {
			return
		}
		h.add(c, claims.UserID)
		defer h.remove(c)
		defer func() { _ = c.Close(websocket.StatusNormalClosure, "") }()

		ctx := g.Request.Context()
		for { // 读循环保持连接;收到错误(断开)即退出
			if _, _, err := c.Read(ctx); err != nil {
				return
			}
		}
	}
}
