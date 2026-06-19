//go:build integration

package inventory

import (
	"context"
	"fmt"
	"testing"

	"github.com/atm-erp/server/internal/inventory/cost"
	"github.com/atm-erp/server/internal/testutil"
	"github.com/shopspring/decimal"
	"gorm.io/gorm"
)

// ── 账本断言辅助 ───────────────────────────────────────────────────────────

func latestLedger(t *testing.T, db *gorm.DB, item, wh uint64) cost.ItemCostRecord {
	t.Helper()
	var r cost.ItemCostRecord
	if err := db.Where("item_id = ? AND warehouse_id = ?", item, wh).
		Order("created_at DESC").Order("id DESC").First(&r).Error; err != nil {
		t.Fatalf("load ledger (item=%d wh=%d): %v", item, wh, err)
	}
	return r
}

func ledgerCount(t *testing.T, db *gorm.DB, item, wh uint64) int64 {
	t.Helper()
	var n int64
	db.Model(&cost.ItemCostRecord{}).Where("item_id = ? AND warehouse_id = ?", item, wh).Count(&n)
	return n
}

func eqDec(t *testing.T, label string, got decimal.Decimal, want string) {
	t.Helper()
	if !got.Equal(decimal.RequireFromString(want)) {
		t.Errorf("%s=%s 期望 %s", label, got.String(), want)
	}
}

// 对账运行中的 Django StockMove confirm → Stock 加权平均 + 成本账本联动。
// 序列(均 COMPLETED):IN 10@100、IN 5@130、IN 3@121.50、OUT 4。
// Django Stock 裁判:qty=14.00 avg=111.92;账本裁判(同算法,cost_test 已对裁判验证):
// bal_qty=14.0000 bal_cost=1566.83 bal_unit=111.9164,出库行 qty=-4 unit=111.9167 total=-447.67。
func TestStockMoveConfirmMatchesDjango(t *testing.T) {
	dsn := "host=127.0.0.1 port=55514 user=u password=p dbname=d sslmode=disable TimeZone=Asia/Shanghai"
	db := testutil.OpenDB(t, dsn, &Stock{}, &StockMove{}, &cost.ItemCostRecord{})
	svc := NewService(NewRepo(db))
	ctx := context.Background()
	const wh, item = uint64(1), uint64(1)
	p := func(v uint64) *uint64 { return &v }

	mk := func(mt string, qty, cost float64, wf, wt *uint64) {
		_, err := svc.CreateMove(ctx, StockMoveCreateInput{
			ItemID: item, WarehouseFrom: wf, WarehouseTo: wt,
			Qty: qty, UnitCost: cost, MoveType: mt, MoveDate: "2026-01-01", Status: MoveStatusCompleted,
		})
		if err != nil {
			t.Fatalf("%s: %v", mt, err)
		}
	}

	mk(MoveTypeInPurchase, 10, 100, nil, p(wh))
	mk(MoveTypeInPurchase, 5, 130, nil, p(wh))
	mk(MoveTypeInPurchase, 3, 121.50, nil, p(wh))
	mk(MoveTypeOutSales, 4, 0, p(wh), nil)

	var st Stock
	if err := db.Where("warehouse_id = ? AND item_id = ?", wh, item).First(&st).Error; err != nil {
		t.Fatalf("load stock: %v", err)
	}
	if got := fmt.Sprintf("%.2f", st.QtyOnHand); got != "14.00" {
		t.Errorf("qty_on_hand=%s 期望 14.00", got)
	}
	if got := fmt.Sprintf("%.2f", st.WeightedAvgCost); got != "111.92" {
		t.Errorf("weighted_avg_cost=%s 期望 111.92", got)
	}

	// 账本与 Stock 同事务联动:4 行(3 入 1 出),结存对账。
	if n := ledgerCount(t, db, item, wh); n != 4 {
		t.Errorf("账本行数=%d 期望 4(3 入 + 1 出)", n)
	}
	last := latestLedger(t, db, item, wh)
	eqDec(t, "bal_qty", last.BalanceQty, "14")
	eqDec(t, "bal_cost", last.BalanceCost, "1566.83")
	eqDec(t, "bal_unit", last.BalanceUnitCost, "111.9164")
	// 出库行(最新一行即 OUT):金额取账本结存单价、先量化再扣减。
	eqDec(t, "out_qty", last.Quantity, "-4")
	eqDec(t, "out_unit", last.UnitCost, "111.9167")
	eqDec(t, "out_total", last.TotalCost, "-447.67")
	// Django 保真:transaction_type 映射合法枚举、transaction_date 用业务日期。
	if last.TransactionType != "SALES_OUT" {
		t.Errorf("出库行 transaction_type=%s 期望 SALES_OUT", last.TransactionType)
	}
	if got := last.TransactionDate.Format("2006-01-02"); got != "2026-01-01" {
		t.Errorf("transaction_date=%s 期望业务日期 2026-01-01", got)
	}
	// 一致性:账本结存单价截 2dp == Stock 加权均价。
	if !last.BalanceUnitCost.Round(2).Equal(decimal.NewFromFloat(st.WeightedAvgCost).Round(2)) {
		t.Errorf("账本结存单价 %s 截 2dp 应 == Stock 均价 %.2f", last.BalanceUnitCost, st.WeightedAvgCost)
	}
}

