package projects

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/atm-erp/server/internal/iam"
	"gorm.io/gorm"
)

// 领域错误。Handler 据此映射 HTTP 状态码。
var (
	ErrNotFound   = errors.New("记录不存在")
	ErrValidation = errors.New("校验失败")
	ErrConflict   = errors.New("状态冲突")
)

// Service 承载项目上下文的业务规则(校验/编号/状态流转),忠实迁移 Django ViewSet 行为。
type Service struct{ repo *Repo }

// NewService 构造 Service。
func NewService(repo *Repo) *Service { return &Service{repo: repo} }

// validationErr 包装带消息的校验错误。
func validationErr(msg string) error { return fmt.Errorf("%w: %s", ErrValidation, msg) }

// conflictErr 包装带消息的状态冲突错误。
func conflictErr(msg string) error { return fmt.Errorf("%w: %s", ErrConflict, msg) }

// ===========================================================================
// Project
// ===========================================================================

func (s *Service) ListProjects(ctx context.Context, q ProjectListQuery, offset, limit int) ([]Project, int64, error) {
	return s.repo.ListProjects(ctx, q, offset, limit)
}

func (s *Service) GetProject(ctx context.Context, id uint64) (*Project, error) {
	p, err := s.repo.GetProject(ctx, id)
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, ErrNotFound
	}
	return p, err
}

func (s *Service) CreateProject(ctx context.Context, in ProjectCreateInput) (*Project, error) {
	p := &Project{
		Code:           in.Code,
		Name:           in.Name,
		CustomerID:     in.CustomerID,
		SalesOrderID:   in.SalesOrderID,
		ManagerID:      in.ManagerID,
		StartDate:      in.StartDate,
		EndDate:        in.EndDate,
		Status:         in.Status,
		BudgetTotal:    in.BudgetTotal,
		BudgetMaterial: in.BudgetMaterial,
		BudgetLabor:    in.BudgetLabor,
		BudgetExpense:  in.BudgetExpense,
		Description:    in.Description,
		Notes:          in.Notes,
	}
	if p.Status == "" {
		p.Status = ProjectStatusDraft
	}
	// 自动生成项目编号(Django: generate_code('PRJ', rule_type='PROJECT'))。
	// TODO(verify): 现状走 CodeRule 模型;此处用回退规则 PRJ+yyyymmdd+序号,共库切流前与 CodeRule 对账。
	if p.Code == "" {
		p.Code = s.genCode(ctx, "PRJ", func(prefix string) (int64, error) {
			return s.repo.CountProjectsByCodePrefix(ctx, prefix)
		})
	}
	if err := s.repo.CreateProject(ctx, p); err != nil {
		return nil, err
	}
	return p, nil
}

func (s *Service) UpdateProject(ctx context.Context, id uint64, in ProjectUpdateInput) (*Project, error) {
	p, err := s.GetProject(ctx, id)
	if err != nil {
		return nil, err
	}
	if in.Name != nil {
		p.Name = *in.Name
	}
	if in.CustomerID != nil {
		p.CustomerID = *in.CustomerID
	}
	if in.SalesOrderID != nil {
		p.SalesOrderID = in.SalesOrderID
	}
	if in.ManagerID != nil {
		p.ManagerID = *in.ManagerID
	}
	if in.StartDate != nil {
		p.StartDate = in.StartDate
	}
	if in.EndDate != nil {
		p.EndDate = in.EndDate
	}
	if in.Status != nil {
		p.Status = *in.Status
	}
	if in.BudgetTotal != nil {
		p.BudgetTotal = *in.BudgetTotal
	}
	if in.BudgetMaterial != nil {
		p.BudgetMaterial = *in.BudgetMaterial
	}
	if in.BudgetLabor != nil {
		p.BudgetLabor = *in.BudgetLabor
	}
	if in.BudgetExpense != nil {
		p.BudgetExpense = *in.BudgetExpense
	}
	if in.Description != nil {
		p.Description = *in.Description
	}
	if in.Notes != nil {
		p.Notes = *in.Notes
	}
	if err := s.repo.UpdateProject(ctx, p); err != nil {
		return nil, err
	}
	return p, nil
}

