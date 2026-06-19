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

// Announcement 公告,移植自 Django apps.core.announcement.Announcement
// (db_table=core_announcement)。归入 OA 协同模块统一管理。
type Announcement struct {
	model.Base
	Title             string     `gorm:"column:title;size:200" json:"title"`
	Content           string     `gorm:"column:content" json:"content"`
	Summary           string     `gorm:"column:summary;size:500" json:"summary"`
	AnnouncementType  string     `gorm:"column:announcement_type;size:20" json:"announcement_type"`
	Priority          string     `gorm:"column:priority;size:20" json:"priority"`
	Status            string     `gorm:"column:status;size:20" json:"status"`
	PublishTime       *time.Time `gorm:"column:publish_time" json:"publish_time"`
	ExpireTime        *time.Time `gorm:"column:expire_time" json:"expire_time"`
	IsTop             bool       `gorm:"column:is_top" json:"is_top"`
	IsPopup           bool       `gorm:"column:is_popup" json:"is_popup"`
	TargetAll         bool       `gorm:"column:target_all" json:"target_all"`
	TargetDepartments JSONList   `gorm:"column:target_departments;type:jsonb" json:"target_departments"`
	TargetRoles       JSONList   `gorm:"column:target_roles;type:jsonb" json:"target_roles"`
	Attachments       JSONList   `gorm:"column:attachments;type:jsonb" json:"attachments"`
	ViewCount         int        `gorm:"column:view_count" json:"view_count"`
	PublisherID       *uint64    `gorm:"column:publisher_id" json:"publisher_id"`
}

// TableName 对齐 Django Meta.db_table。
func (Announcement) TableName() string { return "core_announcement" }

// Announcement 状态常量。
const (
	AnnouncementDraft     = "DRAFT"
	AnnouncementPublished = "PUBLISHED"
	AnnouncementExpired   = "EXPIRED"
	AnnouncementWithdrawn = "WITHDRAWN"
)

// =====================
// DTO
// =====================

// AnnouncementCreateInput 新建公告入参。
type AnnouncementCreateInput struct {
	Title             string     `json:"title" binding:"required"`
	Content           string     `json:"content" binding:"required"`
	Summary           string     `json:"summary"`
	AnnouncementType  string     `json:"announcement_type"`
	Priority          string     `json:"priority"`
	Status            string     `json:"status"`
	PublishTime       *time.Time `json:"publish_time"`
	ExpireTime        *time.Time `json:"expire_time"`
	IsTop             bool       `json:"is_top"`
	IsPopup           bool       `json:"is_popup"`
	TargetAll         *bool      `json:"target_all"`
	TargetDepartments JSONList   `json:"target_departments"`
	TargetRoles       JSONList   `json:"target_roles"`
	Attachments       JSONList   `json:"attachments"`
}

// AnnouncementUpdateInput 局部更新公告入参。
type AnnouncementUpdateInput struct {
	Title             *string    `json:"title"`
	Content           *string    `json:"content"`
	Summary           *string    `json:"summary"`
	AnnouncementType  *string    `json:"announcement_type"`
	Priority          *string    `json:"priority"`
	Status            *string    `json:"status"`
	PublishTime       *time.Time `json:"publish_time"`
	ExpireTime        *time.Time `json:"expire_time"`
	IsTop             *bool      `json:"is_top"`
	IsPopup           *bool      `json:"is_popup"`
	TargetAll         *bool      `json:"target_all"`
	TargetDepartments JSONList   `json:"target_departments"`
	TargetRoles       JSONList   `json:"target_roles"`
	Attachments       JSONList   `json:"attachments"`
}

// AnnouncementListQuery 列表筛选条件。
type AnnouncementListQuery struct {
	Keyword          string
	Status           string
	AnnouncementType string
	Priority         string
}

// =====================
// Repo
// =====================

// AnnouncementRepo 公告数据访问。
type AnnouncementRepo struct{ db *gorm.DB }

func NewAnnouncementRepo(db *gorm.DB) *AnnouncementRepo { return &AnnouncementRepo{db: db} }

func (r *AnnouncementRepo) scoped(ctx context.Context) *gorm.DB {
	q := r.db.WithContext(ctx).Model(&Announcement{})
	if u, ok := iam.AuthUserFrom(ctx); ok {
		q = iam.ApplyScope(q, u, scopeModule, "created_by_id")
	}
	return q
}

