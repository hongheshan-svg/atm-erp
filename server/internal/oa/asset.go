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

// Asset 办公资产,对齐 Django oa.Asset(db_table=oa_asset)。
type Asset struct {
	model.Base
	AssetNo            string     `gorm:"column:asset_no;size:50;uniqueIndex" json:"asset_no"`
	Name               string     `gorm:"column:name;size:200" json:"name"`
	CategoryID         *uint64    `gorm:"column:category_id" json:"category_id"`
	Brand              string     `gorm:"column:brand;size:50" json:"brand"`
	Model              string     `gorm:"column:model;size:100" json:"model"`
	Specification      string     `gorm:"column:specification;size:200" json:"specification"`
	SerialNo           string     `gorm:"column:serial_no;size:100" json:"serial_no"`
	PurchaseDate       *time.Time `gorm:"column:purchase_date" json:"purchase_date"`
	PurchasePrice      float64    `gorm:"column:purchase_price" json:"purchase_price"`
	SupplierID         *uint64    `gorm:"column:supplier_id" json:"supplier_id"`
	WarrantyExpireDate *time.Time `gorm:"column:warranty_expire_date" json:"warranty_expire_date"`
	DepreciationMethod string     `gorm:"column:depreciation_method;size:20" json:"depreciation_method"`
	DepreciationYears  int        `gorm:"column:depreciation_years" json:"depreciation_years"`
	ResidualRate       float64    `gorm:"column:residual_rate" json:"residual_rate"`
	CurrentValue       float64    `gorm:"column:current_value" json:"current_value"`
	Location           string     `gorm:"column:location;size:200" json:"location"`
	DepartmentName     string     `gorm:"column:department_name;size:100" json:"department_name"`
	CurrentUserID      *uint64    `gorm:"column:current_user_id" json:"current_user_id"`
	Status             string     `gorm:"column:status;size:20" json:"status"`
	Image              string     `gorm:"column:image;size:500" json:"image"`
	Attachments        JSONList   `gorm:"column:attachments;type:jsonb" json:"attachments"`
	Notes              string     `gorm:"column:notes" json:"notes"`
}

// TableName 对齐 Django Meta.db_table。
func (Asset) TableName() string { return "oa_asset" }

// Asset 状态常量。
const (
	AssetIdle     = "IDLE"
	AssetInUse    = "IN_USE"
	AssetRepair   = "REPAIR"
	AssetScrapped = "SCRAPPED"
	AssetLost     = "LOST"
)

// =====================
// DTO
// =====================

// AssetCreateInput 新建资产入参。asset_no 由服务端生成(对齐 read_only)。
type AssetCreateInput struct {
	Name               string     `json:"name" binding:"required"`
	CategoryID         *uint64    `json:"category_id"`
	Brand              string     `json:"brand"`
	Model              string     `json:"model"`
	Specification      string     `json:"specification"`
	SerialNo           string     `json:"serial_no"`
	PurchaseDate       *time.Time `json:"purchase_date"`
	PurchasePrice      float64    `json:"purchase_price"`
	SupplierID         *uint64    `json:"supplier_id"`
	WarrantyExpireDate *time.Time `json:"warranty_expire_date"`
	DepreciationMethod string     `json:"depreciation_method"`
	DepreciationYears  int        `json:"depreciation_years"`
	ResidualRate       float64    `json:"residual_rate"`
	CurrentValue       float64    `json:"current_value"`
	Location           string     `json:"location"`
	DepartmentName     string     `json:"department_name"`
	CurrentUserID      *uint64    `json:"current_user_id"`
	Status             string     `json:"status"`
	Image              string     `json:"image"`
	Attachments        JSONList   `json:"attachments"`
	Notes              string     `json:"notes"`
}

