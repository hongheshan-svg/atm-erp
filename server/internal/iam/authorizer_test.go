package iam

import "testing"

func TestHasPermission(t *testing.T) {
	perms := []string{"purchase:order", "masterdata:item:view"}
	cases := []struct {
		code string
		want bool
	}{
		{"purchase:order", true},
		{"purchase:order:create", true}, // 父码覆盖子树
		{"purchase", false},             // 子码不反向覆盖父码
		{"masterdata:item:view", true},
		{"masterdata:item:delete", false},
		{"sales:order", false},
	}
	for _, c := range cases {
		if got := HasPermission(perms, c.code); got != c.want {
			t.Errorf("HasPermission(%q)=%v want %v", c.code, got, c.want)
		}
	}
	if !HasPermission([]string{"*"}, "anything:at:all") {
		t.Error("通配 * 应覆盖一切")
	}
}

func TestResolveFailClosed(t *testing.T) {
	u := &AuthUser{ID: 1, DataScopes: map[string]string{}}
	if got := u.Resolve("masterdata"); got != ScopeSelf {
		t.Errorf("未配置数据范围应 fail-closed 到 self,得到 %q", got)
	}
	su := &AuthUser{ID: 1, IsSuperuser: true}
	if got := su.Resolve("masterdata"); got != ScopeAll {
		t.Errorf("超管应为 all,得到 %q", got)
	}
}
