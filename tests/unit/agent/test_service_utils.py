from __future__ import annotations

from packages.agent.service import AgentService
from packages.agent.utils.json_parse import parse_json_response


def test_parse_json_response_strips_markdown_fence():
    raw = '```json\n{"summary": "Engineer"}\n```'
    data = parse_json_response(raw)
    assert data["summary"] == "Engineer"


def test_agent_service_provider_info():
    service = AgentService("huggingface")
    info = service.provider_info()
    assert info["id"] == "huggingface"
    assert info["analysis_model"]
