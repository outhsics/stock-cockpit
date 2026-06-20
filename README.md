# 📈 Stock Cockpit · 美股投资驾驶舱

一个开箱即用的美股投资管理系统：登录后即可看到**每日 AI 简报**、**持仓总览**、**新闻聚合**，后续会集成 OpenBB 深度研究和 Ghostfolio。

> ⚠️ 本项目仅提供数据展示和 AI 分析辅助，**不构成任何投资建议**。所有投资决策请自行判断并自担风险。

---

## ✨ 功能（第一阶段 MVP）

| 模块 | 功能 |
|---|---|
| 🔐 登录系统 | JWT 认证，首次启动自动创建 `admin` 账户 |
| 💼 持仓管理 | 录入 QQQ/VOO/个股，自动算市值/盈亏/收益率 |
| 📊 总览仪表盘 | 总资产、今日盈亏、净值曲线、资产配置饼图 |
| 📰 新闻聚合 | Yahoo Finance / CNBC / WSJ / MarketWatch 自动抓取 |
| 🤖 AI 每日简报 | 基于你的持仓+新闻，AI 解读"为什么涨跌" |
| ⏰ 定时任务 | 每日自动生成简报 + 定期刷新新闻 |

---

## 🚀 快速开始（3 分钟）

### 前置条件

- **Docker**（推荐 [OrbStack](https://orbstack.dev/) macOS，或 Docker Desktop）
  - 验证：`docker --version` 和 `docker compose version`

### 步骤

```bash
# 1. 进入项目目录
cd stock-cockpit

# 2. 拷贝配置文件
cp .env.example .env

# 3. （重要）编辑 .env，至少填这两项：
#    - SECRET_KEY: 改成随机字符串（生产必改）
#    - LLM_API_KEY: 智谱 Z.ai 的 Key（不填则 AI 简报是占位内容）
#      获取地址：https://open.bigmodel.cn  注册后在控制台创建 API Key

# 4. 一键启动
docker compose up -d --build

# 5. 查看启动日志，找到自动生成的 admin 密码
docker compose logs cockpit | grep -A 3 "Admin created"

# 6. 打开浏览器
open http://localhost:8000
```

### 默认账号

- 用户名：`admin`
- 密码：首次启动时**随机生成并打印到日志**（如果你没在 `.env` 里设置 `DEFAULT_ADMIN_PASSWORD`）
  - 查看命令：`docker compose logs cockpit | grep "Admin created"`

---

## 🔧 配置说明（.env）

| 配置项 | 默认值 | 说明 |
|---|---|---|
| `SECRET_KEY` | 需修改 | JWT 签名密钥，生产必改 |
| `DEFAULT_ADMIN_USERNAME` | `admin` | 默认管理员用户名 |
| `DEFAULT_ADMIN_PASSWORD` | 空（随机） | 留空则每次首次启动随机生成 |
| `LLM_PROVIDER` | `glm` | AI 厂商：`glm`/`deepseek`/`openai`/`ollama`/`custom` |
| `LLM_API_KEY` | 空（必填） | 对应厂商的 API Key |
| `LLM_BASE_URL` | 智谱地址 | OpenAI 兼容端点 |
| `LLM_MODEL` | `glm-4-flash` | 模型名 |
| `BRIEFING_CRON_HOUR` | `5` | 每日简报生成时间（UTC，5≈美东 01:00） |
| `NEWS_REFRESH_MINUTES` | `30` | 新闻刷新间隔（分钟） |

### 切换 AI 提供商

只需在 `.env` 改 3 行，例如换 DeepSeek：

```env
LLM_PROVIDER=deepseek
LLM_API_KEY=sk-your-deepseek-key
LLM_MODEL=deepseek-chat
```

（`LLM_BASE_URL` 会自动用该 provider 的预设地址，无需手动填）

---

## 🛠 开发模式（本地前后端分别跑）

如果想改代码，可以用开发模式热更新：

```bash
# 终端 1：后端（需要 Python 3.11+，不要用 3.14，pydantic-core 没 wheel）
cd backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 终端 2：前端（Vite 热更新，自动代理 /api 到 :8000）
cd frontend
npm install
npm run dev
# 打开 http://localhost:5173
```

---

## 📂 项目结构

```
stock-cockpit/
├── Dockerfile                  # 多阶段：前端构建 + 后端运行
├── docker-compose.yml          # 一键启动
├── .env.example                # 配置模板
├── data/                       # SQLite 数据（持久化，gitignore）
├── backend/
│   ├── requirements.txt
│   ├── Dockerfile              # （已合并到根 Dockerfile，保留备用）
│   ├── app/
│   │   ├── main.py             # FastAPI 入口
│   │   ├── config.py           # 环境变量配置
│   │   ├── database.py         # SQLAlchemy
│   │   ├── models.py           # User/Holding/NewsItem/Briefing
│   │   ├── auth/               # JWT 认证
│   │   ├── portfolio/          # 持仓 + 收益计算
│   │   ├── market/             # yfinance 行情
│   │   ├── news/               # RSS 新闻聚合
│   │   ├── briefing/           # AI 简报 + LLM 抽象层
│   │   └── scheduler.py        # APScheduler 定时任务
│   └── scripts/seed.py         # 初始化管理员
└── frontend/
    ├── package.json
    ├── vite.config.ts
    └── src/
        ├── pages/              # Login/Dashboard/Portfolio/Briefing/News
        ├── components/ui/      # Card/Button/Input/Stat
        ├── components/charts/  # Recharts 图表
        └── lib/api.ts          # API 客户端
```

---

## 🗺 路线图

- ✅ **阶段 1（已交付）**：登录 + 持仓 + 总览 + 新闻 + AI 简报
- 🔜 **阶段 2**：集成 OpenBB SDK（ETF 对比/回测/宏观）+ Ghostfolio（更细的财富管理）
- 🔜 **阶段 3**：多 AI Agent 协作（巴菲特/林奇/逆向风格）+ 告警推送 + 策略回测

---

## ❓ 常见问题

**Q: 启动后 AI 简报显示"未配置 LLM_API_KEY"？**
A: 编辑 `.env` 填入 `LLM_API_KEY`，然后 `docker compose down && docker compose up -d --build`。

**Q: 持仓价格显示 $0 或"无数据"？**
A: 默认数据源是 Yahoo Finance 免费接口，**在容器/数据中心 IP 上常被限流**（这是 Yahoo 的限制，不是 bug）。
   解决方案（强烈推荐）：申请一个免费的 Alpha Vantage Key（[alphavantage.co](https://www.alphavantage.co/support/#api-key)，5 分钟，500 次/天够用），
   然后在 `.env` 设置 `ALPHA_VANTAGE_API_KEY=你的key`，重启即可。配了 Key 后系统会优先用 Alpha Vantage（稳定、不限 IP），Yahoo 作为备用。
   注意：免费 Key 每分钟限 5 次请求，本系统已内置缓存（60 秒），日常使用足够。

**Q: 忘记 admin 密码？**
A: 删掉 `data/cockpit.db` 重启会重新生成（会丢失持仓数据）；或在 `.env` 设置固定的 `DEFAULT_ADMIN_PASSWORD` 后删库重启。

**Q: 想换成本地模型（Ollama）？**
A: 先本机跑 `ollama serve` 并 `ollama pull qwen2.5:7b`，然后 `.env` 设：
```
LLM_PROVIDER=ollama
LLM_BASE_URL=http://host.docker.internal:11434/v1
LLM_MODEL=qwen2.5:7b
```

---

## 📜 License

MIT — 自由使用、修改、分发。投资有风险，本工具不构成任何投资建议。
