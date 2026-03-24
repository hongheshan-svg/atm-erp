import os

app_vue_path = "/home/administrator/erp/frontend/src/App.vue"
with open(app_vue_path, "r", encoding="utf-8") as f:
    content = f.read()

input_styles = """
/* ---- Element Plus Components Style Overrides ---- */
.el-input__wrapper, .el-textarea__inner {
  border-radius: 8px !important;
  box-shadow: 0 0 0 1px var(--border) inset !important;
}
.el-input__wrapper:hover, .el-textarea__inner:hover {
  box-shadow: 0 0 0 1px var(--border-light) inset, 0 1px 3px rgba(0,0,0,0.06) !important;
}
.el-input__wrapper.is-focus, .el-textarea__inner:focus {
  box-shadow: 0 0 0 2px var(--primary-light) inset !important;
}

.el-button {
  border-radius: 8px !important;
  font-weight: 500 !important;
}

.el-button.is-round {
  border-radius: 20px !important;
}

.el-menu-item {
  border-radius: 8px;
}
"""

if "/* ---- Element Plus Components Style Overrides ---- */" not in content:
    content += "\n" + input_styles
    with open(app_vue_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Added input overrides.")
else:
    print("Already added.")