func (r *AnnouncementRepo) List(ctx context.Context, q AnnouncementListQuery, offset, limit int) ([]Announcement, int64, error) {
	tx := r.scoped(ctx)
	if q.Keyword != "" {
		kw := "%" + q.Keyword + "%"
		tx = tx.Where("title LIKE ? OR content LIKE ? OR summary LIKE ?", kw, kw, kw)
	}
	if q.Status != "" {
		tx = tx.Where("status = ?", q.Status)
	}
	if q.AnnouncementType != "" {
		tx = tx.Where("announcement_type = ?", q.AnnouncementType)
	}
	if q.Priority != "" {
		tx = tx.Where("priority = ?", q.Priority)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var rows []Announcement
	// 置顶优先,其后按创建时间倒序(对齐前端公告列表展示预期)。
	if err := tx.Order("is_top DESC, id DESC").Offset(offset).Limit(limit).Find(&rows).Error; err != nil {
		return nil, 0, err
	}
	return rows, total, nil
}

func (r *AnnouncementRepo) Get(ctx context.Context, id uint64) (*Announcement, error) {
	var a Announcement
	if err := r.scoped(ctx).Where("id = ?", id).First(&a).Error; err != nil {
		return nil, err
	}
	return &a, nil
}

func (r *AnnouncementRepo) Create(ctx context.Context, a *Announcement) error {
	return r.db.WithContext(ctx).Create(a).Error
}

func (r *AnnouncementRepo) Update(ctx context.Context, a *Announcement) error {
	return r.db.WithContext(ctx).Save(a).Error
}

func (r *AnnouncementRepo) SoftDelete(ctx context.Context, id uint64) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&Announcement{}).Error
}

// =====================
// Service
// =====================

var ErrAnnouncementNotFound = errors.New("公告不存在")

// AnnouncementService 公告业务逻辑。
type AnnouncementService struct{ repo *AnnouncementRepo }

func NewAnnouncementService(repo *AnnouncementRepo) *AnnouncementService {
	return &AnnouncementService{repo: repo}
}

func (s *AnnouncementService) List(ctx context.Context, q AnnouncementListQuery, offset, limit int) ([]Announcement, int64, error) {
	return s.repo.List(ctx, q, offset, limit)
}

func (s *AnnouncementService) Get(ctx context.Context, id uint64) (*Announcement, error) {
	a, err := s.repo.Get(ctx, id)
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, ErrAnnouncementNotFound
	}
	return a, err
}

func (s *AnnouncementService) Create(ctx context.Context, in AnnouncementCreateInput) (*Announcement, error) {
	targetAll := true
	if in.TargetAll != nil {
		targetAll = *in.TargetAll
	}
	a := &Announcement{
		Title:             in.Title,
		Content:           in.Content,
		Summary:           in.Summary,
		AnnouncementType:  orDefault(in.AnnouncementType, "NOTICE"),
		Priority:          orDefault(in.Priority, "NORMAL"),
		Status:            orDefault(in.Status, AnnouncementDraft),
		PublishTime:       in.PublishTime,
		ExpireTime:        in.ExpireTime,
		IsTop:             in.IsTop,
		IsPopup:           in.IsPopup,
		TargetAll:         targetAll,
		TargetDepartments: in.TargetDepartments,
		TargetRoles:       in.TargetRoles,
		Attachments:       in.Attachments,
	}
	if err := s.repo.Create(ctx, a); err != nil {
		return nil, err
	}
	return a, nil
}

func (s *AnnouncementService) Update(ctx context.Context, id uint64, in AnnouncementUpdateInput) (*Announcement, error) {
	a, err := s.Get(ctx, id)
	if err != nil {
		return nil, err
	}
	if in.Title != nil {
		a.Title = *in.Title
	}
	if in.Content != nil {
		a.Content = *in.Content
	}
	if in.Summary != nil {
		a.Summary = *in.Summary
	}
	if in.AnnouncementType != nil {
		a.AnnouncementType = *in.AnnouncementType
	}
	if in.Priority != nil {
		a.Priority = *in.Priority
	}
	if in.Status != nil {
		a.Status = *in.Status
	}
	if in.PublishTime != nil {
		a.PublishTime = in.PublishTime
	}
	if in.ExpireTime != nil {
		a.ExpireTime = in.ExpireTime
	}
	if in.IsTop != nil {
		a.IsTop = *in.IsTop
	}
	if in.IsPopup != nil {
		a.IsPopup = *in.IsPopup
	}
	if in.TargetAll != nil {
		a.TargetAll = *in.TargetAll
	}
	if in.TargetDepartments != nil {
		a.TargetDepartments = in.TargetDepartments
	}
	if in.TargetRoles != nil {
		a.TargetRoles = in.TargetRoles
	}
	if in.Attachments != nil {
		a.Attachments = in.Attachments
	}
	if err := s.repo.Update(ctx, a); err != nil {
		return nil, err
	}
	return a, nil
}

