# DataHubSync

股票数据分发系统 - 基于 Cloudflare Tunnel 的轻量级数据同步方案。

## 项目概述

将 Windows hub电脑上的股票历史数据（CSV格式）同步到多台客户端服务器：
- 3台局域网客户端
- 3台异地客户端（北京、日本、美国）

## 架构特点

- **hub端**：Python HTTP 服务器 + Cloudflare Tunnel
- **客户端**：curl/wget 或 Python 脚本主动拉取
- **传输**：HTTPS 加密，增量同步，断点续传
- **成本**：完全免费

## 双轨预留设计

当前使用 Cloudflare Tunnel，架构上预留 Tailscale 切换能力：
- 配置抽象：`SERVER_URL` 环境变量
- Docker profile 隔离
- 协议自适应

切换成本：修改配置即可，约 30 分钟。

## 项目结构

```
DataBorder/
├── hub/                      # 🎯 独立Hub端项目
│   ├── src/                 # Hub端源码
│   ├── tests/               # Hub端测试
│   ├── scripts/             # 部署脚本
│   ├── config/              # 配置文件
│   └── README.md           # Hub端文档
├── client/                  # 🎯 独立客户端项目
│   ├── src/                # 客户端源码
│   ├── tests/              # 客户端测试
│   ├── scripts/            # 部署脚本
│   ├── config/             # 配置文件
│   └── README.md          # 客户端文档
├── requirements/            # 需求文档
│   ├── TODO.md
│   ├── REQUIREMENTS_CLOUDFLARE_TUNNEL.md
│   └── SOFTWARE_DESIGN_CLOUDFLARE_TUNNEL.md
├── docs/                   # 项目文档
└── README.md              # 本文件
```
├── requirements/          # 需求文档
│   ├── REQUIREMENTS_CLOUDFLARE_TUNNEL.md
│   ├── SOFTWARE_DESIGN_CLOUDFLARE_TUNNEL.md
│   └── TODO.md
├── src/                   # 源代码
│   ├── server.py         # hub端HTTP服务器
│   └── sync_client.py    # 客户端同步脚本
├── tests/                 # 测试文件
├── docs/plans/           # 设计文档
├── scripts/              # 部署脚本
└── config/               # 配置文件
```

## 快速开始

### Hub端（Windows）

```bash
# 进入Hub端目录
cd hub

# 安装依赖
pip install -r requirements.txt

# 配置（编辑 config/config.yaml）
# 设置数据目录、端口等参数

# 测试
bash scripts/test_hub.sh

# 启动服务
bash scripts/start_hub.sh
```

### 客户端（Linux）

```bash
# 进入客户端目录
cd client

# 安装依赖
pip install -r requirements.txt

# 配置（编辑 config/config.yaml）
# 设置Hub服务器地址、数据集等

# 测试
bash scripts/test_client.sh

# 部署（自动配置crontab）
sudo bash scripts/install_client.sh --setup-crontab
```

### 独立部署

两个项目都可以独立部署：

```bash
# Hub端独立部署
tar -czf hub-package.tar.gz hub/
scp hub-package.tar.gz server:~/
tar -xzf hub-package.tar.gz
cd hub && bash scripts/start_hub.sh

# 客户端独立部署
tar -czf client-package.tar.gz client/
scp client-package.tar.gz client:~/
tar -xzf client-package.tar.gz
cd client && sudo bash scripts/install_client.sh
```

## 开发流程

本项目使用 Superpowers 技能框架：

1. **brainstorming** - 需求细化
2. **writing-plans** - 编写计划
3. **subagent-driven-development** - 子代理执行
4. **test-driven-development** - TDD
5. **systematic-debugging** - 调试

技能文件位于 `workspace/skills/`。

## 文档

- [需求文档](requirements/REQUIREMENTS_CLOUDFLARE_TUNNEL.md)
- [设计文档](requirements/SOFTWARE_DESIGN_CLOUDFLARE_TUNNEL.md)
- [待办清单](requirements/TODO.md)

## License

MIT
