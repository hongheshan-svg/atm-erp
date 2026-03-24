import os

app_vue_path = "/home/administrator/erp/frontend/src/App.vue"
with open(app_vue_path, "r", encoding="utf-8") as f:
    content = f.read()

old_vars = """<style>
:root {
  /* Brand Colors */
  --primary: #4361ee;
  --primary-light: #6c83f4;
  --primary-dark: #3451d1;
  --accent: #06d6a0;
  --accent-light: #34e0b5;
  /* Neutral */
  --bg-page: #f0f2f5;
  --bg-card: #ffffff;
  --bg-sidebar: #1e293b;
  --bg-sidebar-deep: #0f172a;
  --text-primary: #1e293b;
  --text-secondary: #64748b;
  --text-muted: #94a3b8;
  --border: #e2e8f0;
  --border-light: #f1f5f9;
  /* Shadows */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.07), 0 2px 4px -2px rgba(0, 0, 0, 0.05);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.08), 0 4px 6px -4px rgba(0, 0, 0, 0.04);
  /* Radius */
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 12px;
  /* Transition */
  --transition: 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}"""

new_vars = """<style>
:root {
  /* Brand Colors - Gemini INSPIRED */
  --primary: #1a73e8;
  --primary-light: #8ab4f8;
  --primary-dark: #1557b0;
  --primary-soft: #e8f0fe;
  --accent: #12b76a;
  --accent-light: #32d583;
  /* Neutral */
  --bg-page: #f8f9fa;
  --bg-card: #ffffff;
  --bg-sidebar: #ffffff;
  --bg-sidebar-deep: #f8f9fa;
  --text-primary: #202124;
  --text-secondary: #5f6368;
  --text-muted: #9aa0a6;
  --border: #dadce0;
  --border-light: #f1f3f4;
  /* Shadows - Softer Gemini Style */
  --shadow-sm: 0 1px 2px 0 rgba(60, 64, 67, 0.3), 0 1px 3px 1px rgba(60, 64, 67, 0.15);
  --shadow-md: 0 1px 3px 0 rgba(60, 64, 67, 0.3), 0 4px 8px 3px rgba(60, 64, 67, 0.15);
  --shadow-lg: 0 4px 6px 0 rgba(60, 64, 67, 0.3), 0 8px 24px 8px rgba(60, 64, 67, 0.15);
  /* Radius - Highly rounded */
  --radius-sm: 8px;
  --radius-md: 16px;
  --radius-lg: 24px;
  /* Transition */
  --transition: 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}"""

if old_vars in content:
    content = content.replace(old_vars, new_vars)
    with open(app_vue_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("App.vue updated successfully!")
else:
    print("Could not find old_vars in App.vue")
