import os

login_path = "/home/administrator/erp/frontend/src/views/Login.vue"
with open(login_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace gradient background
old_bg = "background: linear-gradient(135deg, var(--bg-sidebar) 0%, #1a365d 50%, var(--primary) 100%);"
new_bg = "background: linear-gradient(135deg, #0d1117 0%, #1e293b 50%, var(--primary-dark) 100%);"
content = content.replace(old_bg, new_bg)

# Replace before/after bubbles to be more generic/modern
old_before = "background: rgba(67, 97, 238, 0.12);"
new_before = "background: radial-gradient(circle, rgba(138, 180, 248, 0.15) 0%, transparent 70%); border-radius: 50%; padding: 200px;"
content = content.replace(old_before, new_before)

old_after = "background: rgba(6, 214, 160, 0.08);"
new_after = "background: radial-gradient(circle, rgba(26, 115, 232, 0.15) 0%, transparent 70%); border-radius: 50%; padding: 150px;"
content = content.replace(old_after, new_after)

with open(login_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Login style patched")
