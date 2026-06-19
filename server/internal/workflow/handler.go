package workflow

import (
	"errors"
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
)

// Handler 聚合四实体的 REST 处理(单 service 注入)。
type Handler struct{ svc *Service }

func NewHandler(svc *Service) *Handler { return &Handler{svc: svc} }

func parseID(c *gin.Context) uint64 {
	id, _ := strconv.ParseUint(c.Param("id"), 10, 64)
	return id
}

func parseUint64Query(c *gin.Context, key string) *uint64 {
	v := c.Query(key)
	if v == "" {
		return nil
	}
	n, err := strconv.ParseUint(v, 10, 64)
	if err != nil {
		return nil
	}
	return &n
}

func parseBoolQuery(c *gin.Context, key string) *bool {
	v := c.Query(key)
	if v == "" {
		return nil
	}
	b, err := strconv.ParseBool(v)
	if err != nil {
		return nil
	}
	return &b
}

// statusFor 把领域错误映射为 HTTP 状态码。
func statusFor(err error) int {
	switch {
	case errors.Is(err, ErrDefinitionNotFound),
		errors.Is(err, ErrStepNotFound),
		errors.Is(err, ErrInstanceNotFound),
		errors.Is(err, ErrTaskNotFound):
		return http.StatusNotFound
	case errors.Is(err, ErrNoPermission), errors.Is(err, ErrNotSubmitter):
		return http.StatusForbidden
	case errors.Is(err, ErrAlreadyActive),
		errors.Is(err, ErrTaskHandled),
		errors.Is(err, ErrNotPending),
		errors.Is(err, ErrRejectNeedReason),
		errors.Is(err, ErrNoWorkflow):
		return http.StatusBadRequest
	default:
		return http.StatusInternalServerError
	}
}
