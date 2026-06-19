package purchase

import (
	"context"
	"errors"
	"net/http"
	"strconv"

	"github.com/atm-erp/server/internal/platform/httpx"
	"github.com/gin-gonic/gin"
)

// Handler 采购模块统一 HTTP 处理器(四主实体共用一个 Service)。
type Handler struct{ svc *Service }

func NewHandler(svc *Service) *Handler { return &Handler{svc: svc} }

func parseID(c *gin.Context) uint64 {
	id, _ := strconv.ParseUint(c.Param("id"), 10, 64)
	return id
}

// statusFor 把领域错误映射到 HTTP 状态码。
func statusFor(err error) int {
	switch {
	case errors.Is(err, ErrNotFound):
		return http.StatusNotFound
	case errors.Is(err, ErrBadStatus), errors.Is(err, ErrValidate):
		return http.StatusBadRequest
	default:
		return http.StatusInternalServerError
	}
}

// ============================ 采购申请 handlers ============================

func (h *Handler) listPR(c *gin.Context) {
	p := httpx.ParsePage(c)
	q := ListQuery{Keyword: c.Query("keyword"), Status: c.Query("status")}
	rows, total, err := h.svc.ListPR(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[PurchaseRequest]{Count: total, Results: rows})
}

func (h *Handler) getPR(c *gin.Context) {
	pr, err := h.svc.GetPR(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, pr)
}

