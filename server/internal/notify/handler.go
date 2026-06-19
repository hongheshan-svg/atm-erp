package notify

import (
	"net/http"
	"strconv"

	"github.com/atm-erp/server/internal/iam"
	"github.com/atm-erp/server/internal/platform/httpx"
	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
)

type Handler struct{ svc *Service }

func NewHandler(svc *Service) *Handler { return &Handler{svc: svc} }

// Routes 注册站内信路由。通知按用户隔离(只看自己的),仅需登录,不额外做权限码校验。
func Routes(rg *gin.RouterGroup, gdb *gorm.DB, perm func(string) gin.HandlerFunc) {
	RoutesWithService(rg, NewService(gdb), perm)
}

// RoutesWithService 用既有 Service 注册路由(便于注入带 WebSocket 推送的 Service)。
func RoutesWithService(rg *gin.RouterGroup, svc *Service, _ func(string) gin.HandlerFunc) {
	h := NewHandler(svc)
	g := rg.Group("/notifications")
	g.GET("", h.list)
	g.GET("/unread_count", h.unreadCount)
	g.POST("/:id/read", h.markRead)
	g.POST("/read_all", h.markAllRead)
}

func (h *Handler) uid(c *gin.Context) (uint64, bool) {
	u, ok := iam.CurrentUser(c)
	if !ok {
		httpx.Error(c, http.StatusUnauthorized, "未认证")
		return 0, false
	}
	return u.ID, true
}

func (h *Handler) list(c *gin.Context) {
	uid, ok := h.uid(c)
	if !ok {
		return
	}
	p := httpx.ParsePage(c)
	onlyUnread := c.Query("unread") == "true"
	items, total, err := h.svc.List(c.Request.Context(), uid, onlyUnread, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[Notification]{Count: total, Results: items})
}

func (h *Handler) unreadCount(c *gin.Context) {
	uid, ok := h.uid(c)
	if !ok {
		return
	}
	n, err := h.svc.UnreadCount(c.Request.Context(), uid)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, gin.H{"unread": n})
}

func (h *Handler) markRead(c *gin.Context) {
	uid, ok := h.uid(c)
	if !ok {
		return
	}
	id, _ := strconv.ParseUint(c.Param("id"), 10, 64)
	if err := h.svc.MarkRead(c.Request.Context(), uid, id); err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.NoContent(c)
}

func (h *Handler) markAllRead(c *gin.Context) {
	uid, ok := h.uid(c)
	if !ok {
		return
	}
	if err := h.svc.MarkAllRead(c.Request.Context(), uid); err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.NoContent(c)
}
