//go:build integration

package workflow_test

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/atm-erp/server/internal/testutil"
	"github.com/atm-erp/server/internal/workflow"
)

const dsn = "host=127.0.0.1 port=55518 user=u password=p dbname=d sslmode=disable TimeZone=Asia/Shanghai"

// setup 起测试引擎 + 迁移本模块四模型 + 注册路由。
func setup(t *testing.T) *http.ServeMux {
	t.Helper()
	db := testutil.OpenDB(t, dsn,
		&workflow.WorkflowDefinition{},
		&workflow.WorkflowStep{},
		&workflow.WorkflowInstance{},
		&workflow.WorkflowTask{},
	)
	r, api := testutil.NewAPIEngine()
	workflow.Routes(api, db, testutil.AllowAll)
	mux := http.NewServeMux()
	mux.Handle("/", r)
	return mux
}

// do 发一次请求并返回 ResponseRecorder。
func do(t *testing.T, h http.Handler, method, path string, body any) *httptest.ResponseRecorder {
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
	h.ServeHTTP(w, req)
	return w
}

func is2xx(code int) bool { return code >= 200 && code < 300 }

// TestIntegrationListEndpoints 所有列表/聚合 GET 端点返回 200。
func TestIntegrationListEndpoints(t *testing.T) {
	h := setup(t)
	gets := []string{
		"/api/workflow/definitions",
		"/api/workflow/steps",
		"/api/workflow/instances",
		"/api/workflow/instances/my_submitted",
		"/api/workflow/tasks",
		"/api/workflow/tasks/my_pending",
		"/api/workflow/tasks/pending_count",
	}
	for _, p := range gets {
		w := do(t, h, http.MethodGet, p, nil)
		if w.Code != http.StatusOK {
			t.Errorf("GET %s => %d, want 200; body=%s", p, w.Code, w.Body.String())
		}
	}
	// history 需要 query 参数。
	w := do(t, h, http.MethodGet, "/api/workflow/instances/history?business_type=purchase_order&business_id=1", nil)
	if w.Code != http.StatusOK {
		t.Errorf("GET instances/history => %d, want 200; body=%s", w.Code, w.Body.String())
	}
}

// TestIntegrationDefinitionCRUD 流程定义 + 步骤的 POST/GET/PUT/DELETE 全链路。
func TestIntegrationDefinitionCRUD(t *testing.T) {
	h := setup(t)

	// 创建流程定义。
	w := do(t, h, http.MethodPost, "/api/workflow/definitions", map[string]any{
		"name":          "采购审批",
		"code":          "po_approval_it",
		"business_type": "purchase_order",
		"description":   "采购单审批流程",
	})
	if !is2xx(w.Code) {
		t.Fatalf("POST definitions => %d, want 2xx; body=%s", w.Code, w.Body.String())
	}
	var def workflow.WorkflowDefinition
	if err := json.Unmarshal(w.Body.Bytes(), &def); err != nil {
		t.Fatalf("decode definition: %v", err)
	}
	if def.ID == 0 {
		t.Fatalf("created definition has no id; body=%s", w.Body.String())
	}

	// 详情。
	w = do(t, h, http.MethodGet, "/api/workflow/definitions/"+itoa(def.ID), nil)
	if w.Code != http.StatusOK {
		t.Errorf("GET definition/:id => %d, want 200; body=%s", w.Code, w.Body.String())
	}

	// 更新。
	newName := "采购审批V2"
	w = do(t, h, http.MethodPut, "/api/workflow/definitions/"+itoa(def.ID), map[string]any{"name": newName})
	if w.Code != http.StatusOK {
		t.Errorf("PUT definition => %d, want 200; body=%s", w.Code, w.Body.String())
	}

	// 创建步骤(挂到该流程)。
	w = do(t, h, http.MethodPost, "/api/workflow/steps", map[string]any{
		"workflow":      def.ID,
		"step_order":    1,
		"name":          "经理审批",
		"approver_type": "USER",
		"approver_user": 1,
	})
	if !is2xx(w.Code) {
		t.Fatalf("POST steps => %d, want 2xx; body=%s", w.Code, w.Body.String())
	}
	var step workflow.WorkflowStep
	if err := json.Unmarshal(w.Body.Bytes(), &step); err != nil {
		t.Fatalf("decode step: %v", err)
	}
	if step.ID == 0 {
		t.Fatalf("created step has no id; body=%s", w.Body.String())
	}

	// 步骤详情。
	w = do(t, h, http.MethodGet, "/api/workflow/steps/"+itoa(step.ID), nil)
	if w.Code != http.StatusOK {
		t.Errorf("GET step/:id => %d, want 200; body=%s", w.Code, w.Body.String())
	}

	// 步骤更新。
	w = do(t, h, http.MethodPut, "/api/workflow/steps/"+itoa(step.ID), map[string]any{"name": "总监审批"})
	if w.Code != http.StatusOK {
		t.Errorf("PUT step => %d, want 200; body=%s", w.Code, w.Body.String())
	}

	// 删除步骤。
	w = do(t, h, http.MethodDelete, "/api/workflow/steps/"+itoa(step.ID), nil)
	if !is2xx(w.Code) {
		t.Errorf("DELETE step => %d, want 2xx; body=%s", w.Code, w.Body.String())
	}

	// 删除流程定义。
	w = do(t, h, http.MethodDelete, "/api/workflow/definitions/"+itoa(def.ID), nil)
	if !is2xx(w.Code) {
		t.Errorf("DELETE definition => %d, want 2xx; body=%s", w.Code, w.Body.String())
	}
}

