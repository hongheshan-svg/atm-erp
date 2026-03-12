#!/usr/bin/env python3
"""
全面的权限测试脚本
测试所有角色访问各个模块的权限
"""
import requests
import json
import sys
from datetime import datetime

BASE_URL = "https://localhost:8443/api"

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_login(username, password):
    """测试登录"""
    url = f"{BASE_URL}/auth/login/"
    data = {"username": username, "password": password}
    response = requests.post(url, json=data, verify=False)
    if response.status_code == 200:
        result = response.json()
        return result['access'], result['user']
    return None, None

def test_endpoint(token, endpoint, method='GET', expected_status=200):
    """测试单个端点"""
    url = f"{BASE_URL}{endpoint}"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        if method == 'GET':
            response = requests.get(url, headers=headers, verify=False, timeout=5)
        elif method == 'POST':
            response = requests.post(url, json={}, headers=headers, verify=False, timeout=5)

        status = response.status_code
        success = (status == expected_status)

        return {
            'success': success,
            'status': status,
            'expected': expected_status,
            'data': response.json() if response.content else {}
        }
    except Exception as e:
        return {
            'success': False,
            'status': 'ERROR',
            'expected': expected_status,
            'error': str(e)
        }

def main():
    print("=" * 80)
    print("全面权限测试 - " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 80)

    # 测试采购员
    print("\n【测试用户】采购员 (test_purchaser)")
    token, user = test_login("test_purchaser", "test123456")

    if not token:
        print("❌ 登录失败")
        sys.exit(1)

    print(f"✅ 登录成功")
    print(f"   角色: {', '.join(user['roles'])}")
    print(f"   权限: {len(user['permissions'])} 个")
    print(f"   菜单: {len(user['menus'])} 个")

    # 采购模块端点
    purchase_endpoints = [
        ("/purchase/requests/", "采购申请列表"),
        ("/purchase/orders/", "采购订单列表"),
        ("/purchase/rfq/", "询价单列表"),
        ("/purchase/receipts/", "收货单列表"),
        ("/purchase/contracts/", "采购合同列表"),
    ]

    print("\n【采购模块测试】")
    results = {'passed': 0, 'failed': 0}

    for endpoint, name in purchase_endpoints:
        result = test_endpoint(token, endpoint, expected_status=200)
        if result['success']:
            print(f"   ✅ {name}: {result['status']}")
            results['passed'] += 1
        else:
            print(f"   ❌ {name}: {result['status']} (预期 {result['expected']})")
            if 'error' in result:
                print(f"      错误: {result['error']}")
            elif 'data' in result and 'detail' in result['data']:
                print(f"      详情: {result['data']['detail']}")
            results['failed'] += 1

    # 其他模块（应该无权限）
    print("\n【其他模块测试（预期无权限）】")
    other_endpoints = [
        ("/projects/projects/", "项目列表", 403),
        ("/sales/orders/", "销售订单列表", 403),
        ("/finance/expenses/", "费用列表", 403),
    ]

    for endpoint, name, expected in other_endpoints:
        result = test_endpoint(token, endpoint, expected_status=expected)
        if result['success']:
            print(f"   ✅ {name}: {result['status']} (正确拒绝)")
            results['passed'] += 1
        else:
            print(f"   ⚠️  {name}: {result['status']} (预期 {expected})")
            results['failed'] += 1

    # 测试管理员
    print("\n" + "=" * 80)
    print("【测试用户】管理员 (admin)")
    admin_token, admin_user = test_login("admin", "admin123")

    if admin_token:
        print(f"✅ 登录成功")
        print(f"   权限: {len(admin_user['permissions'])} 个")

        print("\n【管理员访问测试】")
        for endpoint, name in purchase_endpoints[:3]:
            result = test_endpoint(admin_token, endpoint, expected_status=200)
            if result['success']:
                print(f"   ✅ {name}: {result['status']}")
            else:
                print(f"   ❌ {name}: {result['status']}")

    # 总结
    print("\n" + "=" * 80)
    print(f"测试完成: {results['passed']} 通过, {results['failed']} 失败")
    print("=" * 80)

    return results['failed'] == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
