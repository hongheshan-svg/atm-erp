package collection

import (
	"testing"

	"github.com/shopspring/decimal"
)

func dec(s string) decimal.Decimal { return decimal.RequireFromString(s) }

// 纯状态函数对账 Django CollectionRecord.save 的状态阈值。
func TestMilestoneStatus(t *testing.T) {
	cases := []struct {
		collected, planned, want string
	}{
		{"0", "30000", MilestonePending},
		{"10000", "30000", MilestonePartial},
		{"30000", "30000", MilestoneCollected},
		{"35000", "30000", MilestoneCollected},
	}
	for _, c := range cases {
		if got := MilestoneStatus(dec(c.collected), dec(c.planned)); got != c.want {
			t.Errorf("MilestoneStatus(%s,%s)=%s 期望 %s", c.collected, c.planned, got, c.want)
		}
	}
}

func TestPlanStatus(t *testing.T) {
	// 未满 + 当前 DRAFT → IN_PROGRESS
	if got := PlanStatus(dec("10000"), dec("100000"), PlanDraft); got != PlanInProgress {
		t.Errorf("DRAFT 未满应转 IN_PROGRESS,得到 %s", got)
	}
	// 未满 + 当前 IN_PROGRESS → 不变
	if got := PlanStatus(dec("30000"), dec("100000"), PlanInProgress); got != PlanInProgress {
		t.Errorf("IN_PROGRESS 未满应不变,得到 %s", got)
	}
	// 已满 → COMPLETED
	if got := PlanStatus(dec("100000"), dec("100000"), PlanInProgress); got != PlanCompleted {
		t.Errorf("满额应 COMPLETED,得到 %s", got)
	}
}
