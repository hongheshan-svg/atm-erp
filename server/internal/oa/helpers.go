package oa

import (
	"errors"
	"fmt"
	"net/http"
	"strconv"
	"sync/atomic"
	"time"

	"github.com/gin-gonic/gin"
)

// ErrValidation 表示业务校验失败,Handler 据此返回 400。
// 各 service 中状态机/前置条件不满足时返回包装此 sentinel 的错误。
var ErrValidation = errors.New("校验失败")

// validationErr 构造一个被 statusFor 识别为 400 的业务错误。
func validationErr(msg string) error {
	return fmt.Errorf("%w: %s", ErrValidation, msg)
}

func parseID(c *gin.Context) uint64 {
	id, _ := strconv.ParseUint(c.Param("id"), 10, 64)
	return id
}

// statusFor 将 service 错误映射到 HTTP 状态:notFound→404、校验失败→400、其余→500。
func statusFor(err error, notFound error) int {
	if errors.Is(err, notFound) {
		return http.StatusNotFound
	}
	if errors.Is(err, ErrValidation) {
		return http.StatusBadRequest
	}
	return http.StatusInternalServerError
}

func orDefault(v, def string) string {
	if v == "" {
		return def
	}
	return v
}

func orDefaultInt(v, def int) int {
	if v == 0 {
		return def
	}
	return v
}

// seq 为编号生成提供进程内自增,避免同毫秒冲突。
var seq uint64

// generateCode 复刻 Django apps.core.utils.generate_code 的“前缀+时间戳+序号”风格。
// TODO(verify): Django 实际通过 CodeRule 模型动态生成业务编号(含部门/年份规则)。
// 本实现为占位,共库切流前需对齐 CodeRule 的格式与去重策略,避免编号撞车。
func generateCode(prefix string) string {
	n := atomic.AddUint64(&seq, 1)
	return fmt.Sprintf("%s%s%04d", prefix, time.Now().Format("20060102150405"), n%10000)
}
