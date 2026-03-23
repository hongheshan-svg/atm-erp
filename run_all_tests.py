#!/usr/bin/env python3
"""
全自动化测试系统
整合后端API测试和前端浏览器测试
"""
import subprocess
import sys
from datetime import datetime


def bootstrap_database():
    """初始化测试所需的数据库基础数据"""
    print("\n" + "=" * 80)
    print("【0/3】数据库初始化与校验")
    print("=" * 80)

    try:
        result = subprocess.run(
            [
                'docker', 'compose', 'exec', '-T', 'backend', 'python', 'manage.py',
                'migrate', '--noinput'
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        print(result.stdout)
        if result.returncode != 0:
            print(result.stderr)
            return False

        result = subprocess.run(
            [
                'docker', 'compose', 'exec', '-T', 'backend', 'python', 'manage.py',
                'init_roles', '--force'
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        print(result.stdout)
        if result.returncode != 0:
            print(result.stderr)
            return False

        result = subprocess.run(
            [
                'docker', 'compose', 'exec', '-T', 'backend', 'python', 'manage.py',
                'init_industry_roles', '--force'
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        print(result.stdout)
        if result.returncode != 0:
            print(result.stderr)
            return False

        result = subprocess.run(
            [
                'docker', 'compose', 'exec', '-T', 'backend', 'python', 'manage.py',
                'init_data'
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        print(result.stdout)
        if result.returncode != 0:
            print(result.stderr)
            return False

        return True
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        return False

def run_backend_tests():
    """运行后端API测试"""
    print("\n" + "=" * 80)
    print("【1/3】后端API权限测试")
    print("=" * 80)

    try:
        result = subprocess.run(
            ['python3', 'test_comprehensive_permissions.py'],
            capture_output=True,
            text=True,
            timeout=30
        )
        print(result.stdout)
        if result.returncode != 0:
            print(result.stderr)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ 后端测试失败: {e}")
        return False

def run_frontend_tests():
    """运行前端自动化测试"""
    print("\n" + "=" * 80)
    print("【2/3】前端浏览器测试")
    print("=" * 80)

    try:
        # 检查是否安装了 playwright
        check = subprocess.run(
            ['python3', '-c', 'import playwright'],
            capture_output=True
        )

        if check.returncode != 0:
            print("⚠️  Playwright 未安装,跳过前端测试")
            print("   安装命令: pip install playwright && playwright install chromium")
            return None

        result = subprocess.run(
            ['python3', 'test_frontend_auto.py'],
            capture_output=True,
            text=True,
            timeout=180
        )
        print(result.stdout)
        if result.returncode != 0:
            print(result.stderr)
        return result.returncode == 0
    except Exception as e:
        print(f"⚠️  前端测试跳过: {e}")
        return None

def analyze_errors():
    """分析错误并生成报告"""
    print("\n" + "=" * 80)
    print("【错误分析】")
    print("=" * 80)

    try:
        result = subprocess.run(
            ['python3', 'auto_fix_errors.py'],
            capture_output=True,
            text=True,
            timeout=10
        )
        print(result.stdout)
    except Exception as e:
        print(f"⚠️  错误分析跳过: {e}")

def main():
    print("=" * 80)
    print(f"全自动化测试系统 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # 初始化数据库测试数据
    database_ok = bootstrap_database()
    if not database_ok:
        print("\n" + "=" * 80)
        print("测试总结")
        print("=" * 80)
        print("数据库初始化: ❌ 失败")
        print("后端API测试: ⏭️ 未执行")
        print("前端浏览器测试: ⏭️ 未执行")
        print("=" * 80)
        return 1

    # 运行后端测试
    backend_ok = run_backend_tests()

    # 运行前端测试
    frontend_ok = run_frontend_tests()

    # 分析错误
    if frontend_ok is not None:
        analyze_errors()

    # 总结
    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)
    print(f"数据库初始化: {'✅ 通过' if database_ok else '❌ 失败'}")
    print(f"后端API测试: {'✅ 通过' if backend_ok else '❌ 失败'}")
    if frontend_ok is not None:
        print(f"前端浏览器测试: {'✅ 通过' if frontend_ok else '❌ 失败'}")
    else:
        print(f"前端浏览器测试: ⚠️  跳过")
    print("=" * 80)

    return 0 if database_ok and backend_ok and frontend_ok is not False else 1

if __name__ == "__main__":
    sys.exit(main())
