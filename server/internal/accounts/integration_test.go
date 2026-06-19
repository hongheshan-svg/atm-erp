//go:build integration

package accounts_test

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/atm-erp/server/internal/accounts"
	"github.com/atm-erp/server/internal/testutil"
)

const dsn = "host=127.0.0.1 port=55519 user=u password=p dbname=d sslmode=disable TimeZone=Asia/Shanghai"

// setup 起引擎、连库迁移本模块主模型并装配 accounts 路由。
func setup(t *testing.T) *http.ServeMux {
	t.Helper()
	db := testutil.OpenDB(t, dsn,
		&accounts.Department{},
		&accounts.Role{},
		&accounts.User{},
		&accounts.Permission{},
		&accounts.RolePermission{},
		&accounts.DataScopeRule{},
	)
	r, api := testutil.NewAPIEngine()
	accounts.Routes(api, db, testutil.AllowAll)
	mux := http.NewServeMux()
	mux.Handle("/", r)
	return mux
}

// do 发起请求并返回响应录制器。
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

// must2xx 断言 2xx,否则打印 body。
func must2xx(t *testing.T, w *httptest.ResponseRecorder, label string) {
	t.Helper()
	if w.Code < 200 || w.Code >= 300 {
		t.Fatalf("%s: 期望 2xx, 实得 %d, body=%s", label, w.Code, w.Body.String())
	}
}

// idOf 从 JSON 响应中取 id。
func idOf(t *testing.T, w *httptest.ResponseRecorder) uint64 {
	t.Helper()
	var m map[string]any
	if err := json.Unmarshal(w.Body.Bytes(), &m); err != nil {
		t.Fatalf("unmarshal id: %v body=%s", err, w.Body.String())
	}
	idf, ok := m["id"].(float64)
	if !ok {
		t.Fatalf("响应缺少 id: body=%s", w.Body.String())
	}
	return uint64(idf)
}

func TestIntegrationLists(t *testing.T) {
	h := setup(t)
	for _, p := range []string{
		"/api/accounts/departments",
		"/api/accounts/roles",
		"/api/accounts/users",
		"/api/accounts/permissions",
	} {
		w := do(t, h, http.MethodGet, p, nil)
		if w.Code != http.StatusOK {
			t.Fatalf("GET %s: 期望 200, 实得 %d, body=%s", p, w.Code, w.Body.String())
		}
	}
}

func TestIntegrationDepartmentCRUD(t *testing.T) {
	h := setup(t)
	code := fmt.Sprintf("DEPT-%d", randSuffix())
	w := do(t, h, http.MethodPost, "/api/accounts/departments", map[string]any{
		"name": "研发部", "code": code, "sort_order": 1,
	})
	must2xx(t, w, "create dept")
	id := idOf(t, w)

	must2xx(t, do(t, h, http.MethodGet, fmt.Sprintf("/api/accounts/departments/%d", id), nil), "get dept")

	wn := "研发中心"
	must2xx(t, do(t, h, http.MethodPut, fmt.Sprintf("/api/accounts/departments/%d", id), map[string]any{
		"name": wn,
	}), "update dept")

	if w := do(t, h, http.MethodDelete, fmt.Sprintf("/api/accounts/departments/%d", id), nil); w.Code != http.StatusNoContent {
		t.Fatalf("delete dept: 期望 204, 实得 %d, body=%s", w.Code, w.Body.String())
	}
}

func TestIntegrationRoleCRUD(t *testing.T) {
	h := setup(t)
	code := fmt.Sprintf("ROLE-%d", randSuffix())
	w := do(t, h, http.MethodPost, "/api/accounts/roles", map[string]any{
		"name": "测试角色-" + code, "code": code,
	})
	must2xx(t, w, "create role")
	id := idOf(t, w)

	must2xx(t, do(t, h, http.MethodGet, fmt.Sprintf("/api/accounts/roles/%d", id), nil), "get role")

	desc := "已更新"
	must2xx(t, do(t, h, http.MethodPut, fmt.Sprintf("/api/accounts/roles/%d", id), map[string]any{
		"description": desc,
	}), "update role")

	if w := do(t, h, http.MethodDelete, fmt.Sprintf("/api/accounts/roles/%d", id), nil); w.Code != http.StatusNoContent {
		t.Fatalf("delete role: 期望 204, 实得 %d, body=%s", w.Code, w.Body.String())
	}
}

func TestIntegrationUserCRUD(t *testing.T) {
	h := setup(t)
	uname := fmt.Sprintf("user_%d", randSuffix())
	w := do(t, h, http.MethodPost, "/api/accounts/users", map[string]any{
		"username": uname, "password": "secret123", "email": uname + "@example.com",
	})
	must2xx(t, w, "create user")
	id := idOf(t, w)

	must2xx(t, do(t, h, http.MethodGet, fmt.Sprintf("/api/accounts/users/%d", id), nil), "get user")

	phone := "13800000000"
	must2xx(t, do(t, h, http.MethodPut, fmt.Sprintf("/api/accounts/users/%d", id), map[string]any{
		"phone": phone,
	}), "update user")

	if w := do(t, h, http.MethodDelete, fmt.Sprintf("/api/accounts/users/%d", id), nil); w.Code != http.StatusNoContent {
		t.Fatalf("delete user: 期望 204, 实得 %d, body=%s", w.Code, w.Body.String())
	}
}

func TestIntegrationPermissionCRUD(t *testing.T) {
	h := setup(t)
	code := fmt.Sprintf("perm.%d", randSuffix())
	w := do(t, h, http.MethodPost, "/api/accounts/permissions", map[string]any{
		"code": code, "name": "测试权限", "type": "menu",
	})
	must2xx(t, w, "create permission")
	id := idOf(t, w)

	must2xx(t, do(t, h, http.MethodGet, fmt.Sprintf("/api/accounts/permissions/%d", id), nil), "get permission")

	nm := "测试权限-改"
	must2xx(t, do(t, h, http.MethodPut, fmt.Sprintf("/api/accounts/permissions/%d", id), map[string]any{
		"name": nm,
	}), "update permission")

	if w := do(t, h, http.MethodDelete, fmt.Sprintf("/api/accounts/permissions/%d", id), nil); w.Code != http.StatusNoContent {
		t.Fatalf("delete permission: 期望 204, 实得 %d, body=%s", w.Code, w.Body.String())
	}
}

var suffixCounter uint64

// randSuffix 用单调计数器生成唯一后缀,避免跨用例唯一约束冲突。
func randSuffix() uint64 {
	suffixCounter++
	return suffixCounter
}
