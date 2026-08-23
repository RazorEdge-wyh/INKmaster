# INKmaster 项目完整交接文档

> 本文档面向下一个开发者（人类或 AI），目标是让你在最短时间内完全理解项目现状、已知问题、待办事项，并能立即开始开发。

---

## 一、项目概述

INKmaster 是一个 **AI 驱动的中文网络小说创作平台**，核心功能是通过九步创作流水线（世界观→力量体系→故事大纲→主要角色→冲突引擎→次要角色→爽点节奏→细纲规划→物品道具），利用 AI 大模型自动生成小说设定和正文。

**技术栈**：Python 3.12 + FastAPI + SQLAlchemy (async) + SQLite + pywebview + React SPA（已编译为静态文件）

**GitHub 仓库**：`https://github.com/RazorEdge-wyh/INKmaster.git`


---

## 二、项目目录结构

```
INKmaster/                          # 主项目目录
    ├── requirements.txt                # Python 依赖
    ├── README.md                       # 项目说明
    ├── .gitignore                      # Git 忽略规则
    └── backend/
        ├── run_gui.py                  # 桌面应用启动器（4632 字节）
        └── app/
            ├── config.py               # 配置管理（1793 字节）
            ├── database.py             # 数据库连接（958 字节）
            ├── main.py                 # FastAPI 入口（全部 API 路由）
            ├── ai/                     # AI 供应商抽象层
            │   ├── __init__.py         # 导出 BaseProvider, ProviderFactory
            │   ├── base.py             # 抽象基类（1453 字节）
            │   ├── factory.py          # 工厂模式（1103 字节）
            │   ├── openai_provider.py  # OpenAI 兼容供应商（3546 字节）
            │   └── anthropic_provider.py # Anthropic Claude（3134 字节）
            ├── engine/                 # 九步创作引擎
            │   ├── __init__.py         # 空文件
            │   ├── state.py            # 流水线状态管理（5603 字节）
            │   ├── prompts.py          # Prompt 构建逻辑（6283 字节）
            │   ├── prompts_data.json   # Prompt 文本数据（17457 字节）
            │   └── orchestrator.py     # 流水线编排器（7860 字节）
            ├── models/                 # 数据库模型（12个表）
            │   ├── __init__.py         # 导出所有模型（701 字节）
            │   ├── base.py             # DeclarativeBase（119 字节）
            │   ├── book.py             # 书籍表（2599 字节）
            │   ├── chapter.py          # 章节表（2028 字节）
            │   ├── character.py        # 角色表（2458 字节）
            │   ├── world_setting.py    # 世界观表（1526 字节）
            │   ├── outline.py          # 大纲表（1418 字节）
            │   ├── item.py             # 物品表（1762 字节）
            │   ├── model_config.py     # AI 配置表（851 字节）
            │   ├── generation_record.py # 生成记录表（1411 字节）
            │   ├── truth_file.py       # 真相文件表（1144 字节）
            │   ├── audit_log.py        # 审核日志表（1276 字节）
            │   └── hook.py             # 伏笔表（1355 字节）
            ├── prompts/genres/         # 15 种网文类型模板
            │   ├── xuanhuan.md         # 玄幻（3714 字节）
            │   ├── cultivation.md      # 修仙（3023 字节）
            │   ├── urban.md            # 都市（2622 字节）
            │   ├── horror.md           # 恐怖（2532 字节）
            │   ├── sci-fi.md           # 科幻（2660 字节）
            │   ├── isekai.md           # 异世界（2867 字节）
            │   ├── litrpg.md           # 游戏文学（2367 字节）
            │   ├── xianxia.md          # 仙侠（2010 字节）
            │   ├── dungeon-core.md     # 地下城（2666 字节）
            │   ├── tower-climber.md    # 爬塔（2451 字节）
            │   ├── system-apocalypse.md # 系统流（2610 字节）
            │   ├── progression.md      # 升级流（2621 字节）
            │   ├── romantasy.md        # 言情奇幻（3033 字节）
            │   ├── cozy.md             # 治愈（2637 字节）
            │   └── other.md            # 其他（729 字节）
            └── static/                 # React SPA 编译产物
                ├── index.html          # 入口 HTML（847 字节）
                ├── favicon.svg         # 图标（9522 字节）
                ├── icons.svg           # 图标集（5031 字节）
                └── assets/
                    ├── index-DUVolllF.js  # React 打包 JS（282636 字节）
                    └── index-niZHMdaS.css # React 样式（33133 字节）
```

