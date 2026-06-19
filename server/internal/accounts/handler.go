package accounts

import (
	"errors"
	"net/http"
	"strconv"

	"github.com/atm-erp/server/internal/iam"
	"github.com/atm-erp/server/internal/platform/httpx"
	"github.com/gin-gonic/gin"
)

type Handler struct{ svc *Service }

func NewHandler(svc *Service) *Handler { return &Handler{svc: svc} }

// ---------------- Department ----------------

func (h *Handler) ListDepartments(c *gin.Context) {
	p := httpx.ParsePage(c)
	q := DeptListQuery{Keyword: c.Query("keyword"), ParentID: parseOptID(c.Query("parent_id"))}
	rows, total, err := h.svc.ListDepartments(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[Department]{Count: total, Results: rows})
}

func (h *Handler) RetrieveDepartment(c *gin.Context) {
	d, err := h.svc.GetDepartment(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, d)
}

func (h *Handler) CreateDepartment(c *gin.Context) {
	var in DeptCreateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	d, err := h.svc.CreateDepartment(c.Request.Context(), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.Created(c, d)
}

func (h *Handler) UpdateDepartment(c *gin.Context) {
	var in DeptUpdateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	d, err := h.svc.UpdateDepartment(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, d)
}

func (h *Handler) DeleteDepartment(c *gin.Context) {
	if err := h.svc.DeleteDepartment(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.NoContent(c)
}

// ---------------- Role ----------------

func (h *Handler) ListRoles(c *gin.Context) {
	p := httpx.ParsePage(c)
	q := RoleListQuery{Keyword: c.Query("keyword"), IsActive: parseOptBool(c.Query("is_active"))}
	rows, total, err := h.svc.ListRoles(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[Role]{Count: total, Results: rows})
}

func (h *Handler) RetrieveRole(c *gin.Context) {
	r, err := h.svc.GetRole(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, r)
}

func (h *Handler) CreateRole(c *gin.Context) {
	var in RoleCreateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	r, err := h.svc.CreateRole(c.Request.Context(), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.Created(c, r)
}

func (h *Handler) UpdateRole(c *gin.Context) {
	var in RoleUpdateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	r, err := h.svc.UpdateRole(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, r)
}

func (h *Handler) DeleteRole(c *gin.Context) {
	if err := h.svc.DeleteRole(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.NoContent(c)
}

// ---------------- User ----------------

func (h *Handler) ListUsers(c *gin.Context) {
	p := httpx.ParsePage(c)
	q := UserListQuery{
		Keyword:      c.Query("keyword"),
		DepartmentID: parseOptID(c.Query("department_id")),
		RoleID:       parseOptID(c.Query("role_id")),
		IsActive:     parseOptBool(c.Query("is_active")),
	}
	rows, total, err := h.svc.ListUsers(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[User]{Count: total, Results: rows})
}

func (h *Handler) RetrieveUser(c *gin.Context) {
	u, err := h.svc.GetUser(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, u)
}

func (h *Handler) CreateUser(c *gin.Context) {
	var in UserCreateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	u, err := h.svc.CreateUser(c.Request.Context(), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.Created(c, u)
}

func (h *Handler) UpdateUser(c *gin.Context) {
	var in UserUpdateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	u, err := h.svc.UpdateUser(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, u)
}

func (h *Handler) DeleteUser(c *gin.Context) {
	if err := h.svc.DeleteUser(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.NoContent(c)
}

// ChangePassword 当前登录用户改密(self action)。
func (h *Handler) ChangePassword(c *gin.Context) {
	u, ok := iam.CurrentUser(c)
	if !ok {
		httpx.Error(c, http.StatusUnauthorized, "未认证")
		return
	}
	var in ChangePasswordInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	if err := h.svc.ChangePassword(c.Request.Context(), u.ID, in); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, gin.H{"detail": "密码修改成功"})
}

// ResetPassword 管理员重置指定用户密码。
func (h *Handler) ResetPassword(c *gin.Context) {
	var in ResetPasswordInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	if err := h.svc.ResetPassword(c.Request.Context(), parseID(c), in); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, gin.H{"detail": "密码重置成功"})
}

// ---------------- Permission ----------------

func (h *Handler) ListPermissions(c *gin.Context) {
	p := httpx.ParsePage(c)
	q := PermissionListQuery{
		Keyword:  c.Query("keyword"),
		Type:     c.Query("type"),
		Resource: c.Query("resource"),
		IsActive: parseOptBool(c.Query("is_active")),
	}
	rows, total, err := h.svc.ListPermissions(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[Permission]{Count: total, Results: rows})
}

func (h *Handler) RetrievePermission(c *gin.Context) {
	p, err := h.svc.GetPermission(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, p)
}

func (h *Handler) CreatePermission(c *gin.Context) {
	var in PermissionCreateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	p, err := h.svc.CreatePermission(c.Request.Context(), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.Created(c, p)
}

func (h *Handler) UpdatePermission(c *gin.Context) {
	var in PermissionUpdateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	p, err := h.svc.UpdatePermission(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, p)
}

func (h *Handler) DeletePermission(c *gin.Context) {
	if err := h.svc.DeletePermission(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.NoContent(c)
}

// Register 挂载本模块全部路由(权限码 accounts:<entity>:<action>)。
func (h *Handler) Register(rg *gin.RouterGroup, perm func(string) gin.HandlerFunc) {
	// Departments
	d := rg.Group("/accounts/departments")
	d.GET("", perm("accounts:department:view"), h.ListDepartments)
	d.GET("/:id", perm("accounts:department:view"), h.RetrieveDepartment)
	d.POST("", perm("accounts:department:create"), h.CreateDepartment)
	d.PUT("/:id", perm("accounts:department:update"), h.UpdateDepartment)
	d.DELETE("/:id", perm("accounts:department:delete"), h.DeleteDepartment)

	// Roles
	r := rg.Group("/accounts/roles")
	r.GET("", perm("accounts:role:view"), h.ListRoles)
	r.GET("/:id", perm("accounts:role:view"), h.RetrieveRole)
	r.POST("", perm("accounts:role:create"), h.CreateRole)
	r.PUT("/:id", perm("accounts:role:update"), h.UpdateRole)
	r.DELETE("/:id", perm("accounts:role:delete"), h.DeleteRole)

	// Users
	u := rg.Group("/accounts/users")
	u.GET("", perm("accounts:user:view"), h.ListUsers)
	u.GET("/:id", perm("accounts:user:view"), h.RetrieveUser)
	u.POST("", perm("accounts:user:create"), h.CreateUser)
	u.PUT("/:id", perm("accounts:user:update"), h.UpdateUser)
	u.DELETE("/:id", perm("accounts:user:delete"), h.DeleteUser)
	// change_password 是 self action,无需 accounts:user:* 写权限。
	u.POST("/change_password", h.ChangePassword)
	u.POST("/:id/reset_password", perm("accounts:user:update"), h.ResetPassword)

	// Permissions
	p := rg.Group("/accounts/permissions")
	p.GET("", perm("accounts:permission:view"), h.ListPermissions)
	p.GET("/:id", perm("accounts:permission:view"), h.RetrievePermission)
	p.POST("", perm("accounts:permission:create"), h.CreatePermission)
	p.PUT("/:id", perm("accounts:permission:update"), h.UpdatePermission)
	p.DELETE("/:id", perm("accounts:permission:delete"), h.DeletePermission)
}

// ---------------- helpers ----------------

func parseID(c *gin.Context) uint64 {
	id, _ := strconv.ParseUint(c.Param("id"), 10, 64)
	return id
}

func parseOptID(s string) *uint64 {
	if s == "" {
		return nil
	}
	v, err := strconv.ParseUint(s, 10, 64)
	if err != nil {
		return nil
	}
	return &v
}

func parseOptBool(s string) *bool {
	if s == "" {
		return nil
	}
	v, err := strconv.ParseBool(s)
	if err != nil {
		return nil
	}
	return &v
}

func statusFor(err error) int {
	switch {
	case errors.Is(err, ErrDeptNotFound),
		errors.Is(err, ErrRoleNotFound),
		errors.Is(err, ErrUserNotFound),
		errors.Is(err, ErrPermissionNotFound):
		return http.StatusNotFound
	case errors.Is(err, ErrValidation):
		return http.StatusBadRequest
	default:
		return http.StatusInternalServerError
	}
}
