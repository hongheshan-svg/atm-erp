//go:build integration

package collection_test

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/atm-erp/server/internal/finance/collection"
	"github.com/atm-erp/server/internal/testutil"
	"github.com/shopspring/decimal"
)

// 经真实 REST 路由(httptest)验证回款核销:建计划→2 节点→3 笔收款,
// 级联后计划 collected=100000 / COMPLETED。验证路由接线 + 级联端到端。
func TestCollectionRESTCascade(t *testing.T) {
	dsn := "host=127.0.0.1 port=55561 user=u password=p dbname=d sslmode=disable TimeZone=Asia/Shanghai"
	db := testutil.OpenDB(t, dsn, &collection.CollectionPlan{}, &collection.CollectionMilestone{}, &collection.CollectionRecord{})
	r, api := testutil.NewAPIEngine()
	collection.Routes(api, db, testutil.AllowAll)

	do := func(method, path string, body any) (int, map[string]any) {
		var buf bytes.Buffer
		if body != nil {
			_ = json.NewEncoder(&buf).Encode(body)
		}
		req := httptest.NewRequest(method, path, &buf)
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)
		var out map[string]any
		_ = json.Unmarshal(w.Body.Bytes(), &out)
		return w.Code, out
	}

	code, plan := do("POST", "/api/finance/collection/plans",
		map[string]any{"name": "对账计划", "customer_id": 1, "total_amount": 100000})
	if code != http.StatusCreated {
		t.Fatalf("create plan: %d %v", code, plan)
	}
	planID := uint64(plan["id"].(float64))

	mk := func(name string, amt float64) uint64 {
		code, m := do("POST", fmt.Sprintf("/api/finance/collection/plans/%d/milestones", planID),
			map[string]any{"name": name, "planned_amount": amt})
		if code != http.StatusCreated {
			t.Fatalf("create milestone %s: %d %v", name, code, m)
		}
		return uint64(m["id"].(float64))
	}
	m1 := mk("预付", 30000)
	m2 := mk("尾款", 70000)

	addRec := func(mID uint64, amt float64) {
		code, rec := do("POST", fmt.Sprintf("/api/finance/collection/milestones/%d/records", mID),
			map[string]any{"amount": amt})
		if code != http.StatusCreated {
			t.Fatalf("add record %v -> %d %v", amt, code, rec)
		}
	}
	addRec(m1, 10000)
	addRec(m1, 20000)
	addRec(m2, 70000)

	// GET 详情应 200 且含 plan + milestones
	code, detail := do("GET", fmt.Sprintf("/api/finance/collection/plans/%d", planID), nil)
	if code != http.StatusOK {
		t.Fatalf("get plan: %d", code)
	}
	if _, ok := detail["milestones"]; !ok {
		t.Errorf("详情应含 milestones")
	}

	// 级联正确性:直接读库断言(避免 JSON decimal 解析歧义)
	var p collection.CollectionPlan
	db.First(&p, planID)
	if !p.CollectedAmount.Equal(decimal.RequireFromString("100000")) || p.Status != collection.PlanCompleted {
		t.Errorf("计划 collected=%s status=%s,期望 100000/COMPLETED", p.CollectedAmount, p.Status)
	}
	var ms []collection.CollectionMilestone
	db.Where("plan_id = ?", planID).Order("id").Find(&ms)
	if len(ms) != 2 || ms[0].Status != collection.MilestoneCollected {
		t.Errorf("节点应 2 个且 m1 COLLECTED,得 %d 个", len(ms))
	}
}

// 验证计划 PUT 更新与 DELETE 软删(前端列表「编辑/删除」用到的 REST)。
func TestCollectionPlanUpdateDelete(t *testing.T) {
	dsn := "host=127.0.0.1 port=55561 user=u password=p dbname=d sslmode=disable TimeZone=Asia/Shanghai"
	db := testutil.OpenDB(t, dsn, &collection.CollectionPlan{}, &collection.CollectionMilestone{}, &collection.CollectionRecord{})
	r, api := testutil.NewAPIEngine()
	collection.Routes(api, db, testutil.AllowAll)

	do := func(method, path string, body any) (int, map[string]any) {
		var buf bytes.Buffer
		if body != nil {
			_ = json.NewEncoder(&buf).Encode(body)
		}
		req := httptest.NewRequest(method, path, &buf)
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)
		var out map[string]any
		_ = json.Unmarshal(w.Body.Bytes(), &out)
		return w.Code, out
	}

	code, plan := do("POST", "/api/finance/collection/plans",
		map[string]any{"name": "待改计划", "customer_id": 2, "total_amount": 50000})
	if code != http.StatusCreated {
		t.Fatalf("create: %d %v", code, plan)
	}
	planID := uint64(plan["id"].(float64))

	// PUT 更新名称 + 总额
	code, _ = do("PUT", fmt.Sprintf("/api/finance/collection/plans/%d", planID),
		map[string]any{"name": "已改名", "total_amount": 88000})
	if code != http.StatusOK {
		t.Fatalf("update: %d", code)
	}
	var p collection.CollectionPlan
	db.First(&p, planID)
	if p.Name != "已改名" || !p.TotalAmount.Equal(decimal.RequireFromString("88000")) {
		t.Errorf("更新后 name=%s total=%s,期望 已改名/88000", p.Name, p.TotalAmount)
	}

	// DELETE 软删 → 再 GET 应 404
	if code, _ = do("DELETE", fmt.Sprintf("/api/finance/collection/plans/%d", planID), nil); code != http.StatusNoContent {
		t.Fatalf("delete: %d,期望 204", code)
	}
	if code, _ = do("GET", fmt.Sprintf("/api/finance/collection/plans/%d", planID), nil); code != http.StatusNotFound {
		t.Errorf("软删后 GET 应 404,得 %d", code)
	}
}
