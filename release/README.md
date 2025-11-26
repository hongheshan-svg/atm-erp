# ERP系统 Windows服务器部署工具

本目录包含ERP系统Windows服务器的两种部署方案。

## 📦 部署方案选择

### 方案一：Windows原生部署（推荐）⭐

**特点**：
- ✅ **一键安装** - 自动安装所有依赖
- ✅ **无需Docker** - 直接运行在Windows上
- ✅ **开机自启** - 配置为Windows服务
- ✅ **简单管理** - 提供启动/停止脚本
- ✅ **性能更好** - 原生运行，无虚拟化开销

**适用场景**：
- 没有Docker使用经验
- 不希望安装Docker Desktop
- 需要原生Windows服务
- 生产环境长期部署

**系统要求**：
- Windows Server 2016/2019/2022 或 Windows 10/11 Pro
- 8GB+ 内存
- 50GB+ 磁盘空间
- 管理员权限

**使用方法**：
```bash
# 1. 创建部署包
./create-windows-native-release.sh

# 2. 将生成的压缩包传输到Windows服务器

# 3. 在Windows上解压并运行（PowerShell管理员）
.\install.ps1
```

📁 **输出位置**: `windows-native/output/`

---

### 方案二：Docker部署

**特点**：
- ✅ **容器化** - 环境隔离，易于管理
- ✅ **快速部署** - 无需逐个安装依赖
- ✅ **易于迁移** - 可快速迁移到其他服务器
- ✅ **版本管理** - 易于更新和回滚

**适用场景**：
- 熟悉Docker的用户
- 开发/测试环境
- 需要快速部署和更新
- 多环境部署

**系统要求**：
- Windows Server 2016/2019/2022 或 Windows 10/11 Pro
- 8GB+ 内存
- 100GB+ 磁盘空间
- Docker Desktop for Windows

**使用方法**：
```bash
# 1. 创建部署包
./create-windows-docker-release.sh

# 2. 将生成的压缩包传输到Windows服务器

# 3. 在Windows上解压并运行
部署.bat
```

📁 **输出位置**: `windows-docker/output/`

---

## 🚀 快速创建部署包

### 一键创建所有部署包

```bash
cd release

# 创建Windows原生部署包
./create-windows-native-release.sh

# 创建Docker部署包
./create-windows-docker-release.sh
```

### 单独创建某个部署包

```bash
# 只创建Windows原生部署包
./create-windows-native-release.sh

# 或只创建Docker部署包
./create-windows-docker-release.sh
```

## 📋 目录结构

```
release/
├── README.md                          # 本文件
├── create-windows-native-release.sh   # 创建原生部署包脚本
├── create-windows-docker-release.sh   # 创建Docker部署包脚本
│
├── windows-native/                    # Windows原生部署
│   ├── install.ps1                    # 一键安装脚本
│   ├── README.md                      # 详细说明
│   └── output/                        # 生成的部署包输出目录
│       └── ERP-Windows-Native-*.zip   # 部署包
│
├── windows-docker/                    # Docker部署
│   └── output/                        # 生成的部署包输出目录
│       └── ERP-Windows-Docker-*.zip   # 部署包
│
└── docs/                              # 文档目录
    └── ...
```

## 📊 方案对比

| 特性 | Windows原生 | Docker部署 |
|------|------------|------------|
| 安装难度 | ⭐⭐⭐⭐⭐ 一键安装 | ⭐⭐⭐⭐ 需安装Docker |
| 运行性能 | ⭐⭐⭐⭐⭐ 原生性能 | ⭐⭐⭐⭐ 轻微虚拟化开销 |
| 资源占用 | ⭐⭐⭐⭐ 较少 | ⭐⭐⭐ 较多 |
| 管理难度 | ⭐⭐⭐⭐⭐ 提供管理脚本 | ⭐⭐⭐⭐ Docker命令 |
| 更新升级 | ⭐⭐⭐ 需要重新安装 | ⭐⭐⭐⭐⭐ 拉取新镜像 |
| 环境隔离 | ⭐⭐⭐ 虚拟环境 | ⭐⭐⭐⭐⭐ 容器隔离 |
| 迁移便利性 | ⭐⭐⭐ 需备份配置 | ⭐⭐⭐⭐⭐ 导出容器即可 |
| 适用场景 | 生产环境长期部署 | 开发/测试/快速部署 |

