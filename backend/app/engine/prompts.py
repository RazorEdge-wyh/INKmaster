# -*- coding: utf-8 -*-
"""
Prompt system v4 -- Chinese prompts, concept-centered, step-specific user prompts.
All Chinese text in prompts_data.json. This file is pure logic.
"""

import json
import os
import sys
import re
from typing import Optional

# 定位 prompts_data.json（开发环境使用源码目录，
# PyInstaller 打包后使用 sys._MEIPASS 解压目录）
if getattr(sys, "frozen", False):
    # 打包环境：资源解压在 sys._MEIPASS 下
    _base_path = sys._MEIPASS
    _json_path = os.path.join(_base_path, "app", "engine", "prompts_data.json")
else:
    # 开发环境：JSON 与本模块同目录
    _json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts_data.json")

try:
    with open(_json_path, "r", encoding="utf-8-sig") as f:
        PD = json.load(f)
except (FileNotFoundError, json.JSONDecodeError) as e:
    raise RuntimeError(f"Failed to load prompts_data.json: {e}. "
                       f"Ensure the file exists at {_json_path} and is valid JSON.") from e


PERSONA = PD["PERSONA"]
RULES = PD["RULES"]
FORMAT = PD["FORMAT"]
STEP_WORLD = PD["STEP_WORLD"]
STEP_POWER = PD["STEP_POWER"]
STEP_OUTLINE = PD["STEP_OUTLINE"]
STEP_CHARACTERS = PD["STEP_CHARACTERS"]
STEP_CONFLICT = PD["STEP_CONFLICT"]
STEP_SUPPORT = PD["STEP_SUPPORT"]
STEP_DETAIL = PD["STEP_DETAIL"]
STEP_ITEMS = PD["STEP_ITEMS"]
STEP_MEMORY_HOOKS = PD["STEP_MEMORY_HOOKS"]
CHAPTER_PROMPT = PD["CHAPTER_PROMPT"]
POLISH_PROMPT = PD["POLISH_PROMPT"]


def _join(*parts: str) -> str:
    return "\n\n".join(p for p in parts if p)


STEP_SYSTEM_PROMPTS = {
    "world_setting": _join(PERSONA, RULES, FORMAT, STEP_WORLD),
    "power_system": _join(PERSONA, RULES, FORMAT, STEP_POWER),
    "outline": _join(PERSONA, RULES, FORMAT, STEP_OUTLINE),
    "main_characters": _join(PERSONA, RULES, FORMAT, STEP_CHARACTERS),
    "conflict_engine": _join(PERSONA, RULES, FORMAT, STEP_CONFLICT),
    "supporting_characters": _join(PERSONA, RULES, FORMAT, STEP_SUPPORT),
    "detailed_outline": _join(PERSONA, RULES, FORMAT, STEP_DETAIL),
    "items": _join(PERSONA, RULES, FORMAT, STEP_ITEMS),
    "memory_hooks": _join(PERSONA, RULES, FORMAT, STEP_MEMORY_HOOKS),
}

STEP_PARAMS = {
    "world_setting": {"temperature": 0.8, "max_tokens": 5000, "frequency_penalty": 1.0},
    "power_system": {"temperature": 0.6, "max_tokens": 5000, "frequency_penalty": 1.0},
    "outline": {"temperature": 0.7, "max_tokens": 6000, "frequency_penalty": 0.8},
    "main_characters": {"temperature": 0.85, "max_tokens": 6000, "frequency_penalty": 1.2},
    "conflict_engine": {"temperature": 0.8, "max_tokens": 5000, "frequency_penalty": 1.0},
    "supporting_characters": {"temperature": 0.85, "max_tokens": 5000, "frequency_penalty": 1.2},
    "detailed_outline": {"temperature": 0.6, "max_tokens": 8000, "frequency_penalty": 0.8},
    "items": {"temperature": 0.8, "max_tokens": 5000, "frequency_penalty": 1.0},
    "memory_hooks": {"temperature": 0.7, "max_tokens": 5000, "frequency_penalty": 0.8},
    "chapter": {"temperature": 0.85, "max_tokens": 6000, "frequency_penalty": 1.2},
    "chapter_polish": {"temperature": 0.7, "max_tokens": 6000, "frequency_penalty": 0.5},
}


def build_step_user_prompt(
    step_name: str,
    step_description: str,
    user_concept: str,
    title: str,
    word_count: int,
    previous_context: Optional[str] = None,
    genre_hint: str = "",
    chapter_context: Optional[str] = None,
) -> str:
    """Build step-specific user prompt with concept as the centerpiece."""
    total_chapters = max(1, word_count // 3500)

    parts = [
        "【核心概念 —— 你所有创作必须围绕这个展开，不得偏离】",
        f"「{user_concept}」",
        "",
        f"【作品标题】{title or '未命名'}",
        f"【目标字数】{word_count:,} 字（约 {total_chapters} 章）",
    ]

    if genre_hint:
        parts.append(f"【类型标签】{genre_hint}")

    # 章节上下文（单步生成模式时传入）
    if chapter_context:
        parts.append("")
        parts.append(chapter_context)

    # 前序步骤的产出摘要（保证设定一致性）
    if previous_context:
        summary = _extract_summary(previous_context)
        parts.append("")
        parts.append("【已生成的设定 —— 必须基于以下内容继续，保持一致性】")
        parts.append(summary)

    # 当前任务说明
    parts.append("")
    parts.append(f"【当前任务】{step_name} —— {step_description}")
    parts.append("请基于【核心概念】完成这一步创作。每一个设定都必须能从概念中找到根源。")
    if chapter_context:
        parts.append("你可以在本章中适度增加新的人物、伏笔、道具。增加后系统会记住它们，后续章节会继续使用。")
    parts.append("")

    return "\n".join(parts)


def _extract_summary(full_context: str) -> str:
    """Extract meaningful summary from previous step output.
    Different from v3: preserves actual content sections, not just colons."""
    max_len = 5000
    lines = full_context.split("\n")
    sections = []
    current_section = []

    for line in lines:
        s = line.strip()
        if not s:
            continue
        if s.startswith("===") and s.endswith("==="):
            if current_section:
                sections.append(" ".join(current_section[:8]))
                current_section = []
            sections.append(f"[{s.replace('===', '').strip()}]")
        elif len(s) > 5:
            current_section.append(s)

    if current_section:
        sections.append(" ".join(current_section[:8]))

    result = "\n".join(sections)
    if len(result) > max_len:
        # 超出预算时逐行截断
        keep_lines = []
        total = 0
        for line in result.split("\n"):
            if total + len(line) > max_len:
                keep_lines.append("...[已压缩，保持 token 预算]")
                break
            keep_lines.append(line)
            total += len(line)
        result = "\n".join(keep_lines)

    return result if result.strip() else full_context[:max_len]


# 章节级系统提示词（正文生成与润色）
CHAPTER_SYSTEM_PROMPT = _join(PERSONA, RULES, CHAPTER_PROMPT)
CHAPTER_POLISH_PROMPT = _join(PERSONA, RULES, POLISH_PROMPT)
