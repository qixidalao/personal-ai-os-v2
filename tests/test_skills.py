import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from runtime.skills.registry import get_skill, list_skills
import tools.skills as skills_tool


def test_skill_catalogue_contains_local_markdown_skills():
    skills = list_skills()
    assert {item["id"] for item in skills} >= {"web-research", "interest-scout", "frontend-craft"}
    assert all(item.get("description") and "instructions" not in item for item in skills)
    assert get_skill("../settings") is None


def test_skill_api_exposes_metadata_and_enabled_state():
    with TestClient(app) as client:
        response = client.get("/api/v1/skills")
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] >= 3
    research = next(item for item in payload["skills"] if item["id"] == "web-research")
                                             # 中文：技能

    assert research["enabled"] is True
    assert "instructions" not in research


def test_read_skill_only_loads_enabled_skill(tmp_path: Path, monkeypatch):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps({"enabledSkills": ["web-research"]}), encoding="utf-8")
    monkeypatch.setattr(skills_tool, "SETTINGS_FILE", settings_file)

    result = skills_tool.read_skill("web-research")
    assert "web_search" in result["instructions"]
    with pytest.raises(ValueError, match="未启用"):
        skills_tool.read_skill("interest-scout")


def test_chat_tool_schema_obeys_user_tool_switches(tmp_path: Path, monkeypatch):
    from backend import chat_api

    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps({"agentTools": [{"name": "web_search", "enabled": False}]}), encoding="utf-8")
    monkeypatch.setattr(chat_api, "SETTINGS_FILE", settings_file)
    names = {tool["function"]["name"] for tool in chat_api._get_enabled_tools()}
    assert "web_search" not in names
    assert "read_skill" in names
