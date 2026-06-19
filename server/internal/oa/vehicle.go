// Package oa 是「OA与协同」限界上下文的 Go 实现,移植自 Django apps.oa 与
// apps.core.announcement。包含车辆 Vehicle、办公资产 Asset、电子档案 Archive、
// 公告 Announcement 四个主要实体的 model→repo→service→handler 垂直切片。
//
// 数据范围:统一走 iam.ApplyScope,scopeModule="oa";权限码 oa:<entity>:<action>。
// 软删除:沿用 model.Base 的 gorm.DeletedAt + is_deleted 双写(与 Django 互认)。
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

// scopeModule 标识 OA 所有资源所属权限/数据范围模块。
const scopeModule = "oa"

// =====================
// Model
// =====================

// Vehicle 车辆信息,对齐 Django oa.Vehicle(db_table=oa_vehicle)。
type Vehicle struct {
	model.Base
	PlateNumber          string     `gorm:"column:plate_number;size:20;uniqueIndex" json:"plate_number"`
	VehicleType          string     `gorm:"column:vehicle_type;size:20" json:"vehicle_type"`
	Brand                string     `gorm:"column:brand;size:50" json:"brand"`
	Model                string     `gorm:"column:model;size:50" json:"model"`
	Color                string     `gorm:"column:color;size:20" json:"color"`
	Seats                int        `gorm:"column:seats" json:"seats"`
	EngineNo             string     `gorm:"column:engine_no;size:50" json:"engine_no"`
	VIN                  string     `gorm:"column:vin;size:50" json:"vin"`
	InsuranceCompany     string     `gorm:"column:insurance_company;size:100" json:"insurance_company"`
	InsuranceNo          string     `gorm:"column:insurance_no;size:50" json:"insurance_no"`
	InsuranceExpireDate  *time.Time `gorm:"column:insurance_expire_date" json:"insurance_expire_date"`
	AnnualInspectionDate *time.Time `gorm:"column:annual_inspection_date" json:"annual_inspection_date"`
	NextInspectionDate   *time.Time `gorm:"column:next_inspection_date" json:"next_inspection_date"`
	CurrentMileage       int        `gorm:"column:current_mileage" json:"current_mileage"`
	Status               string     `gorm:"column:status;size:20" json:"status"`
	ManagerID            *uint64    `gorm:"column:manager_id" json:"manager_id"`
	Notes                string     `gorm:"column:notes" json:"notes"`
}

// TableName 对齐 Django Meta.db_table。
func (Vehicle) TableName() string { return "oa_vehicle" }

// Vehicle 状态常量。
const (
	VehicleAvailable   = "AVAILABLE"
	VehicleInUse       = "IN_USE"
	VehicleMaintenance = "MAINTENANCE"
	VehicleDisabled    = "DISABLED"
)

// =====================
// DTO
// =====================

// VehicleCreateInput 新建车辆入参。
type VehicleCreateInput struct {
	PlateNumber          string     `json:"plate_number" binding:"required"`
	VehicleType          string     `json:"vehicle_type"`
	Brand                string     `json:"brand" binding:"required"`
	Model                string     `json:"model" binding:"required"`
	Color                string     `json:"color"`
	Seats                int        `json:"seats"`
	EngineNo             string     `json:"engine_no"`
	VIN                  string     `json:"vin"`
	InsuranceCompany     string     `json:"insurance_company"`
	InsuranceNo          string     `json:"insurance_no"`
	InsuranceExpireDate  *time.Time `json:"insurance_expire_date"`
	AnnualInspectionDate *time.Time `json:"annual_inspection_date"`
	NextInspectionDate   *time.Time `json:"next_inspection_date"`
	CurrentMileage       int        `json:"current_mileage"`
	Status               string     `json:"status"`
	ManagerID            *uint64    `json:"manager_id"`
	Notes                string     `json:"notes"`
}

// VehicleUpdateInput 局部更新车辆入参(指针区分未传与置零)。
type VehicleUpdateInput struct {
	VehicleType          *string    `json:"vehicle_type"`
	Brand                *string    `json:"brand"`
	Model                *string    `json:"model"`
	Color                *string    `json:"color"`
	Seats                *int       `json:"seats"`
	EngineNo             *string    `json:"engine_no"`
	VIN                  *string    `json:"vin"`
	InsuranceCompany     *string    `json:"insurance_company"`
	InsuranceNo          *string    `json:"insurance_no"`
	InsuranceExpireDate  *time.Time `json:"insurance_expire_date"`
	AnnualInspectionDate *time.Time `json:"annual_inspection_date"`
	NextInspectionDate   *time.Time `json:"next_inspection_date"`
	CurrentMileage       *int       `json:"current_mileage"`
	Status               *string    `json:"status"`
	ManagerID            *uint64    `json:"manager_id"`
	Notes                *string    `json:"notes"`
}

// VehicleListQuery 列表筛选条件(对齐 Django filterset/search)。
type VehicleListQuery struct {
	Keyword     string
	Status      string
	VehicleType string
	ManagerID   string
}

