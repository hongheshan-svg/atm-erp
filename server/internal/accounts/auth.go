package accounts

import (
	"net/http"

	"github.com/atm-erp/server/internal/iam"
	"github.com/atm-erp/server/internal/platform/httpx"
	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
)

// AuthHandler 处理登录 / 刷新 / 当前用户资料,组装前端三件套所需的登录响应。
type AuthHandler struct {
	db *gorm.DB
	tm *iam.TokenManager
	ps *GormPermissionService
}

func NewAuthHandler(db *gorm.DB, tm *iam.TokenManager) *AuthHandler {
	return &AuthHandler{db: db, tm: tm, ps: NewGormPermissionService(db)}
}

// MountPublic 注册无需鉴权的端点(登录、刷新)。
func (h *AuthHandler) MountPublic(rg *gin.RouterGroup) {
	rg.POST("/auth/login", h.Login)
	rg.POST("/auth/refresh", h.Refresh)
}

// MountAuthed 注册需鉴权的端点(当前用户资料)。
func (h *AuthHandler) MountAuthed(rg *gin.RouterGroup) {
	rg.GET("/auth/profile", h.Profile)
}

type loginInput struct {
	Username string `json:"username" binding:"required"`
	Password string `json:"password" binding:"required"`
}

func (h *AuthHandler) Login(c *gin.Context) {
	var in loginInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	var u User
	err := h.db.WithContext(c.Request.Context()).
		Where("username = ? AND is_active = ?", in.Username, true).First(&u).Error
	if err != nil || !checkPassword(in.Password, u.Password) {
		// 统一错误,避免泄露用户是否存在
		httpx.Error(c, http.StatusUnauthorized, "用户名或密码错误")
		return
	}
	access, err := h.tm.Access(u.ID)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, "签发令牌失败")
		return
	}
	refresh, _ := h.tm.Refresh(u.ID)
	profile, _ := h.profile(c, u.ID)
	httpx.OK(c, gin.H{"access": access, "refresh": refresh, "user": profile})
}

func (h *AuthHandler) Refresh(c *gin.Context) {
	var body struct {
		Refresh string `json:"refresh" binding:"required"`
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	claims, err := h.tm.Parse(body.Refresh)
	if err != nil || claims.TokenType != "refresh" {
		httpx.Error(c, http.StatusUnauthorized, "刷新令牌无效或已过期")
		return
	}
	access, err := h.tm.Access(claims.UserID)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, "签发令牌失败")
		return
	}
	httpx.OK(c, gin.H{"access": access})
}

func (h *AuthHandler) Profile(c *gin.Context) {
	u, ok := iam.CurrentUser(c)
	if !ok {
		httpx.Error(c, http.StatusUnauthorized, "未认证")
		return
	}
	profile, err := h.profile(c, u.ID)
	if err != nil {
		httpx.Error(c, http.StatusNotFound, "用户不存在")
		return
	}
	httpx.OK(c, profile)
}

// profile 组装登录响应内嵌的用户资料(对齐旧 UserProfileSerializer 的关键字段:
// permissions / menus / data_scopes,供前端权限三件套零改使用)。
func (h *AuthHandler) profile(c *gin.Context, uid uint64) (gin.H, error) {
	au, err := h.ps.Load(c.Request.Context(), uid)
	if err != nil {
		return nil, err
	}
	var u User
	if err := h.db.WithContext(c.Request.Context()).Where("id = ?", uid).First(&u).Error; err != nil {
		return nil, err
	}
	return gin.H{
		"id":            u.ID,
		"username":      u.Username,
		"full_name":     u.FullName(),
		"email":         u.Email,
		"is_superuser":  au.IsSuperuser,
		"department_id": u.DepartmentID,
		"role_id":       u.RoleID,
		"permissions":   au.Permissions,
		"menus":         h.menus(c, au),
		"data_scopes":   au.DataScopes,
	}, nil
}

// menus 返回用户可见的菜单 route_path(menu 类型权限)。超管返回全部启用菜单。
// TODO(verify): 旧 UserProfileSerializer 返回带层级且补全父容器的菜单树,此处先返回扁平 route_path 列表。
func (h *AuthHandler) menus(c *gin.Context, au *iam.AuthUser) []string {
	q := h.db.WithContext(c.Request.Context()).Table("core_permission").
		Where("type = ? AND is_active = ? AND deleted_at IS NULL AND route_path <> ''", "menu", true)
	if !au.IsSuperuser {
		if len(au.Permissions) == 0 {
			return []string{}
		}
		q = q.Where("code IN ?", au.Permissions)
	}
	var paths []string
	_ = q.Pluck("route_path", &paths).Error
	if paths == nil {
		paths = []string{}
	}
	return paths
}
