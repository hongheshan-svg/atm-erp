package oa

import (
	"context"
	"errors"
	"net/http"
	"time"

	"github.com/atm-erp/server/internal/iam"
	"github.com/atm-erp/server/internal/platform/httpx"
	"github.com/atm-erp/server/internal/platform/model"
	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
)

// =====================
// Model
// =====================

// Archive 电子档案,对齐 Django oa.Archive(db_table=oa_archive)。
type Archive struct {
	model.Base
	ArchiveNo       string     `gorm:"column:archive_no;size:50;uniqueIndex" json:"archive_no"`
	Title           string     `gorm:"column:title;size:200" json:"title"`
	CategoryID      *uint64    `gorm:"column:category_id" json:"category_id"`
	FilePath        string     `gorm:"column:file_path;size:500" json:"file_path"`
	FileSize        int64      `gorm:"column:file_size" json:"file_size"`
	FileType        string     `gorm:"column:file_type;size:50" json:"file_type"`
	PageCount       int        `gorm:"column:page_count" json:"page_count"`
	SourceType      string     `gorm:"column:source_type;size:50" json:"source_type"`
	SourceID        *int       `gorm:"column:source_id" json:"source_id"`
	SourceRef       string     `gorm:"column:source_ref;size:100" json:"source_ref"`
	Status          string     `gorm:"column:status;size:20" json:"status"`
	SecurityLevel   string     `gorm:"column:security_level;size:20" json:"security_level"`
	ArchiveDate     *time.Time `gorm:"column:archive_date" json:"archive_date"`
	ExpiryDate      *time.Time `gorm:"column:expiry_date" json:"expiry_date"`
	StorageLocation string     `gorm:"column:storage_location;size:200" json:"storage_location"`
	CabinetNo       string     `gorm:"column:cabinet_no;size:50" json:"cabinet_no"`
	ShelfNo         string     `gorm:"column:shelf_no;size:50" json:"shelf_no"`
	BoxNo           string     `gorm:"column:box_no;size:50" json:"box_no"`
	CustodianID     *uint64    `gorm:"column:custodian_id" json:"custodian_id"`
	Keywords        JSONList   `gorm:"column:keywords;type:jsonb" json:"keywords"`
	Abstract        string     `gorm:"column:abstract" json:"abstract"`
	Notes           string     `gorm:"column:notes" json:"notes"`
	BorrowCount     int        `gorm:"column:borrow_count" json:"borrow_count"`
	ViewCount       int        `gorm:"column:view_count" json:"view_count"`
}

// TableName 对齐 Django Meta.db_table。
func (Archive) TableName() string { return "oa_archive" }

// Archive 状态常量。
const (
	ArchivePending   = "PENDING"
	ArchiveArchived  = "ARCHIVED"
	ArchiveBorrowed  = "BORROWED"
	ArchiveExpired   = "EXPIRED"
	ArchiveDestroyed = "DESTROYED"
)

// =====================
// DTO
// =====================

// ArchiveCreateInput 新建档案入参。archive_no 服务端生成。
type ArchiveCreateInput struct {
	Title           string     `json:"title" binding:"required"`
	CategoryID      *uint64    `json:"category_id"`
	FilePath        string     `json:"file_path"`
	FileSize        int64      `json:"file_size"`
	FileType        string     `json:"file_type"`
	PageCount       int        `json:"page_count"`
	SourceType      string     `json:"source_type"`
	SourceID        *int       `json:"source_id"`
	SourceRef       string     `json:"source_ref"`
	Status          string     `json:"status"`
	SecurityLevel   string     `json:"security_level"`
	ArchiveDate     *time.Time `json:"archive_date"`
	ExpiryDate      *time.Time `json:"expiry_date"`
	StorageLocation string     `json:"storage_location"`
	CabinetNo       string     `json:"cabinet_no"`
	ShelfNo         string     `json:"shelf_no"`
	BoxNo           string     `json:"box_no"`
	CustodianID     *uint64    `json:"custodian_id"`
	Keywords        JSONList   `json:"keywords"`
	Abstract        string     `json:"abstract"`
	Notes           string     `json:"notes"`
}

// ArchiveUpdateInput 局部更新档案入参。
type ArchiveUpdateInput struct {
	Title           *string    `json:"title"`
	CategoryID      *uint64    `json:"category_id"`
	FilePath        *string    `json:"file_path"`
	FileSize        *int64     `json:"file_size"`
	FileType        *string    `json:"file_type"`
	PageCount       *int       `json:"page_count"`
	SourceType      *string    `json:"source_type"`
	SourceID        *int       `json:"source_id"`
	SourceRef       *string    `json:"source_ref"`
	Status          *string    `json:"status"`
	SecurityLevel   *string    `json:"security_level"`
	ArchiveDate     *time.Time `json:"archive_date"`
	ExpiryDate      *time.Time `json:"expiry_date"`
	StorageLocation *string    `json:"storage_location"`
	CabinetNo       *string    `json:"cabinet_no"`
	ShelfNo         *string    `json:"shelf_no"`
	BoxNo           *string    `json:"box_no"`
	CustodianID     *uint64    `json:"custodian_id"`
	Keywords        JSONList   `json:"keywords"`
	Abstract        *string    `json:"abstract"`
	Notes           *string    `json:"notes"`
}