// AssetUpdateInput 局部更新资产入参。
type AssetUpdateInput struct {
	Name               *string    `json:"name"`
	CategoryID         *uint64    `json:"category_id"`
	Brand              *string    `json:"brand"`
	Model              *string    `json:"model"`
	Specification      *string    `json:"specification"`
	SerialNo           *string    `json:"serial_no"`
	PurchaseDate       *time.Time `json:"purchase_date"`
	PurchasePrice      *float64   `json:"purchase_price"`
	SupplierID         *uint64    `json:"supplier_id"`
	WarrantyExpireDate *time.Time `json:"warranty_expire_date"`
	DepreciationMethod *string    `json:"depreciation_method"`
	DepreciationYears  *int       `json:"depreciation_years"`
	ResidualRate       *float64   `json:"residual_rate"`
	CurrentValue       *float64   `json:"current_value"`
	Location           *string    `json:"location"`
	DepartmentName     *string    `json:"department_name"`
	CurrentUserID      *uint64    `json:"current_user_id"`
	Status             *string    `json:"status"`
	Image              *string    `json:"image"`
	Attachments        JSONList   `json:"attachments"`
	Notes              *string    `json:"notes"`
}

// AssetListQuery 列表筛选条件。
type AssetListQuery struct {
	Keyword       string
	Status        string
	CategoryID    string
	CurrentUserID string
}

// =====================
// Repo
// =====================

// AssetRepo 资产数据访问。
type AssetRepo struct{ db *gorm.DB }

func NewAssetRepo(db *gorm.DB) *AssetRepo { return &AssetRepo{db: db} }

func (r *AssetRepo) scoped(ctx context.Context) *gorm.DB {
	q := r.db.WithContext(ctx).Model(&Asset{})
	if u, ok := iam.AuthUserFrom(ctx); ok {
		q = iam.ApplyScope(q, u, scopeModule, "created_by_id")
	}
	return q
}

func (r *AssetRepo) List(ctx context.Context, q AssetListQuery, offset, limit int) ([]Asset, int64, error) {
	tx := r.scoped(ctx)
	if q.Keyword != "" {
		kw := "%" + q.Keyword + "%"
		tx = tx.Where(
			"asset_no LIKE ? OR name LIKE ? OR brand LIKE ? OR model LIKE ? OR serial_no LIKE ? OR department_name LIKE ?",
			kw, kw, kw, kw, kw, kw,
		)
	}
	if q.Status != "" {
		tx = tx.Where("status = ?", q.Status)
	}
	if q.CategoryID != "" {
		tx = tx.Where("category_id = ?", q.CategoryID)
	}
	if q.CurrentUserID != "" {
		tx = tx.Where("current_user_id = ?", q.CurrentUserID)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var rows []Asset
	if err := tx.Order("id DESC").Offset(offset).Limit(limit).Find(&rows).Error; err != nil {
		return nil, 0, err
	}
	return rows, total, nil
}

func (r *AssetRepo) Get(ctx context.Context, id uint64) (*Asset, error) {
	var a Asset
	if err := r.scoped(ctx).Where("id = ?", id).First(&a).Error; err != nil {
		return nil, err
	}
	return &a, nil
}

func (r *AssetRepo) Create(ctx context.Context, a *Asset) error {
	return r.db.WithContext(ctx).Create(a).Error
}

func (r *AssetRepo) Update(ctx context.Context, a *Asset) error {
	return r.db.WithContext(ctx).Save(a).Error
}

func (r *AssetRepo) SoftDelete(ctx context.Context, id uint64) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&Asset{}).Error
}

// =====================
// Service
// =====================

var ErrAssetNotFound = errors.New("资产不存在")

// AssetService 资产业务逻辑。
type AssetService struct{ repo *AssetRepo }

func NewAssetService(repo *AssetRepo) *AssetService { return &AssetService{repo: repo} }

func (s *AssetService) List(ctx context.Context, q AssetListQuery, offset, limit int) ([]Asset, int64, error) {
	return s.repo.List(ctx, q, offset, limit)
}

func (s *AssetService) Get(ctx context.Context, id uint64) (*Asset, error) {
	a, err := s.repo.Get(ctx, id)
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, ErrAssetNotFound
	}
	return a, err
}

