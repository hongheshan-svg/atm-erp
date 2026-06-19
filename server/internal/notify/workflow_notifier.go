package notify

import (
	"context"

	"github.com/atm-erp/server/internal/workflow"
)

// workflowNotifier 把 notify.Service 适配为 workflow.Notifier(站内信)。
type workflowNotifier struct{ svc *Service }

// AsWorkflowNotifier 返回可注入 workflow 引擎的通知器。
func AsWorkflowNotifier(svc *Service) workflow.Notifier { return &workflowNotifier{svc: svc} }

var _ workflow.Notifier = (*workflowNotifier)(nil)

func (w *workflowNotifier) NotifyUser(ctx context.Context, userID uint64, title, message string) {
	if userID == 0 {
		return
	}
	// fire-and-forget:站内信失败不阻断审批。
	_, _ = w.svc.Notify(ctx, userID, TypeInfo, title, message)
}
