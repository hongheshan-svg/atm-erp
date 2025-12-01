@echo off
chcp 65001 >nul
title ERP系统服务管理

cd /d "%~dp0.."

:menu
cls
echo.
echo  ╔═══════════════════════════════════════════════════════╗
echo  ║                                                       ║
echo  ║           ERP系统 服务管理工具                        ║
echo  ║                                                       ║
echo  ╚═══════════════════════════════════════════════════════╝
echo.
echo   [1] 启动所有服务
echo   [2] 停止所有服务
echo   [3] 重启所有服务
echo   [4] 查看服务状态
echo   [5] 查看实时日志
echo   [6] 备份数据库
echo   [7] 进入后端Shell
echo   [8] 执行数据库迁移
echo   [9] 重建并启动服务
echo   [0] 退出
echo.
set /p choice=请选择操作 [0-9]: 

if "%choice%"=="1" goto start
if "%choice%"=="2" goto stop
if "%choice%"=="3" goto restart
if "%choice%"=="4" goto status
if "%choice%"=="5" goto logs
if "%choice%"=="6" goto backup
if "%choice%"=="7" goto shell
if "%choice%"=="8" goto migrate
if "%choice%"=="9" goto rebuild
if "%choice%"=="0" goto exit

echo 无效选择，请重试
timeout /t 2 >nul
goto menu

:start
echo.
echo [i] 启动所有服务...
docker-compose up -d
echo.
echo [√] 服务已启动
pause
goto menu

:stop
echo.
echo [i] 停止所有服务...
docker-compose down
echo.
echo [√] 服务已停止
pause
goto menu

:restart
echo.
echo [i] 重启所有服务...
docker-compose restart
echo.
echo [√] 服务已重启
pause
goto menu

:status
echo.
echo [i] 服务状态:
echo.
docker-compose ps
echo.
pause
goto menu

:logs
echo.
echo [i] 显示实时日志 (按 Ctrl+C 退出)
echo.
docker-compose logs -f --tail=100
goto menu

:backup
echo.
set backup_file=backup_%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%.sql
set backup_file=%backup_file: =0%
echo [i] 备份数据库到: backups\%backup_file%
if not exist backups mkdir backups
docker-compose exec -T db pg_dump -U erp_user erp_db > backups\%backup_file%
echo.
echo [√] 备份完成: backups\%backup_file%
pause
goto menu

:shell
echo.
echo [i] 进入Django Shell (输入 exit() 退出)
echo.
docker-compose exec backend python manage.py shell
goto menu

:migrate
echo.
echo [i] 执行数据库迁移...
docker-compose exec backend python manage.py migrate
echo.
echo [√] 迁移完成
pause
goto menu

:rebuild
echo.
echo [i] 重建并启动服务...
docker-compose down
docker-compose build --no-cache
docker-compose up -d
echo.
echo [√] 服务已重建并启动
pause
goto menu

:exit
exit /b 0