## 💡 使用建议

### 选择Windows原生部署如果：
- ✅ 你是生产环境部署
- ✅ 需要最佳性能
- ✅ 不熟悉Docker
- ✅ 希望系统开机自启
- ✅ 需要Windows服务管理

### 选择Docker部署如果：
- ✅ 你已经熟悉Docker
- ✅ 是开发或测试环境
- ✅ 需要快速部署和销毁
- ✅ 需要多环境部署
- ✅ 希望容易迁移和备份

## 📝 部署包内容

### Windows原生部署包包含：
- ✅ 一键安装脚本（install.ps1）
- ✅ 后端Python代码
- ✅ 前端构建文件
- ✅ Nginx配置
- ✅ 启动/停止/重启脚本
- ✅ 完整文档

### Docker部署包包含：
- ✅ 完整项目代码
- ✅ docker-compose.yml
- ✅ Dockerfile配置
- ✅ 环境配置模板
- ✅ 部署/管理脚本
- ✅ 完整文档

## 🔧 前置准备

### 创建部署包前：

1. **确保前端已构建**
   ```bash
   cd frontend
   npm install
   npm run build
   ```

2. **或确保Docker容器运行中**
   ```bash
   docker-compose up -d frontend
   ```

### 传输到Windows服务器：

- **局域网**: 使用网络共享或FTP
- **互联网**: 使用SFTP或云存储
- **物理介质**: U盘或移动硬盘

## 📖 详细文档

- **Windows原生部署**: `windows-native/README.md`
- **Docker部署**: 解压部署包后查看`README.txt`
- **系统架构**: `../SYSTEM-ARCHITECTURE.md`
- **快速开始**: `../QUICK-START-GUIDE.md`

## ⚙️ 高级配置

### 自定义安装路径（Windows原生）

```powershell
.\install.ps1 -InstallPath "D:\MyERP"
```

### 自定义数据库密码（Windows原生）

```powershell
.\install.ps1 -PostgresPassword "YourSecurePassword!"
```

### 修改Docker配置

编辑`docker-compose.yml`和`.env`文件。

## 🔒 安全建议

无论使用哪种部署方式，都请：

1. ✅ 修改所有默认密码
2. ✅ 设置防火墙规则
3. ✅ 启用HTTPS/SSL
4. ✅ 定期备份数据
5. ✅ 更新系统补丁
6. ✅ 配置日志审计

## 💾 备份恢复

### Windows原生

```powershell
# 备份数据库
pg_dump -U erp_user erp_db > backup.sql

# 备份文件
Copy-Item C:\ERP-System\media backups\
```

### Docker

```powershell
# 运行备份脚本
备份数据.bat

# 或使用命令
docker-compose exec -T db pg_dump -U erp_user erp_db > backup.sql
docker cp erp_backend:/app/media ./media_backup
```

## ❓ 故障排查

### 问题：前端构建文件未找到

**解决**：
```bash
cd frontend
rm -rf node_modules dist
npm install
npm run build
```

### 问题：Docker容器中无前端文件

**解决**：
```bash
docker-compose restart frontend
docker cp erp_frontend:/app/dist ./frontend/
```

### 问题：权限不足

**解决**：
- Windows: 以管理员身份运行PowerShell
- Linux/Mac: 使用`sudo`或修改文件权限

## 📞 技术支持

如有问题，请：

1. 查看对应部署方式的README文档
2. 检查系统日志
3. 确认系统要求满足
4. 验证网络连接
5. 查看项目主README

## 📅 更新日志

- **2024-11-26**: 初始版本
  - 添加Windows原生一键安装
  - 添加Docker部署方式
  - 完善文档和脚本

---

**注意**：生产环境部署前，请务必阅读完整的部署文档，并进行充分测试。

