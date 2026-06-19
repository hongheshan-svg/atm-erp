//go:build integration

package sales_test

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strconv"
	"testing"

	"github.com/atm-erp/server/internal/sales"
	"github.com/atm-erp/server/internal/testutil"
)

const dsn = "host=127.0.0.1 port=55511 user=u password=p dbname=d sslmode=disable TimeZone=Asia/Shanghai"

func setup(t *testing.T) *http.ServeMux {
	t.Helper()
	db := testutil.OpenDB(t, dsn,
		&sales.Quotation{},
		&sales.QuotationLine{},
		&sales.SalesOrder{},
		&sales.SalesOrderLine{},
		&sales.DeliveryOrder{},
		&sales.DeliveryOrderLine{},
		&sales.Lead{},
		&sales.Opportunity{},
	)
	r, api := testutil.NewAPIEngine()
	sales.Routes(api, db, testutil.AllowAll)
	mux := http.NewServeMux()
	mux.Handle("/", r)
	return mux
}

func do(t *testing.T, h http.Handler, method, path string, body any) *httptest.ResponseRecorder {
	t.Helper()
	var buf bytes.Buffer
	if body != nil {
		if err := json.NewEncoder(&buf).Encode(body); err != nil {
			t.Fatalf("encode body: %v", err)
		}
	}
	req := httptest.NewRequest(method, path, &buf)
	req.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	return rec
}

func is2xx(code int) bool { return code >= 200 && code < 300 }

func itoa(id uint64) string { return strconv.FormatUint(id, 10) }

