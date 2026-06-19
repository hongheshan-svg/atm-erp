//go:build integration

package accounts

import (
	"context"
	"testing"

	"github.com/atm-erp/server/internal/iam"
	"github.com/atm-erp/server/internal/testutil"
	"github.com/atm-erp/server/internal/workflow"
	"gorm.io/gorm"
)

// 验证 IAM 真实审批人 resolver(对齐 Django _get_step_assignee):
//
//	step1 ROLE              → 该角色的在岗用户
//	step2 DEPARTMENT_MANAGER → 提交人所在部门的负责人
func TestWorkflowResolverIAM(t *testing.T) {
	dsn := "host=127.0.0.1 port=55562 user=u password=p dbname=d sslmode=disable TimeZone=Asia/Shanghai"
	db := testutil.OpenDB(t, dsn,
		&User{}, &Role{}, &Department{},
		&workflow.WorkflowDefinition{}, &workflow.WorkflowStep{}, &workflow.WorkflowInstance{}, &workflow.WorkflowTask{},
	)

	role := &Role{Name: "审批角色", Code: "approver", IsActive: true}
	must(t, db.Create(role).Error)
	roleUser := &User{Username: "roleuser", EmployeeID: "E10", RoleID: &role.ID, IsActive: true}
	must(t, db.Create(roleUser).Error)
	mgr := &User{Username: "mgr", EmployeeID: "E20", IsActive: true}
	must(t, db.Create(mgr).Error)
	dept := &Department{Name: "研发部", Code: "RD", ManagerID: &mgr.ID}
	must(t, db.Create(dept).Error)
	submitter := &User{Username: "submitter", EmployeeID: "E30", DepartmentID: &dept.ID, IsActive: true}
	must(t, db.Create(submitter).Error)

	bt := "RESOLVER_BT"
	wf := &workflow.WorkflowDefinition{Name: "审批流", Code: "WF1", BusinessType: bt, IsActive: true}
	must(t, db.Create(wf).Error)
	must(t, db.Create(&workflow.WorkflowStep{WorkflowID: wf.ID, StepOrder: 1, Name: "角色审批", ApproverType: workflow.ApproverTypeRole, ApproverRoleID: &role.ID, TimeoutHours: 24}).Error)
	must(t, db.Create(&workflow.WorkflowStep{WorkflowID: wf.ID, StepOrder: 2, Name: "部门经理", ApproverType: workflow.ApproverTypeDepartmentManager, TimeoutHours: 24}).Error)

	svc := workflow.NewService(db, workflow.NewCallbackRegistry(), NewWorkflowResolver(db))
	// 以 submitter 身份发起(Start 取 ctx 当前用户为提交人)。
	ctx := iam.WithAuthUser(context.Background(), &iam.AuthUser{ID: submitter.ID})

	res, err := svc.Start(ctx, workflow.StartInput{BusinessType: bt, BusinessID: 1, BusinessNo: "NO1"})
	if err != nil {
		t.Fatalf("start: %v", err)
	}

	// step1 任务 → 角色用户
	t1 := pendingTask(t, db, res.Instance.ID)
	if t1.AssigneeID != roleUser.ID {
		t.Errorf("step1 ROLE 审批人=%d,期望角色用户 %d", t1.AssigneeID, roleUser.ID)
	}

	// 审批 step1 → step2 任务 → 提交人部门负责人
	if err := svc.ApproveTask(ctx, t1.ID, "", true); err != nil {
		t.Fatalf("approve1: %v", err)
	}
	t2 := pendingTask(t, db, res.Instance.ID)
	if t2.AssigneeID != mgr.ID {
		t.Errorf("step2 DEPARTMENT_MANAGER 审批人=%d,期望部门负责人 %d", t2.AssigneeID, mgr.ID)
	}
}

// PROJECT_MANAGER:business_type → 业务表.project_id → project.manager_id(对齐 Django _get_project_manager);
// 解析不到 → 0 → 引擎兜底 approver_role 用户。
func TestWorkflowResolverProjectManager(t *testing.T) {
	dsn := "host=127.0.0.1 port=55562 user=u password=p dbname=d sslmode=disable TimeZone=Asia/Shanghai"
	db := testutil.OpenDB(t, dsn, &User{}, &Role{}, &Department{},
		&workflow.WorkflowDefinition{}, &workflow.WorkflowStep{}, &workflow.WorkflowInstance{}, &workflow.WorkflowTask{})

	pm := &User{Username: "pm", EmployeeID: "EPM", IsActive: true}
	must(t, db.Create(pm).Error)

	// 真库业务表(本测试只需用到的列):project + sales_order。
	must(t, db.Exec(`CREATE TABLE IF NOT EXISTS project (id bigint PRIMARY KEY, manager_id bigint)`).Error)
	must(t, db.Exec(`CREATE TABLE IF NOT EXISTS sales_order (id bigint PRIMARY KEY, project_id bigint)`).Error)
	projID, soID := int64(9001), int64(7001)
	must(t, db.Exec(`INSERT INTO project (id, manager_id) VALUES (?, ?)
		ON CONFLICT (id) DO UPDATE SET manager_id = EXCLUDED.manager_id`, projID, pm.ID).Error)
	must(t, db.Exec(`INSERT INTO sales_order (id, project_id) VALUES (?, ?)
		ON CONFLICT (id) DO UPDATE SET project_id = EXCLUDED.project_id`, soID, projID).Error)

	r := NewWorkflowResolver(db)
	ctx := context.Background()

	if got := r.projectManager(ctx, "PROJECT", uint64(projID)); got != pm.ID {
		t.Errorf("PROJECT 直接取项目经理=%d,期望 %d", got, pm.ID)
	}
	if got := r.projectManager(ctx, "SALES_ORDER", uint64(soID)); got != pm.ID {
		t.Errorf("SALES_ORDER 单跳取项目经理=%d,期望 %d", got, pm.ID)
	}
	if got := r.projectManager(ctx, "SALES_ORDER", 999999); got != 0 {
		t.Errorf("无此单据应得 0,得 %d", got)
	}

	// 经引擎:PROJECT_MANAGER 步,业务无项目 → 0 → 兜底 approver_role 用户(对齐 Django None 后兜底)。
	role := &Role{Name: "兜底角色", Code: "fbk", IsActive: true}
	must(t, db.Create(role).Error)
	fbUser := &User{Username: "fbk", EmployeeID: "EFB", RoleID: &role.ID, IsActive: true}
	must(t, db.Create(fbUser).Error)
	step := &workflow.WorkflowStep{ApproverType: workflow.ApproverTypeProjectManager, ApproverRoleID: &role.ID}
	inst := &workflow.WorkflowInstance{BusinessType: "SALES_ORDER", BusinessID: 999999}
	id, err := r.Resolve(ctx, step, inst)
	if err != nil {
		t.Fatal(err)
	}
	if id != fbUser.ID {
		t.Errorf("PM 解析失败应兜底到 approver_role 用户=%d,得 %d", fbUser.ID, id)
	}
}

func must(t *testing.T, err error) {
	t.Helper()
	if err != nil {
		t.Fatalf("seed: %v", err)
	}
}

func pendingTask(t *testing.T, db *gorm.DB, instanceID uint64) *workflow.WorkflowTask {
	t.Helper()
	var task workflow.WorkflowTask
	if err := db.Where("instance_id = ? AND status = ?", instanceID, workflow.TaskStatusPending).
		Order("id DESC").First(&task).Error; err != nil {
		t.Fatalf("无 PENDING 任务: %v", err)
	}
	return &task
}
