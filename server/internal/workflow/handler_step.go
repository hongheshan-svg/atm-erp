package workflow

import (
	"net/http"

	"github.com/atm-erp/server/internal/platform/httpx"
	"github.com/gin-gonic/gin"
)

func (h *Handler) listSteps(c *gin.Context) {
	p := httpx.ParsePage(c)
	q := StepListQuery{
		WorkflowID:   parseUint64Query(c, "workflow"),
		ApproverType: c.Query("approver_type"),
	}
	items, total, err := h.svc.ListSteps(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[WorkflowStep]{Count: total, Results: items})
}

func (h *Handler) retrieveStep(c *gin.Context) {
	st, err := h.svc.GetStep(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, st)
}

func (h *Handler) createStep(c *gin.Context) {
	var in StepCreateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	st, err := h.svc.CreateStep(c.Request.Context(), in)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.Created(c, st)
}

func (h *Handler) updateStep(c *gin.Context) {
	var in StepUpdateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	st, err := h.svc.UpdateStep(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, st)
}

func (h *Handler) deleteStep(c *gin.Context) {
	if err := h.svc.DeleteStep(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.NoContent(c)
}

// reorderSteps 交换两步骤顺序(对齐 WorkflowStepViewSet.reorder)。
func (h *Handler) reorderSteps(c *gin.Context) {
	var in ReorderInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	if err := h.svc.ReorderSteps(c.Request.Context(), in.StepID, in.TargetID); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, gin.H{"message": "顺序已更新"})
}