// ArchiveListQuery 列表筛选条件。
type ArchiveListQuery struct {
	Keyword       string
	Status        string
	CategoryID    string
	SecurityLevel string
}

// =====================
// Repo
// =====================

// ArchiveRepo 档案数据访问。
type ArchiveRepo struct{ db *gorm.DB }

func NewArchiveRepo(db *gorm.DB) *ArchiveRepo { return &ArchiveRepo{db: db} }

func (r *ArchiveRepo) scoped(ctx context.Context) *gorm.DB {
	q := r.db.WithContext(ctx).Model(&Archive{})
	if u, ok := iam.AuthUserFrom(ctx); ok {
		q = iam.ApplyScope(q, u, scopeModule, "created_by")
	}
	return q
}

func (r *ArchiveRepo) List(ctx context.Context, q ArchiveListQuery, offset, limit int) ([]Archive, int64, error) {
	tx := r.scoped(ctx)
	if q.Keyword != "" {
		kw := "%" + q.Keyword + "%"
		tx = tx.Where("archive_no LIKE ? OR title LIKE ? OR abstract LIKE ?", kw, kw, kw)
	}
	if q.Status != "" {
		tx = tx.Where("status = ?", q.Status)
	}
	if q.CategoryID != "" {
		tx = tx.Where("category_id = ?", q.CategoryID)
	}
	if q.SecurityLevel != "" {
		tx = tx.Where("security_level = ?", q.SecurityLevel)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var rows []Archive
	if err := tx.Order("archive_date DESC, id DESC").Offset(offset).Limit(limit).Find(&rows).Error; err != nil {
		return nil, 0, err
	}
	return rows, total, nil
}

func (r *ArchiveRepo) Get(ctx context.Context, id uint64) (*Archive, error) {
	var a Archive
	if err := r.scoped(ctx).Where("id = ?", id).First(&a).Error; err != nil {
		return nil, err
	}
	return &a, nil
}

func (r *ArchiveRepo) Create(ctx context.Context, a *Archive) error {
	return r.db.WithContext(ctx).Create(a).Error
}

func (r *ArchiveRepo) Update(ctx context.Context, a *Archive) error {
	return r.db.WithContext(ctx).Save(a).Error
}

func (r *ArchiveRepo) SoftDelete(ctx context.Context, id uint64) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&Archive{}).Error
}

// =====================
// Service
// =====================

var ErrArchiveNotFound = errors.New("档案不存在")

// ArchiveService 档案业务逻辑。
type ArchiveService struct{ repo *ArchiveRepo }

func NewArchiveService(repo *ArchiveRepo) *ArchiveService { return &ArchiveService{repo: repo} }

func (s *ArchiveService) List(ctx context.Context, q ArchiveListQuery, offset, limit int) ([]Archive, int64, error) {
	return s.repo.List(ctx, q, offset, limit)
}

func (s *ArchiveService) Get(ctx context.Context, id uint64) (*Archive, error) {
	a, err := s.repo.Get(ctx, id)
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, ErrArchiveNotFound
	}
	return a, err
}

func (s *ArchiveService) Create(ctx context.Context, in ArchiveCreateInput) (*Archive, error) {
	a := &Archive{
		ArchiveNo:       generateCode("ARC"),
		Title:           in.Title,
		CategoryID:      in.CategoryID,
		FilePath:        in.FilePath,
		FileSize:        in.FileSize,
		FileType:        in.FileType,
		PageCount:       orDefaultInt(in.PageCount, 1),
		SourceType:      in.SourceType,
		SourceID:        in.SourceID,
		SourceRef:       in.SourceRef,
		Status:          orDefault(in.Status, ArchivePending),
		SecurityLevel:   orDefault(in.SecurityLevel, "INTERNAL"),
		ArchiveDate:     in.ArchiveDate,
		ExpiryDate:      in.ExpiryDate,
		StorageLocation: in.StorageLocation,
		CabinetNo:       in.CabinetNo,
		ShelfNo:         in.ShelfNo,
		BoxNo:           in.BoxNo,
		CustodianID:     in.CustodianID,
		Keywords:        in.Keywords,
		Abstract:        in.Abstract,
		Notes:           in.Notes,
	}
	// TODO(verify): Django Archive.save 在 archive_date+category 存在且未填 expiry_date 时,
	// 按 category.retention_years 自动推算到期日。此处缺少 ArchiveCategory 跨实体读取
	// (本轮不跨模块依赖),保留入参 expiry_date 原样;待 ArchiveCategory 子实体落地后补全。
	if err := s.repo.Create(ctx, a); err != nil {
		return nil, err
	}
	return a, nil
}