// TestIntegrationInstanceLifecycle 启动实例 -> 审批走完 -> 列表可见。
func TestIntegrationInstanceLifecycle(t *testing.T) {
	h := setup(t)

	// 准备:一个启用流程 + 一个 USER 步骤(审批人=超管 uid 1)。
	w := do(t, h, http.MethodPost, "/api/workflow/definitions", map[string]any{
		"name":          "请款审批",
		"code":          "expense_approval_lc",
		"business_type": "expense",
		"is_active":     true,
	})
	if !is2xx(w.Code) {
		t.Fatalf("POST definitions => %d; body=%s", w.Code, w.Body.String())
	}
	var def workflow.WorkflowDefinition
	_ = json.Unmarshal(w.Body.Bytes(), &def)

	w = do(t, h, http.MethodPost, "/api/workflow/steps", map[string]any{
		"workflow":      def.ID,
		"step_order":    1,
		"name":          "财务审批",
		"approver_type": "USER",
		"approver_user": 1,
	})
	if !is2xx(w.Code) {
		t.Fatalf("POST steps => %d; body=%s", w.Code, w.Body.String())
	}

	// 启动实例(主实体 POST)。
	w = do(t, h, http.MethodPost, "/api/workflow/instances", map[string]any{
		"business_type": "expense",
		"business_id":   1001,
		"business_no":   "EXP-2026-0001",
	})
	if !is2xx(w.Code) {
		t.Fatalf("POST instances => %d, want 2xx; body=%s", w.Code, w.Body.String())
	}

	// 实例列表应可见。
	w = do(t, h, http.MethodGet, "/api/workflow/instances?business_type=expense", nil)
	if w.Code != http.StatusOK {
		t.Errorf("GET instances filtered => %d; body=%s", w.Code, w.Body.String())
	}

	// 任务列表(超管即审批人,应有一条待办)。
	w = do(t, h, http.MethodGet, "/api/workflow/tasks/my_pending", nil)
	if w.Code != http.StatusOK {
		t.Errorf("GET tasks/my_pending => %d; body=%s", w.Code, w.Body.String())
	}
}

// itoa 把 uint64 转十进制串(避免引 strconv 到测试顶层)。
func itoa(n uint64) string {
	if n == 0 {
		return "0"
	}
	var buf [20]byte
	i := len(buf)
	for n > 0 {
		i--
		buf[i] = byte('0' + n%10)
		n /= 10
	}
	return string(buf[i:])
}
