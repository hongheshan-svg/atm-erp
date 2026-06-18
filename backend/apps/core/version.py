"""应用版本与部署模式来源,以及 semver 比较。"""
from __future__ import annotations

import os


def get_app_version() -> str:
    """当前运行版本。Docker 由 compose 注入 APP_VERSION=<image tag>;
    原生由部署脚本写入。缺省回退 '0.0.0'(开发态)。"""
    return os.environ.get('APP_VERSION', '0.0.0').strip() or '0.0.0'


def get_deploy_mode() -> str:
    """部署模式:docker | native | unknown。"""
    mode = os.environ.get('DEPLOY_MODE', '').strip().lower()
    return mode if mode in ('docker', 'native') else 'unknown'


def _parse(v: str) -> list[int]:
    v = v.strip()
    if v.startswith('v'):
        v = v[1:]
    parts = []
    for seg in v.split('.'):
        num = ''.join(ch for ch in seg if ch.isdigit())
        parts.append(int(num) if num else 0)
    return parts


def compare_versions(a: str, b: str) -> int:
    """返回 -1 (a<b) / 0 (a==b) / 1 (a>b),按 semver 整型分段比较。"""
    pa, pb = _parse(a), _parse(b)
    n = max(len(pa), len(pb))
    pa += [0] * (n - len(pa))
    pb += [0] * (n - len(pb))
    for x, y in zip(pa, pb):
        if x < y:
            return -1
        if x > y:
            return 1
    return 0
