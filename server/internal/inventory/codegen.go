package inventory

import (
	"fmt"
	"time"

	"gorm.io/gorm"
)

// generateMoveNo 生成库存移动单号。
//
// TODO(verify): Django 用 apps.core.utils.generate_code('SM', rule_type='STOCK_MOVE'),
// 走 CodeRule 模型(可配置前缀/日期段/序号位数/步长,并发安全自增)。本轮 core.CodeRule
// 尚未移植到 Go,这里用「SM + YYYYMMDD + 当日序号」做形态近似的占位实现:
// 单号格式与默认规则相近,但未读取 CodeRule 配置、未跨进程加锁。切流前需替换为
// 移植后的 codegen 服务,以保证编号规则与 Django 完全一致。
func generateMoveNo(tx *gorm.DB) string {
	return seqNo(tx, "SM", &StockMove{}, "move_no")
}

// seqNo 统计当日同前缀记录数 +1,拼成 PREFIX+YYYYMMDD+4位序号。
// 注意:非强一致(并发下可能撞号),仅作脚手架占位,见上方 TODO(verify)。
func seqNo(tx *gorm.DB, prefix string, model any, col string) string {
	day := time.Now().Format("20060102")
	like := prefix + day + "%"
	var n int64
	// 绕过软删除过滤以贴近 unique 全表语义(忽略错误,失败则从 1 开始)。
	_ = tx.Unscoped().Model(model).Where(col+" LIKE ?", like).Count(&n).Error
	return fmt.Sprintf("%s%s%04d", prefix, day, n+1)
}
