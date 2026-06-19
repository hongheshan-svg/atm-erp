package sales

import (
	"fmt"
	"sync/atomic"
	"time"
)

// 业务编号生成。
//
// TODO(port): Django 现状用 core.CodeRule.generate_code(rule_type=...) 统一发号(可配置
// 前缀/日期/序号/步长,且持久化序号)。本轮为避免跨模块依赖 core.CodeRule,先用
// 「前缀 + YYYYMMDD + 进程内自增」临时生成,保证唯一性可用但格式未对齐生产规则。
// 切流前必须替换为 CodeRule 发号以保持编号连续与格式一致。

// seqCounter 以进程启动纳秒为基准做初值,避免「进程重启后从 0 重新发号」
// 与当日既有编号(prefix+YYYYMMDD+0001)发生唯一键冲突(SQLSTATE 23505)。
// 仍是临时方案,切流前须替换为 core.CodeRule 持久化发号(见上方 TODO)。
var seqCounter = uint64(time.Now().UnixNano())

func nextSeq() uint64 { return atomic.AddUint64(&seqCounter, 1) }

func genCode(prefix string) string {
	return fmt.Sprintf("%s%s%04d", prefix, time.Now().Format("20060102"), nextSeq()%10000)
}
