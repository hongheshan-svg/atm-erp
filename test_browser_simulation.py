#!/usr/bin/env python3
"""
ERP System Browser Simulation Test
Simulates real user workflows: login, navigate pages, perform CRUD operations.
Captures all browser console errors and network failures.
"""
import json
import sys
import time
from collections import defaultdict
from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:8080/erp"
USERNAME = "admin"
PASSWORD = "admin123"

ROUTES = {
    "工作台": ["/dashboard"],
    "系统管理": [
        "/system/users",
        "/system/roles",
        "/system/departments",
        "/system/code-rules",
        "/system/notification-settings",
    ],
    "基础资料": [
        "/masterdata/items",
        "/masterdata/customers",
        "/masterdata/suppliers",
        "/masterdata/warehouses",
        "/masterdata/locations",
    ],
    "项目管理": [
        "/projects/list",
        "/projects/tasks",
        "/projects/bom",
        "/projects/drawings",
    ],
    "商务销售": [
        "/sales/quotations",
        "/sales/orders",
        "/sales/contracts",
        "/sales/deliveries",
    ],
    "采购供应": [
        "/purchase/requests",
        "/purchase/rfq",
        "/purchase/orders",
        "/purchase/receipts",
    ],
    "生产制造": [
        "/production/plans",
        "/production/orders",
        "/production/process-routes",
    ],
    "仓储物料": [
        "/inventory/stock",
        "/inventory/moves",
        "/inventory/adjustments",
    ],
    "财务管理": [
        "/finance/invoices",
        "/finance/payments",
        "/finance/expenses",
        "/finance/receivables",
        "/finance/payables",
    ],
    "办公OA": [
        "/oa/announcements",
        "/oa/vehicles",
    ],
    "CRM": [
        "/sales/crm/leads",
        "/sales/crm/opportunities",
    ],
    "报表分析": [
        "/reports/dashboard",
    ],
}


def run_simulation():
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
            if msg.type in ("error", "warning"):
                console_errors.append({
                    "type": msg.type,
                    "text": msg.text,
                    "url": page.url,
                })

        def on_response(response):
            if response.status >= 400:
                network_errors.append({
                    "status": response.status,
                    "url": response.url,
                    "page_url": page.url,
                })

        page.on("console", on_console)
        page.on("response", on_response)

        # Step 1: Login
        print("=" * 60)
        print("Step 1: Login")
        print("=" * 60)
        page.goto(f"{BASE_URL}/login", wait_until="networkidle")
        page.fill('input[placeholder*="用户名"], input[type="text"]', USERNAME)
        page.fill('input[placeholder*="密码"], input[type="password"]', PASSWORD)
        page.click('button:has-text("登")')
        page.wait_for_url("**/dashboard", timeout=15000)
        print(f"  OK Login successful, now at: {page.url}")
        time.sleep(1)

        # Step 2: Navigate each route
        print("\n" + "=" * 60)
        print("Step 2: Navigate all pages")
        print("=" * 60)

        for module, routes in ROUTES.items():
            print(f"\n  [{module}]")
            for route in routes:
                url = f"{BASE_URL}{route}"
                errors_before = len(console_errors)
                net_errors_before = len(network_errors)

                try:
                    page.goto(url, wait_until="networkidle", timeout=20000)
                    time.sleep(0.5)

                    new_errors = len(console_errors) - errors_before
                    new_net_errors = len(network_errors) - net_errors_before

                    status = "OK" if (new_errors == 0 and new_net_errors == 0) else "ERR"
                    detail = ""
                    if new_errors > 0:
                        detail += f" {new_errors} console"
                    if new_net_errors > 0:
                        detail += f" {new_net_errors} network"

                    page_results[route] = {
                        "status": "ok" if status == "OK" else "error",
                        "console_errors": new_errors,
                        "network_errors": new_net_errors,
                    }
                    print(f"    {status} {route}{detail}")
                except Exception as e:
                    page_results[route] = {
                        "status": "timeout",
                        "error": str(e),
                    }
                    print(f"    TIMEOUT {route} - {str(e)[:80]}")

        # Step 3: Test interactions
        print("\n" + "=" * 60)
        print("Step 3: Test interactions")
        print("=" * 60)

        try:
            page.goto(f"{BASE_URL}/masterdata/items", wait_until="networkidle", timeout=15000)
            time.sleep(1)
            new_btn = page.locator('button:has-text("新增"), button:has-text("新建"), button:has-text("添加")')
            if new_btn.count() > 0:
                new_btn.first.click()
                time.sleep(1)
                print("  OK Items: New dialog opened")
                close_btn = page.locator('.el-dialog__close, button:has-text("取消")')
                if close_btn.count() > 0:
                    close_btn.first.click()
                    time.sleep(0.5)
            else:
                print("  -- Items: No new button found")
        except Exception as e:
            print(f"  ERR Items: {e}")

        try:
            page.goto(f"{BASE_URL}/masterdata/customers", wait_until="networkidle", timeout=15000)
            time.sleep(1)
            search_input = page.locator('input[placeholder*="搜索"], input[placeholder*="关键字"], input[placeholder*="名称"]')
            if search_input.count() > 0:
                search_input.first.fill("test")
                time.sleep(0.3)
                search_btn = page.locator('button:has-text("搜索"), button:has-text("查询")')
                if search_btn.count() > 0:
                    search_btn.first.click()
                    time.sleep(1)
                print("  OK Customers: Search tested")
            else:
                print("  -- Customers: No search input found")
        except Exception as e:
            print(f"  ERR Customers: {e}")

        browser.close()

    # Report
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)

    error_summary = defaultdict(list)
    for err in console_errors:
        key = err["text"][:150]
        error_summary[key].append(err["url"])

    print(f"\nConsole errors/warnings: {len(console_errors)} total, {len(error_summary)} unique")
    for text, urls in sorted(error_summary.items()):
        unique_urls = sorted(set(urls))[:3]
        print(f"\n  [{text[:120]}]")
        for u in unique_urls:
            print(f"    on: {u}")

    net_error_summary = defaultdict(list)
    for err in network_errors:
        key = f"{err['status']} {err['url']}"
        net_error_summary[key].append(err["page_url"])

    print(f"\nNetwork errors (4xx/5xx): {len(network_errors)} total, {len(net_error_summary)} unique")
    for key, pages in sorted(net_error_summary.items()):
        unique_pages = sorted(set(pages))[:3]
        print(f"\n  {key}")
        for pg in unique_pages:
            print(f"    on page: {pg}")

    ok_count = sum(1 for r in page_results.values() if r["status"] == "ok")
    error_count = sum(1 for r in page_results.values() if r["status"] == "error")
    timeout_count = sum(1 for r in page_results.values() if r["status"] == "timeout")
    print(f"\nPages: {ok_count} ok, {error_count} with errors, {timeout_count} timeouts")
    print(f"Total pages tested: {len(page_results)}")

    report = {
        "console_errors": [{"text": k, "count": len(v), "pages": sorted(set(v))[:5]} for k, v in error_summary.items()],
        "network_errors": [{"endpoint": k, "count": len(v), "pages": sorted(set(v))[:5]} for k, v in net_error_summary.items()],
        "page_results": page_results,
    }
    with open("/home/administrator/erp/test_browser_report.json", "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("\nReport saved: test_browser_report.json")


if __name__ == "__main__":
    run_simulation()
