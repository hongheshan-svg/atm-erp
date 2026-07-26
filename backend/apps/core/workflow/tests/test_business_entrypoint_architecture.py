import ast
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class WorkflowBusinessEntrypointArchitectureTests(SimpleTestCase):
    def test_business_modules_do_not_call_low_level_start_workflow_directly(self):
        apps_root = Path(settings.BASE_DIR) / 'apps'
        offenders = []

        for path in apps_root.rglob('*.py'):
            relative = path.relative_to(apps_root)
            if 'tests' in relative.parts or relative.parts[:2] == ('core', 'workflow'):
                continue
            if 'WorkflowService.start_workflow(' in path.read_text(encoding='utf-8'):
                offenders.append(str(relative))

        self.assertEqual(
            offenders,
            [],
            'Business views must use WorkflowEnforcementMixin.start_workflow_or_auto_approve '
            f'instead of bypassing the fail-closed decision contract: {offenders}',
        )

    def test_workflow_managed_direct_actions_block_active_instances(self):
        apps_root = Path(settings.BASE_DIR) / 'apps'
        offenders = []

        for path in apps_root.rglob('*.py'):
            relative = path.relative_to(apps_root)
            if 'tests' in relative.parts:
                continue
            source = path.read_text(encoding='utf-8')
            tree = ast.parse(source)
            for class_node in (node for node in tree.body if isinstance(node, ast.ClassDef)):
                bases = {ast.unparse(base) for base in class_node.bases}
                if 'WorkflowEnforcementMixin' not in bases:
                    continue
                for method in class_node.body:
                    if not isinstance(method, ast.FunctionDef) or method.name not in {'approve', 'confirm', 'reject'}:
                        continue
                    method_source = ast.get_source_segment(source, method) or ''
                    if (
                        'check_workflow_allows_direct_action' not in method_source
                        and 'has_active_workflow' not in method_source
                    ):
                        offenders.append(f'{relative}:{class_node.name}.{method.name}')

        self.assertEqual(
            offenders,
            [],
            'Direct approval/confirmation/rejection actions on workflow-managed resources '
            f'must reject active workflow instances: {offenders}',
        )