// =====================
// Repo
// =====================

// VehicleRepo 车辆数据访问。
type VehicleRepo struct{ db *gorm.DB }

func NewVehicleRepo(db *gorm.DB) *VehicleRepo { return &VehicleRepo{db: db} }

func (r *VehicleRepo) scoped(ctx context.Context) *gorm.DB {
	q := r.db.WithContext(ctx).Model(&Vehicle{})
	if u, ok := iam.AuthUserFrom(ctx); ok {
		q = iam.ApplyScope(q, u, scopeModule, "created_by")
	}
	return q
}

func (r *VehicleRepo) List(ctx context.Context, q VehicleListQuery, offset, limit int) ([]Vehicle, int64, error) {
	tx := r.scoped(ctx)
	if q.Keyword != "" {
		kw := "%" + q.Keyword + "%"
		tx = tx.Where("plate_number LIKE ? OR brand LIKE ? OR model LIKE ?", kw, kw, kw)
	}
	if q.Status != "" {
		tx = tx.Where("status = ?", q.Status)
	}
	if q.VehicleType != "" {
		tx = tx.Where("vehicle_type = ?", q.VehicleType)
	}
	if q.ManagerID != "" {
		tx = tx.Where("manager_id = ?", q.ManagerID)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var rows []Vehicle
	if err := tx.Order("plate_number").Offset(offset).Limit(limit).Find(&rows).Error; err != nil {
		return nil, 0, err
	}
	return rows, total, nil
}

func (r *VehicleRepo) Get(ctx context.Context, id uint64) (*Vehicle, error) {
	var v Vehicle
	if err := r.scoped(ctx).Where("id = ?", id).First(&v).Error; err != nil {
		return nil, err
	}
	return &v, nil
}

func (r *VehicleRepo) Create(ctx context.Context, v *Vehicle) error {
	return r.db.WithContext(ctx).Create(v).Error
}

func (r *VehicleRepo) Update(ctx context.Context, v *Vehicle) error {
	return r.db.WithContext(ctx).Save(v).Error
}

func (r *VehicleRepo) SoftDelete(ctx context.Context, id uint64) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&Vehicle{}).Error
}

// =====================
// Service
// =====================

var ErrVehicleNotFound = errors.New("车辆不存在")

// VehicleService 车辆业务逻辑。
type VehicleService struct{ repo *VehicleRepo }

func NewVehicleService(repo *VehicleRepo) *VehicleService { return &VehicleService{repo: repo} }

func (s *VehicleService) List(ctx context.Context, q VehicleListQuery, offset, limit int) ([]Vehicle, int64, error) {
	return s.repo.List(ctx, q, offset, limit)
}

func (s *VehicleService) Get(ctx context.Context, id uint64) (*Vehicle, error) {
	v, err := s.repo.Get(ctx, id)
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, ErrVehicleNotFound
	}
	return v, err
}

func (s *VehicleService) Create(ctx context.Context, in VehicleCreateInput) (*Vehicle, error) {
	v := &Vehicle{
		PlateNumber:          in.PlateNumber,
		VehicleType:          orDefault(in.VehicleType, "CAR"),
		Brand:                in.Brand,
		Model:                in.Model,
		Color:                in.Color,
		Seats:                orDefaultInt(in.Seats, 5),
		EngineNo:             in.EngineNo,
		VIN:                  in.VIN,
		InsuranceCompany:     in.InsuranceCompany,
		InsuranceNo:          in.InsuranceNo,
		InsuranceExpireDate:  in.InsuranceExpireDate,
		AnnualInspectionDate: in.AnnualInspectionDate,
		NextInspectionDate:   in.NextInspectionDate,
		CurrentMileage:       in.CurrentMileage,
		Status:               orDefault(in.Status, VehicleAvailable),
		ManagerID:            in.ManagerID,
		Notes:                in.Notes,
	}
	if err := s.repo.Create(ctx, v); err != nil {
		return nil, err
	}
	return v, nil
}

func (s *VehicleService) Update(ctx context.Context, id uint64, in VehicleUpdateInput) (*Vehicle, error) {
	v, err := s.Get(ctx, id)
	if err != nil {
		return nil, err
	}
	if in.VehicleType != nil {
		v.VehicleType = *in.VehicleType
	}
	if in.Brand != nil {
		v.Brand = *in.Brand
	}
	if in.Model != nil {
		v.Model = *in.Model
	}
	if in.Color != nil {
		v.Color = *in.Color
	}
	if in.Seats != nil {
		v.Seats = *in.Seats
	}
	if in.EngineNo != nil {
		v.EngineNo = *in.EngineNo
	}
	if in.VIN != nil {
		v.VIN = *in.VIN
	}
	if in.InsuranceCompany != nil {
		v.InsuranceCompany = *in.InsuranceCompany
	}
	if in.InsuranceNo != nil {
		v.InsuranceNo = *in.InsuranceNo
	}
	if in.InsuranceExpireDate != nil {
		v.InsuranceExpireDate = in.InsuranceExpireDate
	}
	if in.AnnualInspectionDate != nil {
		v.AnnualInspectionDate = in.AnnualInspectionDate
	}
	if in.NextInspectionDate != nil {
		v.NextInspectionDate = in.NextInspectionDate
	}
	if in.CurrentMileage != nil {
		v.CurrentMileage = *in.CurrentMileage
	}
	if in.Status != nil {
		v.Status = *in.Status
	}
	if in.ManagerID != nil {
		v.ManagerID = in.ManagerID
	}
	if in.Notes != nil {
		v.Notes = *in.Notes
	}
	if err := s.repo.Update(ctx, v); err != nil {
		return nil, err
	}
	return v, nil
}

