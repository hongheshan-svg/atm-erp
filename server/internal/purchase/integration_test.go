//go:build integration

// Package purchase_test 是采购模块的运行期集成测试:起真实 Postgres、AutoMigrate
// 本模块全部主模型、用 httptest 跑该模块路由的列表/创建/详情/更新/删除及状态流转。
package purchase_test

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/atm-erp/server/internal/purchase"
	"github.com/atm-erp/server/internal/testutil"
)

const dsn = "host=127.0.0.1 port=55512 user=u password=p dbname=d sslmode=disable TimeZone=Asia/Shanghai"

// allModels 列出本模块需要 AutoMigrate 的全部表(主实体 + 明细 + 关联)。
func allModels() []any {
	return []any{
		&purchase.PurchaseRequest{}, &purchase.PurchaseRequestLine{},
		&purchase.PurchaseOrder{}, &purchase.PurchaseOrderLine{},
		&purchase.GoodsReceipt{}, &purchase.GoodsReceiptLine{},
		&purchase.RFQ{}, &purchase.RFQLine{}, &purchase.RFQSupplier{},
		&purchase.SupplierQuotation{},
	}
}

// doReq 发起请求并返回响应记录器。
func doReq(t *testing.T, r http.Handler, method, path string, body any) *httptest.ResponseRecorder {
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

// idOf 从创建响应里取 id。
func idOf(t *testing.T, w *httptest.ResponseRecorder) uint64 {
	t.Helper()
	var resp struct {
		ID uint64 `json:"id"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("解析 id 失败: %v; body=%s", err, w.Body.String())
	}
	if resp.ID == 0 {
		t.Fatalf("创建响应缺少 id; body=%s", w.Body.String())
	}
	return resp.ID
}

func TestPurchaseIntegration(t *testing.T) {
	db := testutil.OpenDB(t, dsn, allModels()...)
	// 每次清表,保证幂等。
	for _, m := range allModels() {
		if err := db.Unscoped().Where("1 = 1").Delete(m).Error; err != nil {
			t.Fatalf("清表失败: %v", err)
		}
	}

	r, api := testutil.NewAPIEngine()
	purchase.Routes(api, db, testutil.AllowAll)

	now := time.Now()
	later := now.Add(72 * time.Hour)

	// ---------------- 列表端点全部应 200 ----------------
	for _, path := range []string{
		"/api/purchase/requests",
		"/api/purchase/orders",
		"/api/purchase/receipts",
		"/api/purchase/rfqs",
	} {
		w := doReq(t, r, http.MethodGet, path, nil)
		if w.Code != http.StatusOK {
			t.Fatalf("GET %s 期望 200,得到 %d; body=%s", path, w.Code, w.Body.String())
		}
	}

	// ---------------- 采购申请 PR:创建/详情/更新/状态流转 ----------------
	prID := func() uint64 {
		in := purchase.PRCreateInput{
			RequestorID:  1,
			RequiredDate: later,
			Notes:        "集成测试 PR",
			Lines: []purchase.PRLineInput{
				{ItemID: 1, Qty: 10, EstimatedPrice: 5},
			},
		}
		w := doReq(t, r, http.MethodPost, "/api/purchase/requests", in)
		if w.Code != http.StatusCreated {
			t.Fatalf("创建 PR 期望 201,得到 %d; body=%s", w.Code, w.Body.String())
		}
		return idOf(t, w)
	}()
	if w := doReq(t, r, http.MethodGet, fmt.Sprintf("/api/purchase/requests/%d", prID), nil); w.Code != http.StatusOK {
		t.Fatalf("GET PR 详情期望 200,得到 %d; body=%s", w.Code, w.Body.String())
	}
	if w := doReq(t, r, http.MethodPut, fmt.Sprintf("/api/purchase/requests/%d", prID),
		purchase.PRUpdateInput{Notes: ptr("改后备注")}); w.Code != http.StatusOK {
		t.Fatalf("PUT PR 期望 200,得到 %d; body=%s", w.Code, w.Body.String())
	}
	if w := doReq(t, r, http.MethodPost, fmt.Sprintf("/api/purchase/requests/%d/submit", prID), nil); w.Code != http.StatusOK {
		t.Fatalf("submit PR 期望 200,得到 %d; body=%s", w.Code, w.Body.String())
	}
	if w := doReq(t, r, http.MethodPost, fmt.Sprintf("/api/purchase/requests/%d/approve", prID), nil); w.Code != http.StatusOK {
		t.Fatalf("approve PR 期望 200,得到 %d; body=%s", w.Code, w.Body.String())
	}

	// ---------------- 采购订单 PO:创建/详情/更新 ----------------
	poID := func() uint64 {
		in := purchase.POCreateInput{
			SupplierID:   1,
			DeliveryDate: later,
			Notes:        "集成测试 PO",
			Lines: []purchase.POLineInput{
				{ItemID: 1, Qty: 5, UnitPrice: 100},
			},
		}
		w := doReq(t, r, http.MethodPost, "/api/purchase/orders", in)
		if w.Code != http.StatusCreated {
			t.Fatalf("创建 PO 期望 201,得到 %d; body=%s", w.Code, w.Body.String())
		}
		return idOf(t, w)
	}()
	if w := doReq(t, r, http.MethodGet, fmt.Sprintf("/api/purchase/orders/%d", poID), nil); w.Code != http.StatusOK {
		t.Fatalf("GET PO 详情期望 200,得到 %d; body=%s", w.Code, w.Body.String())
	}
	if w := doReq(t, r, http.MethodPut, fmt.Sprintf("/api/purchase/orders/%d", poID),
		purchase.POUpdateInput{Notes: ptr("PO 改后备注")}); w.Code != http.StatusOK {
		t.Fatalf("PUT PO 期望 200,得到 %d; body=%s", w.Code, w.Body.String())
	}
	// 确认订单以便走收货流程。
	if w := doReq(t, r, http.MethodPost, fmt.Sprintf("/api/purchase/orders/%d/confirm", poID), nil); w.Code != http.StatusOK {
		t.Fatalf("confirm PO 期望 200,得到 %d; body=%s", w.Code, w.Body.String())
	}

	// 取 PO 行 id,供收货明细引用。
	poLineID := func() uint64 {
		w := doReq(t, r, http.MethodGet, fmt.Sprintf("/api/purchase/orders/%d", poID), nil)
		var resp struct {
			Lines []struct {
				ID uint64 `json:"id"`
			} `json:"lines"`
		}
		if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil || len(resp.Lines) == 0 {
			t.Fatalf("取 PO 行失败: %v; body=%s", err, w.Body.String())
		}
		return resp.Lines[0].ID
	}()

	// ---------------- 收货 GR:创建/详情/确认 ----------------
	grID := func() uint64 {
		in := purchase.GRCreateInput{
			POID:        poID,
			WarehouseID: 1,
			ReceiptDate: now,
			Notes:       "集成测试 GR",
			Lines: []purchase.GRLineInput{
				{POLineID: poLineID, ItemID: 1, Qty: 5, QualityStatus: "PASSED"},
			},
		}
		w := doReq(t, r, http.MethodPost, "/api/purchase/receipts", in)
		if w.Code != http.StatusCreated {
			t.Fatalf("创建 GR 期望 201,得到 %d; body=%s", w.Code, w.Body.String())
		}
		return idOf(t, w)
	}()
	if w := doReq(t, r, http.MethodGet, fmt.Sprintf("/api/purchase/receipts/%d", grID), nil); w.Code != http.StatusOK {
		t.Fatalf("GET GR 详情期望 200,得到 %d; body=%s", w.Code, w.Body.String())
	}
	if w := doReq(t, r, http.MethodPost, fmt.Sprintf("/api/purchase/receipts/%d/confirm", grID), nil); w.Code != http.StatusOK {
		t.Fatalf("confirm GR 期望 200,得到 %d; body=%s", w.Code, w.Body.String())
	}

	// ---------------- 询价 RFQ:创建/详情/更新/发送/删除 ----------------
	rfqID := func() uint64 {
		in := purchase.RFQCreateInput{
			ResponseDeadline: later,
			Notes:            "集成测试 RFQ",
			Lines: []purchase.RFQLineInput{
				{ItemID: 1, Qty: 3, RequiredDate: later},
			},
			SupplierIDs: []uint64{1, 2},
		}
		w := doReq(t, r, http.MethodPost, "/api/purchase/rfqs", in)
		if w.Code != http.StatusCreated {
			t.Fatalf("创建 RFQ 期望 201,得到 %d; body=%s", w.Code, w.Body.String())
		}
		return idOf(t, w)
	}()
	if w := doReq(t, r, http.MethodGet, fmt.Sprintf("/api/purchase/rfqs/%d", rfqID), nil); w.Code != http.StatusOK {
		t.Fatalf("GET RFQ 详情期望 200,得到 %d; body=%s", w.Code, w.Body.String())
	}
	if w := doReq(t, r, http.MethodPut, fmt.Sprintf("/api/purchase/rfqs/%d", rfqID),
		purchase.RFQUpdateInput{Notes: ptr("RFQ 改后备注")}); w.Code != http.StatusOK {
		t.Fatalf("PUT RFQ 期望 200,得到 %d; body=%s", w.Code, w.Body.String())
	}
	if w := doReq(t, r, http.MethodPost, fmt.Sprintf("/api/purchase/rfqs/%d/send", rfqID), nil); w.Code != http.StatusOK {
		t.Fatalf("send RFQ 期望 200,得到 %d; body=%s", w.Code, w.Body.String())
	}

	// ---------------- 删除:用一张新的草稿 RFQ 验证 DELETE ----------------
	delRFQ := func() uint64 {
		in := purchase.RFQCreateInput{
			ResponseDeadline: later,
			Lines:            []purchase.RFQLineInput{{ItemID: 1, Qty: 1, RequiredDate: later}},
		}
		w := doReq(t, r, http.MethodPost, "/api/purchase/rfqs", in)
		if w.Code != http.StatusCreated {
			t.Fatalf("创建待删 RFQ 期望 201,得到 %d; body=%s", w.Code, w.Body.String())
		}
		return idOf(t, w)
	}()
	if w := doReq(t, r, http.MethodDelete, fmt.Sprintf("/api/purchase/rfqs/%d", delRFQ), nil); w.Code != http.StatusNoContent {
		t.Fatalf("DELETE RFQ 期望 204,得到 %d; body=%s", w.Code, w.Body.String())
	}
}

func ptr[T any](v T) *T { return &v }
