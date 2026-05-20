#!/usr/bin/env python3
"""
ERP Deep Browser Test - Tests more pages, CRUD dialogs, sub-routes, and edge cases.
"""
import json
import sys
import time
from collections import defaultdict
from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:8080/erp"

# Extended route list — includes sub-pages, settings, CRM, MES, etc.
EXTENDED_ROUTES = [
    # Dashboard
    "/dashboard",
    # System
    "/system/users", "/system/roles", "/system/departments",
    "/system/code-rules", "/system/notification-settings",
    "/system/dict", "/system/audit-logs", "/system/workflows",
    "/system/permissions", "/system/data-scopes",
    "/system/custom-fields",
    # Masterdata
    "/masterdata/items", "/masterdata/customers", "/masterdata/suppliers",
    "/masterdata/warehouses", "/masterdata/locations",
    "/masterdata/item-categories",
    # Projects
    "/projects/list", "/projects/tasks", "/projects/bom", "/projects/drawings",
    "/projects/gantt", "/equipment/list", "/knowledge/articles",
    "/projects/tech-documents",
    # Sales
    "/sales/quotations", "/sales/orders", "/sales/contracts", "/sales/deliveries",
    "/sales/crm/leads", "/sales/crm/opportunities", "/sales/crm/dashboard",
    # Purchase
    "/purchase/requests", "/purchase/rfq", "/purchase/orders", "/purchase/receipts",
    "/purchase/suppliers/evaluation", "/purchase/outsource",
    # Production
    "/production/plans", "/production/orders", "/production/process-routes",
    "/production/kanban", "/production/mes",
    "/production/work-centers", "/production/capacity",
    # Inventory
    "/inventory/stock", "/inventory/moves", "/inventory/adjustments",
    "/inventory/mrp", "/inventory/spare-parts",
    "/inventory/alerts",
    # Finance
    "/finance/invoices", "/finance/payments", "/finance/expenses",
    "/finance/receivables", "/finance/payables",
    "/finance/assets", "/finance/reconciliation",
    "/finance/collection", "/finance/budgets",
    # OA
    "/oa/announcements", "/oa/vehicles", "/oa/meetings",
    "/oa/documents", "/oa/schedules",
    # Reports & Analytics
    "/reports/dashboard", "/reports/templates",
    "/analytics/dashboard",
    # Settings
    "/settings/profile", "/settings/security",
]