func (s *VehicleService) Delete(ctx context.Context, id uint64) error {
	if _, err := s.Get(ctx, id); err != nil {
		return err
	}
	return s.repo.SoftDelete(ctx, id)
}

// UpdateMileage 更新里程,移植 Django update_mileage:新里程不得小于当前里程。
func (s *VehicleService) UpdateMileage(ctx context.Context, id uint64, mileage int) (*Vehicle, error) {
	v, err := s.Get(ctx, id)
	if err != nil {
		return nil, err
	}
	if mileage < v.CurrentMileage {
		return nil, validationErr("里程数不能小于当前里程")
	}
	v.CurrentMileage = mileage
	if err := s.repo.Update(ctx, v); err != nil {
		return nil, err
	}
	return v, nil
}

// =====================
// Handler
// =====================

// VehicleHandler 车辆 REST 处理器。
type VehicleHandler struct{ svc *VehicleService }

func NewVehicleHandler(svc *VehicleService) *VehicleHandler { return &VehicleHandler{svc: svc} }

func (h *VehicleHandler) List(c *gin.Context) {
	p := httpx.ParsePage(c)
	q := VehicleListQuery{
		Keyword:     c.Query("search"),
		Status:      c.Query("status"),
		VehicleType: c.Query("vehicle_type"),
		ManagerID:   c.Query("manager"),
	}
	rows, total, err := h.svc.List(c.Request.Context(), q, p.Offset(), p.PageSize)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.OK(c, httpx.Page[Vehicle]{Count: total, Results: rows})
}

func (h *VehicleHandler) Retrieve(c *gin.Context) {
	v, err := h.svc.Get(c.Request.Context(), parseID(c))
	if err != nil {
		httpx.Error(c, http.StatusNotFound, err.Error())
		return
	}
	httpx.OK(c, v)
}

func (h *VehicleHandler) Create(c *gin.Context) {
	var in VehicleCreateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	v, err := h.svc.Create(c.Request.Context(), in)
	if err != nil {
		httpx.Error(c, http.StatusInternalServerError, err.Error())
		return
	}
	httpx.Created(c, v)
}

func (h *VehicleHandler) Update(c *gin.Context) {
	var in VehicleUpdateInput
	if err := c.ShouldBindJSON(&in); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	v, err := h.svc.Update(c.Request.Context(), parseID(c), in)
	if err != nil {
		httpx.Error(c, statusForVehicle(err), err.Error())
		return
	}
	httpx.OK(c, v)
}

func (h *VehicleHandler) Delete(c *gin.Context) {
	if err := h.svc.Delete(c.Request.Context(), parseID(c)); err != nil {
		httpx.Error(c, statusForVehicle(err), err.Error())
		return
	}
	httpx.NoContent(c)
}

// UpdateMileage 移植 update_mileage 动作。
func (h *VehicleHandler) UpdateMileage(c *gin.Context) {
	var body struct {
		Mileage int `json:"mileage"`
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		httpx.Error(c, http.StatusBadRequest, err.Error())
		return
	}
	v, err := h.svc.UpdateMileage(c.Request.Context(), parseID(c), body.Mileage)
	if err != nil {
		httpx.Error(c, statusForVehicle(err), err.Error())
		return
	}
	httpx.OK(c, v)
}

// Register 挂载车辆路由。
func (h *VehicleHandler) Register(rg *gin.RouterGroup, perm func(string) gin.HandlerFunc) {
	g := rg.Group("/oa/vehicles")
	g.GET("", perm("oa:vehicle:view"), h.List)
	g.GET("/:id", perm("oa:vehicle:view"), h.Retrieve)
	g.POST("", perm("oa:vehicle:create"), h.Create)
	g.PUT("/:id", perm("oa:vehicle:update"), h.Update)
	g.DELETE("/:id", perm("oa:vehicle:delete"), h.Delete)
	g.POST("/:id/update_mileage", perm("oa:vehicle:update"), h.UpdateMileage)
	// TODO(verify): available(按时间段排除占用车辆) / maintenance-records 依赖
	// VehicleRequest、VehicleMaintenance 次要实体,待补全后挂载。
}

func statusForVehicle(err error) int {
	return statusFor(err, ErrVehicleNotFound)
}
