# {{TAG}}

<!-- 发布前替换所有 {{TAG}}，在此填写实际版本变化、兼容性和验证结果。安装与文档区块必须位于发布说明最下方。只列出本次真实上传的附件及可用安装方式。 -->

## 本次更新

<!-- 填写本版变化。 -->

## 📥 Installation

### Docker

下载下方对应平台的 `atm-erp-{{TAG}}-<platform>-docker.zip`，解压并进入目录。需先安装 Docker Engine / Docker Desktop（Linux 容器）和 Compose v2。

```bash
# macOS / Linux
bash install.sh
```

```powershell
# Windows PowerShell
.\install.ps1
```

### One-line install (Linux · Docker)

在空目录执行，需已安装 Docker、Compose v2、curl 和 unzip：

```bash
curl -fL https://github.com/hongheshan-svg/atm-erp/releases/download/{{TAG}}/atm-erp-{{TAG}}-linux-docker.zip -o atm-erp-{{TAG}}-linux-docker.zip && unzip atm-erp-{{TAG}}-linux-docker.zip && (cd atm-erp-{{TAG}}-linux-docker && bash install.sh)
```

安装后默认访问 `http://127.0.0.1:8080/erp/`，用户名 `admin`，首次密码见安装目录 `.env.lean` 中的 `LEAN_ADMIN_PASSWORD`。

### Manual download

从下方 **Assets** 下载适合平台的安装包：

- 平台：`macos` / `linux` / `windows`。
- 安装方式：`docker` / `native`；原生安装步骤见 Installation Guide。
- SHA256 校验清单：`atm-erp-{{TAG}}-SHA256SUMS.txt`。

## 📚 Documentation

- [GitHub Repository](https://github.com/hongheshan-svg/atm-erp)
- [Installation Guide](https://github.com/hongheshan-svg/atm-erp/blob/{{TAG}}/README.md)
