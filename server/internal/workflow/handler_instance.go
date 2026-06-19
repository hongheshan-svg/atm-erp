package workflow

import (
	"net/http"
	"strconv"

	"github.com/atm-erp/server/internal/platform/httpx"
	"github.com/gin-gonic/gin"
)

func (h *Handler) listInstances(c *gin.Context) {
	p := httpx.ParsePage(c)
	q := InstanceListQuery{
		BusinessType: c.Query("business_type"),
		Status:       c.Query("status"),
		SubmitterID:  parseUint64Query(c, "submitter"),
		Keyword:      c.Query("search"),
	}
	items, total, err := h.svc.ListInstances(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[WorkflowInstance]{Count: total, Results: items})
}

func (h *Handler) retrieveInstance(c *gin.Context) {
	inst, err := h.svc.GetInstance(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, inst)
}

// startInstance 启动审批(对齐 WorkflowService.start_workflow 的对外入口)。
func (h *Handler) startInstance(c *gin.Context) {
	var in StartInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	res, err := h.svc.Start(c.Request.Context(), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.Created(c, gin.H{"auto_approved": res.AutoApproved, "instance": res.Instance})
}

// mySubmitted 当前用户提交的审批(对齐 my_submitted)。
func (h *Handler) mySubmitted(c *gin.Context) {
	items, err := h.svc.MySubmitted(c.Request.Context())
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, items)
}

// withdrawInstance 撤回(对齐 withdraw)。
func (h *Handler) withdrawInstance(c *gin.Context) {
	if err := h.svc.Withdraw(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, gin.H{"message": "已撤回"})
}

// instanceHistory 某业务对象的审批历史(对齐 history)。
func (h *Handler) instanceHistory(c *gin.Context) {
	businessType := c.Query("business_type")
	businessIDStr := c.Query("business_id")
	if businessType == "" || businessIDStr == "" {
		httpx.Error(c, http.StatusBadRequest, "请提供 business_type 和 business_id")
		return
	}
	businessID, err := strconv.ParseInt(businessIDStr, 10, 64)
	if err != nil {
		httpx.Error(c, http.StatusBadRequest, "business_id 非法")
		return
	}
	items, err := h.svc.History(c.Request.Context(), businessType, businessID)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, items)
}

// deleteInstance 软删除实例(对齐 admin_delete;权限码控制管理员)。
func (h *Handler) deleteInstance(c *gin.Context) {
	if err := h.svc.DeleteInstance(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.NoContent(c)
}
