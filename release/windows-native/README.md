# ERP系统 Windows原生部署包

## 📦 部署包说明

本部署包提供**无需Docker**的Windows原生安装方式，一键安装所有依赖和服务。

### 特点

✅ **一键安装** - 自动安装PostgreSQL、Python、Redis等所有依赖  
✅ **Windows服务** - 配置为Windows服务，开机自动启动  
✅ **无需Docker** - 直接运行在Windows系统上  
✅ **简单管理** - 提供启动、停止、重启等管理脚本  
✅ **完整功能** - 包含前后端、数据库、缓存等完整功能  

## 🚀 快速开始

### 系统要求

- **操作系统**: Windows Server 2016/2019/2022 或 Windows 10/11 Pro
- **内存**: 8GB 及以上
- **磁盘**: 50GB 可用空间
- **权限**: 管理员权限

### 一键安装

1. **以管理员身份运行PowerShell**
   - 右键点击PowerShell图标
   - 选择"以管理员身份运行"

2. **允许脚本执行**
   ```powershell
   Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```

3. **运行安装脚本**
   ```powershell
   cd C:\path\to\erp-release
   .\install.ps1
   ```

4. **等待安装完成**
   - 脚本会自动安装所有依赖（约10-20分钟）
   - PostgreSQL, Python, Redis, Nginx等
   - 自动配置数据库和服务
   - 按提示创建管理员账号

5. **访问系统**
   - 前端: http://localhost 或 http://服务器IP
   - 后台: http://localhost/admin

就这么简单！🎉

## 📋 详细安装选项

### 自定义安装路径

```powershell
.\install.ps1 -InstallPath "D:\MyERP"
```

### 自定义数据库密码

```powershell
.\install.ps1 -PostgresPassword "YourSecurePassword123!"
```

### 跳过已安装的依赖

如果已经安装了PostgreSQL、Python等：

```powershell
.\install.ps1 -SkipDependencies
```

### 组合使用

```powershell
.\install.ps1 -InstallPath "D:\ERP" -PostgresPassword "MyPass123!" -SkipDependencies
```

## 🔧 安装后管理

安装完成后，在安装目录（默认`C:\ERP-System`）会生成管理脚本：

### 服务管理

| 脚本 | 说明 |
|------|------|
| `启动服务.bat` | 启动ERP系统 |
| `停止服务.bat` | 停止ERP系统 |
| `重启服务.bat` | 重启ERP系统 |
| `查看日志.bat` | 打开日志目录 |

### 使用PowerShell管理

```powershell
# 查看服务状态
Get-Service ERP*

# 启动服务
Start-Service ERPBackend
Start-Service ERPNginx

# 停止服务
Stop-Service ERPBackend
Stop-Service ERPNginx

# 重启服务
Restart-Service ERPBackend
```

### 查看日志

日志文件位置：
- 后端日志: `C:\ERP-System\logs\backend.log`
- 错误日志: `C:\ERP-System\logs\backend-error.log`
- Nginx日志: `C:\nginx\logs\`

## 🗑️ 卸载

```powershell
.\install.ps1 -Uninstall
```

这会：
1. 停止所有ERP服务
2. 删除Windows服务配置
3. 询问是否删除安装目录

## 📁 安装目录结构

```
C:\ERP-System\
├── backend\              # Django后端
│   ├── venv\            # Python虚拟环境
│   ├── manage.py
│   └── ...
├── frontend\             # Vue.js前端
│   ├── index.html
│   ├── assets\
│   └── ...
├── logs\                 # 日志文件
├── backups\              # 备份目录
├── media\                # 上传文件
├── staticfiles\          # 静态文件
├── 启动服务.bat
├── 停止服务.bat
├── 重启服务.bat
└── 查看日志.bat
```

## 🔐 安全配置

### 修改默认密码

安装后请修改：

1. **数据库密码**
   ```powershell
   # 连接PostgreSQL
   psql -U postgres
   # 修改密码
   ALTER USER erp_user WITH PASSWORD 'NewPassword';
   ```

2. **Django SECRET_KEY**
   编辑 `C:\ERP-System\backend\.env`
   ```env
   SECRET_KEY=your-new-random-secret-key
   ```

3. **管理员密码**
   ```powershell
   cd C:\ERP-System\backend
   .\venv\Scripts\Activate.ps1
   python manage.py changepassword admin
   ```

### 配置HTTPS

1. 获取SSL证书（Let's Encrypt或购买）
2. 编辑 `C:\nginx\conf\nginx.conf`
3. 添加SSL配置：
   ```nginx
   server {
       listen 443 ssl;
       ssl_certificate /path/to/cert.pem;
       ssl_certificate_key /path/to/key.pem;
       # ... 其他配置
   }
   ```
4. 重启Nginx服务

### 配置防火墙

安装脚本会自动开放80和8000端口。如需额外配置：

```powershell
# 开放HTTPS端口
New-NetFirewallRule -DisplayName "ERP-HTTPS" -Direction Inbound -Protocol TCP -LocalPort 443 -Action Allow
```

## 💾 备份和恢复

### 数据库备份

```powershell
# 设置密码（替换为您的密码）
$env:PGPASSWORD="YourPassword"