func (s *Service) DeleteProject(ctx context.Context, id uint64) error {
	if _, err := s.GetProject(ctx, id); err != nil {
		return err
	}
	return s.repo.SoftDeleteProject(ctx, id)
}

// SubmitProject 提交项目审批。
// 忠实迁移 Django ProjectViewSet.submit:只能提交 DRAFT/PLANNING/REJECTED。
// TODO(port): WorkflowService.start_workflow 跨 core.workflow 模块,本轮不接入;
// 这里复刻“无审批流程时直接置 IN_PROGRESS”的回退分支(Django 在工作流不可用时的行为)。
func (s *Service) SubmitProject(ctx context.Context, id uint64) (*Project, error) {
	p, err := s.GetProject(ctx, id)
	if err != nil {
		return nil, err
	}
	switch p.Status {
	case ProjectStatusDraft, ProjectStatusPlanning, ProjectStatusRejected:
	default:
		return nil, conflictErr("只能提交草稿、规划中或已拒绝状态的项目")
	}
	// TODO(port): 接入 WorkflowService 后,若配置了审批流应置 PENDING 并启动流程实例。
	p.Status = ProjectStatusInProgress
	if err := s.repo.UpdateProject(ctx, p); err != nil {
		return nil, err
	}
	return p, nil
}

// projectAllowedTransitions 复刻 Django ProjectViewSet.change_status 的状态机。
var projectAllowedTransitions = map[string][]string{
	ProjectStatusDraft:      {ProjectStatusPlanning, ProjectStatusCancelled},
	ProjectStatusPlanning:   {ProjectStatusInProgress, ProjectStatusDraft, ProjectStatusCancelled},
	ProjectStatusInProgress: {ProjectStatusPaused, ProjectStatusCompleted, ProjectStatusCancelled},
	ProjectStatusPaused:     {ProjectStatusInProgress, ProjectStatusCancelled},
	ProjectStatusCompleted:  {ProjectStatusArchived},
}

var projectValidStatuses = map[string]bool{
	ProjectStatusDraft: true, ProjectStatusPlanning: true, ProjectStatusPending: true,
	ProjectStatusRejected: true, ProjectStatusInProgress: true, ProjectStatusActive: true,
	ProjectStatusPaused: true, ProjectStatusCompleted: true, ProjectStatusCancelled: true,
	ProjectStatusArchived: true,
}

// ChangeProjectStatus 校验并执行状态流转。
func (s *Service) ChangeProjectStatus(ctx context.Context, id uint64, newStatus string) (*Project, error) {
	p, err := s.GetProject(ctx, id)
	if err != nil {
		return nil, err
	}
	if !projectValidStatuses[newStatus] {
		return nil, validationErr("无效的状态")
	}
	allowed := projectAllowedTransitions[p.Status]
	ok := false
	for _, a := range allowed {
		if a == newStatus {
			ok = true
			break
		}
	}
	if !ok {
		return nil, conflictErr(fmt.Sprintf("不允许从 %s 转换到 %s", p.Status, newStatus))
	}
	p.Status = newStatus
	if err := s.repo.UpdateProject(ctx, p); err != nil {
		return nil, err
	}
	return p, nil
}

// ===========================================================================
// ProjectTask
// ===========================================================================

func (s *Service) ListTasks(ctx context.Context, q TaskListQuery, offset, limit int) ([]ProjectTask, int64, error) {
	return s.repo.ListTasks(ctx, q, offset, limit)
}

func (s *Service) GetTask(ctx context.Context, id uint64) (*ProjectTask, error) {
	t, err := s.repo.GetTask(ctx, id)
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, ErrNotFound
	}
	return t, err
}

