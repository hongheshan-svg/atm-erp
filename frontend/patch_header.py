import os

layout_path = "/home/administrator/erp/frontend/src/layout/MainLayout.vue"
with open(layout_path, "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace(""".header {
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  flex-shrink: 0;
}""", """.header {
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.3);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  flex-shrink: 0;
  z-index: 10;
}""")

with open(layout_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Header patched")
