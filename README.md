# Personal AI OS

**面向个人与自托管部署的 AI 工作台 / A self-hosted AI workspace**

Personal AI OS brings conversations, model providers, tools, approvals, and optional remote execution into one web application. It runs on infrastructure you control; it is not a hosted cloud-computer service.

Personal AI OS 将对话、模型服务、工具、审批和可选的远程执行整合在一个 Web 应用中。服务运行在你控制的设备或服务器上；本项目不提供托管云电脑服务。

[简体中文](#简体中文) · [English](#english)

---

## 简体中文

产品边界、隔离完成度与后续升级路线见 [产品范围说明](docs/PRODUCT-SCOPE.md)。

### 当前功能

- 邮箱与密码登录；首次启动可在本机创建首个管理员账号。
- 流式聊天、会话历史、图片与文件输入。
- OpenAI 兼容模型服务；每个账号可以配置自己的 Provider 与 API Key。
- 工具调用、风险审批、执行记录和本地受限沙箱。
- 普通账号可使用公网 SSH 服务器，或在自己的 Windows/macOS/Linux 设备运行 AIOS Agent；未配对/离线时不会回退到 AIOS 主机执行。
- 浏览器语音输入与朗读；可选接入第三方 TTS。

### 多用户范围与已知限制

当前已实现按账号隔离的会话、执行记录和个人设置。媒体、文件及其他持久化资源的完整多租户隔离仍未完成，因此：

- 公共自助注册默认关闭；
- 不要将实例开放给不可信用户；
- 不要把本项目当作多人文件托管或云电脑平台。

管理员配置 Provider/邮件/登录安全等实例级设置；普通用户配置自己的模型、账号偏好和执行服务器。详见下方用户手册。

### 环境要求

- Python 3.11 或更新版本。
- Node.js 18 或更新版本，以及 npm。
- Linux 或 WSL2。执行本地沙箱建议安装 Bubblewrap。
- 至少一个兼容的模型服务及其 API Key。
- SMTP 仅在需要邮件验证或密码恢复时需要。
- Docker 仅在部署用户自己的远程执行服务器时需要。

### 安装

```bash
git clone https://github.com/qixidalao/personal-ai-os-v2.git
cd personal-ai-os-v2

python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

cd frontend
npm ci
npm run build
cd ..
```

### 首次启动

在项目根目录运行：

```bash
./scripts/aios.sh start
```

默认仅监听本机 `127.0.0.1:8080`。在同一设备的浏览器打开 <http://127.0.0.1:8080>。若账号库为空，页面会提供**仅限本机**的首个管理员创建流程，不需要先配置 SMTP。

之后登录管理员账号，在 `/#/admin` 配置实例邮件和安全选项；用户通过 `/#/settings` 配置个人模型与偏好。远程访问前必须在可信网络或经过鉴权的 HTTPS 反向代理后部署。不要直接将后端端口暴露到公网，也不要未经审查就将绑定地址改为 `0.0.0.0`。

### 远程执行

普通用户可配置自己控制的公网 SSH 服务器。代码在用户服务器提供的 Docker 容器中运行；未配置时，普通用户的命令**不会**在 AIOS 主机本地执行。普通账号不能将执行目标设为回环、私网或云元数据地址。

仓库提供 `scripts/aios-bootstrap.sh` 和 `scripts/runner/Dockerfile`。Bootstrap 会在用户服务器上本地构建 runner 镜像。执行前请审阅脚本和 Dockerfile；脚本需要管理员权限来安装 Docker、创建专用账号并安装公钥。

详细步骤见：[执行服务器接入指南](docs/AIOS-执行器接入指南.md)。

### 开发与测试

启动前端开发服务器：

```bash
cd frontend
npm install
npm run dev
```

运行检查：

```bash
python -m pytest tests -q
cd frontend
npm run build
```

### 文档

- [用户手册](docs/AIOS-使用手册.md)
- [执行服务器接入指南](docs/AIOS-执行器接入指南.md)
- [文档索引与历史资料说明](docs/README.md)

仓库中的部分架构、API、Termux 和插件文档是历史或参考资料，可能不适用于当前版本。安装和日常使用请以本 README 及上述当前指南为准。

### 数据与凭据

- `storage/` 保存本地设置、账号、会话、日志、上传文件和数据库，默认由 Git 忽略。
- 请私下备份 `storage/`；不要把它上传到公开仓库、Issue 或聊天中。
- 不要提交 `.env`、邮箱授权码、模型 API Key、访问令牌或 SSH 私钥。

### 许可证

GPL-3.0，见 [LICENSE](LICENSE)。

---

## English

### Features

- Email/password authentication, with a loopback-only first-administrator setup on an empty database.
- Streaming chat, conversation history, image and file input.
- OpenAI-compatible model providers; each account can configure its own provider and API key.
- Tool calls, risk-based approvals, run history, and a restricted local sandbox.
- Optional execution on a user-owned SSH server or a paired Windows/macOS/Linux device agent. Regular-user jobs never fall back to the AIOS host.
- Browser speech input and playback, with optional third-party TTS.

### Multi-user scope and limitations

Per-account conversations, run records, and personal settings are isolated. Full multi-tenant isolation for media, files, and other persistent resources is not yet complete. Therefore:

- Public self-registration is disabled by default.
- Do not expose the instance to untrusted users.
- Do not use this project as a multi-user file-hosting or cloud-computer service.

Administrators manage instance-wide provider, email, and login-security settings. Regular users manage their own model providers, preferences, and execution server.

### Requirements

- Python 3.11 or newer.
- Node.js 18 or newer and npm.
- Linux or WSL2. Bubblewrap is recommended for local sandbox execution.
- At least one compatible model provider and its API key.
- SMTP is only needed for email verification and password recovery.
- Docker is only needed on a user's own remote execution server.

### Installation

```bash
git clone https://github.com/qixidalao/personal-ai-os-v2.git
cd personal-ai-os-v2

python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

cd frontend
npm ci
npm run build
cd ..
```

### First launch

From the repository root, run:

```bash
./scripts/aios.sh start
```

The launcher binds to `127.0.0.1:8080` by default. Open <http://127.0.0.1:8080> in a browser on the same device. If the account database is empty, the page offers a **loopback-only** first-administrator setup; SMTP is not required for this initial setup.

Afterward, the administrator configures instance email and security options at `/#/admin`; users configure personal models and preferences at `/#/settings`. For remote access, use a trusted private network or an authenticated HTTPS reverse proxy. Do not expose the backend port directly to the public Internet or change the bind address to `0.0.0.0` without reviewing the security implications.

### Remote execution

A regular user may configure a public SSH server they control. Jobs run in a Docker container on that user's server. Without a configured executor, regular-user commands are **not** run on the AIOS host. Loopback, private-network, and cloud-metadata targets are rejected for regular accounts.

The repository includes `scripts/aios-bootstrap.sh` and `scripts/runner/Dockerfile`. The bootstrap builds the runner image locally on the user's server. Review the script and Dockerfile before use; the bootstrap requires administrative privileges to install Docker, create a dedicated account, and install the SSH public key.

See the [execution server guide](docs/AIOS-执行器接入指南.md).

### Development and tests

Run the frontend development server:

```bash
cd frontend
npm install
npm run dev
```

Run checks:

```bash
python -m pytest tests -q
cd frontend
npm run build
```

### Documentation

- [User guide](docs/AIOS-使用手册.md)
- [Execution server guide](docs/AIOS-执行器接入指南.md)
- [Documentation index and legacy-document notice](docs/README.md)

Some architecture, API, Termux, and plugin documents are historical references and may not apply to the current version. Use this README and the current guides above for installation and day-to-day operation.

### Data and credentials

- `storage/` holds local settings, accounts, conversations, logs, uploads, and databases. It is ignored by Git by default.
- Back up `storage/` privately. Never publish it or attach it to public issues or chats.
- Never commit `.env` files, SMTP credentials, model API keys, access tokens, or SSH private keys.

### License

GPL-3.0. See [LICENSE](LICENSE).

## 用户数据存储 / User data storage

普通用户默认把聊天记录和媒体保存在 AIOS 实例为该账号准备的本地目录；没有远程服务器时，聊天不会因为缺少远程配置而失效。用户配置并测试自己的 SSH 服务器后，可以在“我的账号 → 执行服务器”选择是否迁移已有聊天和媒体。迁移会先复制并回读校验，失败不会删除本地源数据；选择继续本地时也不会自动迁移。远程模式下的新媒体和聊天备份写入该用户专属远程目录，部署端只保留账号/索引和运行所需元数据。

Regular users keep chat history and media in their account directory on the AIOS deployment by default; remote execution is optional and is not required for chat. After configuring and testing their own SSH server, users can choose whether to migrate existing chat/media data. Migration verifies the remote copy before switching and never deletes the local source on failure. In remote mode, new media and chat backups are written to the user's dedicated remote directory; the AIOS deployment keeps only account/index/runtime metadata.
