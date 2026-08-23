"""流水线状态管理 — 九步骨架流水线"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from enum import Enum
import time


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PipelineStep:
    key: str
    number: int
    name: str
    description: str
    is_critical: bool
    estimated_time: str

    # 运行时状态（由引擎在流水线执行过程中更新）
    status: StepStatus = StepStatus.PENDING
    result_text: Optional[str] = None
    streamed_text: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


@dataclass
class StepResult:
    step_number: int
    status: StepStatus
    raw_output: Optional[str] = None
    parsed_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@dataclass
class GenerationSession:
    session_id: str
    book_id: str
    title: str
    concept: str
    word_count: int
    mode: str = "auto"
    genre: str = ""
    steps: Dict[int, PipelineStep] = field(default_factory=dict)
    results: Dict[int, StepResult] = field(default_factory=dict)
    context_log: Dict[int, str] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    is_complete: bool = False

    @classmethod
    def create(cls, session_id: str, book_id: str, title: str, concept: str,
               word_count: int, mode: str = "auto") -> "GenerationSession":
        session = cls(
            session_id=session_id,
            book_id=book_id,
            title=title,
            concept=concept,
            word_count=word_count,
            mode=mode,
        )
        session._init_steps()
        return session

    def _init_steps(self):
        # 顺序必须与编译后前端 static/assets/index-*.js 中的 pn 数组严格一致，
        # 前端以 step 号（1 起）定位步骤卡片，错位会导致 UI 步骤名与进度错乱。
        steps_def = [
            (1, "world_setting", "世界观构建", "物理法则、时代背景、地理、政治、人文", True, "~45s"),
            (2, "outline", "故事大纲", "核心冲突、分卷结构、高潮节点", True, "~60s"),
            (3, "power_system", "成长力量体系", "等级、技能树、修炼逻辑、金手指", False, "~35s"),
            (4, "main_characters", "主要角色", "主角/反派/核心同伴的深层设定", True, "~60s"),
            (5, "conflict_engine", "冲突引擎", "八大矛盾类型组合、升级路径", False, "~40s"),
            (6, "supporting_characters", "次要角色", "配角、路人、功能角色（全书≥20人）", False, "~55s"),
            (7, "detailed_outline", "细纲规划", "卷/章级详细情节（10-60章）", True, "~90s"),
            (8, "items", "物品与道具", "神器、消耗品、伏笔物品（全书≥5件）", False, "~30s"),
            (9, "memory_hooks", "悬念与伏笔", "15+伏笔清单、回收计划", False, "~45s"),
        ]
        for num, key, name, desc, critical, est in steps_def:
            self.steps[num] = PipelineStep(
                key=key, number=num, name=name, description=desc,
                is_critical=critical, estimated_time=est,
            )

    def get_previous_context(self, up_to_step: int) -> str:
        """构建前序上下文（模拟 get_step_context）"""
        parts = []
        for i in range(1, up_to_step):
            if i in self.results and self.results[i].raw_output:
                parts.append(self.results[i].raw_output)
        return "\n\n".join(parts)

    def touch(self):
        self.last_accessed = time.time()


# ---------------------------------------------------------------------------
# 九步骨架流水线静态定义（供 orchestrator 与 API 层共用）
# ---------------------------------------------------------------------------
PIPELINE_STEPS_DEF = [
    {"key": "world_setting", "number": 1, "name": "世界观构建",
     "description": "物理法则、时代背景、地理、政治、人文",
     "is_critical": True, "estimated_time": "~45s"},
    {"key": "outline", "number": 2, "name": "故事大纲",
     "description": "核心冲突、分卷结构、高潮节点",
     "is_critical": True, "estimated_time": "~60s"},
    {"key": "power_system", "number": 3, "name": "成长力量体系",
     "description": "等级、技能树、修炼逻辑、金手指",
     "is_critical": False, "estimated_time": "~35s"},
    {"key": "main_characters", "number": 4, "name": "主要角色",
     "description": "主角/反派/核心同伴的深层设定",
     "is_critical": True, "estimated_time": "~60s"},
    {"key": "conflict_engine", "number": 5, "name": "冲突引擎",
     "description": "八大矛盾类型组合、升级路径",
     "is_critical": False, "estimated_time": "~40s"},
    {"key": "supporting_characters", "number": 6, "name": "次要角色",
     "description": "配角、路人、功能角色（全书≥20人）",
     "is_critical": False, "estimated_time": "~55s"},
    {"key": "detailed_outline", "number": 7, "name": "细纲规划",
     "description": "卷/章级详细情节（10-60章）",
     "is_critical": True, "estimated_time": "~90s"},
    {"key": "items", "number": 8, "name": "物品与道具",
     "description": "神器、消耗品、伏笔物品（全书≥5件）",
     "is_critical": False, "estimated_time": "~30s"},
    {"key": "memory_hooks", "number": 9, "name": "悬念与伏笔",
     "description": "15+伏笔清单、回收计划",
     "is_critical": False, "estimated_time": "~45s"},
]
