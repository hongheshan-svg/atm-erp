@echo off
chcp 65001 >nul
title ERP系统一键安装

echo.
echo  ╔═══════════════════════════════════════════════════════╗
echo  ║                                                       ║
echo  ║     ERP系统 Windows Server 一键安装程序               ║
echo  ║                                                       ║
echo  ╚═══════════════════════════════════════════════════════╝
echo.

:: 检查管理员权限
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [!] 需要管理员权限运行此脚本
    echo [i] 正在请求管理员权限...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

:: 获取脚本所在目录
cd /d "%~dp0"

echo [i] 当前目录: %cd%
echo.

:: 检查Docker
echo [i] 检查 Docker 安装状态...
docker --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [×] Docker 未安装
    echo.
    echo 请先安装 Docker Desktop:
    echo https://www.docker.com/products/docker-desktop
    echo.
    pause
    exit /b 1
)
echo [√] Docker 已安装

:: 检查Docker是否运行
docker info >nul 2>&1
if %errorLevel% neq 0 (
    echo [×] Docker 服务未运行
    echo [i] 请启动 Docker Desktop 后重试
    pause
    exit /b 1
)
echo [√] Docker 服务运行中

echo.
echo [i] 开始执行部署脚本...
echo.

:: 执行PowerShell部署脚本
powershell -ExecutionPolicy Bypass -File "%~dp0scripts\deploy-windows.ps1"

echo.
echo 按任意键退出...
pause >nul
