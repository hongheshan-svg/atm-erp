#!/usr/bin/env python3
"""
权限系统自动化测试脚本
测试不同角色的权限和API访问
"""
import requests
import json
import sys

BASE_URL = "http://localhost:8080/api"

# 禁用 SSL 警告
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
    else:
        print(f"❌ 登录失败: {response.status_code}")
        return None, None

def test_api_access(token, endpoint, method='GET', data=None):
    """测试API访问"""
    url = f"{BASE_URL}{endpoint}"
    headers = {"Authorization": f"Bearer {token}"}

    if method == 'GET':
        response = requests.get(url, headers=headers, verify=False)
    elif method == 'POST':
        response = requests.post(url, json=data, headers=headers, verify=False)

    return response.status_code, response.json() if response.content else {}

def main():
    print("=" * 60)
    print("权限系统自动化测试")
    print("=" * 60)

    # 测试采购员账户
    print("\n【测试1】采购员登录")
    token, user = test_login("test_purchaser", "test123456")

    if not token:
        print("❌ 测试失败：无法登录")
        sys.exit(1)

    print(f"✅ 登录成功: {user['username']}")
    print(f"   角色: {user['roles']}")
    print(f"   权限数量: {len(user['permissions'])}")
    print(f"   菜单数量: {len(user['menus'])}")

    # 测试权限列表
    print("\n【测试2】权限列表")
    for perm in user['permissions'][:5]:
        print(f"   - {perm}")
    if len(user['permissions']) > 5:
        print(f"   ... 还有 {len(user['permissions']) - 5} 个权限")

    # 测试菜单结构
    print("\n【测试3】菜单结构")
    for menu in user['menus']:
        print(f"   📁 {menu['name']} ({menu['code']})")
        for child in menu.get('children', []):
            print(f"      └─ {child['name']} ({child['code']})")

    # 测试API访问
    print("\n【测试4】API访问测试")

    # 测试采购订单列表
    status, data = test_api_access(token, "/purchase/orders/")
    if status == 200:
        print(f"   ✅ 采购订单列表: {status}")
    else:
        print(f"   ❌ 采购订单列表: {status} - {data.get('detail', '')}")

    # 测试权限API
    status, data = test_api_access(token, "/core/permissions/")
    if status == 200:
        print(f"   ✅ 权限列表: {status}")
    else:
        print(f"   ❌ 权限列表: {status} - {data.get('detail', '')}")

    # 测试项目列表（应该无权限）
    status, data = test_api_access(token, "/projects/projects/")
    if status == 403:
        print(f"   ✅ 项目列表（预期无权限）: {status}")
    elif status == 200:
        print(f"   ⚠️  项目列表（预期无权限但可访问）: {status}")
    else:
        print(f"   ❓ 项目列表: {status} - {data.get('detail', '')}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    main()
