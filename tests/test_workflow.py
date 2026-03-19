from fastapi.testclient import TestClient

from ai_multi_agent.app import create_app


def test_multi_agent_workflow_uses_mock_backend() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/workflows/multi-agent",
        json={
            "task": "搭建一个企业知识库问答系统",
            "context": "要求保留工程化能力",
            "max_revisions": 1,
            "force_mock_llm": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["backend"] == "mock"
    assert payload["approved"] is True
    assert payload["revision_count"] == 1
    assert "planner: execution plan created" in payload["trace"]
    assert "synthesizer: final answer generated" in payload["trace"]
    assert payload["final_answer"]
