from __future__ import annotations

import json

from packages.agent.providers.base import AgentTask


def mock_complete(task: AgentTask, prompt: str, *, json_mode: bool = False) -> str:
    if task == AgentTask.INPUT_ANALYSIS:
        return json.dumps(
            {
                "jd_analysis": json.loads(mock_complete(AgentTask.JD_ANALYSIS, prompt, json_mode=True)),
                "resume_analysis": json.loads(
                    mock_complete(AgentTask.RESUME_ANALYSIS, prompt, json_mode=True)
                ),
            }
        )
    if task == AgentTask.JD_ANALYSIS:
        return json.dumps(
            {
                "must_have": [
                    {"requirement": "Python", "category": "skill"},
                    {"requirement": "3+ years experience", "category": "years"},
                ],
                "nice_to_have": [{"requirement": "PostgreSQL", "category": "skill"}],
                "role_type": "ic",
                "seniority_level": "mid",
                "responsibilities": ["Build and maintain APIs", "Collaborate with product"],
                "dealbreakers": [],
                "keywords_weighted": [
                    {"term": "python", "weight": 1.0},
                    {"term": "api", "weight": 0.8},
                    {"term": "postgresql", "weight": 0.5},
                ],
            }
        )
    if task == AgentTask.RESUME_ANALYSIS:
        return json.dumps(
            {
                "sections_present": {
                    "summary": True,
                    "experience": True,
                    "skills": True,
                    "education": False,
                },
                "sections_missing": ["education"],
                "seniority_inferred": "mid",
                "roles": [
                    {
                        "title": "Engineer",
                        "company": "Acme",
                        "dates": "2020-2022",
                        "bullets": ["Built APIs with Python"],
                    }
                ],
                "skills": ["Python", "SQL"],
                "education": [],
                "requirement_evidence": [
                    {
                        "requirement": "Python",
                        "status": "met",
                        "evidence_quote": "Built APIs with Python",
                    },
                    {
                        "requirement": "3+ years experience",
                        "status": "partial",
                        "evidence_quote": "2020-2022",
                    },
                ],
            }
        )
    if task == AgentTask.VALIDATION:
        return "no"
    if json_mode or "JSON" in prompt:
        return (
            '{"summary": "Experienced engineer.", "experience": "Built APIs with Python.",'
            ' "skills": "Python, SQL"}'
        )
    return "Experienced engineer with relevant skills."