func (s *Service) CreateTask(ctx context.Context, in TaskCreateInput) (*ProjectTask, error) {
	// project+code 唯一(Django unique_together = ['project','code'])。
	exists, err := s.repo.TaskCodeExists(ctx, in.ProjectID, in.Code, 0)
	if err != nil {
		return nil, err
	}
	if exists {
		return nil, validationErr("同一项目下任务编号已存在")
	}
	t := &ProjectTask{
		ProjectID:    in.ProjectID,
		ParentID:     in.ParentID,
		Code:         in.Code,
		Name:         in.Name,
		AssigneeID:   in.AssigneeID,
		PlannedHours: in.PlannedHours,
		ActualHours:  in.ActualHours,
		Status:       in.Status,
		StartDate:    in.StartDate,
		EndDate:      in.EndDate,
		Description:  in.Description,
		SortOrder:    in.SortOrder,
	}
	if t.Status == "" {
		t.Status = TaskStatusTodo
	}
	if err := s.repo.CreateTask(ctx, t); err != nil {
		return nil, err
	}
	return t, nil
}

func (s *Service) UpdateTask(ctx context.Context, id uint64, in TaskUpdateInput) (*ProjectTask, error) {
	t, err := s.GetTask(ctx, id)
	if err != nil {
		return nil, err
	}
	if in.Code != nil && *in.Code != t.Code {
		exists, err := s.repo.TaskCodeExists(ctx, t.ProjectID, *in.Code, t.ID)
		if err != nil {
			return nil, err
		}
		if exists {
			return nil, validationErr("同一项目下任务编号已存在")
		}
		t.Code = *in.Code
	}
	if in.ParentID != nil {
		t.ParentID = in.ParentID
	}
	if in.Name != nil {
		t.Name = *in.Name
	}
	if in.AssigneeID != nil {
		t.AssigneeID = in.AssigneeID
	}
	if in.PlannedHours != nil {
		t.PlannedHours = *in.PlannedHours
	}
	if in.ActualHours != nil {
		t.ActualHours = *in.ActualHours
	}
	if in.Status != nil {
		t.Status = *in.Status
	}
	if in.StartDate != nil {
		t.StartDate = in.StartDate
	}
	if in.EndDate != nil {
		t.EndDate = in.EndDate
	}
	if in.Description != nil {
		t.Description = *in.Description
	}
	if in.SortOrder != nil {
		t.SortOrder = *in.SortOrder
	}
	if err := s.repo.UpdateTask(ctx, t); err != nil {
		return nil, err
	}
	return t, nil
}

func (s *Service) DeleteTask(ctx context.Context, id uint64) error {
	if _, err := s.GetTask(ctx, id); err != nil {
		return err
	}
	return s.repo.SoftDeleteTask(ctx, id)
}

// UpdateTaskProgress 复刻 Django ProjectTaskViewSet.update_progress:
// progress>=100 -> COMPLETED;progress>0 -> IN_PROGRESS;可同步 actual_hours。
func (s *Service) UpdateTaskProgress(ctx context.Context, id uint64, in UpdateProgressInput) (*ProjectTask, error) {
	t, err := s.GetTask(ctx, id)
	if err != nil {
		return nil, err
	}
	if in.ProgressPercent != nil {
		pp := *in.ProgressPercent
		if pp < 0 || pp > 100 {
			return nil, validationErr("进度必须在 0-100 之间")
		}
		t.ProgressPercent = pp
		if pp >= 100 {
			t.Status = TaskStatusCompleted
		} else if pp > 0 {
			t.Status = TaskStatusInProgress
		}
	}
	if in.ActualHours != nil {
		t.ActualHours = *in.ActualHours
	}
	if err := s.repo.UpdateTask(ctx, t); err != nil {
		return nil, err
	}
	return t, nil
}

// ===========================================================================
// ProjectBOM
// ===========================================================================

func (s *Service) ListBOM(ctx context.Context, q BOMListQuery, offset, limit int) ([]ProjectBOM, int64, error) {
	return s.repo.ListBOM(ctx, q, offset, limit)
}

func (s *Service) GetBOM(ctx context.Context, id uint64) (*ProjectBOM, error) {
	b, err := s.repo.GetBOM(ctx, id)
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, ErrNotFound
	}
	return b, err
}

