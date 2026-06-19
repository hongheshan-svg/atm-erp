//go:build integration

package notify

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/atm-erp/server/internal/iam"
	"github.com/atm-erp/server/internal/testutil"
	"github.com/atm-erp/server/internal/workflow"
	"gorm.io/gorm"
)

const notifyDSN = "host=127.0.0.1 port=55563 user=u password=p dbname=d sslmode=disable TimeZone=Asia/Shanghai"

// tResolver 测试解析器:USER 取 approver_user;实现 CCResolver 返回固定抄送人。
type tResolver struct{ cc []uint64 }

func (tResolver) Resolve(_ context.Context, step *workflow.WorkflowStep, _ *workflow.WorkflowInstance) (uint64, error) {
	if step.ApproverUserID != nil {
		return *step.ApproverUserID, nil
	}
	return 0, nil
}
func (r tResolver) ResolveAll(ctx context.Context, step *workflow.WorkflowStep, inst *workflow.WorkflowInstance) ([]uint64, error) {
	id, err := r.Resolve(ctx, step, inst)
	if err != nil || id == 0 {
		return nil, err
	}
	return []uint64{id}, nil
}
func (r tResolver) ResolveCC(_ context.Context, _ *workflow.WorkflowStep, _ *workflow.WorkflowInstance) []uint64 {
	return r.cc
}

func hasNotif(t *testing.T, db *gorm.DB, userID uint64, title string) {
	t.Helper()
	var n int64
	db.Model(&Notification{}).Where("user_id = ? AND title = ?", userID, title).Count(&n)
	if n == 0 {
		t.Errorf("用户 %d 应收到标题为「%s」的站内信", userID, title)
	}
}

// 工作流落站内信:待办(审批人)+ 抄送(cc)+ 结果(提交人)。
func TestWorkflowNotifications(t *testing.T) {
	db := testutil.OpenDB(t, notifyDSN,
		&Notification{}, &workflow.WorkflowDefinition{}, &workflow.WorkflowStep{},
		&workflow.WorkflowInstance{}, &workflow.WorkflowTask{})
	svc := workflow.NewService(db, nil, tResolver{cc: []uint64{99}})
	svc.SetNotifier(AsWorkflowNotifier(NewService(db)))

	approver := uint64(10)
	wf := &workflow.WorkflowDefinition{Name: "x", Code: "WN", BusinessType: "BT_NOTIFY", IsActive: true}
	if err := db.Create(wf).Error; err != nil {
		t.Fatal(err)
	}
	if err := db.Create(&workflow.WorkflowStep{WorkflowID: wf.ID, StepOrder: 1, Name: "审批", ApproverType: workflow.ApproverTypeUser, ApproverUserID: &approver, TimeoutHours: 24}).Error; err != nil {
		t.Fatal(err)
	}

	ctx := iam.WithAuthUser(context.Background(), &iam.AuthUser{ID: 30}) // 提交人
	res, err := svc.Start(ctx, workflow.StartInput{BusinessType: "BT_NOTIFY", BusinessID: 1, BusinessNo: "NO1"})
	if err != nil {
		t.Fatal(err)
	}
	hasNotif(t, db, approver, "审批待办") // 审批人收到待办
	hasNotif(t, db, 99, "抄送")         // 抄送人收到抄送

	var task workflow.WorkflowTask
	db.Where("instance_id = ? AND status = ?", res.Instance.ID, workflow.TaskStatusPending).First(&task)
	if err := svc.ApproveTask(ctx, task.ID, "", true); err != nil {
		t.Fatal(err)
	}
	hasNotif(t, db, 30, "审批结果") // 单步通过 → 提交人收到结果
}

// 超时提醒:扫超时待办 → 给审批人发站内信(对齐 Django,仅提醒不改状态)。
func TestRemindOverdue(t *testing.T) {
	db := testutil.OpenDB(t, notifyDSN,
		&Notification{}, &workflow.WorkflowInstance{}, &workflow.WorkflowTask{})
	svc := workflow.NewService(db, nil, nil)
	svc.SetNotifier(AsWorkflowNotifier(NewService(db)))

	inst := &workflow.WorkflowInstance{WorkflowID: 1, BusinessType: "BT_OVD", BusinessID: 5, BusinessNo: "OVD1", Status: workflow.InstanceStatusPending, CurrentStep: 1}
	if err := db.Create(inst).Error; err != nil {
		t.Fatal(err)
	}
	past := time.Now().Add(-2 * time.Hour)
	if err := db.Create(&workflow.WorkflowTask{InstanceID: inst.ID, StepID: 1, AssigneeID: 77, Status: workflow.TaskStatusPending, Deadline: &past}).Error; err != nil {
		t.Fatal(err)
	}

	n, err := svc.RemindOverdue(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if n < 1 {
		t.Errorf("应有 >=1 个超时任务,得 %d", n)
	}
	hasNotif(t, db, 77, "审批超时提醒")
}

// 站内信 REST:列表 / 未读数 / 标记已读(按用户隔离)。
func TestNotifyREST(t *testing.T) {
	db := testutil.OpenDB(t, notifyDSN, &Notification{})
	svc := NewService(db)
	ctx := context.Background()
	// testutil.NewAPIEngine 注入超管 id=1
	if _, err := svc.Notify(ctx, 1, TypeInfo, "r1", "m1"); err != nil {
		t.Fatal(err)
	}
	if _, err := svc.Notify(ctx, 1, TypeInfo, "r2", "m2"); err != nil {
		t.Fatal(err)
	}

	r, api := testutil.NewAPIEngine()
	Routes(api, db, testutil.AllowAll)

	doGet := func(path string) (int, map[string]any) {
		req := httptest.NewRequest(http.MethodGet, path, nil)
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)
		var out map[string]any
		_ = json.Unmarshal(w.Body.Bytes(), &out)
		return w.Code, out
	}
	doPost := func(path string) int {
		req := httptest.NewRequest(http.MethodPost, path, bytes.NewReader(nil))
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)
		return w.Code
	}

	code, body := doGet("/api/notifications/unread_count")
	if code != http.StatusOK || body["unread"].(float64) != 2 {
		t.Fatalf("未读数应 2,得 %d %v", code, body)
	}

	// 取列表,标记第一条已读
	var first Notification
	db.Where("user_id = ?", 1).Order("id").First(&first)
	if c := doPost("/api/notifications/" + itoa(first.ID) + "/read"); c != http.StatusNoContent {
		t.Fatalf("标记已读应 204,得 %d", c)
	}
	_, body2 := doGet("/api/notifications/unread_count")
	if body2["unread"].(float64) != 1 {
		t.Errorf("标记一条后未读应 1,得 %v", body2["unread"])
	}
}

func itoa(v uint64) string {
	const digits = "0123456789"
	if v == 0 {
		return "0"
	}
	var b [20]byte
	i := len(b)
	for v > 0 {
		i--
		b[i] = digits[v%10]
		v /= 10
	}
	return string(b[i:])
}
