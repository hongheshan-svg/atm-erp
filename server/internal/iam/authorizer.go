package iam

import "strings"

// HasPermission 复刻 Django 权限语义:授予的父码覆盖其整棵子树。
//
//	授予 "purchase:order"        → 覆盖 "purchase:order:create"
//	授予 "*"                      → 覆盖一切
//	授予子码不反向覆盖父码(授予 "a:b" 不覆盖 "a")
func HasPermission(perms []string, code string) bool {
	for _, p := range perms {
		if p == "*" || p == code || strings.HasPrefix(code, p+":") {
			return true
		}
	}
	return false
}

// Can 判定当前用户是否拥有某权限码(超管放行)。
func (u *AuthUser) Can(code string) bool {
	if u == nil {
		return false
	}
	if u.IsSuperuser {
		return true
	}
	return HasPermission(u.Permissions, code)
}
