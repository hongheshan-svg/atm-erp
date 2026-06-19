package projects

import (
	"errors"
	"net/http"
	"strconv"

	"github.com/atm-erp/server/internal/platform/httpx"
	"github.com/gin-gonic/gin"
)

// Handler 暴露项目上下文各实体的 REST 端点。
type Handler struct{ svc *Service }

// NewHandler 构造 Handler。
func NewHandler(svc *Service) *Handler { return &Handler{svc: svc} }

// ===========================================================================
// Project
// ===========================================================================

func (h *Handler) listProjects(c *gin.Context) {
	p := httpx.ParsePage(c)
	q := ProjectListQuery{
		Keyword:    c.Query("keyword"),
		CustomerID: parseUintQuery(c, "customer"),
		ManagerID:  parseUintQuery(c, "manager"),
		Status:     c.Query("status"),
	}
	rows, total, err := h.svc.ListProjects(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[Project]{Count: total, Results: rows})
}

func (h *Handler) retrieveProject(c *gin.Context) {
	p, err := h.svc.GetProject(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, p)
}

func (h *Handler) createProject(c *gin.Context) {
	var in ProjectCreateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	p, err := h.svc.CreateProject(c.Request.Context(), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.Created(c, p)
}

func (h *Handler) updateProject(c *gin.Context) {
	var in ProjectUpdateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	p, err := h.svc.UpdateProject(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, p)
}

func (h *Handler) deleteProject(c *gin.Context) {
	if err := h.svc.DeleteProject(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.NoContent(c)
}

func (h *Handler) submitProject(c *gin.Context) {
	p, err := h.svc.SubmitProject(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, p)
}

func (h *Handler) changeProjectStatus(c *gin.Context) {
	var in ChangeStatusInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	p, err := h.svc.ChangeProjectStatus(c.Request.Context(), parseID(c), in.Status)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, p)
}

// ===========================================================================
// ProjectTask
// ===========================================================================

func (h *Handler) listTasks(c *gin.Context) {
	p := httpx.ParsePage(c)
	q := TaskListQuery{
		Keyword:    c.Query("keyword"),
		ProjectID:  parseUintQuery(c, "project"),
		AssigneeID: parseUintQuery(c, "assignee"),
		Status:     c.Query("status"),
	}
	rows, total, err := h.svc.ListTasks(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[ProjectTask]{Count: total, Results: rows})
}

func (h *Handler) retrieveTask(c *gin.Context) {
	t, err := h.svc.GetTask(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, t)
}

func (h *Handler) createTask(c *gin.Context) {
	var in TaskCreateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	t, err := h.svc.CreateTask(c.Request.Context(), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.Created(c, t)
}

func (h *Handler) updateTask(c *gin.Context) {
	var in TaskUpdateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	t, err := h.svc.UpdateTask(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, t)
}

func (h *Handler) deleteTask(c *gin.Context) {
	if err := h.svc.DeleteTask(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.NoContent(c)
}

func (h *Handler) updateTaskProgress(c *gin.Context) {
	var in UpdateProgressInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	t, err := h.svc.UpdateTaskProgress(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, t)
}

// ===========================================================================
// ProjectBOM
// ===========================================================================

func (h *Handler) listBOM(c *gin.Context) {
	p := httpx.ParsePage(c)
	q := BOMListQuery{
		Keyword:     c.Query("keyword"),
		ProjectID:   parseUintQuery(c, "project"),
		ItemID:      parseUintQuery(c, "item"),
		QuoteStatus: c.Query("quote_status"),
		OrderStatus: c.Query("order_status"),
		HasDrawing:  c.Query("has_drawing"),
	}
	rows, total, err := h.svc.ListBOM(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[ProjectBOM]{Count: total, Results: rows})
}

func (h *Handler) retrieveBOM(c *gin.Context) {
	b, err := h.svc.GetBOM(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, b)
}

func (h *Handler) createBOM(c *gin.Context) {
	var in BOMCreateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	b, err := h.svc.CreateBOM(c.Request.Context(), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.Created(c, b)
}

func (h *Handler) updateBOM(c *gin.Context) {
	var in BOMUpdateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	b, err := h.svc.UpdateBOM(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, b)
}

func (h *Handler) deleteBOM(c *gin.Context) {
	if err := h.svc.DeleteBOM(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.NoContent(c)
}

func (h *Handler) confirmBOM(c *gin.Context) {
	b, err := h.svc.ConfirmBOM(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, b)
}

func (h *Handler) releaseBOM(c *gin.Context) {
	b, err := h.svc.ReleaseBOM(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, b)
}

// ===========================================================================
// Drawing
// ===========================================================================

func (h *Handler) listDrawings(c *gin.Context) {
	p := httpx.ParsePage(c)
	q := DrawingListQuery{
		Keyword:   c.Query("keyword"),
		ProjectID: parseUintQuery(c, "project"),
		ItemID:    parseUintQuery(c, "item"),
		Status:    c.Query("status"),
		PartType:  c.Query("part_type"),
	}
	rows, total, err := h.svc.ListDrawings(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[Drawing]{Count: total, Results: rows})
}

func (h *Handler) retrieveDrawing(c *gin.Context) {
	d, err := h.svc.GetDrawing(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, d)
}

func (h *Handler) createDrawing(c *gin.Context) {
	var in DrawingCreateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	d, err := h.svc.CreateDrawing(c.Request.Context(), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.Created(c, d)
}

func (h *Handler) updateDrawing(c *gin.Context) {
	var in DrawingUpdateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	d, err := h.svc.UpdateDrawing(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, d)
}

func (h *Handler) deleteDrawing(c *gin.Context) {
	if err := h.svc.DeleteDrawing(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.NoContent(c)
}

func (h *Handler) submitDrawingReview(c *gin.Context) {
	d, err := h.svc.SubmitDrawingReview(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, d)
}

func (h *Handler) approveDrawing(c *gin.Context) {
	d, err := h.svc.ApproveDrawing(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, d)
}

func (h *Handler) rejectDrawing(c *gin.Context) {
	var in RejectInput
	// reject 的 comment 可选,绑定失败不阻断(空 body 合法)。
	_ = c.ShouldBindJSON(&in)
	d, err := h.svc.RejectDrawing(c.Request.Context(), parseID(c), in.Comment)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, d)
}

func (h *Handler) releaseDrawing(c *gin.Context) {
	d, notice, err := h.svc.ReleaseDrawing(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	resp := gin.H{"drawing": d}
	if notice != nil {
		resp["notice_id"] = notice.ID
	}
	httpx.OK(c, resp)
}

// ===========================================================================
// helpers
// ===========================================================================

func parseID(c *gin.Context) uint64 {
	id, _ := strconv.ParseUint(c.Param("id"), 10, 64)
	return id
}

func parseUintQuery(c *gin.Context, key string) uint64 {
	v, _ := strconv.ParseUint(c.Query(key), 10, 64)
	return v
}

func statusFor(err error) int {
	switch {
	case errors.Is(err, ErrNotFound):
		return http.StatusNotFound
	case errors.Is(err, ErrValidation):
		return http.StatusBadRequest
	case errors.Is(err, ErrConflict):
		return http.StatusBadRequest
	default:
		return http.StatusInternalServerError
	}
}
