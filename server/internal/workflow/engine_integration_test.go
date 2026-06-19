//go:build integration

package workflow

import (
	"context"
	"testing"

	"github.com/atm-erp/server/internal/testutil"
	"gorm.io/gorm"
)

// wfResolver:测试用审批人解析器。Resolve 取 step.ApproverUserID(单人);
// ResolveAll 返回注入的多人(会签)。
type wfResolver struct{ multi []uint64 }

func (wfResolver) Resolve(_ context.Context, step *WorkflowStep, _ *WorkflowInstance) (uint64, error) {
	if step.ApproverUserID != nil {
		return *step.ApproverUserID, nil
	}
	return 0, nil
}
func (r wfResolver) ResolveAll(_ context.Context, _ *WorkflowStep, _ *WorkflowInstance) ([]uint64, error) {
	return r.multi, nil
}

func openWFDB(t *testing.T) *gorm.DB {
	dsn := "host=127.0.0.1 port=55552 user=u password=p dbname=d sslmode=disable TimeZone=Asia/Shanghai"
	return testutil.OpenDB(t, dsn, &WorkflowDefinition{}, &WorkflowStep{}, &WorkflowInstance{}, &WorkflowTask{})
}

func f64(v float64) *float64 { return &v }

// 对账 Django 跳步:step1 skip_amount_threshold=5000,step2 无。
//
//	amount=0    → step1(0 为假,不跳)
//	amount=3000 → step2(3000<5000,跳 step1)
//	amount=8000 → step1(8000>=5000,不跳)
//	amount=nil  → step1(None 为假,不跳)
func TestSkipStepMatchesDjango(t *testing.T) {
	db := openWFDB(t)
	svc := NewService(db, nil, wfResolver{})
	ctx := context.Background()
	uid := uint64(7)
	bt := "ORC_SKIP"

	wf := &WorkflowDefinition{Name: "skip", Code: "SK", BusinessType: bt, IsActive: true}
	if err := db.Create(wf).Error; err != nil {
		t.Fatalf("create wf: %v", err)
	}
	db.Create(&WorkflowStep{WorkflowID: wf.ID, StepOrder: 1, Name: "s1", ApproverType: ApproverTypeUser, ApproverUserID: &uid, SkipAmountThreshold: f64(5000), TimeoutHours: 24})
	db.Create(&WorkflowStep{WorkflowID: wf.ID, StepOrder: 2, Name: "s2", ApproverType: ApproverTypeUser, ApproverUserID: &uid, TimeoutHours: 24})

	check := func(amt *float64, bid int64, wantStep int) {
		res, err := svc.Start(ctx, StartInput{BusinessType: bt, BusinessID: bid, BusinessNo: "NO", Amount: amt})
		if err != nil {
			t.Fatalf("start bid=%d: %v", bid, err)
		}
		var task WorkflowTask
		if err := db.Where("instance_id = ? AND status = ?", res.Instance.ID, TaskStatusPending).First(&task).Error; err != nil {
			t.Fatalf("no pending task bid=%d: %v", bid, err)
		}
		var step WorkflowStep
		db.First(&step, task.StepID)
		if step.StepOrder != wantStep {
			t.Errorf("amount=%v -> step %d,期望 %d", amt, step.StepOrder, wantStep)
		}
	}
	check(f64(0), 1, 1)
	check(f64(3000), 2, 2)
	check(f64(8000), 3, 1)
	check(nil, 4, 1)
}

// 会签(COUNTERSIGN,Go 新增能力):一步两审批人,全 APPROVED 才推进。
func TestCountersignAllApprove(t *testing.T) {
	db := openWFDB(t)
	svc := NewService(db, nil, wfResolver{multi: []uint64{101, 102}})
	ctx := context.Background()
	bt := "ORC_CS"

	wf := &WorkflowDefinition{Name: "cs", Code: "CS", BusinessType: bt, IsActive: true}
	if err := db.Create(wf).Error; err != nil {
		t.Fatalf("create wf: %v", err)
	}
	db.Create(&WorkflowStep{WorkflowID: wf.ID, StepOrder: 1, Name: "会签", ApproverType: ApproverTypeRole, ActionType: ActionTypeCountersign, TimeoutHours: 24})

	res, err := svc.Start(ctx, StartInput{BusinessType: bt, BusinessID: 1, BusinessNo: "NO"})
	if err != nil {
		t.Fatalf("start: %v", err)
	}
	inst := res.Instance

	var tasks []WorkflowTask
	db.Where("instance_id = ?", inst.ID).Order("id").Find(&tasks)
	if len(tasks) != 2 {
		t.Fatalf("会签应生成 2 task,得 %d", len(tasks))
	}

	// 审批第 1 个 → 实例仍 PENDING,第 2 个仍 PENDING(未全签不推进)
	if err := svc.ApproveTask(ctx, tasks[0].ID, "", true); err != nil {
		t.Fatalf("approve1: %v", err)
	}
	var inst1 WorkflowInstance
	db.First(&inst1, inst.ID)
	if inst1.Status != InstanceStatusPending {
		t.Errorf("会签未全签,实例应仍 PENDING,得 %s", inst1.Status)
	}
	var t2 WorkflowTask
	db.First(&t2, tasks[1].ID)
	if t2.Status != TaskStatusPending {
		t.Errorf("第2会签 task 应仍 PENDING,得 %s", t2.Status)
	}

	// 审批第 2 个 → 全签 → 实例 APPROVED(单步完成)
	if err := svc.ApproveTask(ctx, tasks[1].ID, "", true); err != nil {
		t.Fatalf("approve2: %v", err)
	}
	var inst2 WorkflowInstance
	db.First(&inst2, inst.ID)
	if inst2.Status != InstanceStatusApproved {
		t.Errorf("会签全签后实例应 APPROVED,得 %s", inst2.Status)
	}
}
