from app.providers.ai.base import AnalysisProviderResult


class FixtureAnalysisProvider:
    async def analyze(self, *, run, content, transcript, metrics=None):
        evidence_refs = [f"content:{content.id}"]
        if transcript is not None:
            evidence_refs.append(f"transcript:{transcript.id}")
        if run.analysis_level == "l1":
            result = {
                "summary": content.title or content.body_text or "Fixture summary",
                "factors": ["fixture-only validation path"],
                "confidence": 0.8,
                "caveats": ["Not a real model result."],
                "life": "evergreen",
                "life_reason": "Fixture result for automated tests.",
                "recommended_for_l2": True,
            }
        else:
            result = {
                "hook": content.title or "Fixture hook",
                "structure": ["opening", "body", "close"],
                "audience_pains": [],
                "triggers": [],
                "reusable_patterns": ["fixture pattern"],
                "non_reusable_context": [],
                "topic_ideas": [],
                "recommended_channels": [],
                "risks": ["Not a real model result."],
                "fact_checks": [],
                "evidence_refs": evidence_refs,
            }
        return AnalysisProviderResult(result=result, evidence_refs=evidence_refs)
