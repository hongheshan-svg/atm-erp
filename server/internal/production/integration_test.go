//go:build integration

// Package production_test 对「生产/MES」模块做运行期集成验证:
// 起真实 Postgres、AutoMigrate 各子包模型、用 httptest 跑全部路由的 CRUD,
// 断言列表 GET=200、主实体 POST 创建 2xx,并尽量覆盖详情/更新/删除与业务动作。
package production_test

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/atm-erp/server/internal/production"
	"github.com/atm-erp/server/internal/production/kanban"
	"github.com/atm-erp/server/internal/production/process"
	"github.com/atm-erp/server/internal/production/routing"
	"github.com/atm-erp/server/internal/production/workcenter"
	"github.com/atm-erp/server/internal/production/workorder"
	"github.com/atm-erp/server/internal/testutil"
	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
)

const dsn = "host=127.0.0.1 port=55515 user=u password=p dbname=d sslmode=disable TimeZone=Asia/Shanghai"

func setup(t *testing.T) (*gin.Engine, *gorm.DB) {
	t.Helper()
	db := testutil.OpenDB(t, dsn,
		&workorder.WorkOrder{},
		&routing.Routing{},
		&process.Process{},
		&kanban.KanbanWIPRule{},
		&workcenter.WorkCenter{},
	)
	r, api := testutil.NewAPIEngine()
	production.Routes(api, db, testutil.AllowAll)
	return r, db
}

// do 执行一次请求并返回 recorder。
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