// createdID 从创建响应中解析 data.id。
func createdID(t *testing.T, rec *httptest.ResponseRecorder) uint64 {
	t.Helper()
	var resp struct {
		ID uint64 `json:"id"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("unmarshal created resp: %v body=%s", err, rec.Body.String())
	}
	return resp.ID
}

func TestIntegrationListEndpoints(t *testing.T) {
	h := setup(t)
	lists := []string{
		"/api/sales/quotations",
		"/api/sales/orders",
		"/api/sales/deliveries",
		"/api/sales/leads",
		"/api/sales/opportunities",
	}
	for _, p := range lists {
		rec := do(t, h, http.MethodGet, p, nil)
		if rec.Code != http.StatusOK {
			t.Errorf("GET %s = %d, want 200; body=%s", p, rec.Code, rec.Body.String())
		}
	}
}

func TestIntegrationQuotationCRUD(t *testing.T) {
	h := setup(t)
	rec := do(t, h, http.MethodPost, "/api/sales/quotations", map[string]any{
		"customer_id": 1,
		"tax_rate":    13,
		"notes":       "test quotation",
		"lines": []map[string]any{
			{"custom_name": "item A", "qty": 2, "unit_price": 100},
		},
	})
	if !is2xx(rec.Code) {
		t.Fatalf("POST quotation = %d; body=%s", rec.Code, rec.Body.String())
	}
	id := createdID(t, rec)
	if id == 0 {
		t.Fatalf("quotation id == 0; body=%s", rec.Body.String())
	}
	base := "/api/sales/quotations/" + itoa(id)
	if rec := do(t, h, http.MethodGet, base, nil); rec.Code != http.StatusOK {
		t.Errorf("GET quotation detail = %d; body=%s", rec.Code, rec.Body.String())
	}
	if rec := do(t, h, http.MethodPut, base, map[string]any{"notes": "updated"}); rec.Code != http.StatusOK {
		t.Errorf("PUT quotation = %d; body=%s", rec.Code, rec.Body.String())
	}
	if rec := do(t, h, http.MethodDelete, base, nil); !is2xx(rec.Code) {
		t.Errorf("DELETE quotation = %d; body=%s", rec.Code, rec.Body.String())
	}
}

func TestIntegrationSalesOrderCRUD(t *testing.T) {
	h := setup(t)
	rec := do(t, h, http.MethodPost, "/api/sales/orders", map[string]any{
		"customer_id":   1,
		"tax_rate":      13,
		"payment_terms": "NET30",
		"lines": []map[string]any{
			{"custom_name": "part X", "qty": 3, "unit_price": 50},
		},
	})
	if !is2xx(rec.Code) {
		t.Fatalf("POST order = %d; body=%s", rec.Code, rec.Body.String())
	}
	id := createdID(t, rec)
	if rec := do(t, h, http.MethodGet, "/api/sales/orders/"+itoa(id), nil); rec.Code != http.StatusOK {
		t.Errorf("GET order detail = %d; body=%s", rec.Code, rec.Body.String())
	}
}

func TestIntegrationDeliveryCRUD(t *testing.T) {
	h := setup(t)
	// 先建订单与明细以满足发货外键(so_id/so_line_id)。
	rec := do(t, h, http.MethodPost, "/api/sales/orders", map[string]any{
		"customer_id": 1,
		"lines": []map[string]any{
			{"custom_name": "part Y", "qty": 5, "unit_price": 20},
		},
	})
	if !is2xx(rec.Code) {
		t.Fatalf("POST order(for delivery) = %d; body=%s", rec.Code, rec.Body.String())
	}
	soID := createdID(t, rec)

	rec = do(t, h, http.MethodPost, "/api/sales/deliveries", map[string]any{
		"so_id":        soID,
		"warehouse_id": 1,
		"lines": []map[string]any{
			{"so_line_id": 1, "qty": 1},
		},
	})
	if !is2xx(rec.Code) {
		t.Fatalf("POST delivery = %d; body=%s", rec.Code, rec.Body.String())
	}
	id := createdID(t, rec)
	if rec := do(t, h, http.MethodGet, "/api/sales/deliveries/"+itoa(id), nil); rec.Code != http.StatusOK {
		t.Errorf("GET delivery detail = %d; body=%s", rec.Code, rec.Body.String())
	}
}

func TestIntegrationLeadCRUD(t *testing.T) {
	h := setup(t)
	rec := do(t, h, http.MethodPost, "/api/sales/leads", map[string]any{
		"company_name": "Acme Co",
		"contact_name": "Jane",
		"contact_phone": "123456",
	})
	if !is2xx(rec.Code) {
		t.Fatalf("POST lead = %d; body=%s", rec.Code, rec.Body.String())
	}
	base := "/api/sales/leads/" + itoa(createdID(t, rec))
	if rec := do(t, h, http.MethodGet, base, nil); rec.Code != http.StatusOK {
		t.Errorf("GET lead detail = %d; body=%s", rec.Code, rec.Body.String())
	}
	if rec := do(t, h, http.MethodPut, base, map[string]any{"notes": "follow up"}); rec.Code != http.StatusOK {
		t.Errorf("PUT lead = %d; body=%s", rec.Code, rec.Body.String())
	}
	if rec := do(t, h, http.MethodDelete, base, nil); !is2xx(rec.Code) {
		t.Errorf("DELETE lead = %d; body=%s", rec.Code, rec.Body.String())
	}
}

func TestIntegrationOpportunityCRUD(t *testing.T) {
	h := setup(t)
	rec := do(t, h, http.MethodPost, "/api/sales/opportunities", map[string]any{
		"name":             "Big deal",
		"customer_id":      1,
		"estimated_amount": 10000,
		"probability":      50,
	})
	if !is2xx(rec.Code) {
		t.Fatalf("POST opportunity = %d; body=%s", rec.Code, rec.Body.String())
	}
	base := "/api/sales/opportunities/" + itoa(createdID(t, rec))
	if rec := do(t, h, http.MethodGet, base, nil); rec.Code != http.StatusOK {
		t.Errorf("GET opportunity detail = %d; body=%s", rec.Code, rec.Body.String())
	}
	if rec := do(t, h, http.MethodPut, base, map[string]any{"notes": "hot"}); rec.Code != http.StatusOK {
		t.Errorf("PUT opportunity = %d; body=%s", rec.Code, rec.Body.String())
	}
	if rec := do(t, h, http.MethodDelete, base, nil); !is2xx(rec.Code) {
		t.Errorf("DELETE opportunity = %d; body=%s", rec.Code, rec.Body.String())
	}
}
