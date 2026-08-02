from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from app.db.models import GenerationRun


@dataclass(frozen=True, slots=True)
class GenerationProviderResult:
    result: dict
    evidence_refs: list[str]
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: Decimal = Decimal("0")
    latency_ms: int | None = None


class ContentGenerationProvider(Protocol):
    async def generate(self, *, run: GenerationRun) -> GenerationProviderResult: ...


class FixtureContentGenerationProvider:
    async def generate(self, *, run: GenerationRun) -> GenerationProviderResult:
        if run.generation_type == "script_draft":
            return GenerationProviderResult(
                result={
                    "body": "开场：餐厅高峰期最怕的不是忙，而是漏单。\n"
                    "主体：用清晰流程展示问题、证据和解决方案。\n"
                    "结尾：保存这份检查清单并在下次高峰前演练。",
                    "structured_body": {
                        "sections": ["hook", "evidence", "solution", "call_to_action"]
                    },
                    "rationale": "Fixture result for schema and workflow validation.",
                    "evidence_refs": run.evidence_refs,
                },
                evidence_refs=run.evidence_refs,
            )
        if run.generation_type == "content_package":
            script_body = (run.input_payload.get("script") or {}).get("body", "")
            chunk = script_body[:60] or "开场白。"
            return GenerationProviderResult(
                result={
                    "schema_version": 1,
                    "target_platform": run.input_payload.get("target_platform", "xiaohongshu"),
                    "content_type": "talking_video",
                    "target_duration_seconds": 30,
                    "narration": {
                        "full_text": script_body,
                        "spoken_length_chars": len(script_body),
                        "estimated_duration_seconds": 15,
                    },
                    "scenes": [
                        {
                            "id": "scene_01",
                            "layout": "avatar_corner",
                            "narration_chunk": chunk,
                            "visual_hint": "真人出镜，中景，直视镜头",
                            "on_screen_text": chunk[:12],
                            "subtitle": chunk,
                            "estimated_seconds": 8,
                            "asset_queries": [],
                            "evidence_refs": run.evidence_refs,
                        }
                    ],
                    "title_candidates": [
                        {"text": "Fixture 内容包标题", "length_chars": 9, "has_emoji": False}
                    ],
                    "cover": {
                        "headline": "Fixture 封面标题",
                        "subheadline": "Fixture 副标题",
                        "visual_hint": "深色背景大字标题",
                    },
                    "hashtags": ["#口语练习"],
                    "publish_caption": "Fixture 内容包正文描述，来自测试流水线。",
                    "assets_required": [
                        {
                            "kind": "screenshot",
                            "query": "录制界面截图",
                            "source_hint": None,
                            "rights_note": "自录素材",
                        }
                    ],
                    "audio": {
                        "voice_hint": "清晰女声，中速",
                        "music_mood": "轻快",
                        "music_ducking": "-8dB",
                    },
                    "publish_timing_hint": "工作日 20:00",
                    "evidence_refs": run.evidence_refs,
                },
                evidence_refs=run.evidence_refs,
            )
        return GenerationProviderResult(
            result={
                "analysis": {
                    "summary": "The fixture metrics show measurable exposure and engagement.",
                    "primary_metric": run.input_payload.get("primary_metric"),
                },
                "next_actions": ["Keep the winning hook and test one variable next."],
                "evidence_refs": run.evidence_refs,
            },
            evidence_refs=run.evidence_refs,
        )
