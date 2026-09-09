from django.urls import path
from rest_framework.routers import SimpleRouter

from .api.bom import BOMView
from .api.execution import DeliveryView, TaskView, TimeView
from .api.finance import EntryView, PaymentView
from .api.inventory import MoveView, StockView
from .api.masterdata import ItemView, PartnerView
from .api.projects import ProjectView
from .api.purchases import PurchaseView
from .attachments import DocumentView
from .reports import ReportsView
from .sales import SalesView
from .workbench import WorkbenchView

router = SimpleRouter()
router.register('items', ItemView)
router.register('partners', PartnerView)
router.register('projects', ProjectView)
router.register('sales', SalesView)
router.register('bom', BOMView)
router.register('purchases', PurchaseView)
router.register('stocks', StockView)
router.register('moves', MoveView)
router.register('entries', EntryView)
router.register('payments', PaymentView)
router.register('tasks', TaskView)
router.register('deliveries', DeliveryView)
router.register('time', TimeView)
router.register('documents', DocumentView)
urlpatterns = [path('workbench/', WorkbenchView.as_view()), path('reports/', ReportsView.as_view()), *router.urls]