func (s *AssetService) Create(ctx context.Context, in AssetCreateInput) (*Asset, error) {
	a := &Asset{
		AssetNo:            generateCode("AST"),
		Name:               in.Name,
		CategoryID:         in.CategoryID,
		Brand:              in.Brand,
		Model:              in.Model,
		Specification:      in.Specification,
		SerialNo:           in.SerialNo,
		PurchaseDate:       in.PurchaseDate,
		PurchasePrice:      in.PurchasePrice,
		SupplierID:         in.SupplierID,
		WarrantyExpireDate: in.WarrantyExpireDate,
		DepreciationMethod: orDefault(in.DepreciationMethod, "STRAIGHT"),
		DepreciationYears:  orDefaultInt(in.DepreciationYears, 5),
		ResidualRate:       in.ResidualRate,
		CurrentValue:       in.CurrentValue,
		Location:           in.Location,
		DepartmentName:     in.DepartmentName,
		CurrentUserID:      in.CurrentUserID,
		Status:             orDefault(in.Status, AssetIdle),
		Image:              in.Image,
		Attachments:        in.Attachments,
		Notes:              in.Notes,
	}
	// 移植 Asset.save:current_value 未设置时回退为 purchase_price。
	if a.CurrentValue == 0 && a.PurchasePrice != 0 {
		a.CurrentValue = a.PurchasePrice
	}
	if err := s.repo.Create(ctx, a); err != nil {
		return nil, err
	}
	return a, nil
}

func (s *AssetService) Update(ctx context.Context, id uint64, in AssetUpdateInput) (*Asset, error) {
	a, err := s.Get(ctx, id)
	if err != nil {
		return nil, err
	}
	if in.Name != nil {
		a.Name = *in.Name
	}
	if in.CategoryID != nil {
		a.CategoryID = in.CategoryID
	}
	if in.Brand != nil {
		a.Brand = *in.Brand
	}
	if in.Model != nil {
		a.Model = *in.Model
	}
	if in.Specification != nil {
		a.Specification = *in.Specification
	}
	if in.SerialNo != nil {
		a.SerialNo = *in.SerialNo
	}
	if in.PurchaseDate != nil {
		a.PurchaseDate = in.PurchaseDate
	}
	if in.PurchasePrice != nil {
		a.PurchasePrice = *in.PurchasePrice
	}
	if in.SupplierID != nil {
		a.SupplierID = in.SupplierID
	}
	if in.WarrantyExpireDate != nil {
		a.WarrantyExpireDate = in.WarrantyExpireDate
	}
	if in.DepreciationMethod != nil {
		a.DepreciationMethod = *in.DepreciationMethod
	}
	if in.DepreciationYears != nil {
		a.DepreciationYears = *in.DepreciationYears
	}
	if in.ResidualRate != nil {
		a.ResidualRate = *in.ResidualRate
	}
	if in.CurrentValue != nil {
		a.CurrentValue = *in.CurrentValue
	}
	if in.Location != nil {
		a.Location = *in.Location
	}
	if in.DepartmentName != nil {
		a.DepartmentName = *in.DepartmentName
	}
	if in.CurrentUserID != nil {
		a.CurrentUserID = in.CurrentUserID
	}
	if in.Status != nil {
		a.Status = *in.Status
	}
	if in.Image != nil {
		a.Image = *in.Image
	}
	if in.Attachments != nil {
		a.Attachments = in.Attachments
	}
	if in.Notes != nil {
		a.Notes = *in.Notes
	}
	if err := s.repo.Update(ctx, a); err != nil {
		return nil, err
	}
	return a, nil
}

func (s *AssetService) Delete(ctx context.Context, id uint64) error {
	if _, err := s.Get(ctx, id); err != nil {
		return err
	}
	return s.repo.SoftDelete(ctx, id)
}

// Assign 分配资产给用户(状态置 IN_USE),移植 Django assign。
func (s *AssetService) Assign(ctx context.Context, id, userID uint64) (*Asset, error) {
	a, err := s.Get(ctx, id)
	if err != nil {
		return nil, err
	}
	if userID == 0 {
		return nil, validationErr("用户不存在")
	}
	uid := userID
	a.CurrentUserID = &uid
	a.Status = AssetInUse
	if err := s.repo.Update(ctx, a); err != nil {
		return nil, err
	}
	return a, nil
}

