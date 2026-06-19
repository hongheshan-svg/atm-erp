//go:build integration

package projects_test

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/atm-erp/server/internal/projects"
	"github.com/atm-erp/server/internal/testutil"
	"github.com/gin-gonic/gin"
)

const dsn = "host=127.0.0.1 port=55514 user=u password=p dbname=d sslmode=disable TimeZone=Asia/Shanghai"

func setup(t *testing.T) (*gin.Engine, func()) {
	t.Helper()
	db := testutil.OpenDB(t, dsn,
		&projects.Project{},
		&projects.ProjectTask{},
		&projects.ProjectBOM{},
		&projects.Drawing{},
		&projects.DrawingChangeNotice{},
	)
	// 清空本模块表,保证用例可重复运行(软删除会让唯一索引上的 code 残留,
	// 跨次运行复用固定 code 会撞 idx_project_code,故用 TRUNCATE 物理清表)。
	for _, tbl := range []string{
		"project", "project_task", "project_bom", "project_drawing", "project_drawing_change_notice",
	} {
		db.Exec("TRUNCATE TABLE " + tbl + " RESTART IDENTITY CASCADE")
	}
	r, api := testutil.NewAPIEngine()
	projects.Routes(api, db, testutil.AllowAll)
	return r, func() {}
}

