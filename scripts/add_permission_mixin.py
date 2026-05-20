#!/usr/bin/env python3
"""
Script to add PermissionMixin to all Django ViewSets that are missing it.

The mixin is at apps.core.permission_mixin.PermissionMixin.
When permission_module is not set, the mixin is a no-op, so it's safe to add everywhere.
"""

import os
import re
import sys

# Root of the backend apps directory
APPS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend", "apps")

IMPORT_LINE = "from apps.core.permission_mixin import PermissionMixin"

# ViewSets to skip (special cases that don't work with the mixin)
SKIP_CLASSES = {
    'SalesPerformanceViewSet',
    'MaintenanceReminderView',
    'BOMIntegrationViewSet',
    'DrawingImportViewSet',
    'BOMCompareViewSet',
    'AnalyticsViewSet',
    'PasswordPolicyViewSet',
    'NotificationChannelViewSet',
    'SystemConfigViewSet',
    'GlobalSearchViewSet',
    'SupplierAccountViewSet',
    'SupplierOrderViewViewSet',
    'SupplierQualityRecordViewSet',
    'CustomTokenObtainPairView',
    'HealthCheckViewSet',
}

# Regex to match a ViewSet class definition
# Captures: (indentation, class_name, parents_string)
VIEWSET_CLASS_RE = re.compile(
    r'^(class\s+(\w+ViewSet)\s*\()([^)]+)(\)\s*:)',
    re.MULTILINE
)

# Regex to find the last "from apps." import in a file
FROM_APPS_IMPORT_RE = re.compile(r'^from apps\..+$', re.MULTILINE)


def process_file(filepath):
    """
    Process a single Python file. Returns (modified: bool, classes_added: list[str]).
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        original = f.read()

    content = original
    classes_added = []

    # Find all ViewSet class definitions
    matches = list(VIEWSET_CLASS_RE.finditer(content))
    if not matches:
        return False, []

    # We'll rebuild content by processing matches in reverse order
    # (so that offsets remain valid after each substitution)
    replacements = []  # list of (start, end, replacement_text)

    for m in matches:
        class_name = m.group(2)
        parents_str = m.group(3)

        # Skip if in skip list
        if class_name in SKIP_CLASSES:
            continue

        # Parse parent class names (strip whitespace, handle multi-line)
        parents = [p.strip() for p in parents_str.split(',')]
        parent_names = [p.split('.')[-1].split('(')[0].strip() for p in parents]

        # Skip if PermissionMixin already present
        if 'PermissionMixin' in parent_names:
            continue

        # Build the new class definition
        new_parents = 'PermissionMixin, ' + parents_str
        new_class_def = m.group(1) + new_parents + m.group(4)

        replacements.append((m.start(), m.end(), new_class_def))
        classes_added.append(class_name)

    if not classes_added:
        return False, []

    # Apply replacements in reverse order
    for start, end, replacement in reversed(replacements):
        content = content[:start] + replacement + content[end:]

    # Add import if not already present
    if IMPORT_LINE not in content:
        # Find the last "from apps." import line
        all_matches = list(FROM_APPS_IMPORT_RE.finditer(content))
        if all_matches:
            last_match = all_matches[-1]
            insert_pos = last_match.end()
            content = content[:insert_pos] + '\n' + IMPORT_LINE + content[insert_pos:]
        else:
            # No "from apps." imports found; add after the last import block
            # Find the end of the import block (last import line)
            import_re = re.compile(r'^(?:import\s+\S+|from\s+\S+\s+import\s+.+)$', re.MULTILINE)
            import_matches = list(import_re.finditer(content))
            if import_matches:
                last_import = import_matches[-1]
                insert_pos = last_import.end()
                content = content[:insert_pos] + '\n' + IMPORT_LINE + content[insert_pos:]
            else:
                # No imports at all — prepend
                content = IMPORT_LINE + '\n' + content

    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True, classes_added

    return False, []


def walk_apps(apps_dir):
    """Walk all Python files under apps_dir, excluding migrations and __pycache__."""
    for dirpath, dirnames, filenames in os.walk(apps_dir):
        # Skip migrations and __pycache__ dirs in-place
        dirnames[:] = [
            d for d in dirnames
            if d not in ('migrations', '__pycache__', '.git')
        ]
        for filename in filenames:
            if filename.endswith('.py'):
                yield os.path.join(dirpath, filename)


def main():
    total_files_modified = 0
    total_classes_updated = 0
    all_updated = []

    for filepath in sorted(walk_apps(APPS_DIR)):
        modified, classes = process_file(filepath)
        if modified:
            total_files_modified += 1
            total_classes_updated += len(classes)
            rel_path = os.path.relpath(filepath, os.path.dirname(APPS_DIR))
            all_updated.append((rel_path, classes))
            for cls in classes:
                print(f"  [+] {rel_path}: {cls}")

    print()
    print(f"Summary: {total_files_modified} files modified, {total_classes_updated} ViewSets updated")

    if total_classes_updated == 0:
        print("(Nothing to do — all ViewSets already have PermissionMixin or are in SKIP_CLASSES)")

    return 0


if __name__ == '__main__':
    sys.exit(main())
