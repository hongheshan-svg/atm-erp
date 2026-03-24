import os

layout_path = "/home/administrator/erp/frontend/src/layout/MainLayout.vue"
with open(layout_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace sidebar text colors
replacements = [
    ("color: #f1f5f9;", "color: var(--text-primary);"),
    ("border-bottom: 1px solid rgba(255, 255, 255, 0.06);", "border-bottom: 1px solid var(--border-light);"),
    ("color: rgba(255, 255, 255, 0.6) !important;", "color: var(--text-secondary) !important;"),
    ("background-color: rgba(255, 255, 255, 0.06) !important;", "background-color: var(--primary-soft) !important;"),
    ("color: #fff !important;", "color: var(--primary) !important;")
]

for old, new in replacements:
    content = content.replace(old, new)

# But wait, `.sidebar-menu :deep(.el-menu-item.is-active)` had `background: var(--primary) !important; color: #fff !important;`
# The last replace might overlap. Let's fix that.
content = content.replace("""
.sidebar-menu :deep(.el-menu-item.is-active) {
  background: var(--primary) !important;
  color: var(--primary) !important; /* replaced by previous step incorrectly */
  font-weight: 500;
}
""", """
.sidebar-menu :deep(.el-menu-item.is-active) {
  background: var(--primary-soft) !important;
  color: var(--primary) !important;
  font-weight: 600;
  border-radius: var(--radius-md);
}
""")

content = content.replace("""
.sidebar-menu :deep(.el-menu-item.is-active) {
  background: var(--primary) !important;
  color: #fff !important;
  font-weight: 500;
}
""", """
.sidebar-menu :deep(.el-menu-item.is-active) {
  background: var(--primary-soft) !important;
  color: var(--primary) !important;
  font-weight: 600;
  border-radius: var(--radius-md);
}
""")

# Also borders
content = content.replace("border-right: none;", "border-right: 1px solid var(--border-light);")

with open(layout_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Layout updated!")
