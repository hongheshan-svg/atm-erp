#!/usr/bin/env python3
"""Run the complete local CI suite against the Docker deployment."""

import os
import subprocess
import sys
from collections.abc import Sequence

ROOT = os.path.dirname(os.path.abspath(__file__))


def run(
    label: str,
    command: Sequence[str],
    *,
    cwd: str = ROOT,
    env: dict[str, str] | None = None,
) -> bool:
    print(f"\n{'=' * 80}\n{label}\n{'=' * 80}", flush=True)
    completed = subprocess.run(command, cwd=cwd, env=env, check=False)
    if completed.returncode:
        print(f"FAILED ({completed.returncode}): {' '.join(command)}", file=sys.stderr)
        return False
    return True


def compose_exec(*command: str) -> list[str]:
    return ["docker", "compose", "exec", "-T", "app", *command]


def main() -> int:
    secure_env = [
        "-e",
        "SECURE_SSL_REDIRECT=True",
        "-e",
        "SECURE_HSTS_SECONDS=31536000",
        "-e",
        "SECURE_HSTS_INCLUDE_SUBDOMAINS=True",
        "-e",
        "SECURE_HSTS_PRELOAD=True",
        "-e",
        "SESSION_COOKIE_SECURE=True",
        "-e",
        "CSRF_COOKIE_SECURE=True",
    ]
    steps = [
        (
            "后端 Ruff 检查",
            ["uvx", "ruff==0.16.0", "check", "backend"],
            ROOT,
        ),
        (
            "数据库迁移",
            compose_exec("python", "manage.py", "migrate", "--noinput"),
            ROOT,
        ),
        ("权限树初始化", compose_exec("python", "manage.py", "init_permissions"), ROOT),
        (
            "角色初始化",
            compose_exec("python", "manage.py", "init_roles", "--force"),
            ROOT,
        ),
        (
            "仪表盘初始化",
            compose_exec("python", "manage.py", "init_dashboard_widgets"),
            ROOT,
        ),
        (
            "Django 生产检查",
            [
                "docker",
                "compose",
                "exec",
                "-T",
                *secure_env,
                "app",
                "python",
                "-W",
                "error::DeprecationWarning",
                "manage.py",
                "check",
                "--deploy",
            ],
            ROOT,
        ),
        (
            "OpenAPI 校验",
            compose_exec(
                "python",
                "manage.py",
                "spectacular",
                "--file",
                "/tmp/schema.yml",
                "--validate",
                "--fail-on-warn",
            ),
            ROOT,
        ),
        (
            "迁移漂移检查",
            compose_exec(
                "python", "manage.py", "makemigrations", "--check", "--dry-run"
            ),
            ROOT,
        ),
        (
            "Django 全量测试",
            compose_exec(
                "python",
                "-W",
                "error::DeprecationWarning",
                "manage.py",
                "test",
                "--noinput",
            ),
            ROOT,
        ),
        (
            "安装后端测试依赖",
            compose_exec(
                "pip",
                "install",
                "--root-user-action=ignore",
                "-q",
                "-r",
                "requirements-dev.txt",
            ),
            ROOT,
        ),
        ("后端依赖审计", compose_exec("pip-audit", "-r", "requirements.txt"), ROOT),
        (
            "后端集成测试",
            compose_exec(
                "pytest",
                "tests/integration",
                "-v",
                "--tb=short",
                "-W",
                "error::DeprecationWarning",
            ),
            ROOT,
        ),
        (
            "前端依赖安装",
            ["npm", "ci", "--no-audit", "--no-fund"],
            os.path.join(ROOT, "frontend"),
        ),
        (
            "前端依赖审计",
            [
                "npm",
                "audit",
                "--audit-level=high",
                "--registry=https://registry.npmjs.org",
            ],
            os.path.join(ROOT, "frontend"),
        ),
        ("前端类型检查", ["npm", "run", "typecheck"], os.path.join(ROOT, "frontend")),
        ("前端 Lint", ["npm", "run", "lint"], os.path.join(ROOT, "frontend")),
        ("前端单元测试", ["npm", "run", "test"], os.path.join(ROOT, "frontend")),
        ("前端生产构建", ["npm", "run", "build"], os.path.join(ROOT, "frontend")),
        ("浏览器深度巡检", [sys.executable, "test_browser_deep.py"], ROOT),
        ("Vue 运行时巡检", [sys.executable, "test_vue_runtime.py"], ROOT),
    ]

    for label, command, cwd in steps:
        if not run(label, command, cwd=cwd):
            return 1

    print("\n全部检查通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
