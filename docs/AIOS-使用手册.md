# AIOS 用户手册

这份手册描述当前代码版本。AIOS 是供个人或小团队自行部署的 AI 工作台；它不是由本仓库作者托管的云服务。

## 用户端

- **模型与服务**：每个账号配置自己的兼容模型服务和 API Key；不同账号的 Provider 配置互相独立。
- **外观与对话**：主题、界面、显示条数、语音朗读等个人偏好。
- **我的账号**：修改自己的登录信息、退出登录、配置自己的执行服务器。
- **数据与授权**：查看/撤销自己的会话工具授权、管理自己可见的数据。

## 使用执行服务器

若需让 AI 执行代码，请在「我的账号」中连接自己控制的服务器。没有配置执行服务器时，普通账号不能执行本机工具，但仍可聊天。详见[执行服务器接入指南](AIOS-执行器接入指南.md)。

## 账号与隐私

每个 AIOS 实例由其运营者管理。用户会话、媒体、日志和备份的实际存放位置取决于部署配置。管理员可配置实例级模型服务、邮件注册、登录保护和系统运行参数；用户无权改动这些全局选项。

不要把密码、API Key、SSH 私钥或一次性验证码发给他人。发现账号异常，请使用账号设置修改密码并联系实例管理员。

## 当前发布边界

- 第一个管理员只能在本机首次初始化；后续用户注册由实例管理员配置的邮件验证与注册策略控制。
- 普通账号的会话与执行记录按账号过滤；媒体、文件和第三方存储的完整多租户隔离尚未完成，因此不应将实例开放给不可信用户。
- 普通账号的代码执行只允许转发到该账号配置的远程执行服务器；未配置时不在 AIOS 主机本地执行。
- 执行服务器需由用户自行提供并维护。AIOS 不提供云电脑、计算资源或存储额度。

## 首次部署

首次打开时，如果账号库为空，只有本机地址会显示「创建管理员账号」。创建后该入口自动关闭；普通新账号是否能注册由实例管理员在管理员控制台配置。

## 用户数据存储 / User data storage

普通用户默认把聊天记录和媒体保存在 AIOS 实例为该账号准备的本地目录；没有远程服务器时，聊天不会因为缺少远程配置而失效。用户配置并测试自己的 SSH 服务器后，可以在“我的账号 → 执行服务器”选择是否迁移已有聊天和媒体。迁移会先复制并回读校验，失败不会删除本地源数据；选择继续本地时也不会自动迁移。远程模式下的新媒体和聊天备份写入该用户专属远程目录，部署端只保留账号/索引和运行所需元数据。

Regular users keep chat history and media in their account directory on the AIOS deployment by default; remote execution is optional and is not required for chat. After configuring and testing their own SSH server, users can choose whether to migrate existing chat/media data. Migration verifies the remote copy before switching and never deletes the local source on failure. In remote mode, new media and chat backups are written to the user's dedicated remote directory; the AIOS deployment keeps only account/index/runtime metadata.


## 用户存储选择

没有远程服务器时，聊天记录和媒体默认保存在你的 AIOS 账号空间；配置并测试自己的执行服务器后，可在「我的账号 → 执行服务器」选择继续本地保存或迁移到自己的远程目录。迁移失败不会删除本地数据。

## User storage choice

Without a remote server, chat history and media stay in your AIOS account space by default. After configuring and testing your own executor, choose local storage or migration to your own remote directory. A failed migration never deletes the local source.