// doJSON 发起一个带 JSON body 的请求,返回 recorder。
func doJSON(t *testing.T, r *gin.Engine, method, path string, body any) *httptest.ResponseRecorder {
	t.Helper()
	var buf bytes.Buffer
	if body != nil {
		if err := json.NewEncoder(&buf).Encode(body); err != nil {
			t.Fatalf("编码 body 失败: %v", err)
		}
	}
	req := httptest.NewRequest(method, path, &buf)
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

// extractID 从创建响应里取出 id(httpx 信封 {code,message,data}）。
func extractID(t *testing.T, body []byte) uint64 {
	t.Helper()
	var env struct {
		Data struct {
			ID uint64 `json:"id"`
		} `json:"data"`
	}
	if err := json.Unmarshal(body, &env); err != nil {
		t.Fatalf("解析创建响应失败: %v; body=%s", err, body)
	}
	if env.Data.ID == 0 {
		// 兼容裸对象返回
		var raw struct {
			ID uint64 `json:"id"`
		}
		_ = json.Unmarshal(body, &raw)
		return raw.ID
	}
	return env.Data.ID
}

func assertStatus(t *testing.T, w *httptest.ResponseRecorder, want int, what string) {
	t.Helper()
	if w.Code != want {
		t.Fatalf("%s: 期望 %d, 实得 %d; body=%s", what, want, w.Code, w.Body.String())
	}
}

func is2xx(code int) bool { return code >= 200 && code < 300 }

func TestIntegrationListEndpoints(t *testing.T) {
	r, cleanup := setup(t)
	defer cleanup()

	lists := []string{
		"/api/projects/projects",
		"/api/projects/tasks",
		"/api/projects/bom",
		"/api/projects/drawings",
	}
	for _, p := range lists {
		w := doJSON(t, r, http.MethodGet, p, nil)
		assertStatus(t, w, http.StatusOK, "GET "+p)
	}
}

func TestIntegrationProjectCRUD(t *testing.T) {
	r, cleanup := setup(t)
	defer cleanup()

	// Create —— 显式给唯一 code,避免依赖回退编号生成器在跨用例间的计数器碰撞。
	w := doJSON(t, r, http.MethodPost, "/api/projects/projects", map[string]any{
		"name":        "集成测试项目",
		"code":        "IT-PRJ-CRUD",
		"customer_id": 1,
		"manager_id":  1,
	})
	if !is2xx(w.Code) {
		t.Fatalf("POST project 期望 2xx, 实得 %d; body=%s", w.Code, w.Body.String())
	}
	id := extractID(t, w.Body.Bytes())
	if id == 0 {
		t.Fatalf("创建项目未返回 id; body=%s", w.Body.String())
	}

	// Retrieve
	w = doJSON(t, r, http.MethodGet, fmt.Sprintf("/api/projects/projects/%d", id), nil)
	assertStatus(t, w, http.StatusOK, "GET project detail")

	// Update
	w = doJSON(t, r, http.MethodPut, fmt.Sprintf("/api/projects/projects/%d", id), map[string]any{
		"name": "改名后的项目",
	})
	assertStatus(t, w, http.StatusOK, "PUT project")

	// change_status: DRAFT -> PLANNING
	w = doJSON(t, r, http.MethodPost, fmt.Sprintf("/api/projects/projects/%d/change_status", id), map[string]any{
		"status": "PLANNING",
	})
	assertStatus(t, w, http.StatusOK, "POST change_status")

	// Delete
	w = doJSON(t, r, http.MethodDelete, fmt.Sprintf("/api/projects/projects/%d", id), nil)
	if w.Code != http.StatusNoContent && w.Code != http.StatusOK {
		t.Fatalf("DELETE project 期望 204/200, 实得 %d; body=%s", w.Code, w.Body.String())
	}
}

func TestIntegrationTaskCRUD(t *testing.T) {
	r, cleanup := setup(t)
	defer cleanup()

	// 需要一个 project 作为父
	w := doJSON(t, r, http.MethodPost, "/api/projects/projects", map[string]any{
		"name": "任务父项目", "code": "IT-PRJ-TASK", "customer_id": 1, "manager_id": 1,
	})
	if !is2xx(w.Code) {
		t.Fatalf("POST project(for task) 失败: %d; %s", w.Code, w.Body.String())
	}
	pid := extractID(t, w.Body.Bytes())

	// Create task
	w = doJSON(t, r, http.MethodPost, "/api/projects/tasks", map[string]any{
		"project_id": pid,
		"code":       "T001",
		"name":       "集成测试任务",
	})
	if !is2xx(w.Code) {
		t.Fatalf("POST task 期望 2xx, 实得 %d; body=%s", w.Code, w.Body.String())
	}
	tid := extractID(t, w.Body.Bytes())

	w = doJSON(t, r, http.MethodGet, fmt.Sprintf("/api/projects/tasks/%d", tid), nil)
	assertStatus(t, w, http.StatusOK, "GET task detail")

	// update_progress
	prog := 50
	w = doJSON(t, r, http.MethodPost, fmt.Sprintf("/api/projects/tasks/%d/update_progress", tid), map[string]any{
		"progress_percent": prog,
	})
	assertStatus(t, w, http.StatusOK, "POST update_progress")

	w = doJSON(t, r, http.MethodDelete, fmt.Sprintf("/api/projects/tasks/%d", tid), nil)
	if w.Code != http.StatusNoContent && w.Code != http.StatusOK {
		t.Fatalf("DELETE task 期望 204/200, 实得 %d; body=%s", w.Code, w.Body.String())
	}
}

func TestIntegrationBOMCRUD(t *testing.T) {
	r, cleanup := setup(t)
	defer cleanup()

	w := doJSON(t, r, http.MethodPost, "/api/projects/projects", map[string]any{
		"name": "BOM父项目", "code": "IT-PRJ-BOM", "customer_id": 1, "manager_id": 1,
	})
	if !is2xx(w.Code) {
		t.Fatalf("POST project(for bom) 失败: %d; %s", w.Code, w.Body.String())
	}
	pid := extractID(t, w.Body.Bytes())

	// Create BOM
	w = doJSON(t, r, http.MethodPost, "/api/projects/bom", map[string]any{
		"project_id": pid,
		"item_id":    1,
		"item_code":  "ITM-001",
	})
	if !is2xx(w.Code) {
		t.Fatalf("POST bom 期望 2xx, 实得 %d; body=%s", w.Code, w.Body.String())
	}
	bid := extractID(t, w.Body.Bytes())

	w = doJSON(t, r, http.MethodGet, fmt.Sprintf("/api/projects/bom/%d", bid), nil)
	assertStatus(t, w, http.StatusOK, "GET bom detail")

	// confirm: DRAFT -> CONFIRMED
	w = doJSON(t, r, http.MethodPost, fmt.Sprintf("/api/projects/bom/%d/confirm", bid), nil)
	assertStatus(t, w, http.StatusOK, "POST bom confirm")

	// release: CONFIRMED -> RELEASED
	w = doJSON(t, r, http.MethodPost, fmt.Sprintf("/api/projects/bom/%d/release", bid), nil)
	assertStatus(t, w, http.StatusOK, "POST bom release")

	w = doJSON(t, r, http.MethodDelete, fmt.Sprintf("/api/projects/bom/%d", bid), nil)
	if w.Code != http.StatusNoContent && w.Code != http.StatusOK {
		t.Fatalf("DELETE bom 期望 204/200, 实得 %d; body=%s", w.Code, w.Body.String())
	}
}

func TestIntegrationDrawingCRUD(t *testing.T) {
	r, cleanup := setup(t)
	defer cleanup()

	// Create drawing (drawing_no 自动生成)
	w := doJSON(t, r, http.MethodPost, "/api/projects/drawings", map[string]any{
		"name": "集成测试图纸",
	})
	if !is2xx(w.Code) {
		t.Fatalf("POST drawing 期望 2xx, 实得 %d; body=%s", w.Code, w.Body.String())
	}
	did := extractID(t, w.Body.Bytes())

	w = doJSON(t, r, http.MethodGet, fmt.Sprintf("/api/projects/drawings/%d", did), nil)
	assertStatus(t, w, http.StatusOK, "GET drawing detail")

	// 状态流转: submit_review -> approve -> release(联动建 notice)
	w = doJSON(t, r, http.MethodPost, fmt.Sprintf("/api/projects/drawings/%d/submit_review", did), nil)
	assertStatus(t, w, http.StatusOK, "POST submit_review")

	w = doJSON(t, r, http.MethodPost, fmt.Sprintf("/api/projects/drawings/%d/approve", did), nil)
	assertStatus(t, w, http.StatusOK, "POST approve")

	w = doJSON(t, r, http.MethodPost, fmt.Sprintf("/api/projects/drawings/%d/release", did), nil)
	assertStatus(t, w, http.StatusOK, "POST release")

	w = doJSON(t, r, http.MethodDelete, fmt.Sprintf("/api/projects/drawings/%d", did), nil)
	if w.Code != http.StatusNoContent && w.Code != http.StatusOK {
		t.Fatalf("DELETE drawing 期望 204/200, 实得 %d; body=%s", w.Code, w.Body.String())
	}
}