# 备份
pg_dump -U erp_user -h localhost erp_db > C:\ERP-System\backups\backup_$(Get-Date -Format 'yyyyMMdd_HHmmss').sql
```

### 数据库恢复

```powershell
$env:PGPASSWORD="YourPassword"
psql -U erp_user -h localhost erp_db < C:\ERP-System\backups\backup_20231126_120000.sql
```

### 文件备份

```powershell
# 备份上传文件和静态文件
Copy-Item -Path "C:\ERP-System\media" -Destination "C:\ERP-System\backups\media_$(Get-Date -Format 'yyyyMMdd')" -Recurse
```

### 自动备份

创建Windows计划任务自动备份：

```powershell
# 创建备份脚本
$backupScript = @"
`$env:PGPASSWORD='YourPassword'
pg_dump -U erp_user -h localhost erp_db > C:\ERP-System\backups\backup_`$(Get-Date -Format 'yyyyMMdd_HHmmss').sql
Copy-Item -Path 'C:\ERP-System\media' -Destination "C:\ERP-System\backups\media_`$(Get-Date -Format 'yyyyMMdd')" -Recurse
"@

$backupScript | Out-File -FilePath "C:\ERP-System\backup.ps1" -Encoding UTF8

# 创建计划任务（每天凌晨2点）
$action = New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument "-File C:\ERP-System\backup.ps1"
$trigger = New-ScheduledTaskTrigger -Daily -At 2am
Register-ScheduledTask -TaskName "ERP系统自动备份" -Action $action -Trigger $trigger -User "SYSTEM"
```

## 🔄 更新升级

1. **备份当前系统**
   ```powershell
   .\install.ps1 -Uninstall
   # 选择不删除安装目录
   ```

2. **下载新版本部署包**

3. **重新安装**
   ```powershell
   .\install.ps1
   ```

4. **恢复数据**（如果需要）

## ❓ 故障排查

### 服务无法启动

1. 检查端口占用：
   ```powershell
   netstat -ano | findstr :80
   netstat -ano | findstr :8000
   ```

2. 查看服务状态：
   ```powershell
   Get-Service ERP* | Format-Table -AutoSize
   ```

3. 查看日志：
   ```powershell
   Get-Content C:\ERP-System\logs\backend-error.log -Tail 50
   ```

### 数据库连接失败

1. 检查PostgreSQL服务：
   ```powershell
   Get-Service postgresql*
   Start-Service postgresql*
   ```

2. 测试连接：
   ```powershell
   psql -U erp_user -h localhost erp_db
   ```

### 权限问题

确保安装目录有正确的权限：

```powershell
icacls "C:\ERP-System" /grant Users:(OI)(CI)F /T
```

## 📞 技术支持

### 日志位置
- 后端日志: `C:\ERP-System\logs\`
- Nginx日志: `C:\nginx\logs\`
- PostgreSQL日志: `C:\Program Files\PostgreSQL\13\data\log\`

### 配置文件
- Django配置: `C:\ERP-System\backend\.env`
- Nginx配置: `C:\nginx\conf\nginx.conf`
- PostgreSQL配置: `C:\Program Files\PostgreSQL\13\data\postgresql.conf`

### 常用命令

```powershell
# 进入Django shell
cd C:\ERP-System\backend
.\venv\Scripts\Activate.ps1
python manage.py shell

# 创建新的管理员
python manage.py createsuperuser

# 执行数据库迁移
python manage.py migrate

# 收集静态文件
python manage.py collectstatic
```

## 🎯 性能优化

### 1. 增加Gunicorn Workers

编辑NSSM服务配置，使用Gunicorn替代runserver：

```powershell
nssm set ERPBackend AppParameters "C:\ERP-System\backend\venv\Scripts\gunicorn.exe config.wsgi:application --bind 0.0.0.0:8000 --workers 4"
```

### 2. PostgreSQL优化

编辑 `C:\Program Files\PostgreSQL\13\data\postgresql.conf`:

```ini
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 16MB
```

### 3. 配置静态文件缓存

编辑Nginx配置添加缓存：

```nginx
location /static/ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

## 📊 监控

### Windows Performance Monitor

监控系统资源使用：

```powershell
# 打开性能监视器
perfmon.exe

# 添加计数器监控:
# - Processor: % Processor Time
# - Memory: Available MBytes
# - Network Interface: Bytes Total/sec
```

### 应用监控

查看服务资源使用：

```powershell
Get-Process python,nginx | Select-Object Name,CPU,WorkingSet
```

---

## 📝 更新日志

- **v1.0.0** (2024-11-26)
  - 初始版本
  - 支持一键安装
  - Windows服务集成
  - 自动依赖安装

---

**重要提示**: 
- 生产环境部署前，请务必修改所有默认密码
- 定期备份数据库和上传文件
- 配置HTTPS加密传输
- 启用Windows更新和防病毒软件

