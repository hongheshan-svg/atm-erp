package finance

import (
	"errors"
	"net/http"
	"strconv"

	"github.com/atm-erp/server/internal/platform/httpx"
	"github.com/gin-gonic/gin"
)

type Handler struct{ svc *Service }

func NewHandler(svc *Service) *Handler { return &Handler{svc: svc} }

func parseID(c *gin.Context) uint64 {
	id, _ := strconv.ParseUint(c.Param("id"), 10, 64)
	return id
}

func parseOptUint(c *gin.Context, key string) *uint64 {
	v := c.Query(key)
	if v == "" {
		return nil
	}
	n, err := strconv.ParseUint(v, 10, 64)
	if err != nil {
		return nil
	}
	return &n
}

func statusFor(err error) int {
	switch {
	case errors.Is(err, ErrNotFound):
		return http.StatusNotFound
	case errors.Is(err, ErrInvalidStatus), errors.Is(err, ErrPaymentTarget):
		return http.StatusBadRequest
	default:
		return http.StatusInternalServerError
	}
}

// ============================ Currency ============================

func (h *Handler) ListCurrency(c *gin.Context) {
	p := httpx.ParsePage(c)
	q := CurrencyListQuery{Keyword: c.Query("keyword")}
	rows, total, err := h.svc.ListCurrency(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[Currency]{Count: total, Results: rows})
}

func (h *Handler) RetrieveCurrency(c *gin.Context) {
	v, err := h.svc.GetCurrency(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, v)
}

func (h *Handler) CreateCurrency(c *gin.Context) {
	var in CurrencyCreateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	v, err := h.svc.CreateCurrency(c.Request.Context(), in)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.Created(c, v)
}

func (h *Handler) UpdateCurrency(c *gin.Context) {
	var in CurrencyUpdateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	v, err := h.svc.UpdateCurrency(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, v)
}