func (s *ArchiveService) Update(ctx context.Context, id uint64, in ArchiveUpdateInput) (*Archive, error) {
	a, err := s.Get(ctx, id)
	if err != nil {
		return nil, err
	}
	if in.Title != nil {
		a.Title = *in.Title
	}
	if in.CategoryID != nil {
		a.CategoryID = in.CategoryID
	}
	if in.FilePath != nil {
		a.FilePath = *in.FilePath
	}
	if in.FileSize != nil {
		a.FileSize = *in.FileSize
	}
	if in.FileType != nil {
		a.FileType = *in.FileType
	}
	if in.PageCount != nil {
		a.PageCount = *in.PageCount
	}
	if in.SourceType != nil {
		a.SourceType = *in.SourceType
	}
	if in.SourceID != nil {
		a.SourceID = in.SourceID
	}
	if in.SourceRef != nil {
		a.SourceRef = *in.SourceRef
	}
	if in.Status != nil {
		a.Status = *in.Status
	}
	if in.SecurityLevel != nil {
		a.SecurityLevel = *in.SecurityLevel
	}
	if in.ArchiveDate != nil {
		a.ArchiveDate = in.ArchiveDate
	}
	if in.ExpiryDate != nil {
		a.ExpiryDate = in.ExpiryDate
	}
	if in.StorageLocation != nil {
		a.StorageLocation = *in.StorageLocation
	}
	if in.CabinetNo != nil {
		a.CabinetNo = *in.CabinetNo
	}
	if in.ShelfNo != nil {
		a.ShelfNo = *in.ShelfNo
	}
	if in.BoxNo != nil {
		a.BoxNo = *in.BoxNo
	}
	if in.CustodianID != nil {
		a.CustodianID = in.CustodianID
	}
	if in.Keywords != nil {
		a.Keywords = in.Keywords
	}
	if in.Abstract != nil {
		a.Abstract = *in.Abstract
	}
	if in.Notes != nil {
		a.Notes = *in.Notes
	}
	if err := s.repo.Update(ctx, a); err != nil {
		return nil, err
	}
	return a, nil
}

func (s *ArchiveService) Delete(ctx context.Context, id uint64) error {
	if _, err := s.Get(ctx, id); err != nil {
		return err
	}
	return s.repo.SoftDelete(ctx, id)
}

// Archive 归档动作,移植 Django archive:置 ARCHIVED 并记归档日期。
func (s *ArchiveService) Archive(ctx context.Context, id uint64) (*Archive, error) {
	a, err := s.Get(ctx, id)
	if err != nil {
		return nil, err
	}
	a.Status = ArchiveArchived
	if a.ArchiveDate == nil {
		now := time.Now()
		a.ArchiveDate = &now
	}
	if err := s.repo.Update(ctx, a); err != nil {
		return nil, err
	}
	return a, nil
}

// =====================
// Handler
// =====================

// ArchiveHandler 档案 REST 处理器。
type ArchiveHandler struct{ svc *ArchiveService }

func NewArchiveHandler(svc *ArchiveService) *ArchiveHandler { return &ArchiveHandler{svc: svc} }

func (h *ArchiveHandler) List(c *gin.Context) {
	p := httpx.ParsePage(c)
	q := ArchiveListQuery{
		Keyword:       c.Query("search"),
		Status:        c.Query("status"),
		CategoryID:    c.Query("category"),
		SecurityLevel: c.Query("security_level"),
	}
	rows, total, err := h.svc.List(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[Archive]{Count: total, Results: rows})
}

func (h *ArchiveHandler) Retrieve(c *gin.Context) {
	a, err := h.svc.Get(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, http.StatusNotFound, err.Error())
		return
	}
	httpx.OK(c, a)
}

func (h *ArchiveHandler) Create(c *gin.Context) {
	var in ArchiveCreateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	a, err := h.svc.Create(c.Request.Context(), in)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.Created(c, a)
}

func (h *ArchiveHandler) Update(c *gin.Context) {
	var in ArchiveUpdateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	a, err := h.svc.Update(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusForArchive(err), err.Error())
		return
	}
	httpx.OK(c, a)
}

func (h *ArchiveHandler) Delete(c *gin.Context) {
	if err := h.svc.Delete(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusForArchive(err), err.Error())
		return
	}
	httpx.NoContent(c)
}

func (h *ArchiveHandler) Archive(c *gin.Context) {
	a, err := h.svc.Archive(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusForArchive(err), err.Error())
		return
	}
	httpx.OK(c, a)
}

// Register 挂载档案路由。
func (h *ArchiveHandler) Register(rg *gin.RouterGroup, perm func(string) gin.HandlerFunc) {
	g := rg.Group("/oa/archives")
	g.GET("", perm("oa:archive:view"), h.List)
	g.GET("/:id", perm("oa:archive:view"), h.Retrieve)
	g.POST("", perm("oa:archive:create"), h.Create)
	g.PUT("/:id", perm("oa:archive:update"), h.Update)
	g.DELETE("/:id", perm("oa:archive:delete"), h.Delete)
	g.POST("/:id/archive", perm("oa:archive:update"), h.Archive)
	// TODO(verify): expiring/statistics 只读聚合,以及 ArchiveBorrow/ArchiveTransfer/
	// ArchiveDestruction(含 M2M)等子实体与审批流待补全。
}

func statusForArchive(err error) int {
	return statusFor(err, ErrArchiveNotFound)
}
