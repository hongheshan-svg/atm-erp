//go:build integration

package inventory_test

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/atm-erp/server/internal/inventory"
	"github.com/atm-erp/server/internal/testutil"
	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
)

const dsn = "host=127.0.0.1 port=55513 user=u password=p dbname=d sslmode=disable TimeZone=Asia/Shanghai"

func setup(t *testing.T) (*gin.Engine, *gorm.DB) {
	t.Helper()
	db := testutil.OpenDB(t, dsn,
		&inventory.Stock{},
		&inventory.StockMove{},
		&inventory.Batch{},
		&inventory.StockAlert{},
	)
	r, api := testutil.NewAPIEngine()
	inventory.Routes(api, db, testutil.AllowAll)
	return r, db
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

// idFromBody 从创建响应里提取实体 id。响应体形如 {"id":...} 或 {"data":{"id":...}}。
func idFromBody(t *testing.T, body []byte) uint64 {
	t.Helper()
	var m map[string]any
	if err := json.Unmarshal(body, &m); err != nil {
		t.Fatalf("unmarshal create resp: %v (body=%s)", err, body)
	}
	if v, ok := m["id"]; ok {
		if f, ok := v.(float64); ok {
			return uint64(f)
		}
	}
	if d, ok := m["data"].(map[string]any); ok {
		if v, ok := d["id"].(float64); ok {
			return uint64(v)
		}
	}
	t.Fatalf("no id in create resp: %s", body)
	return 0
}

func TestIntegrationListEndpoints(t *testing.T) {
	r, _ := setup(t)
	lists := []string{
		"/api/inventory/stocks",
		"/api/inventory/stock-moves",
		"/api/inventory/batches",
		"/api/inventory/stock-alerts",
	}
	for _, p := range lists {
		w := do(t, r, http.MethodGet, p, nil)
		if w.Code != http.StatusOK {
			t.Errorf("GET %s = %d, want 200; body=%s", p, w.Code, w.Body.String())
		}
	}
}

func TestIntegrationStockMoveCRUD(t *testing.T) {
	r, _ := setup(t)

	// Create (DRAFT)
	create := map[string]any{
		"item_id":      1001,
		"warehouse_to": 1,
		"qty":          10,
		"unit_cost":    5.5,
		"move_type":    inventory.MoveTypeInPurchase,
		"move_date":    "2026-06-19",
	}
	w := do(t, r, http.MethodPost, "/api/inventory/stock-moves", create)
	if w.Code < 200 || w.Code >= 300 {
		t.Fatalf("POST stock-move = %d, want 2xx; body=%s", w.Code, w.Body.String())
	}
	id := idFromBody(t, w.Body.Bytes())

	// Retrieve
	w = do(t, r, http.MethodGet, fmt.Sprintf("/api/inventory/stock-moves/%d", id), nil)
	if w.Code != http.StatusOK {
		t.Errorf("GET stock-move/%d = %d; body=%s", id, w.Code, w.Body.String())
	}

	// Update (draft editable)
	upd := map[string]any{"qty": 12, "notes": "调整数量"}
	w = do(t, r, http.MethodPut, fmt.Sprintf("/api/inventory/stock-moves/%d", id), upd)
	if w.Code != http.StatusOK {
		t.Errorf("PUT stock-move/%d = %d; body=%s", id, w.Code, w.Body.String())
	}

	// Complete -> posts to stock
	w = do(t, r, http.MethodPost, fmt.Sprintf("/api/inventory/stock-moves/%d/complete", id), nil)
	if w.Code != http.StatusOK {
		t.Errorf("complete stock-move/%d = %d; body=%s", id, w.Code, w.Body.String())
	}

	// Stock list should now reflect the inbound
	w = do(t, r, http.MethodGet, "/api/inventory/stocks", nil)
	if w.Code != http.StatusOK {
		t.Errorf("GET stocks after complete = %d; body=%s", w.Code, w.Body.String())
	}
}

func TestIntegrationStockMoveDelete(t *testing.T) {
	r, _ := setup(t)
	create := map[string]any{
		"item_id":      2002,
		"warehouse_to": 1,
		"qty":          3,
		"unit_cost":    1,
		"move_type":    inventory.MoveTypeInPurchase,
		"move_date":    "2026-06-19",
	}
	w := do(t, r, http.MethodPost, "/api/inventory/stock-moves", create)
	if w.Code < 200 || w.Code >= 300 {
		t.Fatalf("POST stock-move = %d; body=%s", w.Code, w.Body.String())
	}
	id := idFromBody(t, w.Body.Bytes())
	w = do(t, r, http.MethodDelete, fmt.Sprintf("/api/inventory/stock-moves/%d", id), nil)
	if w.Code < 200 || w.Code >= 300 {
		t.Errorf("DELETE stock-move/%d = %d; body=%s", id, w.Code, w.Body.String())
	}
}

func TestIntegrationBatchCRUD(t *testing.T) {
	r, _ := setup(t)
	create := map[string]any{
		"batch_no":         "B-INT-001",
		"item_id":          3003,
		"warehouse_id":     1,
		"qty_on_hand":      100,
		"unit_cost":        2.5,
		"manufacture_date": "2026-01-01",
		"expiry_date":      "2027-01-01",
	}
	w := do(t, r, http.MethodPost, "/api/inventory/batches", create)
	if w.Code < 200 || w.Code >= 300 {
		t.Fatalf("POST batch = %d, want 2xx; body=%s", w.Code, w.Body.String())
	}
	id := idFromBody(t, w.Body.Bytes())

	w = do(t, r, http.MethodGet, fmt.Sprintf("/api/inventory/batches/%d", id), nil)
	if w.Code != http.StatusOK {
		t.Errorf("GET batch/%d = %d; body=%s", id, w.Code, w.Body.String())
	}

	upd := map[string]any{"qty_on_hand": 80, "quality_status": inventory.BatchQualityPassed}
	w = do(t, r, http.MethodPut, fmt.Sprintf("/api/inventory/batches/%d", id), upd)
	if w.Code != http.StatusOK {
		t.Errorf("PUT batch/%d = %d; body=%s", id, w.Code, w.Body.String())
	}

	w = do(t, r, http.MethodDelete, fmt.Sprintf("/api/inventory/batches/%d", id), nil)
	if w.Code < 200 || w.Code >= 300 {
		t.Errorf("DELETE batch/%d = %d; body=%s", id, w.Code, w.Body.String())
	}
}

func TestIntegrationStockAlertCRUD(t *testing.T) {
	r, _ := setup(t)
	create := map[string]any{
		"item_id":         4004,
		"warehouse":       1,
		"alert_type":      "LOW_STOCK",
		"severity":        inventory.AlertSeverityWarning,
		"title":           "低库存预警",
		"description":     "低于安全库存",
		"current_qty":     2,
		"threshold_value": 10,
	}
	w := do(t, r, http.MethodPost, "/api/inventory/stock-alerts", create)
	if w.Code < 200 || w.Code >= 300 {
		t.Fatalf("POST stock-alert = %d, want 2xx; body=%s", w.Code, w.Body.String())
	}
	id := idFromBody(t, w.Body.Bytes())

	w = do(t, r, http.MethodGet, fmt.Sprintf("/api/inventory/stock-alerts/%d", id), nil)
	if w.Code != http.StatusOK {
		t.Errorf("GET stock-alert/%d = %d; body=%s", id, w.Code, w.Body.String())
	}

	w = do(t, r, http.MethodPost, fmt.Sprintf("/api/inventory/stock-alerts/%d/acknowledge", id), nil)
	if w.Code != http.StatusOK {
		t.Errorf("acknowledge alert/%d = %d; body=%s", id, w.Code, w.Body.String())
	}

	w = do(t, r, http.MethodPost, fmt.Sprintf("/api/inventory/stock-alerts/%d/resolve", id), map[string]any{"resolution": "已补货"})
	if w.Code != http.StatusOK {
		t.Errorf("resolve alert/%d = %d; body=%s", id, w.Code, w.Body.String())
	}

	w = do(t, r, http.MethodDelete, fmt.Sprintf("/api/inventory/stock-alerts/%d", id), nil)
	if w.Code < 200 || w.Code >= 300 {
		t.Errorf("DELETE stock-alert/%d = %d; body=%s", id, w.Code, w.Body.String())
	}
}