func (h *Handler) createPR(c *gin.Context) {
	var in PRCreateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	pr, err := h.svc.CreatePR(c.Request.Context(), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.Created(c, pr)
}

func (h *Handler) updatePR(c *gin.Context) {
	var in PRUpdateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	pr, err := h.svc.UpdatePR(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, pr)
}

func (h *Handler) deletePR(c *gin.Context) {
	if err := h.svc.DeletePR(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.NoContent(c)
}

func (h *Handler) submitPR(c *gin.Context)  { h.actionPR(c, h.svc.SubmitPR) }
func (h *Handler) approvePR(c *gin.Context) { h.actionPR(c, h.svc.ApprovePR) }
func (h *Handler) rejectPR(c *gin.Context)  { h.actionPR(c, h.svc.RejectPR) }

func (h *Handler) actionPR(c *gin.Context, fn func(ctx context.Context, id uint64) (*PurchaseRequest, error)) {
	pr, err := fn(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, pr)
}

// ============================ 采购订单 handlers ============================

func (h *Handler) listPO(c *gin.Context) {
	p := httpx.ParsePage(c)
	q := ListQuery{Keyword: c.Query("keyword"), Status: c.Query("status")}
	rows, total, err := h.svc.ListPO(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[PurchaseOrder]{Count: total, Results: rows})
}

func (h *Handler) getPO(c *gin.Context) {
	po, err := h.svc.GetPO(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, po)
}

func (h *Handler) createPO(c *gin.Context) {
	var in POCreateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	po, err := h.svc.CreatePO(c.Request.Context(), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.Created(c, po)
}

func (h *Handler) updatePO(c *gin.Context) {
	var in POUpdateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	po, err := h.svc.UpdatePO(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, po)
}

func (h *Handler) deletePO(c *gin.Context) {
	if err := h.svc.DeletePO(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.NoContent(c)
}

func (h *Handler) submitPO(c *gin.Context)  { h.actionPO(c, h.svc.SubmitPO) }
func (h *Handler) confirmPO(c *gin.Context) { h.actionPO(c, h.svc.ConfirmPO) }
func (h *Handler) cancelPO(c *gin.Context)  { h.actionPO(c, h.svc.CancelPO) }

func (h *Handler) actionPO(c *gin.Context, fn func(ctx context.Context, id uint64) (*PurchaseOrder, error)) {
	po, err := fn(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, po)
}

// ============================ 收货 handlers ============================

func (h *Handler) listGR(c *gin.Context) {
	p := httpx.ParsePage(c)
	q := ListQuery{Keyword: c.Query("keyword"), Status: c.Query("status")}
	rows, total, err := h.svc.ListGR(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[GoodsReceipt]{Count: total, Results: rows})
}

func (h *Handler) getGR(c *gin.Context) {
	gr, err := h.svc.GetGR(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, gr)
}

func (h *Handler) createGR(c *gin.Context) {
	var in GRCreateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	gr, err := h.svc.CreateGR(c.Request.Context(), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.Created(c, gr)
}

func (h *Handler) updateGR(c *gin.Context) {
	var in GRUpdateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	gr, err := h.svc.UpdateGR(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, gr)
}

func (h *Handler) deleteGR(c *gin.Context) {
	if err := h.svc.DeleteGR(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.NoContent(c)
}

func (h *Handler) confirmGR(c *gin.Context) {
	gr, err := h.svc.ConfirmGR(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, gr)
}

// ============================ 询价 RFQ handlers ============================

func (h *Handler) listRFQ(c *gin.Context) {
	p := httpx.ParsePage(c)
	q := ListQuery{Keyword: c.Query("keyword"), Status: c.Query("status")}
	rows, total, err := h.svc.ListRFQ(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[RFQ]{Count: total, Results: rows})
}

func (h *Handler) getRFQ(c *gin.Context) {
	rfq, err := h.svc.GetRFQ(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, rfq)
}

func (h *Handler) createRFQ(c *gin.Context) {
	var in RFQCreateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	rfq, err := h.svc.CreateRFQ(c.Request.Context(), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.Created(c, rfq)
}

func (h *Handler) updateRFQ(c *gin.Context) {
	var in RFQUpdateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	rfq, err := h.svc.UpdateRFQ(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, rfq)
}

func (h *Handler) deleteRFQ(c *gin.Context) {
	if err := h.svc.DeleteRFQ(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.NoContent(c)
}

func (h *Handler) sendRFQ(c *gin.Context) {
	var in SendToSuppliersInput
	_ = c.ShouldBindJSON(&in) // 入参可空,空则发给已挂供应商
	rfq, err := h.svc.SendRFQ(c.Request.Context(), parseID(c), in.SupplierIDs)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, rfq)
}

// Register 挂载采购模块全部路由。权限码格式 purchase:<entity>:<action>。
func (h *Handler) Register(rg *gin.RouterGroup, perm func(string) gin.HandlerFunc) {
	// 采购申请
	pr := rg.Group("/purchase/requests")
	pr.GET("", perm("purchase:request:view"), h.listPR)
	pr.GET("/:id", perm("purchase:request:view"), h.getPR)
	pr.POST("", perm("purchase:request:create"), h.createPR)
	pr.PUT("/:id", perm("purchase:request:update"), h.updatePR)
	pr.DELETE("/:id", perm("purchase:request:delete"), h.deletePR)
	pr.POST("/:id/submit", perm("purchase:request:submit"), h.submitPR)
	pr.POST("/:id/approve", perm("purchase:request:approve"), h.approvePR)
	pr.POST("/:id/reject", perm("purchase:request:approve"), h.rejectPR)

	// 采购订单
	po := rg.Group("/purchase/orders")
	po.GET("", perm("purchase:order:view"), h.listPO)
	po.GET("/:id", perm("purchase:order:view"), h.getPO)
	po.POST("", perm("purchase:order:create"), h.createPO)
	po.PUT("/:id", perm("purchase:order:update"), h.updatePO)
	po.DELETE("/:id", perm("purchase:order:delete"), h.deletePO)
	po.POST("/:id/submit", perm("purchase:order:submit"), h.submitPO)
	po.POST("/:id/confirm", perm("purchase:order:confirm"), h.confirmPO)
	po.POST("/:id/cancel", perm("purchase:order:cancel"), h.cancelPO)

	// 收货
	gr := rg.Group("/purchase/receipts")
	gr.GET("", perm("purchase:receipt:view"), h.listGR)
	gr.GET("/:id", perm("purchase:receipt:view"), h.getGR)
	gr.POST("", perm("purchase:receipt:create"), h.createGR)
	gr.PUT("/:id", perm("purchase:receipt:update"), h.updateGR)
	gr.DELETE("/:id", perm("purchase:receipt:delete"), h.deleteGR)
	gr.POST("/:id/confirm", perm("purchase:receipt:confirm"), h.confirmGR)

	// 询价 RFQ
	rfq := rg.Group("/purchase/rfqs")
	rfq.GET("", perm("purchase:rfq:view"), h.listRFQ)
	rfq.GET("/:id", perm("purchase:rfq:view"), h.getRFQ)
	rfq.POST("", perm("purchase:rfq:create"), h.createRFQ)
	rfq.PUT("/:id", perm("purchase:rfq:update"), h.updateRFQ)
	rfq.DELETE("/:id", perm("purchase:rfq:delete"), h.deleteRFQ)
	rfq.POST("/:id/send", perm("purchase:rfq:send"), h.sendRFQ)
}
