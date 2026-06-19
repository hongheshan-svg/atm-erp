package accounts

import (
	"context"

	"github.com/atm-erp/server/internal/workflow"
	"gorm.io/gorm"
)

// WorkflowResolver 是 workflow.AssigneeResolver 的 IAM 实现,对齐 Django
// WorkflowService._get_step_assignee:USER/ROLE/DEPARTMENT_MANAGER/SUPERIOR 走 accounts 表;
// PROJECT_MANAGER 需业务上下文,本实现不解析(由业务 callback 提供,见 TODO)。
//
// 放在 accounts 包(持有 User/Role/Department 模型),实现 workflow 接口;
// workflow 引擎零业务 import,依赖方向为 accounts→workflow(无环)。
type WorkflowResolver struct{ db *gorm.DB }

func NewWorkflowResolver(db *gorm.DB) *WorkflowResolver { return &WorkflowResolver{db: db} }

var _ workflow.AssigneeResolver = (*WorkflowResolver)(nil)

// Resolve 解析单审批人(APPROVE/REVIEW)。兜底顺序对齐 Django:
// 具体类型 → approver_role → 末位 superuser。
func (r *WorkflowResolver) Resolve(ctx context.Context, step *workflow.WorkflowStep, inst *workflow.WorkflowInstance) (uint64, error) {
	switch step.ApproverType {
	case workflow.ApproverTypeUser:
		if step.ApproverUserID != nil {
			return *step.ApproverUserID, nil
		}
	case workflow.ApproverTypeRole:
		if id := r.firstUserWithRole(ctx, step.ApproverRoleID); id != 0 {
			return id, nil
		}
	case workflow.ApproverTypeDepartmentManager, workflow.ApproverTypeSuperior:
		if id := r.deptManager(ctx, inst.SubmitterID); id != 0 {
			return id, nil
		}
	case workflow.ApproverTypeProjectManager:
		// 需业务上下文(项目经理),由业务侧通过 callback/port 提供;引擎据 0 跳过本步。
		return 0, nil
	}
	// 兜底:approver_role 优先,再末位 superuser(对齐 Django;superuser 兜底有越权风险,见设计待定)。
	if id := r.firstUserWithRole(ctx, step.ApproverRoleID); id != 0 {
		return id, nil
	}
	return r.firstSuperuser(ctx), nil
}

// ResolveAll 解析会签(COUNTERSIGN)全部审批人:ROLE 取该角色全部在岗用户,否则退回单人。
func (r *WorkflowResolver) ResolveAll(ctx context.Context, step *workflow.WorkflowStep, inst *workflow.WorkflowInstance) ([]uint64, error) {
	if step.ApproverType == workflow.ApproverTypeRole {
		if ids := r.usersWithRole(ctx, step.ApproverRoleID, 0); len(ids) > 0 {
			return ids, nil
		}
	}
	id, err := r.Resolve(ctx, step, inst)
	if err != nil || id == 0 {
		return nil, err
	}
	return []uint64{id}, nil
}

// usersWithRole 取拥有该角色的在岗用户 id(limit<=0 表示不限)。
// 单 role_id 外键优先;再尝试 Django M2M user_roles(表不存在则忽略)。
func (r *WorkflowResolver) usersWithRole(ctx context.Context, roleID *uint64, limit int) []uint64 {
	if roleID == nil {
		return nil
	}
	var ids []uint64
	q := r.db.WithContext(ctx).Model(&User{}).
		Where("role_id = ? AND is_active = ?", *roleID, true).Order("id")
	if limit > 0 {
		q = q.Limit(limit)
	}
	_ = q.Pluck("id", &ids).Error
	if len(ids) > 0 {
		return ids
	}
	// 兼容 Django M2M(user_roles 表存在时);不存在则忽略错误。
	_ = r.db.WithContext(ctx).Raw(
		`SELECT u.id FROM "user" u JOIN user_roles ur ON ur.user_id = u.id
		 WHERE ur.role_id = ? AND u.is_active AND u.deleted_at IS NULL ORDER BY u.id`, *roleID).
		Scan(&ids).Error
	return ids
}

func (r *WorkflowResolver) firstUserWithRole(ctx context.Context, roleID *uint64) uint64 {
	ids := r.usersWithRole(ctx, roleID, 1)
	if len(ids) > 0 {
		return ids[0]
	}
	return 0
}

// deptManager 取提交人所在部门的负责人(对齐 Django submitter.department.manager)。
func (r *WorkflowResolver) deptManager(ctx context.Context, submitterID uint64) uint64 {
	var u User
	if err := r.db.WithContext(ctx).Where("id = ?", submitterID).First(&u).Error; err != nil || u.DepartmentID == nil {
		return 0
	}
	var d Department
	if err := r.db.WithContext(ctx).Where("id = ?", *u.DepartmentID).First(&d).Error; err != nil || d.ManagerID == nil {
		return 0
	}
	return *d.ManagerID
}

var _ workflow.CCResolver = (*WorkflowResolver)(nil)

// ResolveCC 解析抄送人(cc_users + cc_roles 的在岗用户),对齐 Django WorkflowStep.cc_users/cc_roles。
// M2M 中间表(workflow_step_cc_users / workflow_step_cc_roles)存在时查询,不存在则忽略(best-effort)。
func (r *WorkflowResolver) ResolveCC(ctx context.Context, step *workflow.WorkflowStep, _ *workflow.WorkflowInstance) []uint64 {
	set := map[uint64]struct{}{}

	var userIDs []uint64
	_ = r.db.WithContext(ctx).Raw(
		`SELECT user_id FROM workflow_step_cc_users WHERE workflowstep_id = ?`, step.ID).Scan(&userIDs).Error
	for _, id := range userIDs {
		if id != 0 {
			set[id] = struct{}{}
		}
	}

	var roleIDs []uint64
	_ = r.db.WithContext(ctx).Raw(
		`SELECT role_id FROM workflow_step_cc_roles WHERE workflowstep_id = ?`, step.ID).Scan(&roleIDs).Error
	for _, rid := range roleIDs {
		rid := rid
		for _, uid := range r.usersWithRole(ctx, &rid, 0) {
			set[uid] = struct{}{}
		}
	}

	out := make([]uint64, 0, len(set))
	for id := range set {
		out = append(out, id)
	}
	return out
}

func (r *WorkflowResolver) firstSuperuser(ctx context.Context) uint64 {
	var ids []uint64
	_ = r.db.WithContext(ctx).Model(&User{}).
		Where("is_superuser = ? AND is_active = ?", true, true).Order("id").Limit(1).
		Pluck("id", &ids).Error
	if len(ids) > 0 {
		return ids[0]
	}
	return 0
}
