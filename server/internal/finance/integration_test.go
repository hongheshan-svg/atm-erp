//go:build integration

package finance_test

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/atm-erp/server/internal/finance"
	"github.com/atm-erp/server/internal/testutil"
	"github.com/gin-gonic/gin"
)

const dsn = "host=127.0.0.1 port=55516 user=u password=p dbname=d sslmode=disable TimeZone=Asia/Shanghai"

func setup(t *testing.T) *gin.Engine {
	t.Helper()
	db := testutil.OpenDB(t, dsn,
		&finance.Currency{},
		&finance.Expense{},
		&finance.AccountReceivable{},
		&finance.AccountPayable{},
		&finance.Payment{},
		&finance.Invoice{},
		&finance.InvoiceItem{},
	)
	r, api := testutil.NewAPIEngine()
	finance.Routes(api, db, testutil.AllowAll)
	return r
}

func do(t *testing.T, r *gin.Engine, method, path string, body any) *httptest.ResponseRecorder {
	t.Helper()
	var rdr *bytes.Reader
	if body != nil {
		b, err := json.Marshal(body)
		if err != nil {
			t.Fatalf("marshal body: %v", err)
		}
		rdr = bytes.NewReader(b)
	} else {
		rdr = bytes.NewReader(nil)
	}
	req := httptest.NewRequest(method, path, rdr)
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

func mustStatus(t *testing.T, w *httptest.ResponseRecorder, want int, label string) {
	t.Helper()
	if w.Code != want {
		t.Fatalf("%s: got status %d want %d; body=%s", label, w.Code, want, w.Body.String())
	}
}

func idOf(t *testing.T, w *httptest.ResponseRecorder, label string) uint64 {
	t.Helper()
	var m map[string]any
	if err := json.Unmarshal(w.Body.Bytes(), &m); err != nil {
		t.Fatalf("%s: unmarshal create resp: %v; body=%s", label, err, w.Body.String())
	}
	idf, ok := m["id"].(float64)
	if !ok {
		t.Fatalf("%s: no id in create resp; body=%s", label, w.Body.String())
	}
	return uint64(idf)
}

func TestIntegrationFinanceListEndpoints(t *testing.T) {
	r := setup(t)
	lists := []string{
		"/api/finance/currencies",
		"/api/finance/expenses",
		"/api/finance/receivables",
		"/api/finance/payables",
		"/api/finance/payments",
		"/api/finance/invoices",
	}
	for _, p := range lists {
		w := do(t, r, http.MethodGet, p, nil)
		mustStatus(t, w, http.StatusOK, "GET "+p)
	}
}

func TestIntegrationCurrencyCRUD(t *testing.T) {
	r := setup(t)
	code := fmt.Sprintf("%03d", time.Now().UnixNano()%1000)
	w := do(t, r, http.MethodPost, "/api/finance/currencies", map[string]any{
		"code": code, "name": "测试币", "symbol": "$", "exchange_rate": 1.0,
	})
	mustStatus(t, w, http.StatusCreated, "POST currency")
	id := idOf(t, w, "currency")

	w = do(t, r, http.MethodGet, fmt.Sprintf("/api/finance/currencies/%d", id), nil)
	mustStatus(t, w, http.StatusOK, "GET currency detail")

	w = do(t, r, http.MethodPut, fmt.Sprintf("/api/finance/currencies/%d", id), map[string]any{"name": "改名"})
	mustStatus(t, w, http.StatusOK, "PUT currency")

	w = do(t, r, http.MethodDelete, fmt.Sprintf("/api/finance/currencies/%d", id), nil)
	mustStatus(t, w, http.StatusNoContent, "DELETE currency")
}

func TestIntegrationExpenseCRUD(t *testing.T) {
	r := setup(t)
	w := do(t, r, http.MethodPost, "/api/finance/expenses", map[string]any{
		"user_id":      1,
		"expense_date": "2026-06-19T00:00:00Z",
		"category":     "TRAVEL",
		"amount":       100.5,
		"description":  "差旅",
	})
	mustStatus(t, w, http.StatusCreated, "POST expense")
	id := idOf(t, w, "expense")

	w = do(t, r, http.MethodGet, fmt.Sprintf("/api/finance/expenses/%d", id), nil)
	mustStatus(t, w, http.StatusOK, "GET expense detail")

	w = do(t, r, http.MethodPost, fmt.Sprintf("/api/finance/expenses/%d/submit", id), nil)
	mustStatus(t, w, http.StatusOK, "submit expense")

	w = do(t, r, http.MethodPost, fmt.Sprintf("/api/finance/expenses/%d/approve", id), nil)
	mustStatus(t, w, http.StatusOK, "approve expense")

	w = do(t, r, http.MethodDelete, fmt.Sprintf("/api/finance/expenses/%d", id), nil)
	mustStatus(t, w, http.StatusNoContent, "DELETE expense")
}

func TestIntegrationReceivablePayableAndPayment(t *testing.T) {
	r := setup(t)
	// Receivable
	w := do(t, r, http.MethodPost, "/api/finance/receivables", map[string]any{
		"customer_id":  10,
		"invoice_date": "2026-06-19T00:00:00Z",
		"amount_due":   1000.0,
		"due_date":     "2026-07-19T00:00:00Z",
	})
	mustStatus(t, w, http.StatusCreated, "POST receivable")
	arID := idOf(t, w, "receivable")

	w = do(t, r, http.MethodGet, fmt.Sprintf("/api/finance/receivables/%d", arID), nil)
	mustStatus(t, w, http.StatusOK, "GET receivable detail")

	w = do(t, r, http.MethodPut, fmt.Sprintf("/api/finance/receivables/%d", arID), map[string]any{"amount_paid": 200.0})
	mustStatus(t, w, http.StatusOK, "PUT receivable")

	// Payable
	w = do(t, r, http.MethodPost, "/api/finance/payables", map[string]any{
		"supplier_id":  20,
		"invoice_date": "2026-06-19T00:00:00Z",
		"amount_due":   500.0,
		"due_date":     "2026-07-19T00:00:00Z",
	})
	mustStatus(t, w, http.StatusCreated, "POST payable")
	apID := idOf(t, w, "payable")

	// Payment against AR
	w = do(t, r, http.MethodPost, "/api/finance/payments", map[string]any{
		"payment_type":   "AR",
		"ar_id":          arID,
		"payment_date":   "2026-06-19T00:00:00Z",
		"payment_method": "BANK",
		"amount":         300.0,
	})
	mustStatus(t, w, http.StatusCreated, "POST payment AR")
	payID := idOf(t, w, "payment")

	w = do(t, r, http.MethodGet, fmt.Sprintf("/api/finance/payments/%d", payID), nil)
	mustStatus(t, w, http.StatusOK, "GET payment detail")

	w = do(t, r, http.MethodDelete, fmt.Sprintf("/api/finance/payments/%d", payID), nil)
	mustStatus(t, w, http.StatusNoContent, "DELETE payment")

	w = do(t, r, http.MethodDelete, fmt.Sprintf("/api/finance/payables/%d", apID), nil)
	mustStatus(t, w, http.StatusNoContent, "DELETE payable")
	w = do(t, r, http.MethodDelete, fmt.Sprintf("/api/finance/receivables/%d", arID), nil)
	mustStatus(t, w, http.StatusNoContent, "DELETE receivable")
}

func TestIntegrationInvoiceCRUD(t *testing.T) {
	r := setup(t)
	invNo := fmt.Sprintf("INV%d", time.Now().UnixNano())
	w := do(t, r, http.MethodPost, "/api/finance/invoices", map[string]any{
		"invoice_type":      "INPUT",
		"invoice_no":        invNo,
		"invoice_date":      "2026-06-19T00:00:00Z",
		"amount_before_tax": 1000.0,
		"tax_amount":        130.0,
		"items": []map[string]any{
			{"line_no": 1, "item_name": "钢材", "amount": 1000.0},
		},
	})
	mustStatus(t, w, http.StatusCreated, "POST invoice")
	id := idOf(t, w, "invoice")

	w = do(t, r, http.MethodGet, fmt.Sprintf("/api/finance/invoices/%d", id), nil)
	mustStatus(t, w, http.StatusOK, "GET invoice detail")

	w = do(t, r, http.MethodGet, fmt.Sprintf("/api/finance/invoices/%d/items", id), nil)
	mustStatus(t, w, http.StatusOK, "GET invoice items")

	w = do(t, r, http.MethodPost, fmt.Sprintf("/api/finance/invoices/%d/certify", id), nil)
	mustStatus(t, w, http.StatusOK, "certify invoice")

	w = do(t, r, http.MethodPost, fmt.Sprintf("/api/finance/invoices/%d/void", id), nil)
	mustStatus(t, w, http.StatusOK, "void invoice")

	w = do(t, r, http.MethodDelete, fmt.Sprintf("/api/finance/invoices/%d", id), nil)
	mustStatus(t, w, http.StatusNoContent, "DELETE invoice")
}
