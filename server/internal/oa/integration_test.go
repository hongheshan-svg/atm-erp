//go:build integration

package oa_test

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/atm-erp/server/internal/oa"
	"github.com/atm-erp/server/internal/testutil"
	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
)

const dsn = "host=127.0.0.1 port=55517 user=u password=p dbname=d sslmode=disable TimeZone=Asia/Shanghai"

// setup 起测试引擎 + 迁移 OA 全部主模型,返回引擎与 DB。
func setup(t *testing.T) (*gin.Engine, *gorm.DB) {
	t.Helper()
	db := testutil.OpenDB(t, dsn,
		&oa.Vehicle{},
		&oa.Asset{},
		&oa.Archive{},
		&oa.Announcement{},
	)
	r, api := testutil.NewAPIEngine()
	oa.Routes(api, db, testutil.AllowAll)
	return r, db
}

// do 执行一次请求并返回 recorder。
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

// idOf 从创建响应里提取 id。
func idOf(t *testing.T, w *httptest.ResponseRecorder) uint64 {
	t.Helper()
	var resp struct {
		ID uint64 `json:"id"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("解析创建响应失败: %v, body=%s", err, w.Body.String())
	}
	if resp.ID == 0 {
		t.Fatalf("创建响应缺少 id: body=%s", w.Body.String())
	}
	return resp.ID
}

func assertStatus(t *testing.T, w *httptest.ResponseRecorder, want int, what string) {
	t.Helper()
	if w.Code != want {
		t.Fatalf("%s: 期望 %d, 实际 %d, body=%s", what, want, w.Code, w.Body.String())
	}
}

func TestIntegrationVehicleCRUD(t *testing.T) {
	r, _ := setup(t)

	// 列表
	assertStatus(t, do(t, r, http.MethodGet, "/api/oa/vehicles", nil), http.StatusOK, "vehicle list")

	// 创建
	w := do(t, r, http.MethodPost, "/api/oa/vehicles", map[string]any{
		"plate_number": "沪A12345",
		"brand":        "丰田",
		"model":        "凯美瑞",
	})
	assertStatus(t, w, http.StatusCreated, "vehicle create")
	id := idOf(t, w)

	// 详情
	assertStatus(t, do(t, r, http.MethodGet, fmt.Sprintf("/api/oa/vehicles/%d", id), nil), http.StatusOK, "vehicle retrieve")

	// 更新
	assertStatus(t, do(t, r, http.MethodPut, fmt.Sprintf("/api/oa/vehicles/%d", id), map[string]any{
		"color": "白色",
	}), http.StatusOK, "vehicle update")

	// 自定义动作
	assertStatus(t, do(t, r, http.MethodPost, fmt.Sprintf("/api/oa/vehicles/%d/update_mileage", id), map[string]any{
		"mileage": 1000,
	}), http.StatusOK, "vehicle update_mileage")

	// 删除
	assertStatus(t, do(t, r, http.MethodDelete, fmt.Sprintf("/api/oa/vehicles/%d", id), nil), http.StatusNoContent, "vehicle delete")
}

func TestIntegrationAssetCRUD(t *testing.T) {
	r, _ := setup(t)

	assertStatus(t, do(t, r, http.MethodGet, "/api/oa/assets", nil), http.StatusOK, "asset list")

	w := do(t, r, http.MethodPost, "/api/oa/assets", map[string]any{
		"name":           "笔记本电脑",
		"purchase_price": 8000,
	})
	assertStatus(t, w, http.StatusCreated, "asset create")
	id := idOf(t, w)

	assertStatus(t, do(t, r, http.MethodGet, fmt.Sprintf("/api/oa/assets/%d", id), nil), http.StatusOK, "asset retrieve")
	assertStatus(t, do(t, r, http.MethodPut, fmt.Sprintf("/api/oa/assets/%d", id), map[string]any{
		"location": "三楼",
	}), http.StatusOK, "asset update")
	assertStatus(t, do(t, r, http.MethodPost, fmt.Sprintf("/api/oa/assets/%d/assign", id), map[string]any{
		"user_id": 1,
	}), http.StatusOK, "asset assign")
	assertStatus(t, do(t, r, http.MethodPost, fmt.Sprintf("/api/oa/assets/%d/reclaim", id), nil), http.StatusOK, "asset reclaim")
	assertStatus(t, do(t, r, http.MethodPost, fmt.Sprintf("/api/oa/assets/%d/scrap", id), nil), http.StatusOK, "asset scrap")
	assertStatus(t, do(t, r, http.MethodDelete, fmt.Sprintf("/api/oa/assets/%d", id), nil), http.StatusNoContent, "asset delete")
}

func TestIntegrationArchiveCRUD(t *testing.T) {
	r, _ := setup(t)

	assertStatus(t, do(t, r, http.MethodGet, "/api/oa/archives", nil), http.StatusOK, "archive list")

	w := do(t, r, http.MethodPost, "/api/oa/archives", map[string]any{
		"title": "合同档案",
	})
	assertStatus(t, w, http.StatusCreated, "archive create")
	id := idOf(t, w)

	assertStatus(t, do(t, r, http.MethodGet, fmt.Sprintf("/api/oa/archives/%d", id), nil), http.StatusOK, "archive retrieve")
	assertStatus(t, do(t, r, http.MethodPut, fmt.Sprintf("/api/oa/archives/%d", id), map[string]any{
		"abstract": "重要合同",
	}), http.StatusOK, "archive update")
	assertStatus(t, do(t, r, http.MethodPost, fmt.Sprintf("/api/oa/archives/%d/archive", id), nil), http.StatusOK, "archive archive")
	assertStatus(t, do(t, r, http.MethodDelete, fmt.Sprintf("/api/oa/archives/%d", id), nil), http.StatusNoContent, "archive delete")
}

func TestIntegrationAnnouncementCRUD(t *testing.T) {
	r, _ := setup(t)

	assertStatus(t, do(t, r, http.MethodGet, "/api/oa/announcements", nil), http.StatusOK, "announcement list")

	w := do(t, r, http.MethodPost, "/api/oa/announcements", map[string]any{
		"title":   "系统升级通知",
		"content": "本周末系统升级",
	})
	assertStatus(t, w, http.StatusCreated, "announcement create")
	id := idOf(t, w)

	assertStatus(t, do(t, r, http.MethodGet, fmt.Sprintf("/api/oa/announcements/%d", id), nil), http.StatusOK, "announcement retrieve")
	assertStatus(t, do(t, r, http.MethodPut, fmt.Sprintf("/api/oa/announcements/%d", id), map[string]any{
		"summary": "升级摘要",
	}), http.StatusOK, "announcement update")
	assertStatus(t, do(t, r, http.MethodPost, fmt.Sprintf("/api/oa/announcements/%d/publish", id), nil), http.StatusOK, "announcement publish")
	assertStatus(t, do(t, r, http.MethodPost, fmt.Sprintf("/api/oa/announcements/%d/withdraw", id), nil), http.StatusOK, "announcement withdraw")
	assertStatus(t, do(t, r, http.MethodDelete, fmt.Sprintf("/api/oa/announcements/%d", id), nil), http.StatusNoContent, "announcement delete")
}