func (s *AnnouncementService) Delete(ctx context.Context, id uint64) error {
	if _, err := s.Get(ctx, id); err != nil {
		return err
	}
	return s.repo.SoftDelete(ctx, id)
}

// Publish 发布公告,移植 Django publish:仅 DRAFT/WITHDRAWN 可发布,
// 置 PUBLISHED 并记发布时间 + 发布人。
func (s *AnnouncementService) Publish(ctx context.Context, id uint64) (*Announcement, error) {
	a, err := s.Get(ctx, id)
	if err != nil {
		return nil, err
	}
	if a.Status != AnnouncementDraft && a.Status != AnnouncementWithdrawn {
		return nil, validationErr("只有草稿或已撤回的公告可以发布")
	}
	a.Status = AnnouncementPublished
	now := time.Now()
	a.PublishTime = &now
	if u, ok := iam.AuthUserFrom(ctx); ok {
		uid := u.ID
		a.PublisherID = &uid
	}
	if err := s.repo.Update(ctx, a); err != nil {
		return nil, err
	}
	return a, nil
}

// Withdraw 撤回公告,移植 Django withdraw:仅 PUBLISHED 可撤回。
func (s *AnnouncementService) Withdraw(ctx context.Context, id uint64) (*Announcement, error) {
	a, err := s.Get(ctx, id)
	if err != nil {
		return nil, err
	}
	if a.Status != AnnouncementPublished {
		return nil, validationErr("只有已发布的公告可以撤回")
	}
	a.Status = AnnouncementWithdrawn
	if err := s.repo.Update(ctx, a); err != nil {
		return nil, err
	}
	return a, nil
}

// =====================
// Handler
// =====================

// AnnouncementHandler 公告 REST 处理器。
type AnnouncementHandler struct{ svc *AnnouncementService }

func NewAnnouncementHandler(svc *AnnouncementService) *AnnouncementHandler {
	return &AnnouncementHandler{svc: svc}
}

func (h *AnnouncementHandler) List(c *gin.Context) {
	p := httpx.ParsePage(c)
	q := AnnouncementListQuery{
		Keyword:          c.Query("search"),
		Status:           c.Query("status"),
		AnnouncementType: c.Query("announcement_type"),
		Priority:         c.Query("priority"),
	}
	rows, total, err := h.svc.List(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[Announcement]{Count: total, Results: rows})
}

func (h *AnnouncementHandler) Retrieve(c *gin.Context) {
	a, err := h.svc.Get(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, http.StatusNotFound, err.Error())
		return
	}
	httpx.OK(c, a)
}

func (h *AnnouncementHandler) Create(c *gin.Context) {
	var in AnnouncementCreateInput
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

func (h *AnnouncementHandler) Update(c *gin.Context) {
	var in AnnouncementUpdateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	a, err := h.svc.Update(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusForAnnouncement(err), err.Error())
		return
	}
	httpx.OK(c, a)
}

func (h *AnnouncementHandler) Delete(c *gin.Context) {
	if err := h.svc.Delete(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusForAnnouncement(err), err.Error())
		return
	}
	httpx.NoContent(c)
}

func (h *AnnouncementHandler) Publish(c *gin.Context) {
	a, err := h.svc.Publish(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusForAnnouncement(err), err.Error())
		return
	}
	httpx.OK(c, a)
}

func (h *AnnouncementHandler) Withdraw(c *gin.Context) {
	a, err := h.svc.Withdraw(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusForAnnouncement(err), err.Error())
		return
	}
	httpx.OK(c, a)
}

// Register 挂载公告路由。
func (h *AnnouncementHandler) Register(rg *gin.RouterGroup, perm func(string) gin.HandlerFunc) {
	g := rg.Group("/oa/announcements")
	g.GET("", perm("oa:announcement:view"), h.List)
	g.GET("/:id", perm("oa:announcement:view"), h.Retrieve)
	g.POST("", perm("oa:announcement:create"), h.Create)
	g.PUT("/:id", perm("oa:announcement:update"), h.Update)
	g.DELETE("/:id", perm("oa:announcement:delete"), h.Delete)
	g.POST("/:id/publish", perm("oa:announcement:update"), h.Publish)
	g.POST("/:id/withdraw", perm("oa:announcement:update"), h.Withdraw)
	// TODO(verify): published/unread/popup/read/read_list/mark_all_read/statistics 等
	// 阅读态聚合动作依赖 AnnouncementRead(core_announcement_read)子实体,待补全。
}

func statusForAnnouncement(err error) int {
	return statusFor(err, ErrAnnouncementNotFound)
}
