//go:build integration

package collection

import (
	"context"
	"testing"
	"time"

	"github.com/atm-erp/server/internal/testutil"
	"github.com/shopspring/decimal"
)

// 对账运行中的 Django CollectionRecord.save 级联。裁判:
//
//	m1 +10000 → m1=10000/PARTIAL, plan=10000/IN_PROGRESS
//	m1 +20000 → m1=30000/COLLECTED, plan=30000/IN_PROGRESS
//	m2 +70000 → m2=70000/COLLECTED, plan=100000/COMPLETED;remaining=0
func TestCascadeMatchesDjango(t *testing.T) {
	dsn := "host=127.0.0.1 port=55560 user=u password=p dbname=d sslmode=disable TimeZone=Asia/Shanghai"
	db := testutil.OpenDB(t, dsn, &CollectionPlan{}, &CollectionMilestone{}, &CollectionRecord{})
	svc := NewService(db)
	ctx := context.Background()
	rfs := decimal.RequireFromString

	plan := &CollectionPlan{PlanNo: "ORC-P1", Name: "对账计划", CustomerID: 1, TotalAmount: rfs("100000"), Status: PlanDraft}
	if err := db.Create(plan).Error; err != nil {
		t.Fatalf("create plan: %v", err)
	}
	m1 := &CollectionMilestone{PlanID: plan.ID, Name: "预付", PlannedAmount: rfs("30000"), PlannedDate: time.Now(), Status: MilestonePending}
	m2 := &CollectionMilestone{PlanID: plan.ID, Name: "尾款", PlannedAmount: rfs("70000"), PlannedDate: time.Now(), Status: MilestonePending}
	if err := db.Create(m1).Error; err != nil {
		t.Fatalf("create m1: %v", err)
	}
	if err := db.Create(m2).Error; err != nil {
		t.Fatalf("create m2: %v", err)
	}

	add := func(mID uint64, amt string) {
		if err := svc.AddRecord(ctx, &CollectionRecord{MilestoneID: mID, Amount: rfs(amt), CollectionDate: time.Now()}); err != nil {
			t.Fatalf("AddRecord %s: %v", amt, err)
		}
	}
	check := func(label string, mID uint64, wantMColl, wantMStatus, wantPColl, wantPStatus string) {
		var m CollectionMilestone
		var p CollectionPlan
		db.First(&m, mID)
		db.First(&p, plan.ID)
		if !m.CollectedAmount.Equal(rfs(wantMColl)) || m.Status != wantMStatus {
			t.Errorf("%s: 节点 collected=%s status=%s,期望 %s/%s", label, m.CollectedAmount, m.Status, wantMColl, wantMStatus)
		}
		if !p.CollectedAmount.Equal(rfs(wantPColl)) || p.Status != wantPStatus {
			t.Errorf("%s: 计划 collected=%s status=%s,期望 %s/%s", label, p.CollectedAmount, p.Status, wantPColl, wantPStatus)
		}
	}

	add(m1.ID, "10000")
	check("step1", m1.ID, "10000", MilestonePartial, "10000", PlanInProgress)
	add(m1.ID, "20000")
	check("step2", m1.ID, "30000", MilestoneCollected, "30000", PlanInProgress)
	add(m2.ID, "70000")
	check("step3", m2.ID, "70000", MilestoneCollected, "100000", PlanCompleted)

	var p CollectionPlan
	db.First(&p, plan.ID)
	if !p.RemainingAmount().Equal(rfs("0")) {
		t.Errorf("remaining=%s 期望 0", p.RemainingAmount())
	}
}
