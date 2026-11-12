# AIOS 部署架构与运行容量 / Deployment Architecture and Capacity

## 中文

### 节点

```text
用户浏览器
   │ HTTPS / 反向代理
   ▼
AIOS 控制面（部署者服务器）
   ├─ 账号、配置、会话索引、审批审计
   ├─ 管理员本机沙箱（仅管理员）
   └─ 普通用户不落本机媒体/代码
          │ SSH（用户自备服务器）
          ▼
用户执行/存储节点
   ├─ Docker runner：每任务临时容器
   └─ ~/aios-data：该用户的聊天备份、媒体和产物
```

### 存储策略

- 普通用户默认本地保存聊天记录和媒体，保存到该用户账号空间；没有远程服务器也能正常使用聊天。
- 用户配置并测试远程 SSH 后，可选择“继续本地”或“迁移到我的远程服务器”。
- 迁移流程：复制 → 回读校验 → 成功后切换；失败不删除本地源数据。
- 远程模式的新媒体写入用户服务器的 `~/aios-data/media/`；聊天同步写入 `~/aios-data/conversations/`。
- 其他用户不会使用或读取该目录。部署端保留账号、索引和运行所需元数据。
- `upload-file` 只在内存解析文本，不把原始上传文件持久化到部署端。
- 普通用户的本地媒体路径不属于管理员公开下载接口；接口按账号归属校验。

### 并发与资源

本机 AIOS 是控制面，不应被当作无限并发执行服务器：

| 场景 | 建议 |
|---|---|
| 聊天并发 | 由模型服务和网络决定；本机主要消耗连接、JSON/SSE 内存 |
| 管理员本机工具 | 默认并发信号量 2；按 CPU/内存调整 |
| 普通用户代码 | 在用户自己的 SSH/Docker 节点执行，不占部署端 CPU |
| 单容器 | 默认 1 CPU、512MB 内存、256 进程、无网络、60 秒超时 |
| 文件/媒体 | 无远程节点时使用部署端本地账号空间；有远程节点时由用户自行承担容量 |

建议配置：

- 个人部署：4 核 CPU、8GB RAM、20GB 可用磁盘；
- 5–20 个受控账号：8 核 CPU、16GB RAM，普通用户配置自有执行节点；
- 需要更多用户：增加数据库/对象存储/队列，并先完成媒体与文件多租户隔离；不要简单放开注册。

### 安全边界

- 普通用户不能把任务回退到 AIOS 本机；`127.0.0.1`、私网和 metadata 地址拒绝；
- 管理员配置实例级邮件、登录保护、Provider 默认和开发工具；
- 用户配置个人 Provider、个人存储策略和执行服务器；
- 当前版本适合自托管和受控多用户，不宣称公共 SaaS。

### 发布前检查

```bash
python -m pytest tests -q
cd frontend && npm run build
bash -n scripts/aios.sh scripts/aios-bootstrap.sh
```

## English

### Nodes

```text
User browser
   │ HTTPS / authenticated reverse proxy
   ▼
AIOS control plane (deployment operator's server)
   ├─ accounts, settings, session indexes, approval audit
   ├─ administrator-only local sandbox
   └─ regular-user media/code are not forced onto the host
          │ SSH (user-owned server)
          ▼
User execution/storage node
   ├─ Docker runner: temporary container per task
   └─ ~/aios-data: that user's chat backup, media, and artifacts
```

### Storage policy

- Regular users keep chat history and media locally by default in their account space. Chat works without a remote server.
- After configuring and testing a personal SSH server, a user can choose to keep data local or migrate it to the remote server.
- Migration is copy → read-back verification → switch. Local source data is never deleted on failure.
- In remote mode, new media goes to `~/aios-data/media/` and chat backups go to `~/aios-data/conversations/` on the user's server.
- Other users cannot use or read that directory. The deployment keeps account/index/runtime metadata.
- `upload-file` extracts text in memory and does not persist the original upload on the deployment host.

### Capacity

- The AIOS host is a control plane, not an unlimited execution server.
- Administrator local tools use a default concurrency semaphore of 2.
- Regular-user code runs on the user's own SSH/Docker node.
- Each runner defaults to 1 CPU, 512MB RAM, 256 processes, no network, and a 60-second timeout.
- For larger deployments, add a database/object-store/queue layer after completing full media/file tenant isolation. Do not simply enable public registration.

### Security boundary

- Regular-user jobs never fall back to the AIOS host; loopback, private-network, and cloud-metadata targets are rejected.
- Instance-wide mail, login security, provider defaults, and developer controls belong to the administrator.
- Users control their own providers, storage choice, and execution server.
- This release is suitable for self-hosted and controlled multi-user deployments, not an unrestricted public SaaS.

### Release checks

```bash
python -m pytest tests -q
cd frontend && npm run build
bash -n scripts/aios.sh scripts/aios-bootstrap.sh
```