func (h *Handler) DeleteCurrency(c *gin.Context) {
	if err := h.svc.DeleteCurrency(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.NoContent(c)
}

// ============================ Expense ============================

func (h *Handler) ListExpense(c *gin.Context) {
	p := httpx.ParsePage(c)
	q := ExpenseListQuery{
		Keyword:   c.Query("keyword"),
		Status:    c.Query("status"),
		Category:  c.Query("category"),
		ProjectID: parseOptUint(c, "project_id"),
	}
	rows, total, err := h.svc.ListExpense(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[Expense]{Count: total, Results: rows})
}

func (h *Handler) RetrieveExpense(c *gin.Context) {
	v, err := h.svc.GetExpense(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, v)
}

func (h *Handler) CreateExpense(c *gin.Context) {
	var in ExpenseCreateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	v, err := h.svc.CreateExpense(c.Request.Context(), in)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.Created(c, v)
}

func (h *Handler) UpdateExpense(c *gin.Context) {
	var in ExpenseUpdateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	v, err := h.svc.UpdateExpense(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, v)
}

func (h *Handler) DeleteExpense(c *gin.Context) {
	if err := h.svc.DeleteExpense(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.NoContent(c)
}

func (h *Handler) SubmitExpense(c *gin.Context) {
	v, err := h.svc.SubmitExpense(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, v)
}

func (h *Handler) ApproveExpense(c *gin.Context) {
	v, err := h.svc.ApproveExpense(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, v)
}

func (h *Handler) RejectExpense(c *gin.Context) {
	v, err := h.svc.RejectExpense(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, v)
}

// ============================ Receivable ============================

func (h *Handler) ListReceivable(c *gin.Context) {
	p := httpx.ParsePage(c)
	q := ReceivableListQuery{
		Keyword:    c.Query("keyword"),
		Status:     c.Query("status"),
		CustomerID: parseOptUint(c, "customer_id"),
		ProjectID:  parseOptUint(c, "project_id"),
	}
	rows, total, err := h.svc.ListReceivable(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[AccountReceivable]{Count: total, Results: rows})
}

func (h *Handler) RetrieveReceivable(c *gin.Context) {
	v, err := h.svc.GetReceivable(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, v)
}

func (h *Handler) CreateReceivable(c *gin.Context) {
	var in ReceivableCreateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	v, err := h.svc.CreateReceivable(c.Request.Context(), in)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.Created(c, v)
}

func (h *Handler) UpdateReceivable(c *gin.Context) {
	var in ReceivableUpdateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	v, err := h.svc.UpdateReceivable(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, v)
}

func (h *Handler) DeleteReceivable(c *gin.Context) {
	if err := h.svc.DeleteReceivable(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.NoContent(c)
}

// ============================ Payable ============================

func (h *Handler) ListPayable(c *gin.Context) {
	p := httpx.ParsePage(c)
	q := PayableListQuery{
		Keyword:    c.Query("keyword"),
		Status:     c.Query("status"),
		SupplierID: parseOptUint(c, "supplier_id"),
		ProjectID:  parseOptUint(c, "project_id"),
	}
	rows, total, err := h.svc.ListPayable(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[AccountPayable]{Count: total, Results: rows})
}

func (h *Handler) RetrievePayable(c *gin.Context) {
	v, err := h.svc.GetPayable(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, v)
}

func (h *Handler) CreatePayable(c *gin.Context) {
	var in PayableCreateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	v, err := h.svc.CreatePayable(c.Request.Context(), in)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.Created(c, v)
}

func (h *Handler) UpdatePayable(c *gin.Context) {
	var in PayableUpdateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	v, err := h.svc.UpdatePayable(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, v)
}

func (h *Handler) DeletePayable(c *gin.Context) {
	if err := h.svc.DeletePayable(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.NoContent(c)
}

// ============================ Payment ============================

func (h *Handler) ListPayment(c *gin.Context) {
	p := httpx.ParsePage(c)
	q := PaymentListQuery{
		Keyword:     c.Query("keyword"),
		PaymentType: c.Query("payment_type"),
		ARID:        parseOptUint(c, "ar_id"),
		APID:        parseOptUint(c, "ap_id"),
	}
	rows, total, err := h.svc.ListPayment(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[Payment]{Count: total, Results: rows})
}

func (h *Handler) RetrievePayment(c *gin.Context) {
	v, err := h.svc.GetPayment(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, v)
}

func (h *Handler) CreatePayment(c *gin.Context) {
	var in PaymentCreateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	v, err := h.svc.CreatePayment(c.Request.Context(), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.Created(c, v)
}

func (h *Handler) DeletePayment(c *gin.Context) {
	if err := h.svc.DeletePayment(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.NoContent(c)
}

// ============================ Invoice ============================

func (h *Handler) ListInvoice(c *gin.Context) {
	p := httpx.ParsePage(c)
	q := InvoiceListQuery{
		Keyword:     c.Query("keyword"),
		InvoiceType: c.Query("invoice_type"),
		Status:      c.Query("status"),
		ProjectID:   parseOptUint(c, "project_id"),
	}
	rows, total, err := h.svc.ListInvoice(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[Invoice]{Count: total, Results: rows})
}

func (h *Handler) RetrieveInvoice(c *gin.Context) {
	v, err := h.svc.GetInvoice(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, v)
}

func (h *Handler) ListInvoiceItems(c *gin.Context) {
	rows, err := h.svc.GetInvoiceItems(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, httpx.Page[InvoiceItem]{Count: int64(len(rows)), Results: rows})
}

func (h *Handler) CreateInvoice(c *gin.Context) {
	var in InvoiceCreateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	v, err := h.svc.CreateInvoice(c.Request.Context(), in)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.Created(c, v)
}

func (h *Handler) UpdateInvoice(c *gin.Context) {
	var in InvoiceUpdateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	v, err := h.svc.UpdateInvoice(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, v)
}

func (h *Handler) DeleteInvoice(c *gin.Context) {
	if err := h.svc.DeleteInvoice(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.NoContent(c)
}

func (h *Handler) VoidInvoice(c *gin.Context) {
	v, err := h.svc.VoidInvoice(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, v)
}

func (h *Handler) CertifyInvoice(c *gin.Context) {
	v, err := h.svc.CertifyInvoice(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, v)
}

// Register 挂载本上下文全部路由,权限码格式 finance:<entity>:<action>。
func (h *Handler) Register(rg *gin.RouterGroup, perm func(string) gin.HandlerFunc) {
	// Currency
	cur := rg.Group("/finance/currencies")
	cur.GET("", perm("finance:currency:view"), h.ListCurrency)
	cur.GET("/:id", perm("finance:currency:view"), h.RetrieveCurrency)
	cur.POST("", perm("finance:currency:create"), h.CreateCurrency)
	cur.PUT("/:id", perm("finance:currency:update"), h.UpdateCurrency)
	cur.DELETE("/:id", perm("finance:currency:delete"), h.DeleteCurrency)

	// Expense
	exp := rg.Group("/finance/expenses")
	exp.GET("", perm("finance:expense:view"), h.ListExpense)
	exp.GET("/:id", perm("finance:expense:view"), h.RetrieveExpense)
	exp.POST("", perm("finance:expense:create"), h.CreateExpense)
	exp.PUT("/:id", perm("finance:expense:update"), h.UpdateExpense)
	exp.DELETE("/:id", perm("finance:expense:delete"), h.DeleteExpense)
	exp.POST("/:id/submit", perm("finance:expense:submit"), h.SubmitExpense)
	exp.POST("/:id/approve", perm("finance:expense:approve"), h.ApproveExpense)
	exp.POST("/:id/reject", perm("finance:expense:approve"), h.RejectExpense)

	// Receivable
	ar := rg.Group("/finance/receivables")
	ar.GET("", perm("finance:receivable:view"), h.ListReceivable)
	ar.GET("/:id", perm("finance:receivable:view"), h.RetrieveReceivable)
	ar.POST("", perm("finance:receivable:create"), h.CreateReceivable)
	ar.PUT("/:id", perm("finance:receivable:update"), h.UpdateReceivable)
	ar.DELETE("/:id", perm("finance:receivable:delete"), h.DeleteReceivable)

	// Payable
	ap := rg.Group("/finance/payables")
	ap.GET("", perm("finance:payable:view"), h.ListPayable)
	ap.GET("/:id", perm("finance:payable:view"), h.RetrievePayable)
	ap.POST("", perm("finance:payable:create"), h.CreatePayable)
	ap.PUT("/:id", perm("finance:payable:update"), h.UpdatePayable)
	ap.DELETE("/:id", perm("finance:payable:delete"), h.DeletePayable)

	// Payment
	pay := rg.Group("/finance/payments")
	pay.GET("", perm("finance:payment:view"), h.ListPayment)
	pay.GET("/:id", perm("finance:payment:view"), h.RetrievePayment)
	pay.POST("", perm("finance:payment:create"), h.CreatePayment)
	pay.DELETE("/:id", perm("finance:payment:delete"), h.DeletePayment)

	// Invoice
	inv := rg.Group("/finance/invoices")
	inv.GET("", perm("finance:invoice:view"), h.ListInvoice)
	inv.GET("/:id", perm("finance:invoice:view"), h.RetrieveInvoice)
	inv.GET("/:id/items", perm("finance:invoice:view"), h.ListInvoiceItems)
	inv.POST("", perm("finance:invoice:create"), h.CreateInvoice)
	inv.PUT("/:id", perm("finance:invoice:update"), h.UpdateInvoice)
	inv.DELETE("/:id", perm("finance:invoice:delete"), h.DeleteInvoice)
	inv.POST("/:id/void", perm("finance:invoice:void"), h.VoidInvoice)
	inv.POST("/:id/certify", perm("finance:invoice:certify"), h.CertifyInvoice)
}