---

## 三、核心架构详解

### 3.1 启动流程

```
run_gui.py
  ├── 1. 找空闲端口（_find_free_port）
  ├── 2. daemon 线程启动 FastAPI（uvicorn.run）
  │     └── app/main.py → lifespan → init_db() 创建 SQLite 表
  ├── 3. 轮询 /health 直到后端就绪（最多 20 秒）
  └── 4. pywebview 打开原生窗口（优先 Edge WebView2）
```

**关键细节**：
- 端口是动态分配的，不固定为 8000（config.py 里的 `port: int = 8000` 是默认值，实际被 run_gui.py 覆盖）
- 日志输出到 `data/logs/inkmaster.log`（仅打包环境）
- uvicorn 日志级别设为 WARNING，GUI 模式不刷屏

### 3.2 FastAPI 路由表（main.py）

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/api/books` | 书籍列表 |
| POST | `/api/books` | 创建书籍 |
| GET | `/api/books/{book_id}` | 获取书籍 |
| PUT | `/api/books/{book_id}` | 更新书籍 |
| DELETE | `/api/books/{book_id}` | 删除书籍（级联删除子对象） |
| GET | `/api/books/{book_id}/chapters` | 章节列表 |
| POST | `/api/books/{book_id}/chapters` | 创建章节 |
| GET | `/api/books/{book_id}/characters` | 角色列表 |
| POST | `/api/books/{book_id}/characters` | 创建角色 |
| GET | `/api/books/{book_id}/world-settings` | 世界观列表 |
| POST | `/api/books/{book_id}/world-settings` | 创建世界观 |
| GET | `/api/books/{book_id}/outlines` | 大纲列表 |
| POST | `/api/books/{book_id}/outlines` | 创建大纲 |
| GET | `/api/books/{book_id}/items` | 物品列表 |
| POST | `/api/books/{book_id}/items` | 创建物品 |
| GET | `/api/books/{book_id}/hooks` | 伏笔列表 |
| GET | `/api/model-configs` | AI 配置列表 |
| POST | `/api/model-configs` | 创建 AI 配置 |
| POST | `/api/books/{book_id}/generate` | 启动九步流水线（SSE 流） |
| GET | `/api/books/{book_id}/generation/status` | 获取生成状态 |
| POST | `/api/test-connection` | 测试 AI 连接 |
| GET | `/{path:path}` | SPA 回退（serve index.html） |

**已知问题**：
- 缺少 PUT/DELETE 端点：章节、角色、世界观、大纲、物品、伏笔都只有 GET+POST，没有更新和删除接口
- 缺少 GET 单条记录端点：如 `/api/books/{book_id}/chapters/{chapter_id}`
- `serve_spa` 路由可能拦截 `/api/` 路径——因为 FastAPI 路由按注册顺序匹配，`/{path:path}` 在最后，应该没问题，但需要验证

### 3.3 九步创作流水线（engine/）

**数据流**：
```
用户输入（书名+概念+字数+AI配置）
  → orchestrator.create_session()
  → orchestrator.stream_pipeline(session)
    → 循环 9 步：
      → state.py: PipelineStep 状态更新
      → prompts.py: 构建 system_prompt + user_prompt
      → ai provider: stream_generate() 流式调用 AI
      → yield SSE 事件给前端