// 清库归零:IN 3@100、IN 2@150、OUT 5(清空)。
// 账本裁判:bal_qty=0 bal_cost=0(强制归零)bal_unit=120.0000(沿用结存价)。
func TestStockMoveLedgerClearToZero(t *testing.T) {
	dsn := "host=127.0.0.1 port=55514 user=u password=p dbname=d sslmode=disable TimeZone=Asia/Shanghai"
	db := testutil.OpenDB(t, dsn, &Stock{}, &StockMove{}, &cost.ItemCostRecord{})
	svc := NewService(NewRepo(db))
	ctx := context.Background()
	const wh, item = uint64(1), uint64(2) // 与上例不同 item,避免同库污染
	p := func(v uint64) *uint64 { return &v }
	mk := func(mt string, qty, c float64, wf, wt *uint64) {
		if _, err := svc.CreateMove(ctx, StockMoveCreateInput{
			ItemID: item, WarehouseFrom: wf, WarehouseTo: wt,
			Qty: qty, UnitCost: c, MoveType: mt, MoveDate: "2026-01-01", Status: MoveStatusCompleted,
		}); err != nil {
			t.Fatalf("%s: %v", mt, err)
		}
	}
	mk(MoveTypeInPurchase, 3, 100, nil, p(wh))
	mk(MoveTypeInPurchase, 2, 150, nil, p(wh))
	mk(MoveTypeOutSales, 5, 0, p(wh), nil)

	last := latestLedger(t, db, item, wh)
	eqDec(t, "bal_qty", last.BalanceQty, "0")
	eqDec(t, "bal_cost", last.BalanceCost, "0")
	eqDec(t, "bal_unit", last.BalanceUnitCost, "120") // (3*100+2*150)/5=120,出库后沿用
}

// 调拨写两行账本:仓 from 出库行 + 仓 to 入库行(账本按 item+warehouse 分账)。
func TestTransferWritesTwoLedgerRows(t *testing.T) {
	dsn := "host=127.0.0.1 port=55514 user=u password=p dbname=d sslmode=disable TimeZone=Asia/Shanghai"
	db := testutil.OpenDB(t, dsn, &Stock{}, &StockMove{}, &cost.ItemCostRecord{})
	svc := NewService(NewRepo(db))
	ctx := context.Background()
	const item = uint64(3)
	const from, to = uint64(10), uint64(11)
	p := func(v uint64) *uint64 { return &v }

	// 先给 from 仓建底 10@100
	if _, err := svc.CreateMove(ctx, StockMoveCreateInput{
		ItemID: item, WarehouseTo: p(from), Qty: 10, UnitCost: 100,
		MoveType: MoveTypeInPurchase, MoveDate: "2026-01-01", Status: MoveStatusCompleted,
	}); err != nil {
		t.Fatalf("seed in: %v", err)
	}
	// 调拨 4:from→to,move 单价=from 仓均价 100
	if _, err := svc.CreateMove(ctx, StockMoveCreateInput{
		ItemID: item, WarehouseFrom: p(from), WarehouseTo: p(to), Qty: 4, UnitCost: 100,
		MoveType: MoveTypeTransfer, MoveDate: "2026-01-02", Status: MoveStatusCompleted,
	}); err != nil {
		t.Fatalf("transfer: %v", err)
	}

	// from 仓账本:入库行 + 出库行 = 2 行,结存 6@100
	if n := ledgerCount(t, db, item, from); n != 2 {
		t.Errorf("from 仓账本行数=%d 期望 2", n)
	}
	fromLast := latestLedger(t, db, item, from)
	eqDec(t, "from_bal_qty", fromLast.BalanceQty, "6")
	eqDec(t, "from_bal_unit", fromLast.BalanceUnitCost, "100")
	eqDec(t, "from_out_qty", fromLast.Quantity, "-4")
	if fromLast.TransactionType != "TRANSFER_OUT" {
		t.Errorf("from 出库行 transaction_type=%s 期望 TRANSFER_OUT", fromLast.TransactionType)
	}

	// to 仓账本:入库行 = 1 行,结存 4@100
	if n := ledgerCount(t, db, item, to); n != 1 {
		t.Errorf("to 仓账本行数=%d 期望 1", n)
	}
	toLast := latestLedger(t, db, item, to)
	eqDec(t, "to_bal_qty", toLast.BalanceQty, "4")
	eqDec(t, "to_bal_unit", toLast.BalanceUnitCost, "100")
	eqDec(t, "to_in_qty", toLast.Quantity, "4")
	if toLast.TransactionType != "TRANSFER_IN" {
		t.Errorf("to 入库行 transaction_type=%s 期望 TRANSFER_IN", toLast.TransactionType)
	}

	// Stock 两仓:from 6@100、to 4@100
	var sf, st Stock
	db.Where("warehouse_id = ? AND item_id = ?", from, item).First(&sf)
	db.Where("warehouse_id = ? AND item_id = ?", to, item).First(&st)
	if fmt.Sprintf("%.2f/%.2f", sf.QtyOnHand, sf.WeightedAvgCost) != "6.00/100.00" {
		t.Errorf("from Stock=%.2f/%.2f 期望 6.00/100.00", sf.QtyOnHand, sf.WeightedAvgCost)
	}
	if fmt.Sprintf("%.2f/%.2f", st.QtyOnHand, st.WeightedAvgCost) != "4.00/100.00" {
		t.Errorf("to Stock=%.2f/%.2f 期望 4.00/100.00", st.QtyOnHand, st.WeightedAvgCost)
	}
}

