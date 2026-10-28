"""Read-only inventory for local Markdown Agent Skills."""
from pathlib import Path
import json

from fastapi import APIRouter

from runtime.skills.registry import DEFAULT_ENABLED_SKILLS, list_skills

router = APIRouter(prefix="/api/v1/skills", tags=["skills"])
SETTINGS_FILE = Path("storage/settings.json")


def _enabled_ids() -> set[str]:
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        values = data.get("enabledSkills", DEFAULT_ENABLED_SKILLS)
        return set(values) if isinstance(values, list) else set()
    except (OSError, json.JSONDecodeError):
        return set(DEFAULT_ENABLED_SKILLS)


@router.get("")
async def get_skills():
    enabled = _enabled_ids()
    skills = [{**skill, "enabled": skill["id"] in enabled} for skill in list_skills()]
    return {"skills": skills, "count": len(skills)}
