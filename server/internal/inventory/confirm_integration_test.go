//go:build integration

package inventory

import (
	"context"
	"fmt"
	"testing"

	"github.com/atm-erp/server/internal/testutil"
)

// 对账运行中的 Django StockMove confirm → Stock 加权平均联动。
// 序列(均 COMPLETED):IN 10@100、IN 5@130、IN 3@121.50、OUT 4。
// Django 裁判:Stock qty=14.00 avg=111.92。
func TestStockMoveConfirmMatchesDjango(t *testing.T) {
	dsn := "host=127.0.0.1 port=55514 user=u password=p dbname=d sslmode=disable TimeZone=Asia/Shanghai"
	db := testutil.OpenDB(t, dsn, &Stock{}, &StockMove{})
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
}