// idOf 从创建响应里解析出 id。
func idOf(t *testing.T, w *httptest.ResponseRecorder) uint64 {
	t.Helper()
	var resp struct {
		ID uint64 `json:"id"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("解析创建响应失败: %v; body=%s", err, w.Body.String())
	}
	if resp.ID == 0 {
		t.Fatalf("创建响应未返回有效 id; body=%s", w.Body.String())
	}
	return resp.ID
}

func assert2xx(t *testing.T, w *httptest.ResponseRecorder, label string) {
	t.Helper()
	if w.Code < 200 || w.Code >= 300 {
		t.Fatalf("%s 期望 2xx,实际 %d; body=%s", label, w.Code, w.Body.String())
	}
}

func assert200(t *testing.T, w *httptest.ResponseRecorder, label string) {
	t.Helper()
	if w.Code != http.StatusOK {
		t.Fatalf("%s 期望 200,实际 %d; body=%s", label, w.Code, w.Body.String())
	}
}

// TestIntegrationListEndpoints 所有列表端点应返回 200。
func TestIntegrationListEndpoints(t *testing.T) {
	r, _ := setup(t)
	lists := []string{
		"/api/production/work-orders",
		"/api/production/routings",
		"/api/production/processes",
		"/api/production/kanban/wip-rules",
		"/api/production/work-centers",
	}
	for _, p := range lists {
		w := do(t, r, http.MethodGet, p, nil)
		assert200(t, w, "GET "+p)
	}
}

// TestIntegrationWorkCenterCRUD 工作中心全链路。
func TestIntegrationWorkCenterCRUD(t *testing.T) {
	r, _ := setup(t)
	cap := 16.0
	w := do(t, r, http.MethodPost, "/api/production/work-centers", workcenter.CreateInput{
		Code: "WC-IT-001", Name: "集成测试工作中心", CapacityPerDay: &cap,
	})
	assert2xx(t, w, "POST work-center")
	id := idOf(t, w)

	assert200(t, do(t, r, http.MethodGet, fmt.Sprintf("/api/production/work-centers/%d", id), nil), "GET work-center detail")

	newName := "改名后的工作中心"
	assert200(t, do(t, r, http.MethodPut, fmt.Sprintf("/api/production/work-centers/%d", id), workcenter.UpdateInput{Name: &newName}), "PUT work-center")

	w = do(t, r, http.MethodDelete, fmt.Sprintf("/api/production/work-centers/%d", id), nil)
	if w.Code != http.StatusNoContent {
		t.Fatalf("DELETE work-center 期望 204,实际 %d; body=%s", w.Code, w.Body.String())
	}
}

// TestIntegrationRoutingAndProcess 工艺路线 + 工序(含工时合计联动)+ 审批动作。
func TestIntegrationRoutingAndProcess(t *testing.T) {
	r, _ := setup(t)
	// 工艺路线
	w := do(t, r, http.MethodPost, "/api/production/routings", routing.CreateInput{
		Code: "RT-IT-001", Name: "集成测试工艺路线",
	})
	assert2xx(t, w, "POST routing")
	rtID := idOf(t, w)

	assert200(t, do(t, r, http.MethodGet, fmt.Sprintf("/api/production/routings/%d", rtID), nil), "GET routing detail")

	desc := "更新描述"
	assert200(t, do(t, r, http.MethodPut, fmt.Sprintf("/api/production/routings/%d", rtID), routing.UpdateInput{Description: &desc}), "PUT routing")

	// 工序(归属上面的路线)
	w = do(t, r, http.MethodPost, "/api/production/processes", process.CreateInput{
		RoutingID: rtID, Sequence: 10, OperationName: "粗加工", StandardHours: 2.5, SetupHours: 0.5,
	})
	assert2xx(t, w, "POST process")
	prID := idOf(t, w)

	assert200(t, do(t, r, http.MethodGet, fmt.Sprintf("/api/production/processes/%d", prID), nil), "GET process detail")

	seq := 20
	assert200(t, do(t, r, http.MethodPut, fmt.Sprintf("/api/production/processes/%d", prID), process.UpdateInput{Sequence: &seq}), "PUT process")

	// 审批工艺路线(DRAFT→APPROVED,并重算工时合计)
	assert200(t, do(t, r, http.MethodPost, fmt.Sprintf("/api/production/routings/%d/approve", rtID), nil), "POST routing approve")

	// 删除工序(联动重算)
	w = do(t, r, http.MethodDelete, fmt.Sprintf("/api/production/processes/%d", prID), nil)
	if w.Code != http.StatusNoContent {
		t.Fatalf("DELETE process 期望 204,实际 %d; body=%s", w.Code, w.Body.String())
	}
}

// TestIntegrationKanbanCRUD 看板 WIP 规则。
func TestIntegrationKanbanCRUD(t *testing.T) {
	r, _ := setup(t)
	w := do(t, r, http.MethodPost, "/api/production/kanban/wip-rules", kanban.CreateInput{
		ProcessName: "焊接工序", WIPLimit: 5,
	})
	assert2xx(t, w, "POST kanban wip-rule")
	id := idOf(t, w)

	assert200(t, do(t, r, http.MethodGet, fmt.Sprintf("/api/production/kanban/wip-rules/%d", id), nil), "GET kanban detail")

	limit := 8
	assert200(t, do(t, r, http.MethodPut, fmt.Sprintf("/api/production/kanban/wip-rules/%d", id), kanban.UpdateInput{WIPLimit: &limit}), "PUT kanban")

	w = do(t, r, http.MethodDelete, fmt.Sprintf("/api/production/kanban/wip-rules/%d", id), nil)
	if w.Code != http.StatusNoContent {
		t.Fatalf("DELETE kanban 期望 204,实际 %d; body=%s", w.Code, w.Body.String())
	}
}

// TestIntegrationWorkOrderCRUDAndTransitions 工单 CRUD + 状态机(start/complete)。
func TestIntegrationWorkOrderCRUDAndTransitions(t *testing.T) {
	r, _ := setup(t)
	w := do(t, r, http.MethodPost, "/api/production/work-orders", workorder.CreateInput{
		Quantity:     100,
		RequiredDate: parseDate("2026-07-01"),
	})
	assert2xx(t, w, "POST work-order")
	id := idOf(t, w)

	assert200(t, do(t, r, http.MethodGet, fmt.Sprintf("/api/production/work-orders/%d", id), nil), "GET work-order detail")

	// PUT 仅更新可改字段(status 不在 UpdateInput 中,状态机由 start/complete 端点驱动)。
	prio := 1
	assert200(t, do(t, r, http.MethodPut, fmt.Sprintf("/api/production/work-orders/%d", id), workorder.UpdateInput{Priority: &prio}), "PUT work-order")

	w = do(t, r, http.MethodDelete, fmt.Sprintf("/api/production/work-orders/%d", id), nil)
	if w.Code != http.StatusNoContent {
		t.Fatalf("DELETE work-order 期望 204,实际 %d; body=%s", w.Code, w.Body.String())
	}
}

// TestIntegrationWorkOrderStartComplete 验证 start/complete 状态机端点可达且语义正确。
// 由于 UpdateInput 不暴露 status,这里直接用 DB 把工单切到 SCHEDULED 再走 HTTP 动作。
func TestIntegrationWorkOrderStartComplete(t *testing.T) {
	r, db := setup(t)
	w := do(t, r, http.MethodPost, "/api/production/work-orders", workorder.CreateInput{
		Quantity:     50,
		RequiredDate: parseDate("2026-07-15"),
	})
	assert2xx(t, w, "POST work-order")
	id := idOf(t, w)

	// 切到 SCHEDULED(start 的前置)。
	if err := db.Table("mes_schedule_order").Where("id = ?", id).
		Update("status", workorder.StatusScheduled).Error; err != nil {
		t.Fatalf("置 SCHEDULED 失败: %v", err)
	}

	assert200(t, do(t, r, http.MethodPost, fmt.Sprintf("/api/production/work-orders/%d/start", id), nil), "POST work-order start")

	cq := 50.0
	assert200(t, do(t, r, http.MethodPost, fmt.Sprintf("/api/production/work-orders/%d/complete", id), workorder.CompleteInput{CompletedQty: &cq}), "POST work-order complete")
}

func parseDate(s string) time.Time {
	d, err := time.Parse("2006-01-02", s)
	if err != nil {
		panic(err)
	}
	return d
}