func (s *Service) CreateBOM(ctx context.Context, in BOMCreateInput) (*ProjectBOM, error) {
	b := &ProjectBOM{
		ProjectID:            in.ProjectID,
		ItemID:               in.ItemID,
		ItemCode:             in.ItemCode,
		ItemProperty:         in.ItemProperty,
		Status:               in.Status,
		Priority:             in.Priority,
		PlannedQty:           in.PlannedQty,
		ActualQty:            in.ActualQty,
		UnitQty:              in.UnitQty,
		ScrapRate:            in.ScrapRate,
		EstimatedCost:        in.EstimatedCost,
		TargetCost:           in.TargetCost,
		ActualCost:           in.ActualCost,
		VersionBrand:         in.VersionBrand,
		HasDrawing:           in.HasDrawing,
		DrawingID:            in.DrawingID,
		DrawingNo:            in.DrawingNo,
		DrawingVersion:       in.DrawingVersion,
		MaterialSpec:         in.MaterialSpec,
		SurfaceTreatment:     in.SurfaceTreatment,
		TechnicalRequirement: in.TechnicalRequirement,
		WorkCenterID:         in.WorkCenterID,
		ProcessID:            in.ProcessID,
		AssemblySequence:     in.AssemblySequence,
		AssemblyInstruction:  in.AssemblyInstruction,
		RequirementIDRef:     in.RequirementIDRef,
		FunctionModule:       in.FunctionModule,
		RequiredDate:         in.RequiredDate,
		RequesterID:          in.RequesterID,
		Description:          in.Description,
		Notes:                in.Notes,
		SupplierID:           in.SupplierID,
		ReservedQty:          in.ReservedQty,
		ParentID:             in.ParentID,
		Level:                in.Level,
		SortOrder:            in.SortOrder,
		IsCritical:           in.IsCritical,
		IsLongLead:           in.IsLongLead,
		AssemblyCode:         in.AssemblyCode,
		IsCustomPart:         in.IsCustomPart,
		CustomPartType:       in.CustomPartType,
		CadFileName:          in.CadFileName,
		CadSoftware:          in.CadSoftware,
		ExtraFields:          in.ExtraFields,
	}
	// 默认值对齐 Django field default。
	if b.Status == "" {
		b.Status = BOMStatusDraft
	}
	if b.Priority == "" {
		b.Priority = "NORMAL"
	}
	if b.HasDrawing == "" {
		b.HasDrawing = "PENDING"
	}
	if b.UnitQty == 0 {
		b.UnitQty = 1
	}
	b.OrderStatus = "NOT_ORDERED"
	b.QuoteStatus = "NOT_QUOTED"
	if in.InspectionRequired != nil {
		b.InspectionRequired = *in.InspectionRequired
	} else {
		b.InspectionRequired = true
	}
	// total_cost = actual_cost × actual_qty(Django update_total_cost)。
	b.TotalCost = b.ActualCost * b.ActualQty
	if err := s.repo.CreateBOM(ctx, b); err != nil {
		return nil, err
	}
	return b, nil
}

func (s *Service) UpdateBOM(ctx context.Context, id uint64, in BOMUpdateInput) (*ProjectBOM, error) {
	b, err := s.GetBOM(ctx, id)
	if err != nil {
		return nil, err
	}
	applyBOMUpdate(b, in)
	// 重算总成本(actual_cost × actual_qty)。
	b.TotalCost = b.ActualCost * b.ActualQty
	if err := s.repo.UpdateBOM(ctx, b); err != nil {
		return nil, err
	}
	return b, nil
}

func (s *Service) DeleteBOM(ctx context.Context, id uint64) error {
	if _, err := s.GetBOM(ctx, id); err != nil {
		return err
	}
	return s.repo.SoftDeleteBOM(ctx, id)
}

// ConfirmBOM 将 BOM 行由 DRAFT 置 CONFIRMED。
// TODO(verify): Django 中 BOM 确认入口未见独立 action(状态经 update 流转);此处提供显式动作以贴合前端三件套。
func (s *Service) ConfirmBOM(ctx context.Context, id uint64) (*ProjectBOM, error) {
	b, err := s.GetBOM(ctx, id)
	if err != nil {
		return nil, err
	}
	if b.Status != BOMStatusDraft {
		return nil, conflictErr("只能确认草稿状态的 BOM 行")
	}
	b.Status = BOMStatusConfirmed
	if err := s.repo.UpdateBOM(ctx, b); err != nil {
		return nil, err
	}
	return b, nil
}

