import os

app_vue_path = "/home/administrator/erp/frontend/src/App.vue"
with open(app_vue_path, "r", encoding="utf-8") as f:
    content = f.read()

el_vars_addition = """
/* ---- Element Plus Modern Settings ---- */
:root {
  --el-color-primary: var(--primary);
  --el-color-primary-light-3: var(--primary-light);
  --el-color-primary-light-5: var(--primary-light);
  --el-color-primary-light-7: var(--primary-soft);
  --el-color-primary-light-9: var(--primary-soft);
  --el-color-primary-dark-2: var(--primary-dark);
  
  --el-border-radius-base: 8px;
  --el-border-radius-small: 6px;
  --el-border-radius-round: 24px;
  
  --el-bg-color-page: var(--bg-page);
  --el-bg-color: var(--bg-card);
  --el-border-color-lighter: var(--border-light);
  --el-border-color-light: var(--border);
  --el-text-color-primary: var(--text-primary);
  --el-text-color-regular: var(--text-secondary);
  --el-text-color-secondary: var(--text-muted);
  
  --el-box-shadow-light: var(--shadow-sm);
  --el-box-shadow: var(--shadow-md);
  
  --el-font-weight-primary: 500;
}

body {
  background-color: var(--bg-page);
}

/* Base Layout Fixes */
.el-menu {
  border-right: none !important;
}
"""

if "/* ---- Element Plus Modern Settings ---- */" not in content:
    content = content.replace("/* ---- Element Plus Global Overrides ---- */", el_vars_addition + "\n/* ---- Element Plus Global Overrides ---- */")
    with open(app_vue_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Added Element Plus modern variables.")
else:
    print("Already added.")
