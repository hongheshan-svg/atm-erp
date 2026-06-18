# backend/apps/core/tests/test_progress_relay.py
from django.test import TestCase

from apps.core.models import UpgradeJob
from apps.core.management.commands.upgrade_progress_relay import relay_event


class RelayTest(TestCase):
    def test_relay_updates_job(self):
        job = UpgradeJob.objects.create(
            action='upgrade',
            mode='docker',
            from_version='0.2.0',
            target_version='0.3.0',
        )
        relay_event({
            'job_id': str(job.id),
            'state': {
                'status': 'success',
                'steps': [{'stage': 'done', 'message': 'ok', 'level': 'info'}],
            },
        })
        job.refresh_from_db()
        self.assertEqual(job.status, 'success')
        self.assertEqual(len(job.steps), 1)

    def test_relay_sets_finished_at_on_terminal_status(self):
        job = UpgradeJob.objects.create(
            action='upgrade',
            mode='docker',
            from_version='0.1.0',
            target_version='0.2.0',
        )
        self.assertIsNone(job.finished_at)
        relay_event({
            'job_id': str(job.id),
            'state': {'status': 'failed', 'steps': []},
        })
        job.refresh_from_db()
        self.assertEqual(job.status, 'failed')
        self.assertIsNotNone(job.finished_at)

    def test_relay_ignores_unknown_job(self):
        # Should not raise even for a non-existent job_id (integer PK; BigAutoField)
        relay_event({'job_id': '99999999', 'state': {'status': 'running'}})

    def test_relay_non_terminal_status_leaves_finished_at_none(self):
        job = UpgradeJob.objects.create(
            action='upgrade',
            mode='docker',
            from_version='0.1.0',
            target_version='0.2.0',
        )
        relay_event({
            'job_id': str(job.id),
            'state': {'status': 'running', 'steps': []},
        })
        job.refresh_from_db()
        self.assertEqual(job.status, 'running')
        self.assertIsNone(job.finished_at)
