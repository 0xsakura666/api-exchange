# API Exchange

一个 API Key 中转聚合服务，将多个有限额度的 API Key 统一成一个接口，自动管理和切换，支持余额查询和模型定价。

## 功能特性

- **OpenAI API 兼容** - 提供标准的 `/v1/chat/completions` 接口，可直接用于 Cursor、ChatGPT 客户端等
- **自动 Key 轮换** - 当一个 Key 余额不足或失效时，自动切换到下一个可用 Key
- **远程余额同步** - 自动从上游 API 查询每个 Key 的真实剩余额度
- **模型定价管理** - 支持为不同模型配置不同的扣费价格（通配符匹配）
- **批量导入** - 支持 JSON、CSV、纯文本格式批量导入 API Key
- **可视化管理后台** - Vue 3 构建的现代化管理界面

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         客户端应用                               │
│              (Cursor / ChatGPT / 自定义应用)                     │
└─────────────────────────┬───────────────────────────────────────┘
                          │ 统一 API Key
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API Exchange 服务                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  FastAPI    │  │ Key 管理器  │  │     SQLite 数据库       │  │
│  │  路由层     │◄─┤  轮换/扣费  │◄─┤  - API Keys            │  │
│  │             │  │             │  │  - 模型定价            │  │
│  └──────┬──────┘  └──────┬──────┘  └─────────────────────────┘  │
│         │                │                                       │
│         │         ┌──────┴──────┐                                │
│         │         │ 余额同步器  │                                │
│         │         └──────┬──────┘                                │
└─────────┼────────────────┼──────────────────────────────────────┘
          │                │
          ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        上游 API 服务                             │
