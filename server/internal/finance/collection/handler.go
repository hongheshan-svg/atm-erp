package collection

import (
	"errors"
	"net/http"
	"strconv"

	"github.com/atm-erp/server/internal/platform/httpx"
	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
)

type Handler struct{ svc *Service }

func NewHandler(svc *Service) *Handler { return &Handler{svc: svc} }

// Routes 装配回款核销路由,挂在 finance 下:/finance/collection/...
func Routes(rg *gin.RouterGroup, gdb *gorm.DB, perm func(string) gin.HandlerFunc) {
	h := NewHandler(NewService(gdb))
	g := rg.Group("/finance/collection")
	g.GET("/plans", perm("finance:collection_plan:view"), h.ListPlans)
	g.POST("/plans", perm("finance:collection_plan:create"), h.CreatePlan)
	g.GET("/plans/:id", perm("finance:collection_plan:view"), h.GetPlan)
	g.PUT("/plans/:id", perm("finance:collection_plan:update"), h.UpdatePlan)
	g.DELETE("/plans/:id", perm("finance:collection_plan:delete"), h.DeletePlan)
	g.GET("/plans/:id/milestones", perm("finance:collection_plan:view"), h.ListMilestones)
	g.POST("/plans/:id/milestones", perm("finance:collection_plan:update"), h.CreateMilestone)
	g.POST("/milestones/:id/records", perm("finance:collection_record:create"), h.AddRecord)
}

func (h *Handler) ListPlans(c *gin.Context) {
	p := httpx.ParsePage(c)
	q := PlanListQuery{Keyword: c.Query("keyword"), CustomerID: c.Query("customer_id"), Status: c.Query("status")}
	plans, total, err := h.svc.ListPlans(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[CollectionPlan]{Count: total, Results: plans})
}

func (h *Handler) CreatePlan(c *gin.Context) {
	var in CreatePlanInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	p, err := h.svc.CreatePlan(c.Request.Context(), in)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.Created(c, p)
}

// GetPlan 返回计划 + 其全部节点(便于前端详情页一次拉取)。
func (h *Handler) GetPlan(c *gin.Context) {
	id := parseID(c)
	p, err := h.svc.GetPlan(c.Request.Context(), id)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	ms, err := h.svc.PlanMilestones(c.Request.Context(), id)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, gin.H{"plan": p, "milestones": ms})
}

func (h *Handler) UpdatePlan(c *gin.Context) {
	var in UpdatePlanInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	p, err := h.svc.UpdatePlan(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, p)
}

func (h *Handler) DeletePlan(c *gin.Context) {
	if err := h.svc.DeletePlan(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.NoContent(c)
}

func (h *Handler) ListMilestones(c *gin.Context) {
	ms, err := h.svc.PlanMilestones(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, gin.H{"results": ms})
}

func (h *Handler) CreateMilestone(c *gin.Context) {
	var in CreateMilestoneInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	m, err := h.svc.CreateMilestone(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.Created(c, m)
}

func (h *Handler) AddRecord(c *gin.Context) {
	var in CreateRecordInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	rec, err := h.svc.AddRecordTo(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.Created(c, rec)
}

func parseID(c *gin.Context) uint64 {
	id, _ := strconv.ParseUint(c.Param("id"), 10, 64)
	return id
}

func statusFor(err error) int {
	switch {
	case errors.Is(err, ErrPlanNotFound), errors.Is(err, ErrMilestoneNotFound):
		return http.StatusNotFound
	case errors.Is(err, ErrBadDate):
		return http.StatusBadRequest
	default:
		return http.StatusInternalServerError
	}
}