```

**九步定义**（来自 state.py 第 73-88 行）：

| 步骤 | key | 名称 | 关键性 | 预估时间 |
|------|-----|------|--------|----------|
| 1 | world_setting | 世界观构建 | ✅ 关键 | ~45s |
| 2 | power_system | 成长力量体系 | 可选 | ~35s |
| 3 | outline | 故事大纲 | ✅ 关键 | ~60s |
| 4 | main_characters | 主要角色 | ✅ 关键 | ~60s |
| 5 | conflict_engine | 冲突引擎 | 可选 | ~40s |
| 6 | supporting_characters | 次要角色 | 可选 | ~55s |
| 7 | plot_rhythm | 爽点与节奏规划 | 可选 | ~40s |
| 8 | detailed_outline | 细纲规划 | ✅ 关键 | ~90s |
| 9 | items | 物品与道具 | 可选 | ~30s |

**关键步骤失败会终止流水线**（orchestrator.py 第 117-123 行），可选步骤失败会跳过继续。

**Prompt 构建逻辑**（prompts.py）：
- system_prompt = PERSONA + RULES + FORMAT + STEP_XXX（从 prompts_data.json 加载）
- user_prompt = 核心概念 + 标题 + 字数 + 类型 + 前序上下文摘要 + 当前任务说明
- 前序上下文通过 `_extract_summary()` 压缩到 5000 字以内

**Prompt 风格**：非常直白粗暴，使用大量脏话和口语化表达（如"别他妈写那种文笔优美但屁事没发生的东西"），这是刻意设计的——目的是让 AI 输出更有网感的内容，避免 AI 腔。

### 3.4 AI 供应商层（ai/）

**架构**：策略模式 + 工厂模式
- `BaseProvider`：抽象基类，定义 `generate()`、`stream_generate()`、`validate_connection()` 三个接口
- `OpenAIProvider`：处理 OpenAI 兼容 API（DeepSeek、Ollama 等）
- `AnthropicProvider`：处理 Anthropic Claude API
- `ProviderFactory`：根据 provider 名称创建对应实例

**注册表**（factory.py 第 9-14 行）：
```python
_registry = {
    "openai": OpenAIProvider,
    "deepseek": OpenAIProvider,   # DeepSeek 用 OpenAI 兼容接口
    "ollama": OpenAIProvider,     # Ollama 也用 OpenAI 兼容接口
    "anthropic": AnthropicProvider,
}
```

**重试机制**：所有 AI 调用都有 3 次重试，指数退避（2^attempt 秒）

**已知问题**：
- API Key 以明文存储在数据库 `model_configs.encrypted_api_key` 字段中（名字叫 encrypted 但实际没加密）
- 没有实现 API Key 的加密/解密逻辑
- `ProviderFactory.create()` 的 `api_base` 参数类型为 `str | None`，但调用方可能传空字符串

### 3.5 数据库模型（models/）

**数据库**：SQLite，文件位于 `data/inkmaster.db`（由 config.py 第 33 行定义）

**12 个表及关系**：
```
books (1) ──< chapters
books (1) ──< characters
books (1) ──< world_settings
books (1) ──< outlines
books (1) ──< items
books (1) ──< hooks
books (1) ──< generation_records
books (1) ──< audit_logs
books (1) ──< truth_files
model_configs (独立表)
```

**级联删除**：所有子表都设置了 `ForeignKey("books.id", ondelete="CASCADE")`，删除书籍时自动删除所有关联数据。

**已知问题**：
- `truth_files` 表有 `UniqueConstraint("book_id", "file_name", "snapshot_of")`，但 `snapshot_of` 可以为 None，可能导致约束失效
- `generation_records` 没有 relationship 回 books（只有 ForeignKey，没有 relationship 定义）
- `audit_logs`、`hooks`、`truth_files` 同样没有 relationship 定义
- 所有 `datetime` 字段使用 `datetime.now(UTC)`，Python 3.12 中 `UTC` 需要从 `datetime` 导入（已正确导入）

### 3.6 前端（static/）

**现状**：React SPA 已编译为静态文件（JS 282KB + CSS 33KB），**前端源码不在项目中**。

**入口 HTML**（index.html）：
- 加载 Google Fonts：JetBrains Mono + Noto Sans SC + Noto Serif SC
- 加载 `/assets/index-DUVolllF.js` 和 `/assets/index-niZHMdaS.css`
- 标题：`INKmaster — AI 小说写作平台`

**已知问题**：
- 前端仅交付编译产物，不包含源码（如需修改 UI 需重新构建）
- 修改前端需要从源码重新构建
- JS 文件是 Vite 打包产物（文件名含 hash：`DUVolllF`、`niZHMdaS`）

### 3.7 类型模板系统（prompts/genres/）

每种类型是一个 Markdown 文件，YAML frontmatter 包含元数据：

```yaml
---
name: 玄幻                    # 类型名称
id: xuanhuan                  # 类型 ID
chapterTypes: [...]           # 章节类型列表
fatigueWords: [...]           # 疲劳词列表（AI 常用但读者反感的词）
numericalSystem: true/false   # 是否需要数值系统
powerScaling: true/false      # 是否有力量等级
eraResearch: true/false       # 是否需要年代考据
pacingRule: "..."             # 节奏规则
satisfactionTypes: [...]      # 爽点类型
auditDimensions: [...]        # 审核维度编号
---
```

**疲劳词机制**：每种类型定义了一组"疲劳词"（如玄幻的"冷笑""蝼蚁""倒吸凉气"），这些词在 AI 生成内容时应被避免或替换。

**审核维度**：数字编号对应一套审核标准（具体映射关系在代码中未找到定义，可能是前端硬编码）。

---

## 四、已知 Bug 和待修复项

### 4.1 高优先级

1. **前端源码未包含**：React SPA 以编译产物形式交付，不包含源码；如需修改 UI 需重新构建前端。

2. **API Key 未加密**：`model_configs.encrypted_api_key` 字段名为 "encrypted" 但实际存储明文。需要实现加密逻辑（建议用 `cryptography.fernet` 或系统 DPAPI）。

3. **缺少 CRUD 端点**：章节、角色、世界观、大纲、物品、伏笔都缺少 PUT 和 DELETE 接口。用户无法在 UI 中编辑或删除这些对象（即使前端有按钮，后端也不支持）。

### 4.2 中优先级

5. **`serve_spa` 路由可能冲突**：`/{path:path}` 是 catch-all 路由，如果前端请求的 API 路径不匹配任何已注册路由，会被 SPA 回退拦截返回 index.html。建议添加路由优先级或排除 `/api/` 前缀。

6. **引擎会话内存泄漏**：`_engines` 字典中的 `NovelGenerationEngine` 实例永不过期（虽然有 `cleanup_expired_sessions()` 方法，但没有被任何地方调用）。

7. **SSE 流没有取消机制**：用户关闭窗口后，后端的 AI 调用仍在继续消耗 token。需要实现 SSE 连接断开时取消 AI 调用的逻辑。

8. **数据库迁移**：使用 `Base.metadata.create_all()` 创建表，没有迁移机制（如 Alembic）。如果修改模型定义，现有数据库不会自动更新。

### 4.3 低优先级

9. **config.py 中 `host: str = "0.0.0.0"`**：但 run_gui.py 实际使用 `127.0.0.1`。config 中的值没被使用。

10. **`cors_origins` 硬编码**：只允许 `localhost:5173` 和 `127.0.0.1:5173`（Vite 开发服务器端口），但实际运行时端口是动态的。

11. **类型模板未被使用**：`prompts/genres/*.md` 文件存在，但 `prompts.py` 和 `orchestrator.py` 中没有加载或使用这些文件的代码。类型选择功能可能在前端实现，但后端没有将类型信息传递给 prompt 构建逻辑。

12. **`GenerationParams` 中 `extra: dict` 未使用**：`base.py` 第 15 行定义了 `extra` 字段，但所有 provider 都忽略了它。

---

## 五、待开发功能

### 5.1 后端

1. **章节生成**：流水线只生成设定，不生成正文。需要实现 `POST /api/books/{book_id}/chapters/generate` 端点，使用 `CHAPTER_PROMPT` 和 `POLISH_PROMPT`（已在 prompts_data.json 中定义）。

2. **连续性审核**：`audit_logs` 表已建好，但没有审核逻辑。需要根据每种类型的 `auditDimensions` 实现 AI 审核。

3. **真相文件管理**：`truth_files` 表已建好，但没有 CRUD 端点。真相文件是 InkOS 项目的概念——用于维护故事一致性。

4. **Token 用量统计**：`generation_records` 表记录了每次 AI 调用的 token 用量，但没有统计/展示接口。

5. **导出功能**：没有将小说导出为 TXT/EPUB/PDF 的功能。

6. **类型模板集成**：将 `prompts/genres/*.md` 中的规则注入到 prompt 构建逻辑中。当前 `build_step_user_prompt()` 接受 `genre_hint` 参数但没有实际使用类型模板文件。

### 5.2 前端

前端需要从零重建（源码丢失）。建议技术栈：React + Vite + TypeScript + Tailwind CSS。

核心页面：
1. **书籍管理**：列表、创建、编辑、删除
2. **创作流水线**：九步进度展示、SSE 流式输出、步骤结果查看
3. **章节编辑器**：正文查看/编辑、AI 生成、润色
4. **设定浏览器**：世界观、角色、大纲、物品、伏笔的查看/编辑
5. **AI 配置**：供应商管理、API Key 输入、连接测试
6. **导出**：TXT/EPUB 导出

---

## 六、环境配置

### 6.1 Python 环境

- **版本**：Python 3.12.6（已安装）
- **虚拟环境**：未创建，建议创建：
  ```bash
  cd INKmaster
  python -m venv venv
  venv\Scripts\activate
  pip install -r requirements.txt
  ```

### 6.2 依赖安装

```bash
pip install fastapi uvicorn[standard] sqlalchemy aiosqlite openai anthropic pywebview pydantic-settings httpx
```

### 6.3 运行

```bash
cd backend
python run_gui.py
```

或仅启动后端（不打开窗口）：
```bash
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 6.4 数据目录

- 数据库：`backend\data\inkmaster.db`
- 日志：`backend\data\logs\inkmaster.log`（仅打包环境）
- 书籍导出目录：`backend\data\books\`

---

## 七、关键设计决策记录

1. **为什么用 SSE 而不是 WebSocket？** 九步流水线是单向流（服务器→客户端），SSE 更简单且天然支持断线重连。

2. **为什么 Prompt 用脏话风格？** 实测发现直白粗暴的指令能让 AI 输出更有"网感"的内容，避免 AI 腔（如"值得一提的是""总的来说"）。这是刻意的设计选择。

3. **为什么用 SQLite 而不是 PostgreSQL？** 桌面应用，单用户，SQLite 足够且无需额外安装数据库服务。

4. **为什么前端以编译产物交付？** 项目定位为桌面应用，前端源码未随仓库分发，仓库内仅包含编译后的静态文件。

5. **为什么 API Key 用 Fernet 加密？** 桌面应用需要持久化 API Key，明文存储有安全风险。Fernet 是对称加密，密钥存储在本地文件，无需用户记忆密码。

---

## 八、快速上手清单

给下一个开发者的行动清单：

- [ ] 安装 Python 3.12（如未安装）
- [ ] 创建虚拟环境并安装依赖
- [ ] 运行 `python run_gui.py` 验证应用能启动
- [ ] 安装 git，初始化仓库并推送到 GitHub
- [ ] 补全 CRUD 端点（PUT/DELETE）
- [ ] 实现 API Key 加密
- [ ] 实现章节生成功能
- [ ] 集成类型模板到 prompt 构建逻辑
- [ ] 添加导出功能

---

## 九、数据库表结构详解

### 9.1 books 表（核心表）

| 字段 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| id | String(36) | UUID 主键 | uuid4() |
| title | String(200) | 书名 | "未命名书籍" |
| concept | Text | 核心创意（用户输入的故事概念） | "" |
| genre | String(100) | 题材（玄幻/都市/恐怖等） | "玄幻" |
| description | Text | 简介 | None |
| author | String(200) | 作者 | None |
| tags | Text | 标签（逗号分隔） | None |
| cover_image | String(500) | 封面图路径 | None |
| total_chapters | Integer | 已生成章节数 | 0 |
| total_words | Integer | 总字数 | 0 |
| target_words | Integer | 目标字数 | 500000 |
| chapter_word_count | Integer | 单章目标字数 | 3500 |
| platform | String(50) | 发布平台 | "other" |
| language | String(10) | 语言 | "zh" |
| fanfic_mode | String(20) | 同人模式 | None |
| status | String(20) | 状态（draft/active/completed） | "draft" |
| pipeline_progress | Integer | 创作流水线进度（0-9） | 0 |
| created_at | DateTime | 创建时间 | now(UTC) |
| updated_at | DateTime | 更新时间 | now(UTC) |

### 9.2 chapters 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | String(36) | UUID 主键 |
| book_id | String(36) | 外键 → books.id |
| chapter_number | Integer | 章节序号 |
| title | String(300) | 章节标题 |
| content | Text | 正文内容 |
| summary | Text | 章节摘要 |
| word_count | Integer | 字数 |
| status | String(20) | 状态（draft/final） |
| source | String(20) | 来源（ai/manual） |
| has_hook | Integer | 是否包含钩子（0/1） |
| hook_type | String(50) | 钩子类型 |
| audit_status | String(30) | 连续性审核状态 |
| audit_issues | Text | 审核问题（JSON） |
| token_usage | Text | Token 用量（JSON） |
| sort_order | Integer | 排序序号 |

### 9.3 characters 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | String(36) | UUID 主键 |
| book_id | String(36) | 外键 → books.id |
| name | String(100) | 姓名 |
| role | String(50) | 角色定位（中文，如"主角""反派"） |
| role_type | String(50) | 角色类型（英文，如"protagonist""antagonist"） |
| description | Text | 简介 |
| background | Text | 背景故事 |
| notes | Text | 备注 |
| personality | Text | 性格 |
| speech_style | Text | 语言风格 |
| motivation | Text | 动机 |
| flaws | Text | 缺陷 |
| arc | Text | 成长弧线 |
| appearance | Text | 外貌 |
| abilities | Text | 能力 |
| relationships | Text | 人物关系（JSON） |
| current_location | String(300) | 当前位置 |
| known_info | Text | 已知信息（JSON） |
| state_snapshot | Text | 状态快照（JSON） |

### 9.4 model_configs 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | String(36) | UUID 主键 |
| provider | String(50) | 供应商（deepseek/openai/anthropic） |
| model_name | String(100) | 模型名称（如 deepseek-chat） |
| api_base | String(300) | API 地址 |
| encrypted_api_key | String(500) | API Key（**明文存储，未加密**） |
| is_active | Boolean | 是否启用 |

---

## 十、API 请求/响应示例

### 10.1 创建书籍

**请求**：
```http
POST /api/books
Content-Type: application/json

{
  "title": "斗破苍穹",
  "concept": "一个被家族抛弃的少年觉醒血脉，踏上修炼之路",
  "genre": "玄幻",
  "target_words": 500000,
  "chapter_word_count": 3500
}
```

**响应**：
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "斗破苍穹"
}
```

### 10.2 启动九步流水线

**请求**：
```http
POST /api/books/{book_id}/generate
Content-Type: application/json

{
  "provider": "deepseek",
  "api_key": "sk-xxx",
  "model": "deepseek-chat",
  "api_base": "https://api.deepseek.com/v1",
  "concept": "一个被家族抛弃的少年觉醒血脉",
  "mode": "auto"
}
```

**响应**（SSE 流）：
```
data: {"type": "pipeline_start", "session_id": "sess_abc123"}

data: {"type": "step_start", "step": 1, "name": "世界观构建", "description": "物理法则、时代背景..."}

data: {"type": "token", "step": 1, "token": "这是一个"}

data: {"type": "token", "step": 1, "token": "以斗气为尊的世界"}

data: {"type": "step_complete", "step": 1, "result": "完整的世界观设定文本..."}

data: {"type": "pipeline_complete", "completed_steps": 9, "total_steps": 9}
```

### 10.3 测试 AI 连接

**请求**：
```http
POST /api/test-connection
Content-Type: application/json

{
  "provider": "deepseek",
  "api_key": "sk-xxx",
  "model": "deepseek-chat",
  "api_base": "https://api.deepseek.com/v1"
}
```

**响应**：
```json
{
  "success": true,
  "message": "连接成功 (模型: deepseek-chat)"
}
```

---

## 十一、九步流水线状态机

```
PENDING → RUNNING → COMPLETED
                  → FAILED (关键步骤 → 终止流水线)
                  → SKIPPED (可选步骤 → 继续下一步)
```

**状态转换逻辑**（orchestrator.py）：

1. **PENDING → RUNNING**：第 88-91 行，流水线开始执行某一步时
2. **RUNNING → COMPLETED**：第 103-110 行，AI 成功返回结果
3. **RUNNING → FAILED**：第 118-123 行，AI 调用失败且是关键步骤
4. **RUNNING → SKIPPED**：第 125-127 行，AI 调用失败但是可选步骤

**上下文传递**：每一步的 `result_text` 会通过 `session.get_previous_context()` 传递给下一步，作为 AI 的输入上下文。这确保了设定的连贯性。

---

## 十二、Prompt 构建详解

### 12.1 System Prompt 结构

```
PERSONA + RULES + FORMAT + STEP_XXX
```

- **PERSONA**：角色设定（"你是网文设定架构师"）
- **RULES**：7 条铁律（禁止 AI 腔、情绪身体化、节奏短句等）
- **FORMAT**：输出格式要求（使用 `=== 板块名 ===` 分隔）
- **STEP_XXX**：具体步骤的指令（如 STEP_WORLD、STEP_OUTLINE 等）

### 12.2 User Prompt 结构

```
【核心概念】
「用户输入的故事概念」

【作品标题】书名
【目标字数】500,000 字（约 142 章）
【类型标签】玄幻

【已生成的设定 —— 必须基于以下内容继续，保持一致性】
（前序步骤的输出摘要，压缩到 5000 字以内）

【当前任务】世界观构建 —— 物理法则、时代背景、地理、政治、人文
请基于【核心概念】完成这一步创作。每一个设定都必须能从概念中找到根源。
```

### 12.3 上下文压缩算法（prompts.py 第 125-161 行）

`_extract_summary()` 函数将前序步骤的完整输出压缩到 5000 字以内：

1. 按行遍历，识别 `=== 板块名 ===` 分隔符
2. 每个板块保留前 8 行
3. 如果总长度超过 5000 字，逐行截断并添加 `[...已压缩，保持 token 预算]`

---

## 十三、前端静态文件分析

### 13.1 index.html

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>INKmaster — AI 小说写作平台</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Noto+Sans+SC:wght@300;400;500;600;700;900&family=Noto+Serif+SC:wght@400;500;600;700;900&display=swap" rel="stylesheet" />
    <script type="module" crossorigin src="/assets/index-DUVolllF.js"></script>
    <link rel="stylesheet" crossorigin href="/assets/index-niZHMdaS.css">
  </head>
  <body>
    <div id="root"></div>
  </body>
</html>
```

**分析**：
- 使用 Google Fonts：JetBrains Mono（代码字体）+ Noto Sans SC（正文）+ Noto Serif SC（标题）
- React 入口：`<div id="root"></div>`
- JS 文件：282KB（压缩后），包含所有 React 组件和逻辑
- CSS 文件：33KB（压缩后）

### 13.2 重建前端的建议

如果需要重建前端，建议技术栈：
- **框架**：React 18 + TypeScript
- **构建工具**：Vite
- **样式**：Tailwind CSS
- **状态管理**：Zustand 或 Redux Toolkit
- **HTTP 客户端**：Axios 或 fetch
- **SSE 客户端**：EventSource API

核心组件：
1. `BookList` - 书籍列表页
2. `BookDetail` - 书籍详情页（包含标签页：设定、章节、角色、世界观等）
3. `PipelineView` - 九步流水线视图（SSE 流式输出）
4. `ChapterEditor` - 章节编辑器
5. `SettingsPage` - AI 配置页

---

## 十五、测试建议

### 15.1 单元测试

建议为以下模块编写单元测试：

1. **AI 供应商层**：
   - `test_openai_provider.py` - 测试 OpenAI 兼容 API 调用
   - `test_anthropic_provider.py` - 测试 Anthropic API 调用
   - `test_factory.py` - 测试工厂模式

2. **九步引擎**：
   - `test_state.py` - 测试状态机转换
   - `test_prompts.py` - 测试 Prompt 构建逻辑
   - `test_orchestrator.py` - 测试流水线编排

3. **数据库模型**：
   - `test_models.py` - 测试所有模型的 CRUD 操作

### 15.2 集成测试

1. **API 端点测试**：使用 `httpx` 测试所有 FastAPI 端点
2. **SSE 流测试**：测试九步流水线的 SSE 输出
3. **端到端测试**：从创建书籍到完成九步流水线的完整流程

### 15.3 手动测试清单

- [ ] 启动应用，验证窗口正常打开
- [ ] 创建书籍，验证数据库记录
- [ ] 配置 AI 供应商，测试连接
- [ ] 启动九步流水线，验证 SSE 流式输出
- [ ] 检查每一步的输出是否符合预期
- [ ] 验证章节、角色、世界观等数据的 CRUD 操作

---

## 十六、部署建议

### 16.1 开发环境

```bash
# 1. 克隆仓库
git clone https://github.com/RazorEdge-wyh/INKmaster.git
cd INKmaster

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 运行（开发模式）
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 16.2 生产环境（打包为 EXE）

```bash
# 1. 安装 PyInstaller
pip install pyinstaller

# 2. 打包
pyinstaller inkmaster.spec

# 3. 生成的 EXE 在 dist/ 目录下
```

**注意**：`inkmaster.spec` 文件不在项目中，需要重新创建。建议参考 PyInstaller 文档。

### 16.3 Docker 部署（可选）

如果需要 Docker 部署，建议 Dockerfile：

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
WORKDIR /app/backend

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 十七、性能优化建议

1. **数据库查询优化**：
   - 为 `book_id` 字段添加索引（已在模型中定义 `index=True`）
   - 使用 `selectinload()` 预加载关联对象，避免 N+1 查询

2. **AI 调用优化**：
   - 实现请求缓存，避免重复调用
   - 添加超时控制（当前硬编码为 300 秒）
   - 实现请求队列，避免并发过高

3. **前端优化**：
   - 代码分割（React.lazy + Suspense）
   - 虚拟滚动（章节列表可能很长）
   - 防抖/节流（输入框、滚动事件）

---

## 十八、安全建议

1. **API Key 加密**：使用 `cryptography.fernet` 或系统 DPAPI 加密 API Key
2. **CORS 配置**：生产环境应限制 `cors_origins`，不使用 `*`
3. **输入验证**：使用 Pydantic 模型验证所有 API 输入
4. **SQL 注入防护**：SQLAlchemy 已提供防护，但需确保不使用原生 SQL
5. **XSS 防护**：前端应对用户输入进行转义

---

## 十九、联系方式

如有问题，请参考以下资源：

2. **GitHub 仓库**：`https://github.com/RazorEdge-wyh/INKmaster.git`

---

**文档版本**：v1.0  
**最后更新**：2026-08-23  
**编写者**：INKmaster 项目维护团队