│         /v1/chat/completions    /dashboard/billing/*            │
└─────────────────────────────────────────────────────────────────┘
```

## 项目结构

```
api-exchange/
├── main.py              # FastAPI 应用入口
├── config.py            # 配置管理（环境变量）
├── models.py            # Pydantic 数据模型
├── database.py          # SQLite 数据库操作
├── key_manager.py       # Key 选择与轮换逻辑
├── usage_checker.py     # 远程余额查询
├── proxy.py             # API 代理核心（请求转发）
├── admin.py             # 管理接口路由
├── requirements.txt     # Python 依赖
├── .env.example         # 环境变量示例
├── keys.db              # SQLite 数据库（运行时生成）
├── static/              # 前端构建产物
└── frontend/            # Vue 3 前端源码
    ├── src/
    │   ├── App.vue      # 主组件
    │   ├── api.js       # API 调用封装
    │   └── main.js      # 入口
    ├── package.json
    └── vite.config.js
```

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/your-repo/api-exchange.git
cd api-exchange
```

### 2. 创建虚拟环境并安装依赖

```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 配置环境变量（可选）

复制示例配置文件：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
# 管理员密钥（同时也是 API 访问密钥）
API_EXCHANGE_ADMIN_KEY=sk-your-secret-key

# 上游 API 地址
API_EXCHANGE_UPSTREAM_BASE_URL=https://api2.qiandao.mom/v1

# 服务端口
API_EXCHANGE_PORT=8000
```

### 4. 构建前端（可选，已预构建）

```bash
cd frontend
npm install
npm run build
cd ..
```

### 5. 启动服务

```bash
python main.py
```

服务将在 http://localhost:8000 启动。

## 使用教程

### 访问管理后台

打开浏览器访问：http://localhost:8000

使用管理密钥登录（默认：`sk-api-exchange-admin`）

### 导入 API Keys

#### 方式一：通过管理后台界面

1. 登录管理后台
2. 点击「批量导入」标签
3. 在文本框中粘贴 Keys，格式为每行一个：
   ```
   sk-key1,0.24
   sk-key2,0.40
   sk-key3
   ```
   （余额可选，不填则使用默认值）
4. 点击「导入」按钮

#### 方式二：通过 CSV 文件导入

创建 `keys.csv` 文件：

```csv
sk-iB6knKZKHGc5eJNBgBKyEsHAC0czsOcu8uMPQxEhiGRifGbT,0.24
sk-YCs9LOzqENgFyP128swgenAa1x5txf41Oqvu9yRKvCXIbYL4,0.40
sk-j9aKOoxztMpaAU1bM5eitOKUDf4ENS0z6gXvUCPc2arPmazF,0.24
```

使用 curl 导入：

```bash
curl -X POST http://localhost:8000/admin/keys/import/csv \
  -H "Authorization: Bearer sk-api-exchange-admin" \
  -F "file=@keys.csv"
```

#### 方式三：通过 API 导入 JSON

```bash
curl -X POST http://localhost:8000/admin/keys/import \
  -H "Authorization: Bearer sk-api-exchange-admin" \
  -H "Content-Type: application/json" \
  -d '{
    "keys": [
      {"key": "sk-xxx1", "balance": 0.24},
      {"key": "sk-xxx2", "balance": 0.40}
    ]
  }'
```

### 同步远程余额

导入 Keys 后，点击「同步远程余额」按钮，系统会自动查询每个 Key 的真实剩余额度。

也可以通过 API 同步：

```bash
# 同步所有 Keys
curl -X POST http://localhost:8000/admin/sync \
  -H "Authorization: Bearer sk-api-exchange-admin"

# 同步单个 Key
curl -X POST http://localhost:8000/admin/keys/{key_id}/sync \
  -H "Authorization: Bearer sk-api-exchange-admin"
```

### 配置模型定价

1. 在管理后台点击「定价配置」标签
2. 查看和修改现有定价规则
3. 添加新的定价规则（支持通配符）

定价规则示例：
- `gemini-3-pro-*` → 0.08 额度/次
- `claude-opus-*` → 0.12 额度/次
- `*` → 0.08 额度/次（默认）

### 查看可用模型

1. 在管理后台点击「模型列表」标签
2. 查看上游支持的所有模型，按分类显示
3. 每个模型显示对应的扣费价格

### 使用统一 API

配置你的客户端（Cursor、ChatGPT 等）：

| 配置项 | 值 |
|-------|-----|
| API Base URL | `http://localhost:8000/v1` |
| API Key | `sk-api-exchange-admin`（或你自定义的密钥） |

示例请求：

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer sk-api-exchange-admin" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-3-pro-preview-y",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": true
  }'
```

## API 接口文档

### 代理接口（OpenAI 兼容）

| 接口 | 方法 | 说明 |
|------|------|------|
| `/v1/chat/completions` | POST | Chat 补全（支持流式） |
| `/v1/models` | GET | 获取模型列表 |

### 管理接口

所有管理接口需要 Header：`Authorization: Bearer <admin_key>`

#### Keys 管理

| 接口 | 方法 | 说明 |
|------|------|------|
| `/admin/keys` | GET | 获取所有 Keys |
| `/admin/keys` | POST | 添加单个 Key |
| `/admin/keys/import` | POST | 批量导入 (JSON) |
| `/admin/keys/import/csv` | POST | 导入 CSV 文件 |
| `/admin/keys/import/text` | POST | 导入纯文本文件 |
| `/admin/keys/{id}` | DELETE | 删除 Key |
| `/admin/keys/{id}/sync` | POST | 同步单个 Key 余额 |
| `/admin/sync` | POST | 同步所有 Keys 余额 |
| `/admin/stats` | GET | 获取统计信息 |

#### 模型定价

| 接口 | 方法 | 说明 |
|------|------|------|
| `/admin/models` | GET | 获取上游模型列表（分类+价格） |
| `/admin/pricing` | GET | 获取定价配置 |
| `/admin/pricing` | POST | 添加定价规则 |
| `/admin/pricing/{id}` | PUT | 更新定价规则 |
| `/admin/pricing/{id}` | DELETE | 删除定价规则 |
| `/admin/pricing/check?model=xxx` | GET | 查询指定模型价格 |

### 其他接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 管理后台页面 |
| `/api/status` | GET | 服务状态 |
| `/health` | GET | 健康检查 |
| `/docs` | GET | Swagger API 文档 |

## 配置说明

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `API_EXCHANGE_HOST` | `0.0.0.0` | 监听地址 |
| `API_EXCHANGE_PORT` | `8000` | 监听端口 |
| `API_EXCHANGE_ADMIN_KEY` | `sk-api-exchange-admin` | 管理员/访问密钥 |
| `API_EXCHANGE_UPSTREAM_BASE_URL` | `https://api2.qiandao.mom/v1` | 上游 API 地址 |
| `API_EXCHANGE_DATABASE_PATH` | `keys.db` | 数据库文件路径 |
| `API_EXCHANGE_REQUEST_TIMEOUT` | `120.0` | 请求超时（秒） |
| `API_EXCHANGE_AUTO_SYNC_USAGE` | `true` | 是否自动同步用量 |
| `API_EXCHANGE_SYNC_INTERVAL` | `300` | 同步间隔（秒） |

## 工作原理

### Key 选择策略

1. 查询所有 `status=active` 且 `balance >= 模型价格` 的 Key
2. 按 `last_used` 升序排列（最久未使用的优先）
3. 选择第一个可用的 Key 发起请求

### 自动切换机制

1. 请求成功 → 扣除余额，更新使用时间
2. 请求失败（余额不足/Key 失效）→ 标记 Key 状态，自动重试下一个 Key
3. 所有 Key 都不可用 → 返回 503 错误

### 余额同步

通过上游 API 查询真实余额：
- `/dashboard/billing/subscription` → 获取总额度
- `/dashboard/billing/usage` → 获取已用额度
- 剩余额度 = 总额度 - 已用额度

## Key 状态说明

| 状态 | 说明 |
|------|------|
| `active` | 可用状态 |
| `exhausted` | 余额已耗尽 |
| `invalid` | Key 无效或已失效 |

## 常见问题

### Q: 如何修改管理密钥？

编辑 `.env` 文件，设置 `API_EXCHANGE_ADMIN_KEY=your-new-key`，然后重启服务。

### Q: 支持哪些上游 API？

目前默认配置为 `api2.qiandao.mom`，理论上支持任何 OpenAI 兼容的 API 服务，只需修改 `API_EXCHANGE_UPSTREAM_BASE_URL`。

### Q: 如何备份数据？

复制 `keys.db` 文件即可，这是 SQLite 数据库，包含所有 Keys 和定价配置。

### Q: 定价规则的匹配顺序？

按添加顺序匹配，建议将具体的规则（如 `gemini-3-pro-*`）放在前面，通用规则（如 `*`）放在最后。

## 部署指南

### Railway 部署（推荐）

Railway 是部署 Python 后端的最佳选择，支持持久化存储。

1. **Fork 或 Push 代码到 GitHub**

2. **在 Railway 创建项目**
   - 访问 [railway.app](https://railway.app)
   - 点击 "New Project" → "Deploy from GitHub repo"
   - 选择你的 `api-exchange` 仓库

3. **配置环境变量**
   
   在 Railway 项目设置中添加：
   ```
   API_EXCHANGE_ADMIN_KEY=你的管理密钥
   API_EXCHANGE_UPSTREAM_BASE_URL=https://api2.qiandao.mom/v1
   ```

4. **配置持久化存储（重要）**
   - 在项目中添加 "Volume"
   - 挂载路径设为 `/app/data`
   - 设置环境变量 `API_EXCHANGE_DATABASE_PATH=/app/data/keys.db`

5. **生成域名**
   - 在 Settings → Networking → Generate Domain
   - 获得类似 `api-exchange-xxx.up.railway.app` 的域名

6. **使用**
   ```
   API Base URL: https://your-app.up.railway.app/v1
   API Key: 你设置的管理密钥
   ```

### Vercel 部署（仅前端）

由于 Vercel Serverless 函数有执行时间限制（10-60秒），不适合作为 API 代理的长连接场景。

如果你只想部署前端管理界面，可以：

1. 修改 `frontend/src/api.js` 中的 API 地址指向你的 Railway 后端
2. 在 Vercel 部署 `frontend` 目录

### Docker 部署

```bash
# 构建镜像
docker build -t api-exchange .

# 运行容器
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -e API_EXCHANGE_ADMIN_KEY=your-key \
  -e API_EXCHANGE_DATABASE_PATH=/app/data/keys.db \
  api-exchange
```

## License

MIT
