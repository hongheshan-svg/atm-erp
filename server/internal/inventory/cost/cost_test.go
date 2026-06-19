package cost

import (
	"testing"

	"github.com/shopspring/decimal"
)

func d(s string) decimal.Decimal { return decimal.RequireFromString(s) }

// TestWeightedAverageMatchesDjangoOracle 用运行中的旧 Django(CostCalculationService)
// 产出的权威数字对账:入库 10@100、10@200、2@13,再出库 5。
//
//	Django 裁判结果:bal_qty=17.0000  bal_cost=2338.27  bal_unit=137.5453
//	(关键:出库金额 5×137.5455=687.7275 先量化到 687.73 再扣减)
func TestWeightedAverageMatchesDjangoOracle(t *testing.T) {
	// step1: 入 10@100
	q, c, u := Inbound(decimal.Zero, decimal.Zero, d("10"), d("100"))
	assertStep(t, "in1", q, c, u, "10", "1000.00", "100.0000")

	// step2: 入 10@200
	q, c, u = Inbound(q, c, d("10"), d("200"))
	assertStep(t, "in2", q, c, u, "20", "3000.00", "150.0000")

	// step3: 入 2@13 → 单价 3026/22=137.5455(4dp HALF_UP)
	q, c, u = Inbound(q, c, d("2"), d("13"))
	assertStep(t, "in3", q, c, u, "22", "3026.00", "137.5455")

	// step4: 出 5 → 出库额 687.73,结存 17 / 2338.27 / 137.5453
	var outTotal decimal.Decimal
	q, c, u, _, outTotal = Outbound(q, c, u, d("5"))
	if !outTotal.Equal(d("687.73")) {
		t.Fatalf("out 金额=%s 期望 687.73(先量化再扣减)", outTotal)
	}
	assertStep(t, "out", q, c, u, "17", "2338.27", "137.5453")
}

func assertStep(t *testing.T, name string, q, c, u decimal.Decimal, wq, wc, wu string) {
	t.Helper()
	if !q.Equal(d(wq)) {
		t.Errorf("%s 结存数量=%s 期望 %s", name, q, wq)
	}
	if !c.Equal(d(wc)) {
		t.Errorf("%s 结存金额=%s 期望 %s", name, c, wc)
	}
	if !u.Equal(d(wu)) {
		t.Errorf("%s 结存单价=%s 期望 %s", name, u, wu)
	}
}
