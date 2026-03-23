<template>
  <router-view />
</template>

<script setup>
</script>

<style>
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
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

#app {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
    'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: var(--text-primary);
}

/* ---- Element Plus Global Overrides ---- */

/* Card */
.el-card {
  border-radius: var(--radius-md) !important;
  border: 1px solid var(--border-light) !important;
  box-shadow: var(--shadow-sm) !important;
  transition: box-shadow var(--transition), transform var(--transition) !important;
}
.el-card:hover {
  box-shadow: var(--shadow-md) !important;
}
.el-card__header {
  border-bottom: 1px solid var(--border-light) !important;
  padding: 14px 20px !important;
}
.el-card__body {
  padding: 16px 20px !important;
}

/* Table */
.el-table {
  --el-table-border-color: var(--border-light);
  --el-table-header-bg-color: #f8fafc;
  --el-table-header-text-color: var(--text-secondary);
  font-size: 13px !important;
}
.el-table th.el-table__cell {
  font-weight: 600 !important;
  font-size: 12px !important;
  text-transform: uppercase !important;
  letter-spacing: 0.03em !important;
}

/* Tag */
.el-tag {
  border-radius: 4px !important;
}

/* Button refinements */
.el-button--primary {
  --el-button-bg-color: var(--primary) !important;
  --el-button-border-color: var(--primary) !important;
  --el-button-hover-bg-color: var(--primary-light) !important;
  --el-button-hover-border-color: var(--primary-light) !important;
}

/* Dialog */
.el-dialog {
  border-radius: var(--radius-lg) !important;
}
.el-dialog__header {
  border-bottom: 1px solid var(--border-light);
  margin-right: 0 !important;
  padding: 16px 20px !important;
}

/* Breadcrumb */
.el-breadcrumb__item .el-breadcrumb__inner {
  font-weight: 400 !important;
  color: var(--text-muted) !important;
}
.el-breadcrumb__item:last-child .el-breadcrumb__inner {
  color: var(--text-primary) !important;
  font-weight: 500 !important;
}

/* Scrollbar global */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
</style>
