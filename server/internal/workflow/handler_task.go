package workflow

import (
	"net/http"

	"github.com/atm-erp/server/internal/platform/httpx"
	"github.com/gin-gonic/gin"
)

func (h *Handler) listTasks(c *gin.Context) {
	p := httpx.ParsePage(c)
	q := TaskListQuery{
		InstanceID: parseUint64Query(c, "instance"),
		AssigneeID: parseUint64Query(c, "assignee"),
		Status:     c.Query("status"),
	}
	items, total, err := h.svc.ListTasks(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[WorkflowTask]{Count: total, Results: items})
}

func (h *Handler) retrieveTask(c *gin.Context) {
	t, err := h.svc.GetTask(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, t)
}

// myPending 当前用户待办(对齐 my_pending)。
func (h *Handler) myPending(c *gin.Context) {
	items, err := h.svc.MyPending(c.Request.Context())
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, items)
}

// pendingCount 待办计数(对齐 pending_count)。
func (h *Handler) pendingCount(c *gin.Context) {
	n, err := h.svc.PendingCount(c.Request.Context())
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, gin.H{"count": n})
}

// approveTask 审批通过(对齐 approve)。
func (h *Handler) approveTask(c *gin.Context) {
	var in TaskActionInput
	_ = c.ShouldBindJSON(&in) // comment 可空
	if err := h.svc.ApproveTask(c.Request.Context(), parseID(c), in.Comment, false); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, gin.H{"message": "审批通过"})
}

// rejectTask 审批拒绝(对齐 reject;comment 必填,由 service 校验)。
func (h *Handler) rejectTask(c *gin.Context) {
	var in TaskActionInput
	_ = c.ShouldBindJSON(&in)
	if err := h.svc.RejectTask(c.Request.Context(), parseID(c), in.Comment, false); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, gin.H{"message": "已拒绝"})
}
