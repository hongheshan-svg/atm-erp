#!/usr/bin/env python3
"""Check for Vue runtime warnings, JS errors, and failed network requests across all pages."""
import json, time
from collections import defaultdict
from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:8080/erp"

ROUTES = [
    "/dashboard",
    "/system/users", "/system/roles", "/system/departments",
    "/system/code-rules", "/system/notification-settings",
    "/system/dict", "/system/audit-logs", "/system/workflows",
    "/system/permissions", "/system/data-scopes", "/system/custom-fields",
    "/masterdata/items", "/masterdata/customers", "/masterdata/suppliers",
    "/masterdata/warehouses", "/masterdata/locations", "/masterdata/item-categories",
    "/projects/list", "/projects/tasks", "/projects/bom", "/projects/drawings",
    "/projects/gantt", "/equipment/list", "/knowledge/articles", "/projects/tech-documents",
    "/sales/quotations", "/sales/orders", "/sales/contracts", "/sales/deliveries",
    "/sales/crm/leads", "/sales/crm/opportunities", "/sales/crm/dashboard",
    "/purchase/requests", "/purchase/rfq", "/purchase/orders", "/purchase/receipts",
    "/purchase/suppliers/evaluation", "/purchase/outsource",
    "/production/plans", "/production/orders", "/production/process-routes",
    "/production/kanban", "/production/mes", "/production/work-centers", "/production/capacity",
    "/inventory/stock", "/inventory/moves", "/inventory/adjustments",
    "/inventory/mrp", "/inventory/spare-parts", "/inventory/alerts",
    "/finance/invoices", "/finance/payments", "/finance/expenses",
    "/finance/receivables", "/finance/payables", "/finance/assets",
    "/finance/reconciliation", "/finance/collection", "/finance/budgets",
    "/oa/announcements", "/oa/vehicles", "/oa/meetings", "/oa/documents", "/oa/schedules",
    "/reports/dashboard", "/reports/templates", "/analytics/dashboard",
    "/settings/profile", "/settings/security",
]

def run():
    all_console = []
    all_network = []
    vue_warnings = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width":1920,"height":1080}, ignore_https_errors=True)
        page = ctx.new_page()

        def on_console(msg):
            text = msg.text
            url = page.url
            if msg.type == "error":
                all_console.append({"type":"error","text":text[:300],"url":url})
            elif msg.type == "warning" and ("[Vue warn]" in text or "warn" in text.lower()):
                vue_warnings.append({"text":text[:300],"url":url})

        def on_response(resp):
            if resp.status >= 400:
                all_network.append({"status":resp.status,"endpoint":resp.url.split("?")[0],"page":page.url})

        page.on("console", on_console)
        page.on("response", on_response)

        # Login
        page.goto(f"{BASE_URL}/login", wait_until="networkidle")
        page.fill('input[placeholder*="用户名"], input[type="text"]', "admin")
        page.fill('input[placeholder*="密码"], input[type="password"]', "admin123")
        page.click('button:has-text("登")')
        page.wait_for_url("**/dashboard", timeout=15000)
        time.sleep(1)
        print("Logged in\n")

        total = len(ROUTES)
        for i, route in enumerate(ROUTES, 1):
            ce_b, ne_b, vw_b = len(all_console), len(all_network), len(vue_warnings)
            try:
                page.goto(f"{BASE_URL}{route}", wait_until="networkidle", timeout=15000)
                time.sleep(0.5)
            except:
                print(f"  [{i:2d}/{total}] TIMEOUT {route}")
                continue
            ce_n = len(all_console)-ce_b
            ne_n = len(all_network)-ne_b
            vw_n = len(vue_warnings)-vw_b
            parts = []
            if ce_n: parts.append(f"{ce_n} err")
            if ne_n: parts.append(f"{ne_n} net")
            if vw_n: parts.append(f"{vw_n} warn")
            status = "OK" if not parts else "!!"
            detail = f" [{', '.join(parts)}]" if parts else ""
            print(f"  [{i:2d}/{total}] {status} {route}{detail}")

        browser.close()

    # Report
    print("\n" + "="*60)
    # Deduplicate
    errs = defaultdict(list)
    for e in all_console:
        errs[e["text"][:120]].append(e["url"])
    nets = defaultdict(list)
    for e in all_network:
        nets[f'{e["status"]} {e["endpoint"]}'].append(e["page"])
    warns = defaultdict(list)
    for w in vue_warnings:
        warns[w["text"][:120]].append(w["url"])

    if errs:
        print(f"\nJS Errors ({len(all_console)} total, {len(errs)} unique):")
        for t, urls in sorted(errs.items()):
            print(f"  - {t}")
            for u in sorted(set(urls))[:2]:
                print(f"    @ {u}")
    else:
        print("\nNo JS errors!")

    if nets:
        print(f"\nNetwork Errors ({len(all_network)} total, {len(nets)} unique):")
        for k, pages in sorted(nets.items()):
            print(f"  - {k}")
            for pg in sorted(set(pages))[:2]:
                print(f"    @ {pg}")
    else:
        print("No network errors!")

    if warns:
        print(f"\nVue Warnings ({len(vue_warnings)} total, {len(warns)} unique):")
        for t, urls in sorted(warns.items()):
            print(f"  - {t}")
            for u in sorted(set(urls))[:2]:
                print(f"    @ {u}")
    else:
        print("No Vue warnings!")

    print(f"\nTotals: {len(all_console)} JS errors, {len(all_network)} network errors, {len(vue_warnings)} Vue warnings")

    with open("test_vue_runtime_report.json","w") as f:
        json.dump({"js_errors":list(errs.keys()),"network_errors":list(nets.keys()),"vue_warnings":list(warns.keys())},f,ensure_ascii=False,indent=2)

if __name__=="__main__":
    run()
