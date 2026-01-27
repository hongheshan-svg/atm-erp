"""
URL configuration for sales app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SalesQuotationViewSet, SalesQuotationLineViewSet,
    SalesOrderViewSet, SalesOrderLineViewSet,
    DeliveryOrderViewSet, DeliveryOrderLineViewSet,
    SalesContractViewSet
)
from .crm_views import (
    LeadSourceViewSet, LeadViewSet, OpportunityViewSet,
    OpportunityActivityViewSet, SalesForecastViewSet
)
from .quote_templates import QuoteTemplateViewSet, QuoteHistoryViewSet
from .contract_templates import (
    ContractTemplateViewSet, ContractClauseViewSet, GeneratedContractViewSet
)
from .performance import SalesTargetViewSet, SalesCommissionViewSet, SalesPerformanceViewSet
from .customer_analysis import CustomerSegmentViewSet, CustomerRFMViewSet
from .funnel_analysis import (
    SalesFunnelView, OpportunityStageAnalysisView, SalesTrendView, SalespersonRankingView
)
from .win_loss_analysis import (
    WinLossReasonViewSet, OpportunityCloseRecordViewSet,
    WinLossAnalysisView, WinLossComparisonView
)
from .marketing import (
    MarketingEmailTemplateViewSet, MarketingCampaignViewSet,
    CampaignRecipientViewSet, EmailSendLogViewSet
)
from .ai_prediction import (
    SalesPredictionViewSet, CustomerChurnRiskViewSet,
    SalesPredictionView, ChurnPredictionView, AIInsightsView
)
from .sms_marketing import (
    SMSTemplateViewSet, SMSCampaignViewSet, SMSSendLogViewSet
)
from .wechat_marketing import (
    WeChatOfficialAccountViewSet, WeChatFollowerViewSet,
    WeChatTemplateViewSet, WeChatCampaignViewSet, WeChatMessageLogViewSet
)
from .quote_estimation import (
    CostCategoryViewSet, LaborRateViewSet, QuoteEstimationViewSet,
    EstimationMaterialItemViewSet, EstimationLaborItemViewSet,
    EstimationOutsourceItemViewSet, ProjectCostHistoryViewSet
)
from .customer_training import (
    TrainingCourseViewSet, TrainingMaterialViewSet, TrainingPlanViewSet,
    TraineeViewSet, TrainingExamViewSet, TrainingFeedbackViewSet
)
from .quote_prediction import (
    QuoteVersionViewSet, QuoteCostItemViewSet, QuoteComparisonViewSet,
    QuoteProjectCostRefViewSet
)
from .after_sales_service import (
    ServiceContractViewSet, PreventiveMaintenanceViewSet,
    ServiceRequestViewSet, KnowledgeBaseArticleViewSet,
    CustomerPortalLoginView, CustomerPortalDashboardView, CustomerPortalSubmitRequestView
)

router = DefaultRouter()
router.register(r'quotations', SalesQuotationViewSet, basename='quotation')
router.register(r'quotation-lines', SalesQuotationLineViewSet, basename='quotation-line')
router.register(r'orders', SalesOrderViewSet, basename='order')
router.register(r'order-lines', SalesOrderLineViewSet, basename='order-line')
router.register(r'deliveries', DeliveryOrderViewSet, basename='delivery')
router.register(r'delivery-lines', DeliveryOrderLineViewSet, basename='delivery-line')
router.register(r'contracts', SalesContractViewSet, basename='contract')

# CRM - 商机线索管理
router.register(r'lead-sources', LeadSourceViewSet, basename='lead-source')
router.register(r'leads', LeadViewSet, basename='lead')
router.register(r'opportunities', OpportunityViewSet, basename='opportunity')
router.register(r'opportunity-activities', OpportunityActivityViewSet, basename='opportunity-activity')
router.register(r'forecasts', SalesForecastViewSet, basename='forecast')

# Quote Templates - 报价单模板
router.register(r'quote-templates', QuoteTemplateViewSet, basename='quote-template')
router.register(r'quote-history', QuoteHistoryViewSet, basename='quote-history')

# Contract Templates - 合同模板
router.register(r'contract-templates', ContractTemplateViewSet, basename='contract-template')
router.register(r'contract-clauses', ContractClauseViewSet, basename='contract-clause')
router.register(r'generated-contracts', GeneratedContractViewSet, basename='generated-contract')

# 销售业绩管理
router.register(r'targets', SalesTargetViewSet, basename='target')
router.register(r'commissions', SalesCommissionViewSet, basename='commission')
router.register(r'performance', SalesPerformanceViewSet, basename='performance')

# 客户分析
router.register(r'customer-segments', CustomerSegmentViewSet, basename='customer-segment')
router.register(r'customer-rfm', CustomerRFMViewSet, basename='customer-rfm')

# 赢单/丢单分析
router.register(r'win-loss-reasons', WinLossReasonViewSet, basename='win-loss-reason')
router.register(r'opportunity-closes', OpportunityCloseRecordViewSet, basename='opportunity-close')
router.register(r'close-records', OpportunityCloseRecordViewSet, basename='close-record')  # 别名

# 营销自动化
router.register(r'marketing-email-templates', MarketingEmailTemplateViewSet, basename='marketing-email-template')
router.register(r'campaigns', MarketingCampaignViewSet, basename='campaign')
router.register(r'campaign-recipients', CampaignRecipientViewSet, basename='campaign-recipient')
router.register(r'email-logs', EmailSendLogViewSet, basename='email-log')

# AI预测
router.register(r'sales-predictions', SalesPredictionViewSet, basename='sales-prediction')
router.register(r'churn-risks', CustomerChurnRiskViewSet, basename='churn-risk')

# 短信营销
router.register(r'sms-templates', SMSTemplateViewSet, basename='sms-template')
router.register(r'sms-campaigns', SMSCampaignViewSet, basename='sms-campaign')
router.register(r'sms-logs', SMSSendLogViewSet, basename='sms-log')

# 微信营销
router.register(r'wechat-accounts', WeChatOfficialAccountViewSet, basename='wechat-account')
router.register(r'wechat-followers', WeChatFollowerViewSet, basename='wechat-follower')
router.register(r'wechat-templates', WeChatTemplateViewSet, basename='wechat-template')
router.register(r'wechat-campaigns', WeChatCampaignViewSet, basename='wechat-campaign')
router.register(r'wechat-message-logs', WeChatMessageLogViewSet, basename='wechat-message-log')

# 非标报价估算工具
router.register(r'cost-categories', CostCategoryViewSet, basename='cost-category')
router.register(r'labor-rates', LaborRateViewSet, basename='labor-rate')
router.register(r'quote-estimations', QuoteEstimationViewSet, basename='quote-estimation')
router.register(r'estimation-materials', EstimationMaterialItemViewSet, basename='estimation-material')
router.register(r'estimation-labors', EstimationLaborItemViewSet, basename='estimation-labor')
router.register(r'estimation-outsources', EstimationOutsourceItemViewSet, basename='estimation-outsource')
router.register(r'project-cost-history', ProjectCostHistoryViewSet, basename='project-cost-history')

# 客户培训管理
router.register(r'training-courses', TrainingCourseViewSet, basename='training-course')
router.register(r'training-materials', TrainingMaterialViewSet, basename='training-material')
router.register(r'training-plans', TrainingPlanViewSet, basename='training-plan')
router.register(r'trainees', TraineeViewSet, basename='trainee')
router.register(r'training-exams', TrainingExamViewSet, basename='training-exam')
router.register(r'training-feedbacks', TrainingFeedbackViewSet, basename='training-feedback')

# 报价成本预测优化
router.register(r'quote-versions', QuoteVersionViewSet, basename='quote-version')
router.register(r'quote-cost-items', QuoteCostItemViewSet, basename='quote-cost-item')
router.register(r'quote-comparisons', QuoteComparisonViewSet, basename='quote-comparison')
router.register(r'quote-cost-refs', QuoteProjectCostRefViewSet, basename='quote-cost-ref')

# 售后服务管理
router.register(r'service-contracts', ServiceContractViewSet, basename='service-contract')
router.register(r'preventive-maintenance', PreventiveMaintenanceViewSet, basename='preventive-maintenance')
router.register(r'service-requests', ServiceRequestViewSet, basename='service-request')
router.register(r'knowledge-base', KnowledgeBaseArticleViewSet, basename='knowledge-base')

urlpatterns = [
    path('', include(router.urls)),
    
    # 销售分析
    path('analysis/funnel/', SalesFunnelView.as_view(), name='sales-funnel'),
    path('analysis/stages/', OpportunityStageAnalysisView.as_view(), name='opportunity-stages'),
    path('analysis/trend/', SalesTrendView.as_view(), name='sales-trend'),
    path('analysis/ranking/', SalespersonRankingView.as_view(), name='salesperson-ranking'),
    
    # 赢单/丢单分析
    path('analysis/win-loss/', WinLossAnalysisView.as_view(), name='win-loss-analysis'),
    path('analysis/win-loss-comparison/', WinLossComparisonView.as_view(), name='win-loss-comparison'),
    
    # AI预测
    path('ai/sales-prediction/', SalesPredictionView.as_view(), name='ai-sales-prediction'),
    path('ai/churn-prediction/', ChurnPredictionView.as_view(), name='ai-churn-prediction'),
    path('ai/insights/', AIInsightsView.as_view(), name='ai-insights'),
    
    # 客户门户
    path('customer-portal/login/', CustomerPortalLoginView.as_view(), name='customer-portal-login'),
    path('customer-portal/<int:customer_id>/dashboard/', CustomerPortalDashboardView.as_view(), name='customer-portal-dashboard'),
    path('customer-portal/<int:customer_id>/submit-request/', CustomerPortalSubmitRequestView.as_view(), name='customer-portal-submit-request'),
]

