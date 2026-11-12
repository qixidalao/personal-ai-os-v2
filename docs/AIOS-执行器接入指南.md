# 执行服务器接入指南

这份指南面向需要让 AI 在**自己控制的服务器**上运行代码的用户。它不要求域名或 HTTPS 证书，只需要公网 IP 和 SSH。

## 使用前提

- 一台你有权管理的 Linux 服务器；
- 公网 IP 可达；
- SSH 服务开启（默认端口 22）；
- Docker 可安装，且服务器可构建/运行容器。

AIOS 不提供执行服务器。没有服务器时，普通聊天仍可使用，但执行工具不可用。

## 在 AIOS 获取连接公钥

1. 打开「设置 → 我的账号 → 执行服务器」；
2. 点击「获取接入密钥」；
3. 复制页面显示的整行 `ssh-ed25519 ...` 公钥。

## 在服务器安装执行环境

把本仓库的 `scripts/aios-bootstrap.sh` 和 `scripts/runner/` 目录放到服务器同一个 `scripts/` 目录下。然后以 root 身份运行：

```bash
bash scripts/aios-bootstrap.sh --public-key "粘贴 AIOS 显示的整行公钥"
```

脚本会安装/检查 Docker，创建 `aios` 专用账号，安装公钥，并从仓库内的 `scripts/runner/Dockerfile` 在服务器本地构建 `aios-runner:latest`。不依赖公共镜像仓库发布该镜像。部署时需把 `aios-bootstrap.sh` 和 `runner/` 目录一起放入服务器的 `scripts/` 目录。

完成后检查：

```bash
docker run --rm aios-runner:latest sh -lc 'echo AIOS_OK'
```

应输出 `AIOS_OK`。若 Docker 无法安装或镜像构建失败，按终端错误修复系统依赖后重跑脚本。

## 获取服务器指纹

在服务器运行 SSH 服务后，复制其主机公钥指纹：

```bash
ssh-keyscan -p 22 你的公网IP
```

复制一条完整输出（例如 `1.2.3.4 ssh-ed25519 AAAA...`）。若 SSH 使用其他端口，把 `22` 换成实际端口。

## 在 AIOS 填入连接信息

在「设置 → 我的账号 → 执行服务器」填写：

| 字段 | 内容 |
|---|---|
| 执行方式 | 使用我的服务器 |
| 服务器地址 | 服务器公网 IP 或域名 |
| 端口 | SSH 端口，通常为 22 |
| 登录用户 | `aios` |
| 运行环境 | 保留 `aios-runner:latest` |
| 服务器指纹 | 粘贴上一步复制的完整一行 |

保存后点击「测试连接」。成功时应返回 `AIOS_OK`。随后要求 AI 执行一个简单命令，如 `echo hello`，确认输出可返回对话。

## 安全限制与资源

- 普通账号不能把执行任务发送到 AIOS 主机本身、回环地址、私网或云元数据地址；
- SSH 主机指纹用于确认连接到正确的服务器；
- 任务在 Docker 容器中运行：默认无网络、只读根文件系统、512MB 内存、1 CPU、最多 256 个进程；
- 默认 60 秒超时，最多 300 秒；输出上限 200KB；
- 任务容器退出后自动移除；
- 服务器资源、Docker 维护、SSH 安全组与费用由服务器所有者负责。

## 常见问题

| 错误 | 检查项 |
|---|---|
| SSH 连接超时 | 公网 IP、云安全组的 SSH 端口、服务器 `sshd` 是否运行 |
| `Permission denied (publickey)` | 公钥是否完整安装到 `/home/aios/.ssh/authorized_keys`，目录权限是否正确 |
| `Host key verification failed` | 重新运行 `ssh-keyscan`，检查指纹是否粘贴完整 |
| Docker daemon 不可用 | Docker 服务状态、`aios` 是否可运行 Docker |
| runner 镜像不存在 | 确认 `scripts/runner/Dockerfile` 同目录存在，重新运行 bootstrap |
| 普通账号配置被拒绝 | 只能填写公网目标，不能填本机、内网或元数据地址 |

修改或重装服务器后，重新验证并更新指纹；停止使用时，在 AIOS 将执行方式切换为「不启用」，并从服务器移除该账号的公钥。


## 用户存储选择

没有远程服务器时，聊天记录和媒体默认保存在你的 AIOS 账号空间；配置并测试自己的执行服务器后，可在「我的账号 → 执行服务器」选择继续本地保存或迁移到自己的远程目录。迁移失败不会删除本地数据。

## User storage choice

Without a remote server, chat history and media stay in your AIOS account space by default. After configuring and testing your own executor, choose local storage or migration to your own remote directory. A failed migration never deletes the local source.


## 使用本机设备（Windows / macOS / Linux）

SSH 地址中的 `127.0.0.1` 指向 AIOS 服务器，不是你的电脑，因此不能直接填写。要让自己的电脑成为执行器：

1. 在 AIOS「我的账号 → 执行服务器」选择「使用我的本机设备」；
2. 点击「生成配对码」；
3. 在自己的 Windows/macOS/Linux 设备下载仓库的 `scripts/aios-agent.py`，运行：

```bash
python scripts/aios-agent.py pair --server https://你的AIOS地址 --code 6位配对码
python scripts/aios-agent.py run
```

4. 设备端每个任务默认要求本机用户确认；确认后才执行；
5. AIOS 页面会显示设备在线状态，可随时撤销。

Agent 主动连接 AIOS，不需要用户设备公网 IP、端口转发或 SSH 入站。Windows、macOS、Linux 支持 Python Agent。Android 目前只能在前台手动运行 Python Agent，不承诺后台常驻；iOS 和鸿蒙暂未提供 Agent，不宣称支持。\n