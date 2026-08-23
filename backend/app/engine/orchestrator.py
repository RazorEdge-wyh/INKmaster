"""Pipeline orchestrator -- 9-step skeleton pipeline with SSE streaming."""
import time
import uuid
from typing import AsyncIterator, Optional, Dict, Callable

from .state import GenerationSession, StepStatus, StepResult, PIPELINE_STEPS_DEF
from .prompts import STEP_SYSTEM_PROMPTS, STEP_PARAMS, build_step_user_prompt
from ..ai.base import BaseProvider, GenerationParams
from ..prompts import genre_rules_text


class NovelGenerationEngine:
    def __init__(self, provider: BaseProvider):
        self.provider = provider
        self._sessions = {}
        self._book_index = {}
        self._on_step_complete = None

    def on_step_complete(self, callback: Callable):
        """Register a callback(session, step_num, result_text) after each step."""
        self._on_step_complete = callback

    def create_session(self, book_id: str, title: str, concept: str,
                       word_count: int, mode: str = "auto") -> GenerationSession:
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        session = GenerationSession.create(
            session_id=session_id, book_id=book_id, title=title,
            concept=concept, word_count=word_count, mode=mode)

        self._sessions[session_id] = session
        self._book_index[book_id] = session_id
        return session

    def get_session(self, session_id: str) -> Optional[GenerationSession]:
        s = self._sessions.get(session_id)
        if s: s.touch()
        return s

    def get_session_by_book_id(self, book_id: str) -> Optional[GenerationSession]:
        sid = self._book_index.get(book_id)
        if sid and sid in self._sessions:
            self._sessions[sid].touch()
            return self._sessions[sid]
        return None


    def _prepare_step(self, session: GenerationSession, step_num: int, step_key: str):
        step_def = next((s for s in PIPELINE_STEPS_DEF if s["number"] == step_num), None)
        name = step_def["name"] if step_def else step_key
        desc = step_def["description"] if step_def else ""

        # 测试模式：True 时跳过 AI 调用，直接返回固定内容（用于联调）
        TEST_MODE = False
        if TEST_MODE:
            system_prompt = "你是一个测试助手。"
            user_prompt = f"请直接返回以下内容，不要添加任何其他文字：\n\n【测试】第{step_num}步 {name} - 测试内容已生成。标题：{session.title}，简介：{session.concept[:30]}..."
            params = GenerationParams(temperature=0.1, max_tokens=200, frequency_penalty=0.0)
            return system_prompt, user_prompt, params

        system_prompt = STEP_SYSTEM_PROMPTS.get(step_key, "")
        genre_rules = genre_rules_text(session.genre)
        if genre_rules:
            system_prompt = system_prompt + "\n\n" + genre_rules
        previous_context = session.get_previous_context(step_num)
        user_prompt = build_step_user_prompt(
            step_name=name, step_description=desc,
            user_concept=session.concept, title=session.title,
            word_count=session.word_count,
            previous_context=previous_context if previous_context else None)

        sp = STEP_PARAMS.get(step_key, {})
        params = GenerationParams(
            temperature=sp.get("temperature", 0.7),
            max_tokens=sp.get("max_tokens", 4000),
            frequency_penalty=sp.get("frequency_penalty", 0.0))

        return system_prompt, user_prompt, params


    async def stream_pipeline(self, session: GenerationSession) -> AsyncIterator[dict]:
        yield {"type": "pipeline_start", "session_id": session.session_id}

        for step_def in PIPELINE_STEPS_DEF:
            step_num = step_def["number"]
            step_key = step_def["key"]
            step = session.steps[step_num]

            if step.status == StepStatus.COMPLETED:
                yield {"type": "step_skip", "step": step_num}
                continue

            step.status = StepStatus.RUNNING
            step.started_at = time.time()
            yield {"type": "step_start", "step": step_num,
                   "name": step_def["name"], "description": step_def["description"]}

            try:
                system_prompt, user_prompt, params = self._prepare_step(
                    session, step_num, step_key)

                full_text = ""
                async for token in self.provider.stream_generate(
                    system_prompt, user_prompt, params):
                    full_text += token
                    yield {"type": "token", "step": step_num, "token": token}

                step.status = StepStatus.COMPLETED
                step.result_text = full_text
                step.completed_at = time.time()
                session.results[step_num] = StepResult(
                    step_number=step_num, status=StepStatus.COMPLETED, raw_output=full_text)
                session.context_log[step_num] = full_text

                yield {"type": "step_complete", "step": step_num, "result": full_text}

                if self._on_step_complete:
                    self._on_step_complete(session, step_num, full_text)

            except Exception as e:
                error_msg = str(e)
                if step.is_critical:
                    step.status = StepStatus.FAILED
                    step.error = error_msg
                    session.results[step_num] = StepResult(
                        step_number=step_num, status=StepStatus.FAILED, error=error_msg)
                    yield {"type": "pipeline_error", "step": step_num, "error": error_msg}
                    return
                else:
                    step.status = StepStatus.SKIPPED
                    step.error = error_msg
                    yield {"type": "step_error", "step": step_num, "error": error_msg}
                    continue

        session.is_complete = True
        completed = sum(1 for r in session.results.values() if r.status == StepStatus.COMPLETED)
        yield {"type": "pipeline_complete", "completed_steps": completed, "total_steps": 9}


    async def execute_single_step(self, session: GenerationSession, step_num: int) -> StepResult:
        step_def = next((s for s in PIPELINE_STEPS_DEF if s["number"] == step_num), None)
        if not step_def:
            raise ValueError(f"Invalid step number: {step_num}")

        system_prompt, user_prompt, params = self._prepare_step(
            session, step_num, step_def["key"])

        try:
            response = await self.provider.generate(system_prompt, user_prompt, params)
            result = StepResult(step_number=step_num, status=StepStatus.COMPLETED,
                                raw_output=response.content)
            session.steps[step_num].status = StepStatus.COMPLETED
            session.steps[step_num].result_text = response.content
            session.results[step_num] = result
            session.context_log[step_num] = response.content

            if self._on_step_complete:
                self._on_step_complete(session, step_num, response.content)

            return result
        except Exception as e:
            if step_def["is_critical"]:
                raise
            return StepResult(step_number=step_num, status=StepStatus.FAILED, error=str(e))


    async def cleanup_expired_sessions(self):
        now = time.time()
        expired = [sid for sid, s in self._sessions.items()
                   if now - s.last_accessed > 7200]
        for sid in expired:
            if sid in self._book_index.values():
                self._book_index = {k: v for k, v in self._book_index.items() if v != sid}
            del self._sessions[sid]

        if len(self._sessions) > 1000:
            excess = len(self._sessions) - 1000
            oldest = sorted(self._sessions.items(), key=lambda x: x[1].last_accessed)[:excess]
            for sid, _ in oldest:
                if sid in self._book_index.values():
                    self._book_index = {k: v for k, v in self._book_index.items() if v != sid}
                del self._sessions[sid]
