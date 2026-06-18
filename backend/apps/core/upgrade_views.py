"""远程升级 admin API。权限 system:upgrade。"""
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import upgrade_service
from apps.core.permission_service import get_user_permissions
from apps.core.version import get_deploy_mode


def _check_upgrade_permission(request):
    """
    Check that the user holds the system:upgrade menu permission.

    Superusers bypass the check.  Any other user must have the 'system:upgrade'
    permission code (or a prefix that covers it) in their permission set.

    PermissionMixin is ViewSet-oriented and relies on self.action (a ViewSet
    attribute) to map DRF actions to permission actions.  On bare APIView
    self.action is absent, so the mixin's check_permissions exits early after
    only verifying IsAuthenticated.  We therefore implement the check inline
    here using the same helper that PermissionMixin's _has_module_menu_access
    uses under the hood.
    """
    user = request.user
    if user.is_superuser:
        return
    user_perms = get_user_permissions(user)
    required = 'system:upgrade'
    has = any(p == required or p.startswith(required + ':') for p in user_perms)
    if not has:
        raise PermissionDenied('You do not have permission to access system upgrade.')


class SystemVersionView(APIView):
    """GET /api/v1/system/version — public to any authenticated user."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({'version': upgrade_service.get_app_version(), 'deploy_mode': get_deploy_mode()})


class CheckUpdateView(APIView):
    """GET /api/v1/system/check-update"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        _check_upgrade_permission(request)
        force = request.query_params.get('force') in ('1', 'true', 'True')
        return Response(upgrade_service.check_update(force=force))


class PerformUpgradeView(APIView):
    """POST /api/v1/system/upgrade"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        _check_upgrade_permission(request)
        try:
            job = upgrade_service.perform_upgrade(request.user)
        except upgrade_service.UpgradeBusy as e:
            return Response(
                {'detail': str(e), 'code': 'UPGRADE_BUSY'},
                status=status.HTTP_409_CONFLICT,
            )
        except upgrade_service.NoUpdateAvailable as e:
            return Response(
                {'detail': str(e), 'code': 'ALREADY_UP_TO_DATE'},
                status=status.HTTP_409_CONFLICT,
            )
        except upgrade_service.UpgradeNotAllowed as e:
            return Response(
                {'detail': str(e), 'code': 'UPGRADE_NOT_ALLOWED'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {'job_id': str(job.id), 'status': job.status},
            status=status.HTTP_202_ACCEPTED,
        )


class RollbackView(APIView):
    """POST /api/v1/system/rollback"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        _check_upgrade_permission(request)
        try:
            job = upgrade_service.perform_rollback(request.user)
        except upgrade_service.UpgradeBusy as e:
            return Response(
                {'detail': str(e), 'code': 'UPGRADE_BUSY'},
                status=status.HTTP_409_CONFLICT,
            )
        except upgrade_service.NoUpdateAvailable as e:
            return Response(
                {'detail': str(e), 'code': 'NO_ROLLBACK'},
                status=status.HTTP_409_CONFLICT,
            )
        except upgrade_service.UpgradeNotAllowed as e:
            return Response(
                {'detail': str(e), 'code': 'UPGRADE_NOT_ALLOWED'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {'job_id': str(job.id), 'status': job.status},
            status=status.HTTP_202_ACCEPTED,
        )


def _job_dict(job):
    return {
        'id': str(job.id),
        'action': job.action,
        'mode': job.mode,
        'from_version': job.from_version,
        'target_version': job.target_version,
        'status': job.status,
        'steps': job.steps,
        'started_at': job.started_at,
        'finished_at': job.finished_at,
    }


class UpgradeJobDetailView(APIView):
    """GET /api/v1/system/upgrade/jobs/<uuid:job_id>"""

    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        _check_upgrade_permission(request)
        job = upgrade_service.get_job(job_id)
        if job is None:
            return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(_job_dict(job))


class UpgradeJobListView(APIView):
    """GET /api/v1/system/upgrade/jobs"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        _check_upgrade_permission(request)
        return Response([_job_dict(j) for j in upgrade_service.list_jobs()])
