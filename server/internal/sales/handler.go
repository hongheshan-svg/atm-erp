package sales

import (
	"errors"
	"net/http"
	"strconv"

	"github.com/atm-erp/server/internal/platform/httpx"
	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
)

// Handler 承载 sales 上下文全部 REST 端点。
type Handler struct{ svc *Service }

func NewHandler(svc *Service) *Handler { return &Handler{svc: svc} }

// Routes 是 sales 限界上下文的统一装配入口。
// 调用方: sales.Routes(api, gdb, middleware.RequirePermission)。
func Routes(rg *gin.RouterGroup, gdb *gorm.DB, perm func(string) gin.HandlerFunc) {
	h := NewHandler(NewService(NewRepo(gdb)))
	h.Register(rg, perm)
}

// Register 挂载全部子路由,权限码格式 sales:<entity>:<action>。
func (h *Handler) Register(rg *gin.RouterGroup, perm func(string) gin.HandlerFunc) {
	// 报价
	q := rg.Group("/sales/quotations")
	q.GET("", perm("sales:quotation:view"), h.ListQuotations)
	q.GET("/:id", perm("sales:quotation:view"), h.GetQuotation)
	q.POST("", perm("sales:quotation:create"), h.CreateQuotation)
	q.PUT("/:id", perm("sales:quotation:update"), h.UpdateQuotation)
	q.DELETE("/:id", perm("sales:quotation:delete"), h.DeleteQuotation)
	q.POST("/:id/submit", perm("sales:quotation:submit"), h.SubmitQuotation)
	q.POST("/:id/convert_to_so", perm("sales:quotation:convert"), h.ConvertToSO)

	// 销售订单
	so := rg.Group("/sales/orders")
	so.GET("", perm("sales:order:view"), h.ListSalesOrders)
	so.GET("/:id", perm("sales:order:view"), h.GetSalesOrder)
	so.POST("", perm("sales:order:create"), h.CreateSalesOrder)
	so.PUT("/:id", perm("sales:order:update"), h.UpdateSalesOrder)
	so.DELETE("/:id", perm("sales:order:delete"), h.DeleteSalesOrder)
	so.POST("/:id/submit", perm("sales:order:submit"), h.SubmitSalesOrder)
	so.POST("/:id/confirm", perm("sales:order:confirm"), h.ConfirmSalesOrder)
	so.POST("/:id/cancel", perm("sales:order:cancel"), h.CancelSalesOrder)
	so.POST("/:id/return_to_draft", perm("sales:order:update"), h.ReturnSalesOrderToDraft)

	// 发货单
	d := rg.Group("/sales/deliveries")
	d.GET("", perm("sales:delivery:view"), h.ListDeliveries)
	d.GET("/:id", perm("sales:delivery:view"), h.GetDelivery)
	d.POST("", perm("sales:delivery:create"), h.CreateDelivery)
	d.PUT("/:id", perm("sales:delivery:update"), h.UpdateDelivery)
	d.DELETE("/:id", perm("sales:delivery:delete"), h.DeleteDelivery)
	d.POST("/:id/submit", perm("sales:delivery:submit"), h.SubmitDelivery)

	// 线索
	l := rg.Group("/sales/leads")
	l.GET("", perm("sales:lead:view"), h.ListLeads)
	l.GET("/:id", perm("sales:lead:view"), h.GetLead)
	l.POST("", perm("sales:lead:create"), h.CreateLead)
	l.PUT("/:id", perm("sales:lead:update"), h.UpdateLead)
	l.DELETE("/:id", perm("sales:lead:delete"), h.DeleteLead)
	l.POST("/:id/convert", perm("sales:lead:convert"), h.ConvertLead)

	// 商机
	o := rg.Group("/sales/opportunities")
	o.GET("", perm("sales:opportunity:view"), h.ListOpportunities)
	o.GET("/:id", perm("sales:opportunity:view"), h.GetOpportunity)
	o.POST("", perm("sales:opportunity:create"), h.CreateOpportunity)
	o.PUT("/:id", perm("sales:opportunity:update"), h.UpdateOpportunity)
	o.DELETE("/:id", perm("sales:opportunity:delete"), h.DeleteOpportunity)
}

// ===== Quotation handlers =====

func (h *Handler) ListQuotations(c *gin.Context) {
	p := httpx.ParsePage(c)
	q := ListQuery{Keyword: c.Query("keyword"), Status: c.Query("status"), CustomerID: c.Query("customer")}
	items, total, err := h.svc.ListQuotations(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[Quotation]{Count: total, Results: items})
}

func (h *Handler) GetQuotation(c *gin.Context) {
	v, err := h.svc.GetQuotation(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, v)
}