// ReleaseBOM 将 BOM 行由 CONFIRMED 置 RELEASED(下发)。
func (s *Service) ReleaseBOM(ctx context.Context, id uint64) (*ProjectBOM, error) {
	b, err := s.GetBOM(ctx, id)
	if err != nil {
		return nil, err
	}
	if b.Status != BOMStatusConfirmed {
		return nil, conflictErr("只能下发已确认的 BOM 行")
	}
	b.Status = BOMStatusReleased
	if err := s.repo.UpdateBOM(ctx, b); err != nil {
		return nil, err
	}
	return b, nil
}

// ===========================================================================
// Drawing
// ===========================================================================

func (s *Service) ListDrawings(ctx context.Context, q DrawingListQuery, offset, limit int) ([]Drawing, int64, error) {
	return s.repo.ListDrawings(ctx, q, offset, limit)
}

func (s *Service) GetDrawing(ctx context.Context, id uint64) (*Drawing, error) {
	d, err := s.repo.GetDrawing(ctx, id)
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, ErrNotFound
	}
	return d, err
}

func (s *Service) CreateDrawing(ctx context.Context, in DrawingCreateInput) (*Drawing, error) {
	d := &Drawing{
		DrawingNo:         in.DrawingNo,
		Name:              in.Name,
		Version:           in.Version,
		Revision:          in.Revision,
		PartType:          in.PartType,
		ProjectID:         in.ProjectID,
		ItemID:            in.ItemID,
		BomItemID:         in.BomItemID,
		ParentDrawingID:   in.ParentDrawingID,
		Material:          in.Material,
		Weight:            in.Weight,
		SurfaceTreatment:  in.SurfaceTreatment,
		HeatTreatment:     in.HeatTreatment,
		ToleranceGrade:    in.ToleranceGrade,
		Roughness:         in.Roughness,
		CadFileName:       in.CadFileName,
		CadSoftware:       in.CadSoftware,
		FileType:          in.FileType,
		FilePath:          in.FilePath,
		FileSize:          in.FileSize,
		PublicSharePath:   in.PublicSharePath,
		DesignerID:        in.DesignerID,
		ReviewerID:        in.ReviewerID,
		ChangeDescription: in.ChangeDescription,
		Notes:             in.Notes,
	}
	if d.Version == "" {
		d.Version = "A0"
	}
	if d.Revision == 0 {
		d.Revision = 1
	}
	if d.PartType == "" {
		d.PartType = "PART"
	}
	if d.FileType == "" {
		d.FileType = "PDF"
	}
	if d.Status == "" {
		d.Status = DrawingStatusDraft
	}
	// 自动生成图纸号(Django: generate_code('DWG', rule_type='DRAWING'))。
	if d.DrawingNo == "" {
		d.DrawingNo = s.genCode(ctx, "DWG", func(prefix string) (int64, error) {
			return s.repo.CountDrawingsByNoPrefix(ctx, prefix)
		})
	}
	if err := s.repo.CreateDrawing(ctx, d); err != nil {
		return nil, err
	}
	return d, nil
}

func (s *Service) UpdateDrawing(ctx context.Context, id uint64, in DrawingUpdateInput) (*Drawing, error) {
	d, err := s.GetDrawing(ctx, id)
	if err != nil {
		return nil, err
	}
	applyDrawingUpdate(d, in)
	if err := s.repo.UpdateDrawing(ctx, d); err != nil {
		return nil, err
	}
	return d, nil
}

func (s *Service) DeleteDrawing(ctx context.Context, id uint64) error {
	if _, err := s.GetDrawing(ctx, id); err != nil {
		return err
	}
	return s.repo.SoftDeleteDrawing(ctx, id)
}

