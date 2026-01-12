"""
OA协同办公模块 URL 配置
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .im import IMConversationViewSet, IMMessageViewSet
from .archive import (
    ArchiveCategoryViewSet, ArchiveViewSet, ArchiveBorrowViewSet,
    ArchiveTransferViewSet, ArchiveDestructionViewSet
)
from .electronic_signature import (
    SignatureSealViewSet, SignatureDocumentViewSet, SignatureLogViewSet
)

router = DefaultRouter()
router.register(r'conversations', IMConversationViewSet, basename='im-conversation')
router.register(r'messages', IMMessageViewSet, basename='im-message')

# 档案管理
router.register(r'archive-categories', ArchiveCategoryViewSet, basename='archive-category')
router.register(r'archives', ArchiveViewSet, basename='archive')
router.register(r'archive-borrows', ArchiveBorrowViewSet, basename='archive-borrow')
router.register(r'archive-transfers', ArchiveTransferViewSet, basename='archive-transfer')
router.register(r'archive-destructions', ArchiveDestructionViewSet, basename='archive-destruction')

# 电子签章
router.register(r'signature-seals', SignatureSealViewSet, basename='signature-seal')
router.register(r'signature-documents', SignatureDocumentViewSet, basename='signature-document')
router.register(r'signature-logs', SignatureLogViewSet, basename='signature-log')

urlpatterns = [
    path('', include(router.urls)),
]
