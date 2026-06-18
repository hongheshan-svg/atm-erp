from django.test import TestCase
from apps.core.models import UpgradeJob


class UpgradeJobTest(TestCase):
    def test_create_defaults(self):
        job = UpgradeJob.objects.create(
            action=UpgradeJob.ACTION_UPGRADE, mode=UpgradeJob.MODE_DOCKER,
            from_version='0.1.0', target_version='0.2.0',
        )
        self.assertEqual(job.status, UpgradeJob.STATUS_PENDING)
        self.assertEqual(job.steps, [])

    def test_append_step(self):
        job = UpgradeJob.objects.create(
            action=UpgradeJob.ACTION_UPGRADE, mode=UpgradeJob.MODE_DOCKER,
            from_version='0.1.0', target_version='0.2.0',
        )
        job.append_step('backup', 'pg_dump done')
        job.refresh_from_db()
        self.assertEqual(len(job.steps), 1)
        self.assertEqual(job.steps[0]['stage'], 'backup')
        self.assertEqual(job.steps[0]['level'], 'info')