func (h *Handler) CreateQuotation(c *gin.Context) {
	var in QuotationCreateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	v, err := h.svc.CreateQuotation(c.Request.Context(), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.Created(c, v)
}

func (h *Handler) UpdateQuotation(c *gin.Context) {
	var in QuotationUpdateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	v, err := h.svc.UpdateQuotation(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, v)
}

func (h *Handler) DeleteQuotation(c *gin.Context) {
	if err := h.svc.DeleteQuotation(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.NoContent(c)
}

func (h *Handler) SubmitQuotation(c *gin.Context) {
	v, err := h.svc.SubmitQuotation(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, v)
}

func (h *Handler) ConvertToSO(c *gin.Context) {
	var in ConvertToSOInput
	_ = c.ShouldBindJSON(&in) // body 可选
	so, err := h.svc.ConvertToSO(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.Created(c, so)
}

// ===== SalesOrder handlers =====

func (h *Handler) ListSalesOrders(c *gin.Context) {
	p := httpx.ParsePage(c)
	q := ListQuery{Keyword: c.Query("keyword"), Status: c.Query("status"), CustomerID: c.Query("customer")}
	items, total, err := h.svc.ListSalesOrders(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[SalesOrder]{Count: total, Results: items})
}

func (h *Handler) GetSalesOrder(c *gin.Context) {
	v, err := h.svc.GetSalesOrder(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, v)
}

func (h *Handler) CreateSalesOrder(c *gin.Context) {
	var in SalesOrderCreateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	v, err := h.svc.CreateSalesOrder(c.Request.Context(), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.Created(c, v)
}

func (h *Handler) UpdateSalesOrder(c *gin.Context) {
	var in SalesOrderUpdateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	v, err := h.svc.UpdateSalesOrder(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, v)
}

func (h *Handler) DeleteSalesOrder(c *gin.Context) {
	if err := h.svc.DeleteSalesOrder(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.NoContent(c)
}

func (h *Handler) SubmitSalesOrder(c *gin.Context) {
	v, err := h.svc.SubmitSalesOrder(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, v)
}

func (h *Handler) ConfirmSalesOrder(c *gin.Context) {
	v, err := h.svc.ConfirmSalesOrder(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, v)
}

func (h *Handler) CancelSalesOrder(c *gin.Context) {
	v, err := h.svc.CancelSalesOrder(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, v)
}

func (h *Handler) ReturnSalesOrderToDraft(c *gin.Context) {
	v, err := h.svc.ReturnSalesOrderToDraft(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, v)
}

// ===== DeliveryOrder handlers =====

func (h *Handler) ListDeliveries(c *gin.Context) {
	p := httpx.ParsePage(c)
	q := ListQuery{Keyword: c.Query("keyword"), Status: c.Query("status"), SOID: c.Query("so")}
	items, total, err := h.svc.ListDeliveries(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[DeliveryOrder]{Count: total, Results: items})
}

func (h *Handler) GetDelivery(c *gin.Context) {
	v, err := h.svc.GetDelivery(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, v)
}

func (h *Handler) CreateDelivery(c *gin.Context) {
	var in DeliveryCreateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	v, err := h.svc.CreateDelivery(c.Request.Context(), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.Created(c, v)
}

func (h *Handler) UpdateDelivery(c *gin.Context) {
	var in DeliveryUpdateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	v, err := h.svc.UpdateDelivery(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, v)
}

func (h *Handler) DeleteDelivery(c *gin.Context) {
	if err := h.svc.DeleteDelivery(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.NoContent(c)
}

func (h *Handler) SubmitDelivery(c *gin.Context) {
	v, err := h.svc.SubmitDelivery(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, v)
}

// ===== Lead handlers =====

func (h *Handler) ListLeads(c *gin.Context) {
	p := httpx.ParsePage(c)
	q := ListQuery{Keyword: c.Query("keyword"), Status: c.Query("status")}
	items, total, err := h.svc.ListLeads(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[Lead]{Count: total, Results: items})
}

func (h *Handler) GetLead(c *gin.Context) {
	v, err := h.svc.GetLead(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, v)
}

func (h *Handler) CreateLead(c *gin.Context) {
	var in LeadCreateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	v, err := h.svc.CreateLead(c.Request.Context(), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.Created(c, v)
}

func (h *Handler) UpdateLead(c *gin.Context) {
	var in LeadUpdateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	v, err := h.svc.UpdateLead(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, v)
}

func (h *Handler) DeleteLead(c *gin.Context) {
	if err := h.svc.DeleteLead(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.NoContent(c)
}

func (h *Handler) ConvertLead(c *gin.Context) {
	var in LeadConvertInput
	_ = c.ShouldBindJSON(&in)
	lead, opp, err := h.svc.ConvertLead(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	resp := gin.H{"lead": lead}
	if opp != nil {
		resp["opportunity"] = opp
		resp["opportunity_id"] = opp.ID
	}
	httpx.OK(c, resp)
}

// ===== Opportunity handlers =====

func (h *Handler) ListOpportunities(c *gin.Context) {
	p := httpx.ParsePage(c)
	q := ListQuery{Keyword: c.Query("keyword"), Stage: c.Query("stage"), CustomerID: c.Query("customer")}
	items, total, err := h.svc.ListOpportunities(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[Opportunity]{Count: total, Results: items})
}

func (h *Handler) GetOpportunity(c *gin.Context) {
	v, err := h.svc.GetOpportunity(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, v)
}

func (h *Handler) CreateOpportunity(c *gin.Context) {
	var in OpportunityCreateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	v, err := h.svc.CreateOpportunity(c.Request.Context(), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.Created(c, v)
}

func (h *Handler) UpdateOpportunity(c *gin.Context) {
	var in OpportunityUpdateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	v, err := h.svc.UpdateOpportunity(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, v)
}

func (h *Handler) DeleteOpportunity(c *gin.Context) {
	if err := h.svc.DeleteOpportunity(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.NoContent(c)
}

// ===== helpers =====

func parseID(c *gin.Context) uint64 {
	id, _ := strconv.ParseUint(c.Param("id"), 10, 64)
	return id
}

// statusFor 把领域错误映射为 HTTP 状态码。
func statusFor(err error) int {
	switch {
	case errors.Is(err, ErrNotFound):
		return http.StatusNotFound
	case errors.Is(err, ErrInvalidState), errors.Is(err, ErrValidation), errors.Is(err, ErrProjectNeeded):
		return http.StatusBadRequest
	default:
		return http.StatusInternalServerError
	}
}
