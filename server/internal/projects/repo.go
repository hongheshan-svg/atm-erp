package projects

import (
	"context"

	"github.com/atm-erp/server/internal/iam"
	"gorm.io/gorm"
)

// scopeModule 标识该上下文所属权限/数据范围模块(对齐 Django permission_module='projects')。
const scopeModule = "projects"

// Repo 聚合项目上下文各实体的数据访问(共用同一 *gorm.DB,scoped 套用数据范围)。
type Repo struct{ db *gorm.DB }

// NewRepo 构造 Repo。
func NewRepo(db *gorm.DB) *Repo { return &Repo{db: db} }

// scopedModel 对给定模型套用数据范围过滤(软删除由 gorm.DeletedAt 默认过滤)。
func (r *Repo) scopedModel(ctx context.Context, m any) *gorm.DB {
	q := r.db.WithContext(ctx).Model(m)
	if u, ok := iam.AuthUserFrom(ctx); ok {
		q = iam.ApplyScope(q, u, scopeModule, "created_by_id")
	}
	return q
}

// ---------------------------------------------------------------------------
// Project
// ---------------------------------------------------------------------------

func (r *Repo) ListProjects(ctx context.Context, q ProjectListQuery, offset, limit int) ([]Project, int64, error) {
	tx := r.scopedModel(ctx, &Project{})
	if q.Keyword != "" {
		kw := "%" + q.Keyword + "%"
		tx = tx.Where("code LIKE ? OR name LIKE ?", kw, kw)
	}
	if q.CustomerID != 0 {
		tx = tx.Where("customer_id = ?", q.CustomerID)
	}
	if q.ManagerID != 0 {
		tx = tx.Where("manager_id = ?", q.ManagerID)
	}
	if q.Status != "" {
		tx = tx.Where("status = ?", q.Status)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var rows []Project
	if err := tx.Order("created_at DESC").Offset(offset).Limit(limit).Find(&rows).Error; err != nil {
		return nil, 0, err
	}
	return rows, total, nil
}

func (r *Repo) GetProject(ctx context.Context, id uint64) (*Project, error) {
	var p Project
	if err := r.scopedModel(ctx, &Project{}).Where("id = ?", id).First(&p).Error; err != nil {
		return nil, err
	}
	return &p, nil
}

func (r *Repo) CreateProject(ctx context.Context, p *Project) error {
	return r.db.WithContext(ctx).Create(p).Error
}

func (r *Repo) UpdateProject(ctx context.Context, p *Project) error {
	return r.db.WithContext(ctx).Save(p).Error
}

func (r *Repo) SoftDeleteProject(ctx context.Context, id uint64) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&Project{}).Error
}

// CountProjectsByCodePrefix 用于编号生成时的同前缀计数(回退规则)。
func (r *Repo) CountProjectsByCodePrefix(ctx context.Context, prefix string) (int64, error) {
	var n int64
	err := r.db.WithContext(ctx).Model(&Project{}).Where("code LIKE ?", prefix+"%").Count(&n).Error
	return n, err
}

// ---------------------------------------------------------------------------
// ProjectTask
// ---------------------------------------------------------------------------

func (r *Repo) ListTasks(ctx context.Context, q TaskListQuery, offset, limit int) ([]ProjectTask, int64, error) {
	tx := r.scopedModel(ctx, &ProjectTask{})
	if q.Keyword != "" {
		kw := "%" + q.Keyword + "%"
		tx = tx.Where("code LIKE ? OR name LIKE ?", kw, kw)
	}
	if q.ProjectID != 0 {
		tx = tx.Where("project_id = ?", q.ProjectID)
	}
	if q.AssigneeID != 0 {
		tx = tx.Where("assignee_id = ?", q.AssigneeID)
	}
	if q.Status != "" {
		tx = tx.Where("status = ?", q.Status)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var rows []ProjectTask
	if err := tx.Order("project_id, sort_order, code").Offset(offset).Limit(limit).Find(&rows).Error; err != nil {
		return nil, 0, err
	}
	return rows, total, nil
}

func (r *Repo) GetTask(ctx context.Context, id uint64) (*ProjectTask, error) {
	var t ProjectTask
	if err := r.scopedModel(ctx, &ProjectTask{}).Where("id = ?", id).First(&t).Error; err != nil {
		return nil, err
	}
	return &t, nil
}

func (r *Repo) CreateTask(ctx context.Context, t *ProjectTask) error {
	return r.db.WithContext(ctx).Create(t).Error
}

func (r *Repo) UpdateTask(ctx context.Context, t *ProjectTask) error {
	return r.db.WithContext(ctx).Save(t).Error
}

func (r *Repo) SoftDeleteTask(ctx context.Context, id uint64) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&ProjectTask{}).Error
}

