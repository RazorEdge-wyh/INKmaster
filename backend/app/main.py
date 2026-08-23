"""INKmaster — FastAPI application entry point.

统一 API 契约：
- 所有路由前缀为 /api/v1/（与编译后的 React 前端保持一致）
- 对外返回 camelCase 字段
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Optional
from urllib.parse import quote

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings, STATIC_DIR, BOOKS_DIR
from app.database import get_db, init_db
from app.models import (
    Book, Chapter, Character, WorldSetting, Outline, Item,
    ModelConfig, GenerationRecord, TruthFile, AuditLog, Hook,
)
from app.ai.factory import ProviderFactory
from app.ai.base import BaseProvider, GenerationParams
from app.engine.orchestrator import NovelGenerationEngine
from app.engine.prompts import (
    CHAPTER_SYSTEM_PROMPT, CHAPTER_POLISH_PROMPT, build_step_user_prompt,
)
from app.prompts import genre_rules_text
from app.security import encrypt, decrypt


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    cleanup_task = asyncio.create_task(_periodic_session_cleanup())
    yield
    cleanup_task.cancel()
    # 关闭所有 AI provider 的底层 HTTP client
    for engine in _engines.values():
        try:
            await engine.provider.close()
        except Exception:
            pass


async def _periodic_session_cleanup():
    """周期性清理过期会话，避免 _engines / _sessions 无界增长。"""
    while True:
        await asyncio.sleep(1800)  # 每 30 分钟
        for engine in _engines.values():
            try:
                await engine.cleanup_expired_sessions()
            except Exception:
                pass


app = FastAPI(title="INKmaster", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

# 引擎缓存（按 provider:model 复用）
_engines: dict[str, NovelGenerationEngine] = {}


# ---------------------------------------------------------------------------
# 序列化辅助 —— 数据库字段 → camelCase
# ---------------------------------------------------------------------------
def _dt(v: Any) -> Optional[str]:
    return v.isoformat() if v else None


def _book_to_dict(b: Book) -> dict:
    steps = b.pipeline_progress or 0
    return {
        "id": b.id,
        "title": b.title,
        "concept": b.concept,
        "genre": b.genre,
        "description": b.description,
        "author": b.author,
        "tags": b.tags,
        "coverImage": b.cover_image,
        "chapterCount": b.total_chapters,
        "totalWords": b.total_words,
        "targetWords": b.target_words,
        "chapterWordCount": b.chapter_word_count,
        "platform": b.platform,
        "language": b.language,
        "fanficMode": b.fanfic_mode,
        "status": b.status,
        "pipelineProgress": round(steps / 9.0, 3),
        "lastStep": steps,
        "createdAt": _dt(b.created_at),
        "updatedAt": _dt(b.updated_at),
    }


def _chapter_to_dict(c: Chapter) -> dict:
    return {
        "id": c.id,
        "bookId": c.book_id,
        "number": c.chapter_number,
        "title": c.title,
        "content": c.content,
        "summary": c.summary,
        "wordCount": c.word_count,
        "status": c.status,
        "source": c.source,
        "hasHook": bool(c.has_hook),
        "hookType": c.hook_type,
        "auditStatus": c.audit_status,
        "tokenUsage": c.token_usage,
        "sortOrder": c.sort_order,
        "createdAt": _dt(c.created_at),
        "updatedAt": _dt(c.updated_at),
    }


def _character_to_dict(c: Character) -> dict:
    return {
        "id": c.id,
        "bookId": c.book_id,
        "name": c.name,
        "role": c.role,
        "roleType": c.role_type,
        "description": c.description,
        "background": c.background,
        "notes": c.notes,
        "personality": c.personality,
        "speechStyle": c.speech_style,
        "motivation": c.motivation,
        "flaws": c.flaws,
        "arc": c.arc,
        "appearance": c.appearance,
        "abilities": c.abilities,
        "relationships": c.relationships,
        "currentLocation": c.current_location,
        "knownInfo": c.known_info,
        "stateSnapshot": c.state_snapshot,
        "sortOrder": c.sort_order,
    }


def _world_setting_to_dict(w: WorldSetting) -> dict:
    return {
        "id": w.id,
        "bookId": w.book_id,
        "category": w.category,
        "name": w.name,
        "description": w.description,
        "content": w.content,
        "rules": w.rules,
        "parentId": w.parent_id,
        "sortOrder": w.sort_order,
    }


def _item_to_dict(i: Item) -> dict:
    return {
        "id": i.id,
        "bookId": i.book_id,
        "name": i.name,
        "itemType": i.item_type,
        "acquisitionCost": i.acquisition_cost,
        "usageLimit": i.usage_limit,
        "hiddenProperty": i.hidden_property,
        "conflictPotential": i.conflict_potential,
        "description": i.description,
        "quantity": i.quantity,
        "currentHolder": i.current_holder,
        "firstUseChapter": i.first_use_chapter,
        "usageCount": i.usage_count,
        "sortOrder": i.sort_order,
    }


def _outline_to_dict(o: Outline) -> dict:
    return {
        "id": o.id,
        "bookId": o.book_id,
        "title": o.title,
        "type": o.type,
        "stepName": o.step_name,
        "content": o.content,
        "status": o.status,
        "sortOrder": o.sort_order,
    }


def _hook_to_dict(h: Hook) -> dict:
    return {
        "id": h.id,
        "bookId": h.book_id,
        "hookId": h.hook_id,
        "type": h.type,
        "description": h.description,
        "plantedChapter": h.planted_chapter,
        "expectedReveal": h.expected_reveal,
        "status": h.status,
        "resolutionText": h.resolution_text,
    }


def _truth_file_to_dict(t: TruthFile) -> dict:
    return {
        "id": t.id,
        "bookId": t.book_id,
        "name": t.file_name,
        "file_name": t.file_name,
        "content": t.content,
        "snapshotOf": t.snapshot_of,
        "createdAt": _dt(t.created_at),
        "updatedAt": _dt(t.updated_at),
    }


# 从请求体（可能 camelCase 或 snake_case）取值
def _pick(data: dict, *keys: str, default=None):
    for k in keys:
        if k in data and data[k] is not None:
            return data[k]
    return default


def _content_disposition(title: str, ext: str) -> str:
    """构建下载响应头，兼容中文书名（RFC 5987 filename* 编码 + ASCII 回退）。"""
    base = title or "book"
    encoded = quote(f"{base}.{ext}")
    return f"attachment; filename=\"book.{ext}\"; filename*=UTF-8''{encoded}"


# ---------------------------------------------------------------------------
# AI 配置解析：优先请求参数，回退到数据库中的激活配置
# ---------------------------------------------------------------------------
async def _active_model_config(db: AsyncSession) -> Optional[ModelConfig]:
    result = await db.execute(select(ModelConfig).where(ModelConfig.is_active.is_(True)))
    return result.scalars().first()


async def _resolve_ai(db: AsyncSession, data: dict) -> dict:
    """返回 {provider, api_key, model, api_base}。

    解析优先级：
    1. 请求体（provider / model / apiKey / apiBase）
    2. 数据库中的激活 ModelConfig（apiKey 加密存储）
    3. 环境变量 / .env（DEEPSEEK_API_KEY、OPENAI_API_KEY、ANTHROPIC_API_KEY 等）
    """
    provider = _pick(data, "provider") or settings.default_provider
    model = _pick(data, "model") or settings.default_model
    api_key = _pick(data, "api_key", "apiKey") or ""
    api_base = _pick(data, "api_base", "apiBase") or None

    if not api_key:
        cfg = await _active_model_config(db)
        if cfg:
            provider = provider or cfg.provider
            model = model or cfg.model_name
            api_base = api_base or cfg.api_base
            api_key = decrypt(cfg.encrypted_api_key)

    # 环境变量兜底（便于桌面应用免登录 / 服务端部署）
    if not api_key:
        env_map = {
            "deepseek": ("deepseek_api_key", "deepseek_base_url"),
            "openai": ("openai_api_key", "openai_base_url"),
            "anthropic": ("anthropic_api_key", "anthropic_base_url"),
        }
        key_attr, base_attr = env_map.get(provider, ("", ""))
        if key_attr:
            api_key = getattr(settings, key_attr, "") or ""
        if not api_base and base_attr:
            api_base = getattr(settings, base_attr, "") or None

    # 前端 localStorage 中的 key 只含 provider/model/apiKey，不含 apiBase。
    # 按 provider 名补默认 Base URL，避免 OpenAI 兼容供应商连错地址
    # （尤其 DeepSeek / Ollama 必须显式指定 base_url）。
    if not api_base:
        default_bases = {
            "deepseek": settings.deepseek_base_url,
            "openai": settings.openai_base_url,
            "anthropic": settings.anthropic_base_url,
        }
        api_base = default_bases.get(provider) or None

    return {"provider": provider, "model": model, "api_key": api_key, "api_base": api_base}


def _get_engine(provider: str, api_key: str, model: str, api_base: str | None) -> NovelGenerationEngine:
    # 缓存键必须包含 API Key 哈希：同一 provider/model 但不同 key（多账号切换）
    # 不能复用同一个 engine/provider 实例，否则会串号使用旧 key。
    key_hash = hashlib.sha256((api_key or "").encode("utf-8")).hexdigest()[:8]
    key = f"{provider}:{model}:{api_base or ''}:{key_hash}"
    if key not in _engines:
        p = ProviderFactory.create(provider=provider, api_key=api_key, model=model, api_base=api_base)
        _engines[key] = NovelGenerationEngine(provider=p)
    return _engines[key]


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Books
# ---------------------------------------------------------------------------
@app.get("/api/v1/books")
async def list_books(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Book).order_by(Book.updated_at.desc()))
    return [_book_to_dict(b) for b in result.scalars().all()]


@app.post("/api/v1/books")
async def create_book(data: dict, db: AsyncSession = Depends(get_db)):
    book = Book(
        title=_pick(data, "title", default="未命名书籍"),
        concept=_pick(data, "concept", default=""),
        genre=_pick(data, "genre", default="玄幻"),
        description=_pick(data, "description"),
        author=_pick(data, "author"),
        tags=_pick(data, "tags"),
        cover_image=_pick(data, "coverImage", "cover_image"),
        total_chapters=_pick(data, "chapterCount", "total_chapters", default=0),
        total_words=_pick(data, "totalWords", "total_words", default=0),
        target_words=_pick(data, "targetWords", "target_words", default=500000),
        chapter_word_count=_pick(data, "chapterWordCount", "chapter_word_count", default=3500),
        platform=_pick(data, "platform", default="other"),
        language=_pick(data, "language", default="zh"),
        fanfic_mode=_pick(data, "fanficMode", "fanfic_mode"),
        status=_pick(data, "status", default="draft"),
        pipeline_progress=_pick(data, "lastStep", "pipeline_progress", default=0),
    )
    db.add(book)
    await db.flush()
    return _book_to_dict(book)


@app.get("/api/v1/books/{book_id}")
async def get_book(book_id: str, db: AsyncSession = Depends(get_db)):
    book = await db.get(Book, book_id)
    if not book:
        raise HTTPException(404, "书籍不存在")
    return _book_to_dict(book)


@app.put("/api/v1/books/{book_id}")
async def update_book(book_id: str, data: dict, db: AsyncSession = Depends(get_db)):
    book = await db.get(Book, book_id)
    if not book:
        raise HTTPException(404, "书籍不存在")
    mapping = {
        "title": "title", "concept": "concept", "genre": "genre",
        "description": "description", "author": "author", "tags": "tags",
        "coverImage": "cover_image", "cover_image": "cover_image",
        "chapterCount": "total_chapters", "total_chapters": "total_chapters",
        "totalWords": "total_words", "total_words": "total_words",
        "targetWords": "target_words", "target_words": "target_words",
        "chapterWordCount": "chapter_word_count", "chapter_word_count": "chapter_word_count",
        "platform": "platform", "language": "language",
        "fanficMode": "fanfic_mode", "fanfic_mode": "fanfic_mode", "status": "status",
    }
    for k, v in data.items():
        if k in mapping and k != "id":
            setattr(book, mapping[k], v)
    await db.flush()
    return _book_to_dict(book)


@app.delete("/api/v1/books/{book_id}")
async def delete_book(book_id: str, db: AsyncSession = Depends(get_db)):
    book = await db.get(Book, book_id)
    if not book:
        raise HTTPException(404, "书籍不存在")
    await db.delete(book)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Chapters
# ---------------------------------------------------------------------------
@app.get("/api/v1/books/{book_id}/chapters")
async def list_chapters(book_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Chapter).where(Chapter.book_id == book_id).order_by(Chapter.sort_order)
    )
    return [_chapter_to_dict(c) for c in result.scalars().all()]


@app.post("/api/v1/books/{book_id}/chapters")
async def create_chapter(book_id: str, data: dict, db: AsyncSession = Depends(get_db)):
    if not await db.get(Book, book_id):
        raise HTTPException(404, "书籍不存在")
    content = _pick(data, "content")
    chapter = Chapter(
        book_id=book_id,
        chapter_number=_pick(data, "number", "chapter_number", default=1),
        title=_pick(data, "title", default=""),
        content=content,
        summary=_pick(data, "summary"),
        # 未显式传入 wordCount 时，自动按正文长度统计（避免保存后字数为 0）
        word_count=_pick(data, "wordCount", "word_count", default=len(content) if content else 0),
        status=_pick(data, "status", default="draft"),
        source=_pick(data, "source", default="ai"),
        has_hook=1 if _pick(data, "hasHook", "has_hook", default=False) else 0,
        hook_type=_pick(data, "hookType", "hook_type"),
        sort_order=_pick(data, "sortOrder", "sort_order", default=0),
    )
    db.add(chapter)
    await db.flush()
    return _chapter_to_dict(chapter)


@app.get("/api/v1/books/{book_id}/chapters/{chapter_id}")
async def get_chapter(book_id: str, chapter_id: str, db: AsyncSession = Depends(get_db)):
    chapter = await db.get(Chapter, chapter_id)
    if not chapter or chapter.book_id != book_id:
        raise HTTPException(404, "章节不存在")
    return _chapter_to_dict(chapter)


@app.put("/api/v1/books/{book_id}/chapters/{chapter_id}")
async def update_chapter(book_id: str, chapter_id: str, data: dict, db: AsyncSession = Depends(get_db)):
    chapter = await db.get(Chapter, chapter_id)
    if not chapter or chapter.book_id != book_id:
        raise HTTPException(404, "章节不存在")
    mapping = {
        "number": "chapter_number", "chapter_number": "chapter_number",
        "title": "title", "content": "content", "summary": "summary",
        "wordCount": "word_count", "word_count": "word_count",
        "status": "status", "source": "source",
        "hookType": "hook_type", "hook_type": "hook_type",
        "sortOrder": "sort_order", "sort_order": "sort_order",
    }
    for k, v in data.items():
        if k in mapping:
            setattr(chapter, mapping[k], v)
        elif k in ("hasHook", "has_hook"):
            setattr(chapter, "has_hook", 1 if v else 0)
    # 更新正文但未显式更新字数时，自动重算
    if ("content" in data and "wordCount" not in data and "word_count" not in data
            and chapter.content is not None):
        chapter.word_count = len(chapter.content)
    await db.flush()
    return _chapter_to_dict(chapter)


@app.delete("/api/v1/books/{book_id}/chapters/{chapter_id}")
async def delete_chapter(book_id: str, chapter_id: str, db: AsyncSession = Depends(get_db)):
    chapter = await db.get(Chapter, chapter_id)
    if not chapter or chapter.book_id != book_id:
        raise HTTPException(404, "章节不存在")
    await db.delete(chapter)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Characters / WorldSettings / Items / Outlines / Hooks（完整 CRUD）
# ---------------------------------------------------------------------------
@app.get("/api/v1/books/{book_id}/characters")
async def list_characters(book_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Character).where(Character.book_id == book_id).order_by(Character.sort_order)
    )
    return [_character_to_dict(c) for c in result.scalars().all()]


@app.post("/api/v1/books/{book_id}/characters")
async def create_character(book_id: str, data: dict, db: AsyncSession = Depends(get_db)):
    if not await db.get(Book, book_id):
        raise HTTPException(404, "书籍不存在")
    char = Character(
        book_id=book_id,
        name=_pick(data, "name", default=""),
        role=_pick(data, "role", default="配角"),
        role_type=_pick(data, "roleType", "role_type", default="supporting"),
        description=_pick(data, "description"),
        background=_pick(data, "background"),
        notes=_pick(data, "notes"),
        personality=_pick(data, "personality"),
        speech_style=_pick(data, "speechStyle", "speech_style"),
        motivation=_pick(data, "motivation"),
        flaws=_pick(data, "flaws"),
        arc=_pick(data, "arc"),
        appearance=_pick(data, "appearance"),
        abilities=_pick(data, "abilities"),
        relationships=_pick(data, "relationships"),
        sort_order=_pick(data, "sortOrder", "sort_order", default=0),
    )
    db.add(char)
    await db.flush()
    return _character_to_dict(char)


@app.get("/api/v1/books/{book_id}/characters/{character_id}")
async def get_character(book_id: str, character_id: str, db: AsyncSession = Depends(get_db)):
    char = await db.get(Character, character_id)
    if not char or char.book_id != book_id:
        raise HTTPException(404, "角色不存在")
    return _character_to_dict(char)


@app.put("/api/v1/books/{book_id}/characters/{character_id}")
async def update_character(book_id: str, character_id: str, data: dict, db: AsyncSession = Depends(get_db)):
    char = await db.get(Character, character_id)
    if not char or char.book_id != book_id:
        raise HTTPException(404, "角色不存在")
    mapping = {
        "name": "name", "role": "role", "role_type": "role_type", "roleType": "role_type",
        "description": "description", "background": "background", "notes": "notes",
        "personality": "personality", "speech_style": "speech_style", "speechStyle": "speech_style",
        "motivation": "motivation", "flaws": "flaws", "arc": "arc",
        "appearance": "appearance", "abilities": "abilities", "relationships": "relationships",
        "current_location": "current_location", "currentLocation": "current_location",
        "known_info": "known_info", "knownInfo": "known_info",
        "state_snapshot": "state_snapshot", "stateSnapshot": "state_snapshot",
        "sort_order": "sort_order", "sortOrder": "sort_order",
    }
    for k, v in data.items():
        if k in mapping:
            setattr(char, mapping[k], v)
    await db.flush()
    return _character_to_dict(char)


@app.delete("/api/v1/books/{book_id}/characters/{character_id}")
async def delete_character(book_id: str, character_id: str, db: AsyncSession = Depends(get_db)):
    char = await db.get(Character, character_id)
    if not char or char.book_id != book_id:
        raise HTTPException(404, "角色不存在")
    await db.delete(char)
    return {"ok": True}


@app.get("/api/v1/books/{book_id}/world-settings")
async def list_world_settings(book_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(WorldSetting).where(WorldSetting.book_id == book_id).order_by(WorldSetting.sort_order)
    )
    return [_world_setting_to_dict(w) for w in result.scalars().all()]


@app.post("/api/v1/books/{book_id}/world-settings")
async def create_world_setting(book_id: str, data: dict, db: AsyncSession = Depends(get_db)):
    if not await db.get(Book, book_id):
        raise HTTPException(404, "书籍不存在")
    ws = WorldSetting(
        book_id=book_id,
        category=_pick(data, "category", default=""),
        name=_pick(data, "name", default=""),
        description=_pick(data, "description"),
        content=_pick(data, "content", default=""),
        rules=_pick(data, "rules"),
        parent_id=_pick(data, "parentId", "parent_id"),
        sort_order=_pick(data, "sortOrder", "sort_order", default=0),
    )
    db.add(ws)
    await db.flush()
    return _world_setting_to_dict(ws)


@app.get("/api/v1/books/{book_id}/world-settings/{setting_id}")
async def get_world_setting(book_id: str, setting_id: str, db: AsyncSession = Depends(get_db)):
    ws = await db.get(WorldSetting, setting_id)
    if not ws or ws.book_id != book_id:
        raise HTTPException(404, "设定不存在")
    return _world_setting_to_dict(ws)


@app.put("/api/v1/books/{book_id}/world-settings/{setting_id}")
async def update_world_setting(book_id: str, setting_id: str, data: dict, db: AsyncSession = Depends(get_db)):
    ws = await db.get(WorldSetting, setting_id)
    if not ws or ws.book_id != book_id:
        raise HTTPException(404, "设定不存在")
    mapping = {
        "category": "category", "name": "name", "description": "description",
        "content": "content", "rules": "rules",
        "parent_id": "parent_id", "parentId": "parent_id",
        "sort_order": "sort_order", "sortOrder": "sort_order",
    }
    for k, v in data.items():
        if k in mapping:
            setattr(ws, mapping[k], v)
    await db.flush()
    return _world_setting_to_dict(ws)


@app.delete("/api/v1/books/{book_id}/world-settings/{setting_id}")
async def delete_world_setting(book_id: str, setting_id: str, db: AsyncSession = Depends(get_db)):
    ws = await db.get(WorldSetting, setting_id)
    if not ws or ws.book_id != book_id:
        raise HTTPException(404, "设定不存在")
    await db.delete(ws)
    return {"ok": True}


@app.get("/api/v1/books/{book_id}/items")
async def list_items(book_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Item).where(Item.book_id == book_id).order_by(Item.sort_order)
    )
    return [_item_to_dict(i) for i in result.scalars().all()]


@app.post("/api/v1/books/{book_id}/items")
async def create_item(book_id: str, data: dict, db: AsyncSession = Depends(get_db)):
    if not await db.get(Book, book_id):
        raise HTTPException(404, "书籍不存在")
    item = Item(
        book_id=book_id,
        name=_pick(data, "name", default=""),
        item_type=_pick(data, "itemType", "item_type", default="other"),
        acquisition_cost=_pick(data, "acquisitionCost", "acquisition_cost"),
        usage_limit=_pick(data, "usageLimit", "usage_limit"),
        hidden_property=_pick(data, "hiddenProperty", "hidden_property"),
        conflict_potential=_pick(data, "conflictPotential", "conflict_potential"),
        description=_pick(data, "description"),
        quantity=_pick(data, "quantity", default=1),
        current_holder=_pick(data, "currentHolder", "current_holder"),
        first_use_chapter=_pick(data, "firstUseChapter", "first_use_chapter"),
        usage_count=_pick(data, "usageCount", "usage_count", default=0),
        sort_order=_pick(data, "sortOrder", "sort_order", default=0),
    )
    db.add(item)
    await db.flush()
    return _item_to_dict(item)


@app.get("/api/v1/books/{book_id}/items/{item_id}")
async def get_item(book_id: str, item_id: str, db: AsyncSession = Depends(get_db)):
    item = await db.get(Item, item_id)
    if not item or item.book_id != book_id:
        raise HTTPException(404, "物品不存在")
    return _item_to_dict(item)


@app.put("/api/v1/books/{book_id}/items/{item_id}")
async def update_item(book_id: str, item_id: str, data: dict, db: AsyncSession = Depends(get_db)):
    item = await db.get(Item, item_id)
    if not item or item.book_id != book_id:
        raise HTTPException(404, "物品不存在")
    mapping = {
        "name": "name", "item_type": "item_type", "itemType": "item_type",
        "acquisition_cost": "acquisition_cost", "acquisitionCost": "acquisition_cost",
        "usage_limit": "usage_limit", "usageLimit": "usage_limit",
        "hidden_property": "hidden_property", "hiddenProperty": "hidden_property",
        "conflict_potential": "conflict_potential", "conflictPotential": "conflict_potential",
        "description": "description", "quantity": "quantity",
        "current_holder": "current_holder", "currentHolder": "current_holder",
        "first_use_chapter": "first_use_chapter", "firstUseChapter": "first_use_chapter",
        "usage_count": "usage_count", "usageCount": "usage_count",
        "sort_order": "sort_order", "sortOrder": "sort_order",
    }
    for k, v in data.items():
        if k in mapping:
            setattr(item, mapping[k], v)
    await db.flush()
    return _item_to_dict(item)


@app.delete("/api/v1/books/{book_id}/items/{item_id}")
async def delete_item(book_id: str, item_id: str, db: AsyncSession = Depends(get_db)):
    item = await db.get(Item, item_id)
    if not item or item.book_id != book_id:
        raise HTTPException(404, "物品不存在")
    await db.delete(item)
    return {"ok": True}


@app.get("/api/v1/books/{book_id}/outlines")
async def list_outlines(book_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Outline).where(Outline.book_id == book_id).order_by(Outline.sort_order)
    )
    return [_outline_to_dict(o) for o in result.scalars().all()]


@app.post("/api/v1/books/{book_id}/outlines")
async def create_outline(book_id: str, data: dict, db: AsyncSession = Depends(get_db)):
    if not await db.get(Book, book_id):
        raise HTTPException(404, "书籍不存在")
    outline = Outline(
        book_id=book_id,
        title=_pick(data, "title", default=""),
        type=_pick(data, "type", default="full"),
        step_name=_pick(data, "stepName", "step_name"),
        content=_pick(data, "content", default="{}"),
        status=_pick(data, "status", default="draft"),
        sort_order=_pick(data, "sortOrder", "sort_order", default=0),
    )
    db.add(outline)
    await db.flush()
    return _outline_to_dict(outline)


@app.put("/api/v1/books/{book_id}/outlines/{outline_id}")
async def update_outline(book_id: str, outline_id: str, data: dict, db: AsyncSession = Depends(get_db)):
    outline = await db.get(Outline, outline_id)
    if not outline or outline.book_id != book_id:
        raise HTTPException(404, "大纲不存在")
    mapping = {
        "title": "title", "type": "type", "step_name": "step_name", "stepName": "step_name",
        "content": "content", "status": "status",
        "sort_order": "sort_order", "sortOrder": "sort_order",
    }
    for k, v in data.items():
        if k in mapping:
            setattr(outline, mapping[k], v)
    await db.flush()
    return _outline_to_dict(outline)


@app.delete("/api/v1/books/{book_id}/outlines/{outline_id}")
async def delete_outline(book_id: str, outline_id: str, db: AsyncSession = Depends(get_db)):
    outline = await db.get(Outline, outline_id)
    if not outline or outline.book_id != book_id:
        raise HTTPException(404, "大纲不存在")
    await db.delete(outline)
    return {"ok": True}


@app.get("/api/v1/books/{book_id}/hooks")
async def list_hooks(book_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Hook).where(Hook.book_id == book_id))
    return [_hook_to_dict(h) for h in result.scalars().all()]


@app.post("/api/v1/books/{book_id}/hooks")
async def create_hook(book_id: str, data: dict, db: AsyncSession = Depends(get_db)):
    if not await db.get(Book, book_id):
        raise HTTPException(404, "书籍不存在")
    hook = Hook(
        book_id=book_id,
        hook_id=_pick(data, "hookId", "hook_id", default=""),
        type=_pick(data, "type"),
        description=_pick(data, "description", default=""),
        planted_chapter=_pick(data, "plantedChapter", "planted_chapter"),
        expected_reveal=_pick(data, "expectedReveal", "expected_reveal"),
        status=_pick(data, "status", default="pending"),
        resolution_text=_pick(data, "resolutionText", "resolution_text"),
    )
    if not hook.hook_id:
        raise HTTPException(400, "hook_id 不能为空")
    db.add(hook)
    await db.flush()
    return _hook_to_dict(hook)


@app.put("/api/v1/books/{book_id}/hooks/{hook_id}")
async def update_hook(book_id: str, hook_id: str, data: dict, db: AsyncSession = Depends(get_db)):
    hook = await db.get(Hook, hook_id)
    if not hook or hook.book_id != book_id:
        raise HTTPException(404, "伏笔不存在")
    mapping = {
        "type": "type", "description": "description",
        "planted_chapter": "planted_chapter", "plantedChapter": "planted_chapter",
        "expected_reveal": "expected_reveal", "expectedReveal": "expected_reveal",
        "status": "status", "resolution_text": "resolution_text", "resolutionText": "resolution_text",
    }
    for k, v in data.items():
        if k in mapping:
            setattr(hook, mapping[k], v)
    await db.flush()
    return _hook_to_dict(hook)


@app.delete("/api/v1/books/{book_id}/hooks/{hook_id}")
async def delete_hook(book_id: str, hook_id: str, db: AsyncSession = Depends(get_db)):
    hook = await db.get(Hook, hook_id)
    if not hook or hook.book_id != book_id:
        raise HTTPException(404, "伏笔不存在")
    await db.delete(hook)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Model Configs（API Key 加密存储）
# ---------------------------------------------------------------------------
@app.get("/api/v1/model-configs")
async def list_model_configs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ModelConfig))
    out = []
    for c in result.scalars().all():
        out.append({
            "id": c.id,
            "provider": c.provider,
            "modelName": c.model_name,
            "apiBase": c.api_base,
            "isActive": c.is_active,
            "hasKey": bool(c.encrypted_api_key),
        })
    return out


@app.post("/api/v1/model-configs")
async def create_model_config(data: dict, db: AsyncSession = Depends(get_db)):
    key = _pick(data, "api_key", "apiKey", "encrypted_api_key", default="")
    config = ModelConfig(
        provider=_pick(data, "provider", default="deepseek"),
        model_name=_pick(data, "model_name", "modelName", "model", default="deepseek-chat"),
        api_base=_pick(data, "api_base", "apiBase"),
        encrypted_api_key=encrypt(key),
        is_active=_pick(data, "is_active", "isActive", default=False),
    )
    db.add(config)
    await db.flush()
    return {"id": config.id, "provider": config.provider}


@app.put("/api/v1/model-configs/{config_id}")
async def update_model_config(config_id: str, data: dict, db: AsyncSession = Depends(get_db)):
    config = await db.get(ModelConfig, config_id)
    if not config:
        raise HTTPException(404, "配置不存在")
    if _pick(data, "provider") is not None:
        config.provider = _pick(data, "provider")
    if _pick(data, "model_name", "modelName") is not None:
        config.model_name = _pick(data, "model_name", "modelName")
    if _pick(data, "api_base", "apiBase") is not None:
        config.api_base = _pick(data, "api_base", "apiBase")
    if _pick(data, "is_active", "isActive") is not None:
        config.is_active = bool(_pick(data, "is_active", "isActive"))
    key = _pick(data, "api_key", "apiKey")
    if key is not None and key != "":
        config.encrypted_api_key = encrypt(key)
    await db.flush()
    return {"id": config.id, "provider": config.provider}


@app.delete("/api/v1/model-configs/{config_id}")
async def delete_model_config(config_id: str, db: AsyncSession = Depends(get_db)):
    config = await db.get(ModelConfig, config_id)
    if not config:
        raise HTTPException(404, "配置不存在")
    await db.delete(config)
    return {"ok": True}


@app.post("/api/v1/test-connection")
async def test_connection(data: dict, db: AsyncSession = Depends(get_db)):
    cfg = await _resolve_ai(db, data)
    if not cfg["api_key"]:
        return {"success": False, "message": "缺少 API Key（请先在设置中配置 AI 或传入 api_key）"}
    try:
        p = ProviderFactory.create(**cfg)
        ok, msg = await p.validate_connection()
        await p.close()
        return {"success": ok, "message": msg}
    except Exception as e:
        return {"success": False, "message": str(e)}


# ---------------------------------------------------------------------------
# 九步流水线（SSE）
# ---------------------------------------------------------------------------
@app.post("/api/v1/books/{book_id}/pipeline/stream")
async def start_pipeline(book_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    book = await db.get(Book, book_id)
    if not book:
        raise HTTPException(404, "书籍不存在")

    body = {}
    try:
        body = await request.json() or {}
    except Exception:
        pass

    # 前端：title/concept/word_count 走 query，mode 走 body
    q = request.query_params
    title = q.get("title") or book.title
    concept = q.get("concept") or book.concept or ""
    try:
        word_count = int(q.get("word_count") or 0)
    except ValueError:
        word_count = 0
    word_count = word_count or book.target_words or 500000
    mode = body.get("mode", "auto")

    cfg = await _resolve_ai(db, body)
    if not cfg["api_key"]:
        raise HTTPException(400, "缺少 API Key（请先配置 AI）")

    engine = _get_engine(cfg["provider"], cfg["api_key"], cfg["model"], cfg["api_base"])
    session = engine.create_session(book_id=book_id, title=title, concept=concept,
                                    word_count=word_count, mode=mode)
    session.genre = book.genre or ""

    async def event_stream():
        cancelled = False
        try:
            async for event in engine.stream_pipeline(session):
                if await request.is_disconnected():
                    cancelled = True
                    break
                yield _sse(event)
            # 客户端断开连接时不应落库（可能只生成了部分步骤）
            if cancelled:
                return
            await _persist_pipeline(book_id, session, cfg, db)
            if session.is_complete:
                book.pipeline_progress = 9
                await db.commit()
        except Exception as e:
            if not cancelled:
                yield _sse({"type": "error", "error": str(e)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/v1/books/{book_id}/generation/status")
async def get_generation_status(book_id: str):
    for engine in _engines.values():
        session = engine.get_session_by_book_id(book_id)
        if session:
            steps = {}
            for num, step in session.steps.items():
                steps[num] = {"name": step.name, "status": step.status.value, "error": step.error}
            return {"session_id": session.session_id, "is_complete": session.is_complete, "steps": steps}
    return {"session_id": None, "is_complete": False, "steps": {}}


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


async def _persist_pipeline(book_id: str, session, cfg: dict, db: AsyncSession):
    """把九步产出落库：world_settings 解析 + 各步骤 Outline 归档 + 生成记录。"""
    from app.engine.state import StepStatus

    step_names = {
        "world_setting": "世界观构建", "outline": "故事大纲", "power_system": "成长力量体系",
        "main_characters": "主要角色", "conflict_engine": "冲突引擎",
        "supporting_characters": "次要角色", "detailed_outline": "细纲规划",
        "items": "物品与道具", "memory_hooks": "悬念与伏笔",
    }
    sort = 0
    for num in sorted(session.results.keys()):
        r = session.results[num]
        if r.status != StepStatus.COMPLETED or not r.raw_output:
            continue
        key = session.steps[num].key
        text = r.raw_output.strip()
        sort += 1

        if key == "world_setting":
            for section_name, content in _split_sections(text):
                db.add(WorldSetting(book_id=book_id, category=section_name,
                                    name=section_name, content=content, sort_order=sort))
        elif key in ("main_characters", "supporting_characters"):
            for cname, cdesc in _split_sections(text):
                db.add(Character(book_id=book_id, name=cname, role="主角" if key == "main_characters" else "配角",
                                 role_type="protagonist" if key == "main_characters" else "supporting",
                                 description=cdesc, sort_order=sort))
        elif key == "items":
            for iname, idesc in _split_sections(text):
                db.add(Item(book_id=book_id, name=iname, item_type="other", description=idesc, sort_order=sort))

        # 所有步骤都归档为 Outline（保留原始产出，便于后续章节生成引用）
        db.add(Outline(book_id=book_id, title=step_names.get(key, key), type="pipeline",
                       step_name=key, content=json.dumps({"raw": text}, ensure_ascii=False),
                       status="completed", sort_order=sort))

        db.add(GenerationRecord(
            book_id=book_id, step_name=key, provider=cfg["provider"], model=cfg["model"],
            prompt_tokens=0, completion_tokens=len(text), success=True,
        ))

    await db.commit()


def _split_sections(text: str) -> list[tuple[str, str]]:
    """按 === 板块名 === 拆分为 (标题, 内容) 列表。"""
    lines = text.split("\n")
    sections: list[tuple[str, str]] = []
    current_title: Optional[str] = None
    buf: list[str] = []
    for line in lines:
        s = line.strip()
        if s.startswith("===") and s.endswith("===") and len(s) > 6:
            title = s.strip("=").strip() or "未命名"
            if current_title is not None or buf:
                sections.append((current_title or "未命名", "\n".join(buf).strip()))
            current_title = title
            buf = []
        else:
            buf.append(line)
    if current_title is not None or buf:
        sections.append((current_title or "未命名", "\n".join(buf).strip()))
    # 无分隔符时整体作为一段
    if not sections and text.strip():
        sections.append(("设定", text.strip()))
    return [(t, c) for t, c in sections if c.strip()]


# ---------------------------------------------------------------------------
# 章节批量生成（SSE）
# ---------------------------------------------------------------------------
@app.post("/api/v1/books/{book_id}/chapters/generate/stream")
async def generate_chapters(book_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    book = await db.get(Book, book_id)
    if not book:
        raise HTTPException(404, "书籍不存在")

    body = {}
    try:
        body = await request.json() or {}
    except Exception:
        pass
    count = int(_pick(body, "count", "chapterCount", default=0) or 0)
    count = count or int(request.query_params.get("count") or 1)
    count = max(1, min(count, 200))

    cfg = await _resolve_ai(db, body)
    if not cfg["api_key"]:
        raise HTTPException(400, "缺少 API Key（请先配置 AI）")

    engine = _get_engine(cfg["provider"], cfg["api_key"], cfg["model"], cfg["api_base"])
    provider = engine.provider

    # 现有章节
    result = await db.execute(
        select(Chapter).where(Chapter.book_id == book_id).order_by(Chapter.sort_order)
    )
    existing = result.scalars().all()
    next_number = max([c.chapter_number for c in existing], default=0) + 1

    context = await _build_chapter_context(book_id, db)

    async def event_stream():
        try:
            yield _sse({"type": "batch_start", "step": count})
            for i in range(count):
                if await request.is_disconnected():
                    return
                number = next_number + i
                # 前端依赖 chapter_start 重置当前章节的流式显示状态
                yield _sse({"type": "chapter_start", "step": number,
                            "token": f"第{number}章"})

                content_buf = ""
                async for token in provider.stream_generate(
                    CHAPTER_SYSTEM_PROMPT,
                    _build_chapter_prompt(book, context, number),
                    GenerationParams(temperature=0.85, max_tokens=6000, frequency_penalty=1.2),
                ):
                    if await request.is_disconnected():
                        return
                    content_buf += token
                    yield _sse({"type": "token", "token": token})

                if not content_buf.strip():
                    yield _sse({"type": "batch_error", "error": "AI 未返回内容"})
                    return

                title, body = _split_chapter_title(content_buf, number)
                if not body.strip():
                    body = content_buf
                chapter = Chapter(
                    book_id=book_id, chapter_number=number, title=title,
                    content=body, word_count=len(body),
                    status="draft", source="ai", has_hook=0, sort_order=number,
                )
                db.add(chapter)
                book.total_chapters = number
                book.total_words = (book.total_words or 0) + len(body)
                # 逐章提交：长批次生成时进程中断/断线也不丢失已完成章节
                await db.commit()

                yield _sse({"type": "chapter_complete", "step": number,
                            "result": body, "title": title})

            yield _sse({"type": "batch_complete", "step": count})
        except Exception as e:
            await db.rollback()
            yield _sse({"type": "batch_error", "error": str(e)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


async def _build_chapter_context(book_id: str, db: AsyncSession) -> dict:
    """汇总已有设定，作为章节生成的一致性上下文。"""
    worlds = (await db.execute(select(WorldSetting).where(WorldSetting.book_id == book_id))).scalars().all()
    chars = (await db.execute(select(Character).where(Character.book_id == book_id))).scalars().all()
    outlines = (await db.execute(select(Outline).where(Outline.book_id == book_id).order_by(Outline.sort_order))).scalars().all()
    return {
        "worlds": "\n".join(f"【{w.category}】{w.content[:400]}" for w in worlds[:10]),
        "characters": "\n".join(f"{c.name}（{c.role}）：{c.description or ''}" for c in chars[:20]),
        "outlines": "\n".join(_outline_text(o) for o in outlines if o.step_name in ("outline", "detailed_outline", "memory_hooks"))[:3000],
        "chapterCount": 0,
    }


def _outline_text(o: Outline) -> str:
    try:
        d = json.loads(o.content)
        return d.get("raw", o.content)[:1500]
    except Exception:
        return (o.content or "")[:1500]


def _split_chapter_title(text: str, number: int) -> tuple[str, str]:
    """从 AI 输出中剥离首行标题，返回 (标题, 正文)。

    AI 被要求以「# 标题」开头，但实际可能不遵守；需要稳健解析：
    - 首行若为 Markdown 标题（# 开头），去掉 # 及空白作为标题；
    - 无换行、或首行不像是标题时，回退为「第 N 章」并把全文当正文。
    """
    text = text.strip()
    if "\n" not in text:
        return f"第{number}章", text

    first_line, rest = text.split("\n", 1)
    stripped = first_line.strip()
    if stripped.startswith("#"):
        title = stripped.lstrip("#").strip() or f"第{number}章"
        return title, rest.strip()
    # 首行较短且不含正文标点时，也视作标题行（AI 常漏掉 #）
    if len(stripped) <= 30 and not any(p in stripped for p in "，。！？：；、…"):
        return stripped, rest.strip()

    return f"第{number}章", text


def _build_chapter_prompt(book: Book, context: dict, number: int) -> str:
    parts = [
        "【核心概念】",
        book.concept or "",
        "",
        f"【作品标题】{book.title or '未命名'}",
        f"【类型】{book.genre or '玄幻'}",
        f"【本章】第{number}章",
        "",
    ]
    genre_rules = genre_rules_text(book.genre or "")
    if genre_rules:
        parts += [genre_rules, ""]
    if context.get("worlds"):
        parts += ["【世界观设定】", context["worlds"]]
    if context.get("characters"):
        parts += ["【角色设定】", context["characters"]]
    if context.get("outlines"):
        parts += ["【大纲/细纲】", context["outlines"]]
    parts += [
        "",
        f"请写第{number}章正文。直接输出章节内容（含一个简短章节标题）。文末必须有钩子。",
        "输出第一行是章节标题（以 # 开头），之后是正文。",
    ]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Chapter Polish（章节润色）
# ---------------------------------------------------------------------------
@app.post("/api/v1/books/{book_id}/chapters/{chapter_id}/polish")
async def polish_chapter(book_id: str, chapter_id: str, request: Request,
                         db: AsyncSession = Depends(get_db)):
    """AI 润色章节正文，SSE 流式返回润色结果（不自动覆盖原稿，前端拿到后自行保存）。

    body 可选：{"style": "polish"|"concise"|"vivid"}
    """
    chapter = await db.get(Chapter, chapter_id)
    if not chapter or chapter.book_id != book_id:
        raise HTTPException(404, "章节不存在")
    content = chapter.content or ""
    if not content.strip():
        raise HTTPException(400, "章节为空，无法润色")

    body = {}
    try:
        body = await request.json() or {}
    except Exception:
        pass

    cfg = await _resolve_ai(db, body)
    if not cfg["api_key"]:
        raise HTTPException(400, "缺少 API Key（请先配置 AI）")

    engine = _get_engine(cfg["provider"], cfg["api_key"], cfg["model"], cfg["api_base"])
    provider = engine.provider

    style = _pick(body, "style", default="polish")
    style_hint = {
        "concise": "在保留信息量与节奏的前提下，删掉一切冗余和重复，让句子更短更利落。",
        "vivid": "增补具体感官细节（视觉/听觉/触觉），让场景更鲜活可感，但不堆砌形容词。",
        "polish": "",
    }.get(style, "")

    user_prompt = "\n\n".join(filter(None, [
        f"【作品标题】{book.title or '未命名'}",
        f"【类型】{book.genre or '玄幻'}",
        f"【本章】第{chapter.chapter_number}章{(' ' + chapter.title) if chapter.title else ''}",
        "【原稿】\n" + content,
        style_hint,
        "直接输出润色后的完整章节。第一行保留章节标题（以 # 开头），之后是润色后的正文。",
    ]))

    async def event_stream():
        try:
            yield _sse({"type": "polish_start", "step": chapter.chapter_number})
            buf = ""
            async for token in provider.stream_generate(
                CHAPTER_POLISH_PROMPT,
                user_prompt,
                GenerationParams(temperature=0.8, max_tokens=8000, frequency_penalty=0.6),
            ):
                if await request.is_disconnected():
                    return
                buf += token
                yield _sse({"type": "token", "token": token})
            if not buf.strip():
                yield _sse({"type": "polish_error", "error": "AI 未返回内容"})
                return
            yield _sse({"type": "polish_complete", "step": chapter.chapter_number,
                        "result": buf})
        except Exception as e:
            yield _sse({"type": "polish_error", "error": str(e)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Truth Files（真相文件）
# ---------------------------------------------------------------------------
@app.get("/api/v1/books/{book_id}/truth-files")
async def list_truth_files(book_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TruthFile).where(TruthFile.book_id == book_id))
    return [_truth_file_to_dict(t) for t in result.scalars().all()]


@app.get("/api/v1/books/{book_id}/truth-files/{file_name}")
async def get_truth_file(book_id: str, file_name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TruthFile).where(TruthFile.book_id == book_id, TruthFile.file_name == file_name)
    )
    t = result.scalars().first()
    if not t:
        raise HTTPException(404, "真相文件不存在")
    return _truth_file_to_dict(t)


@app.put("/api/v1/books/{book_id}/truth-files/{file_name}")
async def upsert_truth_file(book_id: str, file_name: str, data: dict, db: AsyncSession = Depends(get_db)):
    if not await db.get(Book, book_id):
        raise HTTPException(404, "书籍不存在")
    result = await db.execute(
        select(TruthFile).where(TruthFile.book_id == book_id, TruthFile.file_name == file_name)
    )
    t = result.scalars().first()
    content = _pick(data, "content", default="")
    if not t:
        t = TruthFile(book_id=book_id, file_name=file_name, content=content)
        db.add(t)
    else:
        t.content = content
    await db.flush()
    return _truth_file_to_dict(t)


@app.delete("/api/v1/books/{book_id}/truth-files/{file_name}")
async def delete_truth_file(book_id: str, file_name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TruthFile).where(TruthFile.book_id == book_id, TruthFile.file_name == file_name)
    )
    t = result.scalars().first()
    if not t:
        raise HTTPException(404, "真相文件不存在")
    await db.delete(t)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Token 用量统计（generation_records 聚合）
# ---------------------------------------------------------------------------
@app.get("/api/v1/books/{book_id}/token-stats")
async def token_stats(book_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GenerationRecord).where(GenerationRecord.book_id == book_id))
    records = result.scalars().all()
    total_prompt = sum(r.prompt_tokens or 0 for r in records)
    total_completion = sum(r.completion_tokens or 0 for r in records)
    success = sum(1 for r in records if r.success)
    return {
        "calls": len(records),
        "success": success,
        "failed": len(records) - success,
        "totalPromptTokens": total_prompt,
        "totalCompletionTokens": total_completion,
        "totalTokens": total_prompt + total_completion,
        "totalCost": round(sum(r.cost or 0 for r in records), 6),
    }


# ---------------------------------------------------------------------------
# 审核统计
# ---------------------------------------------------------------------------
@app.get("/api/v1/books/{book_id}/audit/stats")
async def audit_stats(book_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AuditLog).where(AuditLog.book_id == book_id))
    stats: dict[str, int] = {}
    for a in result.scalars().all():
        key = a.dimension or "0"
        stats[key] = stats.get(key, 0) + 1
    # 兼容前端以数字索引渲染
    out: dict[str, int] = {}
    for k, v in stats.items():
        out[k] = v
    return out


# ---------------------------------------------------------------------------
# 导出
# ---------------------------------------------------------------------------
@app.get("/api/v1/books/{book_id}/export")
async def export_book(book_id: str, format: str = "txt", db: AsyncSession = Depends(get_db)):
    book = await db.get(Book, book_id)
    if not book:
        raise HTTPException(404, "书籍不存在")
    result = await db.execute(
        select(Chapter).where(Chapter.book_id == book_id).order_by(Chapter.sort_order)
    )
    chapters = result.scalars().all()

    if format in ("txt", "md"):
        lines = [f"{book.title or '未命名'}\n"]
        for c in chapters:
            lines.append(f"\n\n第{c.chapter_number}章 {c.title or ''}\n")
            lines.append(c.content or "")
        content = "".join(lines)
        return StreamingResponse(
            iter([content]), media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": _content_disposition(book.title, "txt")},
        )

    if format == "json":
        payload = {
            "title": book.title, "concept": book.concept, "genre": book.genre,
            "chapters": [_chapter_to_dict(c) for c in chapters],
        }
        return StreamingResponse(
            iter([json.dumps(payload, ensure_ascii=False, indent=2)]),
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": _content_disposition(book.title, "json")},
        )

    raise HTTPException(400, "不支持的导出格式")


# ---------------------------------------------------------------------------
# SPA 回退
# ---------------------------------------------------------------------------
@app.get("/{path:path}")
async def serve_spa(path: str):
    # 未知的 /api/ 路径应返回 404，而不是回退到 index.html（避免前端误判为 200）
    if path == "api" or path.startswith("api/"):
        raise HTTPException(404, "接口不存在")
    file_path = (STATIC_DIR / path).resolve()
    if not str(file_path).startswith(str(STATIC_DIR.resolve())):
        raise HTTPException(404, "路径非法")
    if path and file_path.is_file():
        return FileResponse(file_path)
    return FileResponse(STATIC_DIR / "index.html")