// 出库超量整笔回滚:OUT 超过库存 → ErrInsufficient,Stock 与账本均无残留(同事务原子)。
func TestOutInsufficientRollsBackLedger(t *testing.T) {
	dsn := "host=127.0.0.1 port=55514 user=u password=p dbname=d sslmode=disable TimeZone=Asia/Shanghai"
	db := testutil.OpenDB(t, dsn, &Stock{}, &StockMove{}, &cost.ItemCostRecord{})
	svc := NewService(NewRepo(db))
	ctx := context.Background()
	const wh, item = uint64(20), uint64(4)
	p := func(v uint64) *uint64 { return &v }

	if _, err := svc.CreateMove(ctx, StockMoveCreateInput{
		ItemID: item, WarehouseTo: p(wh), Qty: 5, UnitCost: 100,
		MoveType: MoveTypeInPurchase, MoveDate: "2026-01-01", Status: MoveStatusCompleted,
	}); err != nil {
		t.Fatalf("seed: %v", err)
	}
	before := ledgerCount(t, db, item, wh) // 1(入库行)

	_, err := svc.CreateMove(ctx, StockMoveCreateInput{
		ItemID: item, WarehouseFrom: p(wh), Qty: 9, UnitCost: 0,
		MoveType: MoveTypeOutSales, MoveDate: "2026-01-02", Status: MoveStatusCompleted,
	})
	if err == nil {
		t.Fatal("超量出库应报 ErrInsufficient")
	}
	// 账本不增(出库行随事务回滚),Stock 仍为 5
	if after := ledgerCount(t, db, item, wh); after != before {
		t.Errorf("回滚后账本行数=%d 期望 %d(出库行应随事务回滚)", after, before)
	}
	var st Stock
	db.Where("warehouse_id = ? AND item_id = ?", wh, item).First(&st)
	if fmt.Sprintf("%.2f", st.QtyOnHand) != "5.00" {
		t.Errorf("回滚后 Stock qty=%.2f 期望 5.00", st.QtyOnHand)
	}
}

// 空仓出库:无 Stock 行(Django pass)→ stockOut applied=false → 不写出库账本、不报错,
// 保证账本与 Stock 一致(Stock 没动账本也不动)。
func TestOutFromEmptyStockSkipsLedger(t *testing.T) {
	dsn := "host=127.0.0.1 port=55514 user=u password=p dbname=d sslmode=disable TimeZone=Asia/Shanghai"
	db := testutil.OpenDB(t, dsn, &Stock{}, &StockMove{}, &cost.ItemCostRecord{})
	svc := NewService(NewRepo(db))
	ctx := context.Background()
	const wh, item = uint64(30), uint64(5) // 全新空仓
	p := func(v uint64) *uint64 { return &v }

	if _, err := svc.CreateMove(ctx, StockMoveCreateInput{
		ItemID: item, WarehouseFrom: p(wh), Qty: 3, UnitCost: 0,
		MoveType: MoveTypeOutSales, MoveDate: "2026-01-01", Status: MoveStatusCompleted,
	}); err != nil {
		t.Fatalf("空仓出库应静默成功(Django pass),却报错: %v", err)
	}
	if n := ledgerCount(t, db, item, wh); n != 0 {
		t.Errorf("空仓出库账本行数=%d 期望 0(Stock 未动则账本不写)", n)
	}
}
