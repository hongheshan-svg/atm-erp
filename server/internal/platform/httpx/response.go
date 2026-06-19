// Package httpx 提供统一响应信封与分页,对齐 DRF StandardPagination,保证前端零改。
package httpx

import (
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
)

// Page 对齐 DRF 分页响应 {count,next,previous,results}。
type Page[T any] struct {
	Count    int64   `json:"count"`
	Next     *string `json:"next"`
	Previous *string `json:"previous"`
	Results  []T     `json:"results"`
}

const (
	DefaultPageSize = 20
	MaxPageSize     = 1000
)

type PageParams struct {
	Page     int
	PageSize int
}

func ParsePage(c *gin.Context) PageParams {
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	if page < 1 {
		page = 1
	}
	size, _ := strconv.Atoi(c.DefaultQuery("page_size", strconv.Itoa(DefaultPageSize)))
	if size < 1 {
		size = DefaultPageSize
	}
	if size > MaxPageSize {
		size = MaxPageSize
	}
	return PageParams{Page: page, PageSize: size}
}

func (p PageParams) Offset() int { return (p.Page - 1) * p.PageSize }

func OK(c *gin.Context, data any)      { c.JSON(http.StatusOK, data) }
func Created(c *gin.Context, data any) { c.JSON(http.StatusCreated, data) }
func NoContent(c *gin.Context)         { c.Status(http.StatusNoContent) }

// Error 以 DRF 风格 {detail} 返回错误,前端 request.ts 拦截器已固化解析。
func Error(c *gin.Context, status int, detail string) {
	c.AbortWithStatusJSON(status, gin.H{"detail": detail})
}
