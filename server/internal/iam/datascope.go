package iam

import "gorm.io/gorm"

// DataScope 数据范围(由宽到窄),对齐 Django apps.core 数据范围。
type DataScope string

const (
	ScopeAll      DataScope = "all"
	ScopeDeptTree DataScope = "dept_tree"
	ScopeDept     DataScope = "dept"
	ScopeSelf     DataScope = "self"
	ScopeCustom   DataScope = "custom"
)

// Resolve 取用户在某模块多角色中“最宽”的数据范围;fail-closed 默认 self(超管 all)。
func (u *AuthUser) Resolve(module string) DataScope {
	if u == nil {
		return ScopeSelf
	}
	if u.IsSuperuser {
		return ScopeAll
	}
	if s, ok := u.DataScopes[module]; ok && s != "" {
		return DataScope(s)
	}
	return ScopeSelf
}

// ApplyScope 把数据范围落到查询上;ownerCol 为归属人列(如 created_by)。
// dept / dept_tree 维度在脚手架阶段先 fail-closed 到 self,待 IAM 部门树落地后补全(逐条回归)。
func ApplyScope(q *gorm.DB, u *AuthUser, module, ownerCol string) *gorm.DB {
	switch u.Resolve(module) {
	case ScopeAll:
		return q
	case ScopeSelf:
		return q.Where(ownerCol+" = ?", u.ID)
	case ScopeDept, ScopeDeptTree:
		// TODO(iam): 接入部门树后按 dept_id IN (...) 过滤;当前 fail-closed 到 self。
		return q.Where(ownerCol+" = ?", u.ID)
	default:
		return q.Where(ownerCol+" = ?", u.ID)
	}
}
