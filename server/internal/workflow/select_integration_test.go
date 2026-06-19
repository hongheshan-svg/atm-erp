//go:build integration

package workflow

import (
	"context"
	"testing"

	"github.com/atm-erp/server/internal/testutil"
	"gorm.io/gorm"
)

// 对账运行中的 Django WorkflowService.get_workflow_for_business:
//   - 含 NULL 阈值流程时,PG `ORDER BY amount_threshold DESC` 为 NULLS FIRST,
//     循环首个即 NULL 流程 → 任何金额都选它(裁判:全选 nothr)。
//   - 无 NULL 时:5000/20000/100000 各选 low/mid/high(裁判已确认)。
//
// NULLS 排序是 DB 行为,故必须真库测,不能纯内存。
func fptr(v float64) *float64 { return &v }

func seedDef(t *testing.T, db *gorm.DB, name, code, bt string, thr *float64) {
	t.Helper()
	d := &WorkflowDefinition{Name: name, Code: code, BusinessType: bt, IsActive: true, AmountThreshold: thr}
	if err := db.Create(d).Error; err != nil {
		t.Fatalf("seed %s: %v", name, err)
	}
}

func TestSelectForBusinessMatchesDjango(t *testing.T) {
	dsn := "host=127.0.0.1 port=55550 user=u password=p dbname=d sslmode=disable TimeZone=Asia/Shanghai"
	db := testutil.OpenDB(t, dsn, &WorkflowDefinition{})
	repo := &DefinitionRepo{db: db}
	ctx := context.Background()

	// 场景 A:含 NULL 阈值 → 任何金额都选 nothr
	btA := "ORC_A"
	seedDef(t, db, "low", "A-low", btA, fptr(0))
	seedDef(t, db, "mid", "A-mid", btA, fptr(10000))
	seedDef(t, db, "high", "A-high", btA, fptr(50000))
	seedDef(t, db, "nothr", "A-nothr", btA, nil)
	for _, amt := range []*float64{nil, fptr(5000), fptr(20000), fptr(100000)} {
		got, err := repo.SelectForBusiness(ctx, btA, amt)
		if err != nil || got == nil {
			t.Fatalf("A select err=%v got=%v", err, got)
		}
		if got.Name != "nothr" {
			t.Errorf("A amount=%v -> %s,期望 nothr(NULL 阈值应永远胜出)", amt, got.Name)
		}
	}

	// 场景 B:无 NULL → 阈值匹配
	btB := "ORC_B"
	seedDef(t, db, "low", "B-low", btB, fptr(0))
	seedDef(t, db, "mid", "B-mid", btB, fptr(10000))
	seedDef(t, db, "high", "B-high", btB, fptr(50000))
	for _, c := range []struct {
		amt  float64
		want string
	}{{5000, "low"}, {20000, "mid"}, {100000, "high"}} {
		got, err := repo.SelectForBusiness(ctx, btB, fptr(c.amt))
		if err != nil || got == nil {
			t.Fatalf("B select err=%v", err)
		}
		if got.Name != c.want {
			t.Errorf("B amount=%v -> %s,期望 %s", c.amt, got.Name, c.want)
		}
	}
}