// Reclaim 回收资产(置闲置),移植 Django reclaim。
func (s *AssetService) Reclaim(ctx context.Context, id uint64) (*Asset, error) {
	a, err := s.Get(ctx, id)
	if err != nil {
		return nil, err
	}
	a.CurrentUserID = nil
	a.Status = AssetIdle
	if err := s.repo.Update(ctx, a); err != nil {
		return nil, err
	}
	return a, nil
}

// Scrap 报废资产(当前价值清零),移植 Django scrap。
func (s *AssetService) Scrap(ctx context.Context, id uint64) (*Asset, error) {
	a, err := s.Get(ctx, id)
	if err != nil {
		return nil, err
	}
	a.Status = AssetScrapped
	a.CurrentValue = 0
	if err := s.repo.Update(ctx, a); err != nil {
		return nil, err
	}
	return a, nil
}

// =====================
// Handler
// =====================

// AssetHandler 资产 REST 处理器。
type AssetHandler struct{ svc *AssetService }

func NewAssetHandler(svc *AssetService) *AssetHandler { return &AssetHandler{svc: svc} }

func (h *AssetHandler) List(c *gin.Context) {
	p := httpx.ParsePage(c)
	q := AssetListQuery{
		Keyword:       c.Query("search"),
		Status:        c.Query("status"),
		CategoryID:    c.Query("category"),
		CurrentUserID: c.Query("current_user"),
	}
	rows, total, err := h.svc.List(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[Asset]{Count: total, Results: rows})
}

func (h *AssetHandler) Retrieve(c *gin.Context) {
	a, err := h.svc.Get(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, http.StatusNotFound, err.Error())
		return
	}
	httpx.OK(c, a)
}

func (h *AssetHandler) Create(c *gin.Context) {
	var in AssetCreateInput
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

func (h *AssetHandler) Update(c *gin.Context) {
	var in AssetUpdateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	a, err := h.svc.Update(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusForAsset(err), err.Error())
		return
	}
	httpx.OK(c, a)
}

func (h *AssetHandler) Delete(c *gin.Context) {
	if err := h.svc.Delete(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusForAsset(err), err.Error())
		return
	}
	httpx.NoContent(c)
}

func (h *AssetHandler) Assign(c *gin.Context) {
	var body struct {
		UserID uint64 `json:"user_id"`
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	a, err := h.svc.Assign(c.Request.Context(), parseID(c), body.UserID)
	if err != nil {
		httpx.Error(c, statusForAsset(err), err.Error())
		return
	}
	httpx.OK(c, a)
}

func (h *AssetHandler) Reclaim(c *gin.Context) {
	a, err := h.svc.Reclaim(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusForAsset(err), err.Error())
		return
	}
	httpx.OK(c, a)
}

func (h *AssetHandler) Scrap(c *gin.Context) {
	a, err := h.svc.Scrap(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, statusForAsset(err), err.Error())
		return
	}
	httpx.OK(c, a)
}

// Register 挂载资产路由。
func (h *AssetHandler) Register(rg *gin.RouterGroup, perm func(string) gin.HandlerFunc) {
	g := rg.Group("/oa/assets")
	g.GET("", perm("oa:asset:view"), h.List)
	g.GET("/:id", perm("oa:asset:view"), h.Retrieve)
	g.POST("", perm("oa:asset:create"), h.Create)
	g.PUT("/:id", perm("oa:asset:update"), h.Update)
	g.DELETE("/:id", perm("oa:asset:delete"), h.Delete)
	g.POST("/:id/assign", perm("oa:asset:update"), h.Assign)
	g.POST("/:id/reclaim", perm("oa:asset:update"), h.Reclaim)
	g.POST("/:id/scrap", perm("oa:asset:update"), h.Scrap)
	// TODO(verify): idle/my_assets/warranty_expiring/statistics 等只读聚合动作,
	// 以及借用 AssetBorrow / 调拨 AssetTransfer / 维修 AssetMaintenance 子实体待补全。
}

func statusForAsset(err error) int {
	return statusFor(err, ErrAssetNotFound)
}
