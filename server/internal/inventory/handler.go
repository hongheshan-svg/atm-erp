package inventory

import (
	"errors"
	"net/http"
	"strconv"

	"github.com/atm-erp/server/internal/platform/httpx"
	"github.com/gin-gonic/gin"
)

type Handler struct{ svc *Service }

func NewHandler(svc *Service) *Handler { return &Handler{svc: svc} }

// ── Stock(只读)────────────────────────────────────────────────────────

func (h *Handler) ListStock(c *gin.Context) {
	p := httpx.ParsePage(c)
	q := StockListQuery{
		WarehouseID: parseUintQuery(c, "warehouse_id"),
		ItemID:      parseUintQuery(c, "item_id"),
		LowStock:    c.Query("low_stock") == "true",
	}
	rows, total, err := h.svc.ListStock(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[Stock]{Count: total, Results: rows})
}

func (h *Handler) RetrieveStock(c *gin.Context) {
	st, err := h.svc.GetStock(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, st)
}

// ── StockMove ──────────────────────────────────────────────────────────

func (h *Handler) ListMove(c *gin.Context) {
	p := httpx.ParsePage(c)
	q := StockMoveListQuery{
		ItemID:   parseUintQuery(c, "item_id"),
		MoveType: c.Query("move_type"),
		Status:   c.Query("status"),
	}
	rows, total, err := h.svc.ListMove(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[StockMove]{Count: total, Results: rows})
}

func (h *Handler) RetrieveMove(c *gin.Context) {
	m, err := h.svc.GetMove(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, m)
}

func (h *Handler) CreateMove(c *gin.Context) {
	var in StockMoveCreateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	m, err := h.svc.CreateMove(c.Request.Context(), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.Created(c, m)
}

func (h *Handler) UpdateMove(c *gin.Context) {
	var in StockMoveUpdateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	m, err := h.svc.UpdateMove(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, m)
}

func (h *Handler) DeleteMove(c *gin.Context) {
	if err := h.svc.DeleteMove(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.NoContent(c)
}

// CompleteMove 草稿移动 → COMPLETED,落账实。
func (h *Handler) CompleteMove(c *gin.Context) {
	m, err := h.svc.CompleteMove(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, m)
}

// ── Batch ──────────────────────────────────────────────────────────────

func (h *Handler) ListBatch(c *gin.Context) {
	p := httpx.ParsePage(c)
	q := BatchListQuery{
		ItemID:        parseUintQuery(c, "item_id"),
		WarehouseID:   parseUintQuery(c, "warehouse_id"),
		QualityStatus: c.Query("quality_status"),
		ExpiringOnly:  c.Query("expiring") == "true",
	}
	rows, total, err := h.svc.ListBatch(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[Batch]{Count: total, Results: rows})
}

func (h *Handler) RetrieveBatch(c *gin.Context) {
	b, err := h.svc.GetBatch(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, b)
}

func (h *Handler) CreateBatch(c *gin.Context) {
	var in BatchCreateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	b, err := h.svc.CreateBatch(c.Request.Context(), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.Created(c, b)
}

func (h *Handler) UpdateBatch(c *gin.Context) {
	var in BatchUpdateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	b, err := h.svc.UpdateBatch(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, b)
}

func (h *Handler) DeleteBatch(c *gin.Context) {
	if err := h.svc.DeleteBatch(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.NoContent(c)
}

// ── StockAlert ─────────────────────────────────────────────────────────

func (h *Handler) ListAlert(c *gin.Context) {
	p := httpx.ParsePage(c)
	q := AlertListQuery{
		ItemID:    parseUintQuery(c, "item_id"),
		Status:    c.Query("status"),
		Severity:  c.Query("severity"),
		AlertType: c.Query("alert_type"),
	}
	rows, total, err := h.svc.ListAlert(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[StockAlert]{Count: total, Results: rows})
}

func (h *Handler) RetrieveAlert(c *gin.Context) {
	a, err := h.svc.GetAlert(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, a)
}

func (h *Handler) CreateAlert(c *gin.Context) {
	var in AlertCreateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	a, err := h.svc.CreateAlert(c.Request.Context(), in)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.Created(c, a)
}

func (h *Handler) DeleteAlert(c *gin.Context) {
	if err := h.svc.DeleteAlert(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.NoContent(c)
}

func (h *Handler) AcknowledgeAlert(c *gin.Context) {
	a, err := h.svc.Acknowledge(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, a)
}

func (h *Handler) ResolveAlert(c *gin.Context) {
	var in AlertResolveInput
	_ = c.ShouldBindJSON(&in) // body 可选
	a, err := h.svc.Resolve(c.Request.Context(), parseID(c), in.Resolution)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, a)
}

func (h *Handler) IgnoreAlert(c *gin.Context) {
	var in AlertResolveInput
	_ = c.ShouldBindJSON(&in)
	a, err := h.svc.Ignore(c.Request.Context(), parseID(c), in.Reason)
	if err != nil {
		httpx.Error(c, statusFor(err), err.Error())
		return
	}
	httpx.OK(c, a)
}

// ── helpers ────────────────────────────────────────────────────────────

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
	case errors.Is(err, ErrInsufficient), errors.Is(err, ErrInvalidStatus),
		errors.Is(err, ErrBadMoveType), errors.Is(err, ErrBadDate):
		return http.StatusBadRequest
	default:
		return http.StatusInternalServerError
	}
}
