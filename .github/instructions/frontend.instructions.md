---
description: "Use when editing Vue components, Pinia stores, router definitions, permission checks, or API wrappers in frontend/src. Covers request wrapper usage, route metadata, menu access, and v-permission patterns."
name: "ERP Frontend Guidelines"
applyTo: "frontend/src/**"
---

# Frontend Guidelines

- Keep API calls in `frontend/src/api/` and use the shared wrapper in `frontend/src/utils/request.js`; avoid raw axios calls from views or components.
- Use the existing module structure under `frontend/src/` and prefer `@` imports for files inside `src/`.
- Preserve the current permission model: route metadata, `hasMenuAccess()`, store-driven menu loading, and `v-permission` for action-level control.
- When adding or changing routes, keep `menuId`, titles, icons, and auth metadata aligned with backend menu permission codes.
- Follow existing ERP page patterns for search forms, tables, dialogs, and pagination instead of introducing a new page architecture.
- Put reusable UI or dialog logic into shared components when a page starts mixing list, form, and detail concerns.
- If a page depends on a backend contract change, update the corresponding API wrapper first and then adjust the consuming view or store.
- Validate with the smallest relevant command first, such as `cd frontend && npm run build`, and use the existing root-level frontend or permission scripts when the change affects menus or access control.
- Be careful with debugging leftovers in views, layouts, or menu components; do not keep temporary console logging, debug menu items, or permission bypasses.