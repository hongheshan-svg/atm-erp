#!/usr/bin/env python3
"""
Batch-add multi-select (selection column + batch toolbar) to all el-table
components in the frontend that don't already have it.
"""

import os
import re

VIEWS_DIR = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'src', 'views')
VIEWS_DIR = os.path.abspath(VIEWS_DIR)

# Directories where delete is not appropriate (read-only/report views)
READ_ONLY_DIRS = {'reports', 'analytics'}

# Skip files whose names match these patterns (non-list pages)
SKIP_PATTERNS = re.compile(r'(Detail|Form|Dialog|Edit|Create|Dashboard|Layout|Login|Register|Home|Index\.vue$)', re.IGNORECASE)

# Toolbar HTML to insert before <el-table
TOOLBAR_WITH_DELETE = '''      <!-- 批量操作 -->
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
        <el-button size="small" @click="batchExport">导出选中</el-button>
      </div>
'''

TOOLBAR_EXPORT_ONLY = '''      <!-- 批量操作 -->
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
        <el-button size="small" @click="batchExport">导出选中</el-button>
      </div>
'''

IMPORT_LINE = "import { useBatchOperation } from '@/composables/useBatchOperation'"

COMPOSABLE_WITH_DELETE = "const {{ selectedRows, handleSelectionChange, batchDelete, batchExport }} = useBatchOperation('{endpoint}')"
COMPOSABLE_EXPORT_ONLY = "const {{ selectedRows, handleSelectionChange, batchExport }} = useBatchOperation('{endpoint}')"


def infer_api_endpoint(content):
    """Try to infer API endpoint from existing request calls or api imports."""
    # Pattern 1: request.get('/xxx/yyy/')
    m = re.search(r"request\.(get|post)\(['\"]([^'\"]+)['\"]", content)
    if m:
        path = m.group(2)
        # Strip query params and trailing specific paths
        path = re.sub(r'\?.*$', '', path)
        # Remove trailing ID patterns like ${id}/ or {id}/
        path = re.sub(r'/\$\{[^}]+\}/?$', '/', path)
        path = re.sub(r'/\d+/?$', '/', path)
        # Remove action suffixes like /submit/ /confirm/
        if not path.endswith('/'):
            path += '/'
        return path

    # Pattern 2: import from '@/api/xxx'
    m = re.search(r"from\s+['\"]@/api/([^'\"]+)['\"]", content)
    if m:
        module = m.group(1).replace('/', '_')
        return f'/api/{module}/'

    return '/api/unknown/'


def get_module_dir(filepath):
    """Get the immediate module directory name."""
    rel = os.path.relpath(filepath, VIEWS_DIR)
    parts = rel.split(os.sep)
    return parts[0] if len(parts) > 1 else ''


def should_skip(filepath):
    """Check if file should be skipped."""
    basename = os.path.basename(filepath)
    if SKIP_PATTERNS.search(basename):
        return True
    return False


def process_file(filepath):
    """Add selection column and batch toolbar to a single .vue file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Skip if already has selection
    if 'type="selection"' in content or "type='selection'" in content:
        return False, 'already has selection'

    # Skip if no el-table
    if '<el-table' not in content:
        return False, 'no el-table'

    # Skip non-list pages
    if should_skip(filepath):
        return False, 'skipped (non-list page)'

    module_dir = get_module_dir(filepath)
    is_read_only = module_dir in READ_ONLY_DIRS

    # --- Step 1: Add @selection-change to <el-table ---
    # Find <el-table that doesn't already have @selection-change
    el_table_pattern = re.compile(r'(<el-table\b[^>]*?)(>)', re.DOTALL)

    def add_selection_change(match):
        tag_content = match.group(1)
        closing = match.group(2)
        if '@selection-change' in tag_content:
            return match.group(0)
        # Add before closing >
        return tag_content + ' @selection-change="handleSelectionChange"' + closing

    new_content = el_table_pattern.sub(add_selection_change, content, count=1)

    # --- Step 2: Add selection column after <el-table ...> ---
    # Find the first <el-table...> and insert selection column after it
    el_table_open = re.compile(r'(<el-table\b[^>]*>)\s*\n')
    m = el_table_open.search(new_content)
    if m:
        insert_pos = m.end()
        indent = '        '
        # Detect indent from next line
        next_line_match = re.search(r'\n(\s*)<el-table-column', new_content[insert_pos:])
        if next_line_match:
            indent = next_line_match.group(1)
        selection_col = f'{indent}<el-table-column type="selection" width="45" />\n'
        new_content = new_content[:insert_pos] + selection_col + new_content[insert_pos:]

    # --- Step 3: Add toolbar before <el-table ---
    toolbar = TOOLBAR_EXPORT_ONLY if is_read_only else TOOLBAR_WITH_DELETE
    # Find the <el-table line and insert toolbar before it
    table_line_pattern = re.compile(r'(\n(\s*)<el-table\b)')
    m = table_line_pattern.search(new_content)
    if m:
        indent = m.group(2)
        # Adjust toolbar indentation
        toolbar_adjusted = toolbar.replace('      ', indent)
        insert_pos = m.start() + 1  # after the \n
        new_content = new_content[:insert_pos] + toolbar_adjusted + new_content[insert_pos:]

    # --- Step 4: Add import and composable call in <script setup> ---
    endpoint = infer_api_endpoint(content)

    if IMPORT_LINE not in new_content:
        # Find <script setup> and add import after existing imports
        script_setup_match = re.search(r'<script\s+setup[^>]*>', new_content)
        if script_setup_match:
            # Find the last import line in the script section
            script_start = script_setup_match.end()
            script_end_match = re.search(r'</script>', new_content[script_start:])
            if script_end_match:
                script_section = new_content[script_start:script_start + script_end_match.start()]

                # Find position after last import
                last_import = -1
                for m_imp in re.finditer(r'^import\s+.+$', script_section, re.MULTILINE):
                    last_import = m_imp.end()

                if last_import == -1:
                    # No imports found, add right after <script setup>
                    insert_pos = script_start
                    prefix = '\n'
                else:
                    insert_pos = script_start + last_import
                    prefix = '\n'

                if is_read_only:
                    composable_line = COMPOSABLE_EXPORT_ONLY.format(endpoint=endpoint)
                else:
                    composable_line = COMPOSABLE_WITH_DELETE.format(endpoint=endpoint)

                inject = f"{prefix}{IMPORT_LINE}\n\n{composable_line}\n"
                new_content = new_content[:insert_pos] + inject + new_content[insert_pos:]

    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True, f'modified (endpoint: {endpoint})'

    return False, 'no changes needed'


def main():
    modified = 0
    skipped = 0
    errors = []

    for root, dirs, files in os.walk(VIEWS_DIR):
        for fname in sorted(files):
            if not fname.endswith('.vue'):
                continue
            filepath = os.path.join(root, fname)
            try:
                changed, reason = process_file(filepath)
                rel_path = os.path.relpath(filepath, VIEWS_DIR)
                if changed:
                    modified += 1
                    print(f'  + {rel_path} — {reason}')
                else:
                    skipped += 1
            except Exception as e:
                rel_path = os.path.relpath(filepath, VIEWS_DIR)
                errors.append((rel_path, str(e)))
                print(f'  ! {rel_path} — ERROR: {e}')

    print(f'\nDone: {modified} modified, {skipped} skipped, {len(errors)} errors')
    if errors:
        print('\nErrors:')
        for path, err in errors:
            print(f'  {path}: {err}')


if __name__ == '__main__':
    main()
