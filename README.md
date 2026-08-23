# INKmaster — AI 中文网络小说创作平台

INKmaster 是一个基于 AI 的中文网络小说创作工具，采用 FastAPI + React 技术栈，提供完整的小说创作流水线：从世界观到正文，从设定到润色，全流程由 AI 大模型驱动。

## 功能特性

- **九步创作流水线**：世界观 → 力量体系 → 故事大纲 → 主要角色 → 冲突引擎 → 次要角色 → 爽点节奏 → 细纲规划 → 物品道具（SSE 实时流式输出，关键步骤失败终止、可选步骤失败自动跳过）
- **章节生成**：批量生成正文（SSE 流式），自动注入题材规则、世界观、角色、大纲上下文，逐章提交不丢进度
- **章节润色**：AI 润色已有章节，支持 `polish` / `concise` / `vivid` 三种风格
- **15 种网文类型模板**：玄幻、修仙、都市、恐怖、科幻、异世界、游戏文学、仙侠、地下城、爬塔、系统流、升级流、言情奇幻、治愈、通用（每类含疲劳词黑名单、节奏规则、爽点类型、题材禁忌）
- **多 AI 供应商**：DeepSeek、OpenAI、Anthropic Claude、Ollama（OpenAI 兼容接口）
- **API Key 加密存储**：Fernet 对称加密，兼容历史明文数据
- **小说导出**：TXT / JSON，中文文件名正确编码
- **Token 用量统计**：按书籍统计调用次数、token、费用
- **真相文件管理**：维护故事一致性的版本化设定文件
- **原生桌面应用**：基于 pywebview（Edge WebView2）的桌面窗口，无需浏览器

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.12 + FastAPI + SQLAlchemy 2.0 (async) |
| 数据库 | SQLite (aiosqlite) |
| AI | openai（OpenAI/DeepSeek/Ollama）+ anthropic |
| 桌面 | pywebview (Edge WebView2) |
| 前端 | React SPA（已编译为静态文件） |

## 快速开始

### 1. 创建虚拟环境并安装依赖

```bash
cd INKmaster
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate    # macOS / Linux
pip install -r requirements.txt
```

### 2. 运行应用

**桌面模式**（打开原生窗口）：

```bash
cd backend
python run_gui.py
```

**仅后端**（开发/调试，不打开窗口）：

```bash
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

访问 http://127.0.0.1:8000 即可使用 Web 界面（API 文档见 http://127.0.0.1:8000/docs）。

### 3. 配置 AI

两种方式任选其一：

- **界面配置**：打开应用 → 设置页面 → 添加供应商与 API Key → 测试连接
- **环境变量**：复制 [backend/.env.example](backend/.env.example) 为 `backend/.env` 并填写：

```env
DEEPSEEK_API_KEY=sk-xxx
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-xxx
```

配置的 API Key 会以 Fernet 加密后存入数据库（密钥文件 `backend/data/.inkmaster.key`，请勿泄露）。

## 项目结构

```
INKmaster/
├── backend/
│   ├── run_gui.py             # 桌面应用启动器
│   ├── _e2e_test.py           # 端到端测试脚本
│   ├── .env.example           # 环境变量模板
│   └── app/
│       ├── main.py            # FastAPI 入口（全部 API 路由）
│       ├── config.py          # 配置管理（pydantic-settings）
│       ├── database.py        # 异步数据库连接
│       ├── security.py        # API Key Fernet 加密
│       ├── ai/                # AI 供应商抽象层（策略 + 工厂）
│       ├── engine/            # 九步创作引擎（状态机 / Prompt 构建 / 编排）
│       ├── models/            # 12 张表的 SQLAlchemy 模型
│       ├── prompts/           # 15 种类型模板加载器 + genres/*.md
│       └── static/            # React SPA 编译产物
├── docs/
│   └── 技术文档.md             # 完整技术文档
├── HANDOVER.md                # 项目维护与交接说明
├── requirements.txt
└── README.md
```

## API 概览

所有路由前缀 `/api/v1/`，输出 camelCase，输入兼容 camelCase / snake_case。

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET/POST/PUT/DELETE | `/api/v1/books[/{id}]` | 书籍 CRUD |
| GET/POST/PUT/DELETE | `/api/v1/books/{book_id}/chapters[/{chapter_id}]` | 章节 CRUD |
| POST | `/api/v1/books/{book_id}/chapters/generate/stream` | 批量生成章节（SSE） |
| POST | `/api/v1/books/{book_id}/chapters/{chapter_id}/polish` | 章节润色（SSE） |
| GET/POST/PUT/DELETE | `/api/v1/books/{book_id}/characters` / `world-settings` / `items` / `outlines` / `hooks` | 设定 CRUD |
| GET/POST/PUT/DELETE | `/api/v1/model-configs[/{id}]` | AI 配置（API Key 加密） |
| POST | `/api/v1/test-connection` | 测试 AI 连接 |
| POST | `/api/v1/books/{book_id}/pipeline/stream` | 启动九步流水线（SSE） |
| GET | `/api/v1/books/{book_id}/generation/status` | 生成状态 |
| GET/PUT/DELETE | `/api/v1/books/{book_id}/truth-files[/{file_name}]` | 真相文件 |
| GET | `/api/v1/books/{book_id}/token-stats` | Token 用量统计 |
| GET | `/api/v1/books/{book_id}/export?format=txt\|json` | 导出小说 |

完整接口说明见 [docs/技术文档.md](docs/技术文档.md)。

## 测试

先启动后端（默认端口 8000），再运行端到端测试：

```bash
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8000
python _e2e_test.py            # 可用 $env:INKMASTER_TEST_BASE 覆盖地址
```

## 打包为 EXE

```bash
pip install pyinstaller
pyinstaller inkmaster.spec     # 注：inkmaster.spec 需按需创建
```

> 说明：`app` 包已添加 `__init__.py` 规范化为正规包，打包时注意收集 `app/prompts/genres/*.md`、`app/engine/prompts_data.json`、`app/static/*` 等数据资源。

## 已知限制

- 前端为编译产物，源码不在此仓库（如需改 UI 需重新构建）
- 无数据库迁移（Alembic），模型变更需手动处理已有数据库
- 连续性审核、EPUB/PDF 导出未实现

## 许可证

MIT License
