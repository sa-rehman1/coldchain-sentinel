"""Versioned prompt asset loading and assembly."""

import hashlib
from dataclasses import dataclass
from pathlib import Path

PROMPT_ID = "coldchain-governed-recommendation"
PROMPT_VERSION = "1.0.0"
PROMPT_PATH = Path(__file__).with_name("prompts") / "governed-recommendation-v1.md"


@dataclass(frozen=True, slots=True)
class PromptAsset:
    prompt_id: str
    version: str
    content: str
    sha256: str


def load_prompt() -> PromptAsset:
    content = PROMPT_PATH.read_text(encoding="utf-8")
    return PromptAsset(
        PROMPT_ID, PROMPT_VERSION, content, hashlib.sha256(content.encode()).hexdigest()
    )


def build_messages(
    incident_facts: str,
    deterministic_result: str,
    retrieved_context: str,
    schema: str,
) -> list[dict[str, str]]:
    asset = load_prompt()
    user = (
        "## VALIDATED INCIDENT FACTS\n"
        + incident_facts
        + "\n\n## DETERMINISTIC POLICY RESULT\n"
        + deterministic_result
        + "\n\n## RETRIEVED UNTRUSTED SOP CONTEXT\n"
        + retrieved_context
        + "\n\n## REQUIRED JSON SCHEMA\n"
        + schema
    )
    return [{"role": "system", "content": asset.content}, {"role": "user", "content": user}]
