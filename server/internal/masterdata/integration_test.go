//go:build integration

// Package masterdata_test 对「主数据」聚合路由(customer/supplier/warehouse)做运行期集成验证:
// 起真实 Postgres、AutoMigrate 本模块模型、用 httptest 跑各端点 CRUD。
package masterdata_test

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/atm-erp/server/internal/masterdata"
	"github.com/atm-erp/server/internal/masterdata/customer"
	"github.com/atm-erp/server/internal/masterdata/supplier"
	"github.com/atm-erp/server/internal/masterdata/warehouse"
	"github.com/atm-erp/server/internal/testutil"
	"github.com/gin-gonic/gin"
)

const dsn = "host=127.0.0.1 port=55510 user=u password=p dbname=d sslmode=disable TimeZone=Asia/Shanghai"

// setup 起库迁移 + 装配聚合路由,返回引擎。
func setup(t *testing.T) *gin.Engine {
	t.Helper()
	db := testutil.OpenDB(t, dsn,
		&customer.Customer{},
		&supplier.Supplier{},
		&warehouse.Warehouse{},
	)
	r, api := testutil.NewAPIEngine()
	masterdata.Routes(api, db, testutil.AllowAll)
	return r
}

// do 发起请求并返回响应录制器。
func do(t *testing.T, r *gin.Engine, method, path string, body any) *httptest.ResponseRecorder {
	t.Helper()
	var buf bytes.Buffer
	if body != nil {
		if err := json.NewEncoder(&buf).Encode(body); err != nil {
			t.Fatalf("编码请求体失败: %v", err)
		}
	}
	req := httptest.NewRequest(method, path, &buf)
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

// extractID 从创建响应中取出 id。
func extractID(t *testing.T, w *httptest.ResponseRecorder) float64 {
	t.Helper()
	var m map[string]any
	if err := json.Unmarshal(w.Body.Bytes(), &m); err != nil {
		t.Fatalf("解析响应失败: %v body=%s", err, w.Body.String())
	}
	id, ok := m["id"].(float64)
	if !ok {
		t.Fatalf("响应缺少 id: %s", w.Body.String())
	}
	return id
}

func assertStatus(t *testing.T, w *httptest.ResponseRecorder, want int, ctx string) {
	t.Helper()
	if w.Code != want {
		t.Fatalf("%s: 期望 %d 实得 %d,body=%s", ctx, want, w.Code, w.Body.String())
	}
}

func TestIntegrationListEndpoints(t *testing.T) {
	r := setup(t)
	for _, p := range []string{
		"/api/masterdata/customers",
		"/api/masterdata/suppliers",
		"/api/masterdata/warehouses",
	} {
		w := do(t, r, http.MethodGet, p, nil)
		assertStatus(t, w, http.StatusOK, "GET "+p)
	}
}

func TestIntegrationCustomerCRUD(t *testing.T) {
	r := setup(t)
	// Create(code 留空,后端生成)
	w := do(t, r, http.MethodPost, "/api/masterdata/customers", map[string]any{
		"name": "集成测试客户A",
	})
	assertStatus(t, w, http.StatusCreated, "POST customer")
	id := extractID(t, w)

	// Retrieve
	w = do(t, r, http.MethodGet, "/api/masterdata/customers/"+itoa(id), nil)
	assertStatus(t, w, http.StatusOK, "GET customer/:id")

	// Update
	w = do(t, r, http.MethodPut, "/api/masterdata/customers/"+itoa(id), map[string]any{
		"phone": "13800000000",
	})
	assertStatus(t, w, http.StatusOK, "PUT customer/:id")

	// ChangeStatus
	w = do(t, r, http.MethodPost, "/api/masterdata/customers/"+itoa(id)+"/change_status", map[string]any{
		"status": "INACTIVE",
	})
	assertStatus(t, w, http.StatusOK, "POST customer change_status")

	// Delete
	w = do(t, r, http.MethodDelete, "/api/masterdata/customers/"+itoa(id), nil)
	assertStatus(t, w, http.StatusNoContent, "DELETE customer/:id")
}

func TestIntegrationSupplierCRUD(t *testing.T) {
	r := setup(t)
	w := do(t, r, http.MethodPost, "/api/masterdata/suppliers", map[string]any{
		"name":              "集成测试供应商A",
		"settlement_method": "NET30",
	})
	assertStatus(t, w, http.StatusCreated, "POST supplier")
	id := extractID(t, w)

	w = do(t, r, http.MethodGet, "/api/masterdata/suppliers/"+itoa(id), nil)
	assertStatus(t, w, http.StatusOK, "GET supplier/:id")

	w = do(t, r, http.MethodPut, "/api/masterdata/suppliers/"+itoa(id), map[string]any{
		"phone": "13900000000",
	})
	assertStatus(t, w, http.StatusOK, "PUT supplier/:id")

	w = do(t, r, http.MethodDelete, "/api/masterdata/suppliers/"+itoa(id), nil)
	assertStatus(t, w, http.StatusNoContent, "DELETE supplier/:id")
}

func TestIntegrationWarehouseCRUD(t *testing.T) {
	r := setup(t)
	w := do(t, r, http.MethodPost, "/api/masterdata/warehouses", map[string]any{
		"code":           "WH-IT-001",
		"name":           "集成测试仓库A",
		"warehouse_type": "MAIN",
	})
	assertStatus(t, w, http.StatusCreated, "POST warehouse")
	id := extractID(t, w)

	w = do(t, r, http.MethodGet, "/api/masterdata/warehouses/"+itoa(id), nil)
	assertStatus(t, w, http.StatusOK, "GET warehouse/:id")

	w = do(t, r, http.MethodPut, "/api/masterdata/warehouses/"+itoa(id), map[string]any{
		"contact_phone": "0571-88888888",
	})
	assertStatus(t, w, http.StatusOK, "PUT warehouse/:id")

	w = do(t, r, http.MethodDelete, "/api/masterdata/warehouses/"+itoa(id), nil)
	assertStatus(t, w, http.StatusNoContent, "DELETE warehouse/:id")
}

// itoa 把创建响应里的 float64 id 转成路径片段。
func itoa(id float64) string {
	return jsonNumber(id)
}

func jsonNumber(f float64) string {
	b, _ := json.Marshal(int64(f))
	return string(b)
}
