"""题材模板加载器。

读取 app/prompts/genres/*.md，解析 YAML frontmatter 与正文规则，
将题材专属创作铁律注入生成提示词，提升网文类型匹配度。
"""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

import yaml


def _genres_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "app" / "prompts" / "genres"
    return Path(__file__).parent / "genres"


# 前端下拉框的中文题材名（及常见口语化说法）→ 文件名 id。
# 不存在对应模板的题材（如 历史/轻小说）不在此映射，返回空串优雅回退。
_ALIASES = {
    "玄幻": "xuanhuan",
    "仙侠": "xianxia",
    "修仙": "cultivation",
    "都市": "urban",
    "科幻": "sci-fi",
    "恐怖": "horror",
    "游戏": "litrpg",
    "游戏文学": "litrpg",
    "异世界": "isekai",
    "穿越": "isekai",
    "末世": "system-apocalypse",
    "爬塔": "tower-climber",
    "升级流": "progression",
    "治愈": "cozy",
    "言情": "romantasy",
    "地下城": "dungeon-core",
}


def _parse(path: Path) -> tuple[dict, str] | None:
    """解析 —— YAML frontmatter 被两段 --- 包裹，其后为正文规则。"""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, text[len(parts[0]) + 3:]
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        meta = {}
    return meta, parts[2].strip()


@lru_cache(maxsize=None)
def _find_file(slug: str) -> Path | None:
    path = _genres_dir() / f"{slug}.md"
    if path.exists():
        return path
    # 按 frontmatter 的 name / id 二次匹配
    for f in _genres_dir().glob("*.md"):
        try:
            meta, _ = _parse(f)
        except Exception:
            continue
        if (meta or {}).get("name") == slug or (meta or {}).get("id") == slug:
            return f
    return None


def genre_rules_text(genre: str) -> str:
    """返回题材专属规则文本；无匹配时返回空串。"""
    g = (genre or "").strip()
    if not g:
        return ""

    slug = _ALIASES.get(g, g)
    path = _find_file(slug)
    if path is None:
        return ""

    parsed = _parse(path)
    if parsed is None:
        return ""
    meta, body = parsed

    name = meta.get("name") or g
    lines = [f"【题材专属创作铁律 · {name}】"]

    fatigue = meta.get("fatigueWords")
    if isinstance(fatigue, list) and fatigue:
        lines.append("禁用疲劳词：" + "、".join(str(w) for w in fatigue))

    pacing = meta.get("pacingRule")
    if pacing:
        lines.append(f"节奏规则：{pacing}")

    satisfaction = meta.get("satisfactionTypes")
    if isinstance(satisfaction, list) and satisfaction:
        lines.append("爽点类型：" + "、".join(str(s) for s in satisfaction))

    if body:
        lines.append(body)

    return "\n".join(lines)