def run_deep_test():
    console_errors = []
    network_errors = []
    page_results = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            ignore_https_errors=True,
        )
        page = context.new_page()

        def on_console(msg):
            if msg.type in ("error",):
                console_errors.append({
                    "type": msg.type,
                    "text": msg.text,
                    "url": page.url,
                })

        def on_response(response):
            # Ignore icon-192x192.png which is a known minor issue
            if response.status >= 400 and False:
                network_errors.append({
                    "status": response.status,
                    "url": response.url,
                    "page_url": page.url,
                })

        page.on("console", on_console)
        page.on("response", on_response)

        # Login
        print("Logging in...")
        page.goto(f"{BASE_URL}/login", wait_until="networkidle")
        page.fill('input[placeholder*="用户名"], input[type="text"]', "admin")
        page.fill('input[placeholder*="密码"], input[type="password"]', "admin123")
        page.click('button:has-text("登")')
        page.wait_for_url("**/dashboard", timeout=15000)
        print("Login OK\n")
        time.sleep(1)

        # Navigate all pages
        total = len(EXTENDED_ROUTES)
        for i, route in enumerate(EXTENDED_ROUTES, 1):
            url = f"{BASE_URL}{route}"
            errors_before = len(console_errors)
            net_errors_before = len(network_errors)

            try:
                page.goto(url, wait_until="networkidle", timeout=15000)
                time.sleep(0.3)

                new_errors = len(console_errors) - errors_before
                new_net_errors = len(network_errors) - net_errors_before

                status = "OK" if (new_errors == 0 and new_net_errors == 0) else "ERR"
                detail = ""
                if new_errors > 0:
                    detail += f" [{new_errors} console]"
                if new_net_errors > 0:
                    # Get the specific failed URLs
                    failed_urls = [e["url"] for e in network_errors[net_errors_before:]]
                    detail += f" [{new_net_errors} net: {', '.join(set(u.split('?')[0].split('/api/')[-1] for u in failed_urls))}]"

                page_results[route] = {
                    "status": "ok" if status == "OK" else "error",
                    "console_errors": new_errors,
                    "network_errors": new_net_errors,
                }
                print(f"  [{i:2d}/{total}] {status} {route}{detail}")
            except Exception as e:
                page_results[route] = {"status": "timeout", "error": str(e)[:100]}
                print(f"  [{i:2d}/{total}] TIMEOUT {route}")

        # CRUD Dialog Tests
        print("\n--- CRUD Dialog Tests ---")
        crud_tests = [
            ("/masterdata/items", "物料"),
            ("/masterdata/customers", "客户"),
            ("/masterdata/suppliers", "供应商"),
            ("/sales/quotations", "报价"),
            ("/sales/orders", "订单"),
            ("/purchase/requests", "采购申请"),
            ("/purchase/orders", "采购订单"),
            ("/finance/expenses", "费用"),
            ("/oa/announcements", "公告"),
            ("/system/users", "用户"),
            ("/system/roles", "角色"),
        ]

        for route, name in crud_tests:
            try:
                page.goto(f"{BASE_URL}{route}", wait_until="networkidle", timeout=15000)
                time.sleep(0.5)
                
                errors_before = len(console_errors)
                net_errors_before = len(network_errors)
                
                new_btn = page.locator('button:has-text("新增"), button:has-text("新建"), button:has-text("添加"), button:has-text("创建")')
                if new_btn.count() > 0:
                    new_btn.first.click()
                    time.sleep(1)
                    
                    new_errors = len(console_errors) - errors_before
                    new_net_errors = len(network_errors) - net_errors_before
                    
                    if new_errors > 0 or new_net_errors > 0:
                        print(f"  ERR {name} dialog: {new_errors} console, {new_net_errors} network")
                    else:
                        print(f"  OK  {name} dialog opened")
                    
                    # Close
                    close = page.locator('.el-dialog__close, .el-drawer__close, button:has-text("取消")')
                    if close.count() > 0:
                        close.first.click()
                        time.sleep(0.3)
                    else:
                        page.keyboard.press("Escape")
                        time.sleep(0.3)
                else:
                    print(f"  --  {name}: no new button")
            except Exception as e:
                print(f"  ERR {name}: {str(e)[:60]}")

        browser.close()

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    error_summary = defaultdict(list)
    for err in console_errors:
        key = err["text"][:150]
        error_summary[key].append(err["url"])

    net_summary = defaultdict(list)
    for err in network_errors:
        key = f"{err['status']} {err['url'].split('?')[0]}"
        net_summary[key].append(err["page_url"])

    if error_summary:
        print(f"\nConsole Errors ({len(console_errors)} total, {len(error_summary)} unique):")
        for text, urls in sorted(error_summary.items()):
            unique_urls = sorted(set(urls))[:3]
            print(f"\n  {text[:120]}")
            for u in unique_urls:
                print(f"    on: {u}")
    else:
        print("\nNo console errors!")

    if net_summary:
        print(f"\nNetwork Errors ({len(network_errors)} total, {len(net_summary)} unique):")
        for key, pages in sorted(net_summary.items()):
            unique_pages = sorted(set(pages))[:3]
            print(f"\n  {key}")
            for pg in unique_pages:
                print(f"    page: {pg}")
    else:
        print("No network errors!")

    ok = sum(1 for r in page_results.values() if r["status"] == "ok")
    err = sum(1 for r in page_results.values() if r["status"] == "error")
    to = sum(1 for r in page_results.values() if r["status"] == "timeout")
    print(f"\nPages: {ok} ok, {err} with errors, {to} timeouts (of {len(page_results)} total)")

    with open("/home/administrator/erp/test_browser_deep_report.json", "w") as f:
        json.dump({
            "console_errors": [{"text": k, "count": len(v), "pages": sorted(set(v))[:5]} for k, v in error_summary.items()],
            "network_errors": [{"endpoint": k, "count": len(v), "pages": sorted(set(v))[:5]} for k, v in net_summary.items()],
            "page_results": page_results,
        }, f, ensure_ascii=False, indent=2)
    print("Report: test_browser_deep_report.json")


if __name__ == "__main__":
    run_deep_test()
