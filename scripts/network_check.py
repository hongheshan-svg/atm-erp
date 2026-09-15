"""Warn when the published port and the allowed hosts disagree, before it surfaces as HTTP 400."""

import argparse
import sys
from pathlib import Path

LOCAL_HOSTS = {'localhost', '::1', '[::1]', '0:0:0:0:0:0:0:1'}


def setting(text, name, default):
    """Last assignment wins, matching how docker compose reads an env file."""
    value = default
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(f'{name}='):
            value = stripped[len(name) + 1 :].strip()
    return value


def local_only(address):
    address = address.strip().strip('"').strip("'")
    return address in LOCAL_HOSTS or address == '127.0.0.1' or address.startswith('127.')


def warnings(bind, hosts):
    remote = [host.strip() for host in hosts.split(',') if host.strip() and not local_only(host.strip())]
    if not local_only(bind) and not remote:
        return [
            f'端口已绑定到 {bind}，局域网可以连上，但 LEAN_ALLOWED_HOSTS 仍只允许本机。'
            '用真实 IP 或域名打开时服务端会直接拒绝（HTTP 400），表现为登录报错或操作失败。'
            '请把实际访问用的 IP 或域名补进 LEAN_ALLOWED_HOSTS，再重新执行安装器。'
        ]
    if local_only(bind) and remote:
        listed = '、'.join(remote)
        return [
            f'LEAN_ALLOWED_HOSTS 已包含 {listed}，但端口只绑定在 {bind}，局域网仍然连不上。'
            '请把 LEAN_BIND_ADDRESS 设为 0.0.0.0 或该网卡地址，再重新执行安装器。'
        ]
    return []


def inspect(config):
    text = Path(config).read_text(encoding='utf-8-sig')
    return warnings(
        setting(text, 'LEAN_BIND_ADDRESS', '127.0.0.1'), setting(text, 'LEAN_ALLOWED_HOSTS', 'localhost,127.0.0.1')
    )


def main():
    parser = argparse.ArgumentParser(description='检查发布端口与允许访问的主机名是否一致')
    parser.add_argument('--config', required=True)
    arguments = parser.parse_args()
    try:
        found = inspect(arguments.config)
    except OSError:
        return 0
    for note in found:
        print(f'注意：{note}', file=sys.stderr)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
