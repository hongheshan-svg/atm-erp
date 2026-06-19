package sales

import (
	"errors"
	"fmt"
	"strings"

	"gorm.io/gorm"
)

// 领域错误(handler 据此映射 HTTP 状态码)。
var (
	ErrNotFound      = errors.New("记录不存在")
	ErrInvalidState  = errors.New("当前状态不允许该操作")
	ErrValidation    = errors.New("校验失败")
	ErrProjectNeeded = errors.New("报价单必须关联项目才能转换为订单")
)

// 税率默认值,对齐 Django default=13。
const defaultTaxRate = 13

type Service struct{ repo *Repo }

func NewService(repo *Repo) *Service { return &Service{repo: repo} }

// errWrap 把领域哨兵错误与人类可读 detail 组合(errors.Is 仍可命中哨兵)。
func errWrap(sentinel error, detail string) error {
	return fmt.Errorf("%w: %s", sentinel, detail)
}

func notFoundOr(err error) error {
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return ErrNotFound
	}
	return err
}

// isDuplicateCode 判断是否为业务编号唯一键冲突(Postgres SQLSTATE 23505)。
// 临时进程内发号(genCode)在「同日 + 4 位序号回绕」下仍可能撞号,
// 故创建时遇唯一冲突需换号重试(切流改 CodeRule 持久化发号后可移除)。
func isDuplicateCode(err error) bool {
	if err == nil {
		return false
	}
	return strings.Contains(err.Error(), "23505") || strings.Contains(err.Error(), "duplicate key")
}

// createWithCodeRetry 反复「重设编号 → 创建」直至成功或非冲突错误。
// setCode 须把新编号写入实体;create 执行落库。
func createWithCodeRetry(setCode func(), create func() error) error {
	const maxAttempts = 5
	var err error
	for i := 0; i < maxAttempts; i++ {
		setCode()
		if err = create(); err == nil {
			return nil
		}
		if !isDuplicateCode(err) {
			return err
		}
	}
	return err
}

// computeTotals 由不含税金额与税率回算税额与含税总额(对齐序列化器口径)。
func computeTotals(amount float64, taxRate int) (tax, withTax float64) {
	tax = amount * float64(taxRate) / 100
	return tax, amount + tax
}