// TaskCodeExists 校验 project+code 唯一(Django unique_together)。
func (r *Repo) TaskCodeExists(ctx context.Context, projectID uint64, code string, excludeID uint64) (bool, error) {
	q := r.db.WithContext(ctx).Model(&ProjectTask{}).Where("project_id = ? AND code = ?", projectID, code)
	if excludeID != 0 {
		q = q.Where("id <> ?", excludeID)
	}
	var n int64
	if err := q.Count(&n).Error; err != nil {
		return false, err
	}
	return n > 0, nil
}

// ---------------------------------------------------------------------------
// ProjectBOM
// ---------------------------------------------------------------------------

func (r *Repo) ListBOM(ctx context.Context, q BOMListQuery, offset, limit int) ([]ProjectBOM, int64, error) {
	tx := r.scopedModel(ctx, &ProjectBOM{})
	if q.Keyword != "" {
		kw := "%" + q.Keyword + "%"
		tx = tx.Where("item_code LIKE ? OR drawing_no LIKE ? OR version_brand LIKE ?", kw, kw, kw)
	}
	if q.ProjectID != 0 {
		tx = tx.Where("project_id = ?", q.ProjectID)
	}
	if q.ItemID != 0 {
		tx = tx.Where("item_id = ?", q.ItemID)
	}
	if q.QuoteStatus != "" {
		tx = tx.Where("quote_status = ?", q.QuoteStatus)
	}
	if q.OrderStatus != "" {
		tx = tx.Where("order_status = ?", q.OrderStatus)
	}
	if q.HasDrawing != "" {
		tx = tx.Where("has_drawing = ?", q.HasDrawing)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var rows []ProjectBOM
	if err := tx.Order("project_id, level, sort_order, created_at DESC").Offset(offset).Limit(limit).Find(&rows).Error; err != nil {
		return nil, 0, err
	}
	return rows, total, nil
}

func (r *Repo) GetBOM(ctx context.Context, id uint64) (*ProjectBOM, error) {
	var b ProjectBOM
	if err := r.scopedModel(ctx, &ProjectBOM{}).Where("id = ?", id).First(&b).Error; err != nil {
		return nil, err
	}
	return &b, nil
}

func (r *Repo) CreateBOM(ctx context.Context, b *ProjectBOM) error {
	return r.db.WithContext(ctx).Create(b).Error
}

func (r *Repo) UpdateBOM(ctx context.Context, b *ProjectBOM) error {
	return r.db.WithContext(ctx).Save(b).Error
}

func (r *Repo) SoftDeleteBOM(ctx context.Context, id uint64) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&ProjectBOM{}).Error
}

// ---------------------------------------------------------------------------
// Drawing
// ---------------------------------------------------------------------------

func (r *Repo) ListDrawings(ctx context.Context, q DrawingListQuery, offset, limit int) ([]Drawing, int64, error) {
	tx := r.scopedModel(ctx, &Drawing{})
	if q.Keyword != "" {
		kw := "%" + q.Keyword + "%"
		tx = tx.Where("drawing_no LIKE ? OR name LIKE ?", kw, kw)
	}
	if q.ProjectID != 0 {
		tx = tx.Where("project_id = ?", q.ProjectID)
	}
	if q.ItemID != 0 {
		tx = tx.Where("item_id = ?", q.ItemID)
	}
	if q.Status != "" {
		tx = tx.Where("status = ?", q.Status)
	}
	if q.PartType != "" {
		tx = tx.Where("part_type = ?", q.PartType)
	}
	var total int64
	if err := tx.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	var rows []Drawing
	if err := tx.Order("created_at DESC").Offset(offset).Limit(limit).Find(&rows).Error; err != nil {
		return nil, 0, err
	}
	return rows, total, nil
}

func (r *Repo) GetDrawing(ctx context.Context, id uint64) (*Drawing, error) {
	var d Drawing
	if err := r.scopedModel(ctx, &Drawing{}).Where("id = ?", id).First(&d).Error; err != nil {
		return nil, err
	}
	return &d, nil
}

func (r *Repo) CreateDrawing(ctx context.Context, d *Drawing) error {
	return r.db.WithContext(ctx).Create(d).Error
}

func (r *Repo) UpdateDrawing(ctx context.Context, d *Drawing) error {
	return r.db.WithContext(ctx).Save(d).Error
}

func (r *Repo) SoftDeleteDrawing(ctx context.Context, id uint64) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&Drawing{}).Error
}

func (r *Repo) CountDrawingsByNoPrefix(ctx context.Context, prefix string) (int64, error) {
	var n int64
	err := r.db.WithContext(ctx).Model(&Drawing{}).Where("drawing_no LIKE ?", prefix+"%").Count(&n).Error
	return n, err
}

// CreateDrawingChangeNotice 在 release 联动时创建变更通知。
func (r *Repo) CreateDrawingChangeNotice(ctx context.Context, n *DrawingChangeNotice) error {
	return r.db.WithContext(ctx).Create(n).Error
}
