#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ERP系统自动截图脚本
使用 Playwright 自动登录系统并截取各页面截图

运行方式: python3 capture_screenshots.py
输出目录: screenshots/
"""

import asyncio
import os
from playwright.async_api import async_playwright

# 配置
BASE_URL = "https://192.168.2.3:8443"
USERNAME = "admin"
PASSWORD = "admin123"
SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")

# 需要截图的页面配置
PAGES_TO_CAPTURE = [
    # (文件名, 路径, 等待时间, 特殊操作)
    ("login.png", "/login", 1, "before_login"),
    ("dashboard.png", "/dashboard", 2, None),
    
    # CRM
    ("leads.png", "/sales/leads", 2, None),
    ("opportunities.png", "/sales/opportunities", 2, None),
    ("customer_list.png", "/customers", 2, None),
    ("quotation.png", "/sales/quotations", 2, None),
    
    # PLM
    ("project_list.png", "/projects", 2, None),
    ("task_list.png", "/projects/tasks", 2, None),
    ("gantt.png", "/projects/gantt", 3, None),
    ("bom_list.png", "/projects/bom", 2, None),
    ("drawings.png", "/projects/drawings", 2, None),
    
    # ERP 销售
    ("sales_order.png", "/sales/orders", 2, None),
    ("delivery.png", "/sales/delivery-orders", 2, None),
    
    # ERP 采购
    ("purchase_request.png", "/purchase/requests", 2, None),
    ("purchase_order.png", "/purchase/orders", 2, None),
    ("goods_receipt.png", "/purchase/goods-receipts", 2, None),
    
    # 供应商
    ("supplier_list.png", "/suppliers", 2, None),
    
    # 库存
    ("inventory.png", "/inventory/stocks", 2, None),
    
    # 财务
    ("expense.png", "/finance/expenses", 2, None),
    
    # MES
    ("production_plan.png", "/production/plans", 2, None),
    ("equipment.png", "/equipment/list", 2, None),
    
    # OA
    ("workflow.png", "/workflow/tasks", 2, None),
    
    # 系统
    ("user_list.png", "/users", 2, None),
    ("role_list.png", "/roles", 2, None),
    ("profile.png", "/profile", 2, None),
    
    # 报表
    ("reports.png", "/reports/profitability", 3, None),
]


async def capture_screenshots():
    """截取所有页面截图"""
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    
    async with async_playwright() as p:
        # 启动浏览器（忽略HTTPS证书错误）
        browser = await p.chromium.launch(
            headless=True,
            args=['--ignore-certificate-errors', '--no-sandbox']
        )
        
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            ignore_https_errors=True,
            locale='zh-CN'
        )
        
        page = await context.new_page()
        
        # 先截取登录页
        print("📸 截取登录页...")
        await page.goto(f"{BASE_URL}/login", wait_until="networkidle")
        await asyncio.sleep(1)
        await page.screenshot(path=os.path.join(SCREENSHOT_DIR, "login.png"), full_page=False)
        print("   ✅ login.png")
        
        # 登录
        print("\n🔐 正在登录...")
        try:
            # 填写用户名
            await page.fill('input[placeholder*="用户名"], input[type="text"]', USERNAME)
            # 填写密码
            await page.fill('input[placeholder*="密码"], input[type="password"]', PASSWORD)
            # 点击登录按钮
            await page.click('button[type="submit"], button:has-text("登录")')
            # 等待登录完成
            await page.wait_for_url(f"{BASE_URL}/dashboard", timeout=10000)
            print("   ✅ 登录成功!\n")
        except Exception as e:
            print(f"   ❌ 登录失败: {e}")
            print("   尝试继续截图...\n")
        
        # 截取其他页面
        success_count = 1  # 登录页已成功
        fail_count = 0
        
        for filename, path, wait_time, special in PAGES_TO_CAPTURE:
            if special == "before_login":
                continue  # 登录页已处理
            
            try:
                print(f"📸 截取 {filename}...")
                await page.goto(f"{BASE_URL}{path}", wait_until="networkidle", timeout=30000)
                await asyncio.sleep(wait_time)
                
                # 等待页面加载完成
                await page.wait_for_load_state("domcontentloaded")
                
                # 截图
                screenshot_path = os.path.join(SCREENSHOT_DIR, filename)
                await page.screenshot(path=screenshot_path, full_page=False)
                print(f"   ✅ {filename}")
                success_count += 1
                
            except Exception as e:
                print(f"   ❌ {filename} 失败: {str(e)[:50]}")
                fail_count += 1
        
        await browser.close()
        
        print(f"\n{'='*50}")
        print(f"📊 截图完成!")
        print(f"   成功: {success_count} 张")
        print(f"   失败: {fail_count} 张")
        print(f"   保存位置: {SCREENSHOT_DIR}")
        print(f"{'='*50}")


async def capture_form_screenshots():
    """截取表单弹窗截图（需要点击新建按钮）"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--ignore-certificate-errors', '--no-sandbox']
        )
        
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            ignore_https_errors=True,
            locale='zh-CN'
        )
        
        page = await context.new_page()
        
        # 登录
        await page.goto(f"{BASE_URL}/login", wait_until="networkidle")
        await page.fill('input[placeholder*="用户名"], input[type="text"]', USERNAME)
        await page.fill('input[placeholder*="密码"], input[type="password"]', PASSWORD)
        await page.click('button[type="submit"], button:has-text("登录")')
        
        try:
            await page.wait_for_url(f"{BASE_URL}/dashboard", timeout=10000)
        except:
            pass
        
        # 截取客户表单
        print("\n📸 截取客户表单...")
        try:
            await page.goto(f"{BASE_URL}/customers", wait_until="networkidle")
            await asyncio.sleep(1)
            # 点击新建按钮
            await page.click('button:has-text("新建"), button:has-text("新增"), button:has-text("添加")')
            await asyncio.sleep(1)
            await page.screenshot(path=os.path.join(SCREENSHOT_DIR, "customer_form.png"))
            print("   ✅ customer_form.png")
        except Exception as e:
            print(f"   ❌ customer_form.png 失败: {e}")
        
        # 截取项目表单
        print("📸 截取项目表单...")
        try:
            await page.goto(f"{BASE_URL}/projects", wait_until="networkidle")
            await asyncio.sleep(1)
            await page.click('button:has-text("新建"), button:has-text("新增"), button:has-text("添加")')
            await asyncio.sleep(1)
            await page.screenshot(path=os.path.join(SCREENSHOT_DIR, "project_form.png"))
            print("   ✅ project_form.png")
        except Exception as e:
            print(f"   ❌ project_form.png 失败: {e}")
        
        await browser.close()


async def main():
    """主函数"""
    print("="*50)
    print("🖼️  ERP系统自动截图工具")
    print("="*50)
    print(f"\n系统地址: {BASE_URL}")
    print(f"用户名: {USERNAME}")
    print(f"输出目录: {SCREENSHOT_DIR}\n")
    
    # 截取列表页面
    await capture_screenshots()
    
    # 截取表单弹窗
    await capture_form_screenshots()
    
    print("\n✨ 所有截图任务完成!")
    print("💡 提示: 运行 python3 generate_word.py 重新生成Word文档以嵌入截图")


if __name__ == "__main__":
    asyncio.run(main())