// SubmitDrawingReview 复刻 Django DrawingViewSet.submit_review:只能提交 DRAFT。
func (s *Service) SubmitDrawingReview(ctx context.Context, id uint64) (*Drawing, error) {
	d, err := s.GetDrawing(ctx, id)
	if err != nil {
		return nil, err
	}
	if d.Status != DrawingStatusDraft {
		return nil, conflictErr("只能提交草稿状态的图纸")
	}
	d.Status = DrawingStatusReviewing
	if err := s.repo.UpdateDrawing(ctx, d); err != nil {
		return nil, err
	}
	return d, nil
}

// ApproveDrawing 复刻 Django DrawingViewSet.approve:只能审批 REVIEWING,记审批人与时间。
func (s *Service) ApproveDrawing(ctx context.Context, id uint64) (*Drawing, error) {
	d, err := s.GetDrawing(ctx, id)
	if err != nil {
		return nil, err
	}
	if d.Status != DrawingStatusReviewing {
		return nil, conflictErr("只能审批审核中的图纸")
	}
	d.Status = DrawingStatusApproved
	if uid, ok := iam.AuthUserFrom(ctx); ok {
		id := uid.ID
		d.ApproverID = &id
	}
	now := time.Now()
	d.ApprovedAt = &now
	if err := s.repo.UpdateDrawing(ctx, d); err != nil {
		return nil, err
	}
	return d, nil
}

// RejectDrawing 复刻 Django DrawingViewSet.reject:REVIEWING 退回 DRAFT,附驳回意见。
func (s *Service) RejectDrawing(ctx context.Context, id uint64, comment string) (*Drawing, error) {
	d, err := s.GetDrawing(ctx, id)
	if err != nil {
		return nil, err
	}
	if d.Status != DrawingStatusReviewing {
		return nil, conflictErr("只能驳回审核中的图纸")
	}
	d.Status = DrawingStatusDraft
	if comment != "" {
		d.ChangeDescription = fmt.Sprintf("%s\n[驳回意见] %s", d.ChangeDescription, comment)
	}
	if err := s.repo.UpdateDrawing(ctx, d); err != nil {
		return nil, err
	}
	return d, nil
}

// ReleaseDrawing 复刻 Django DrawingViewSet.release:只能发布 APPROVED,
// 记发布时间并联动创建 DrawingChangeNotice(revision==1 -> NEW,否则 REVISION)。
// TODO(port): 邮件通知(_send_change_notification)依赖通知/邮件服务,本轮不接入。
func (s *Service) ReleaseDrawing(ctx context.Context, id uint64) (*Drawing, *DrawingChangeNotice, error) {
	d, err := s.GetDrawing(ctx, id)
	if err != nil {
		return nil, nil, err
	}
	if d.Status != DrawingStatusApproved {
		return nil, nil, conflictErr("只能发布已批准的图纸")
	}
	d.Status = DrawingStatusReleased
	now := time.Now()
	d.ReleasedAt = &now
	if err := s.repo.UpdateDrawing(ctx, d); err != nil {
		return nil, nil, err
	}
	changeType := "REVISION"
	if d.Revision == 1 {
		changeType = "NEW"
	}
	desc := d.ChangeDescription
	if desc == "" {
		desc = "图纸发布"
	}
	notice := &DrawingChangeNotice{
		DrawingID:         d.ID,
		ChangeType:        changeType,
		NewVersion:        fmt.Sprintf("%s.%d", d.Version, d.Revision),
		ChangeDescription: desc,
	}
	if err := s.repo.CreateDrawingChangeNotice(ctx, notice); err != nil {
		return d, nil, err
	}
	return d, notice, nil
}

// ===========================================================================
// helpers
// ===========================================================================

// genCode 回退编号生成器:prefix + yyyymmdd + 4 位序号(同前缀计数 +1)。
// TODO(verify): 现状由 core.CodeRule 动态生成,前缀/序号格式可能不同;共库切流前与 CodeRule 对账。
func (s *Service) genCode(ctx context.Context, prefix string, countFn func(string) (int64, error)) string {
	day := time.Now().Format("20060102")
	full := prefix + day
	n, err := countFn(full)
	if err != nil {
		// 计数失败时退化为时间戳后缀,保证不阻塞创建。
		return fmt.Sprintf("%s%d", full, time.Now().Unix()%100000)
	}
	return fmt.Sprintf("%s%04d", full, n+1)
}
