"""Tests for the FastAPI API endpoints."""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


# Patch anthropic before importing api
with patch('anthropic.Anthropic'):
    from api import api, validate_agent_id, ValidationError, AGENT_ID_PATTERN


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(api)


@pytest.fixture(autouse=True)
def clear_app_state():
    """Clear app state before each test."""
    import app
    app.agents.clear()
    app.agent_skills.clear()
    app.agent_memory.clear()
    yield


class TestValidateAgentId:
    """Tests for agent ID validation."""

    def test_valid_agent_id(self):
        assert validate_agent_id("test-agent") == "test-agent"
        assert validate_agent_id("Agent_123") == "Agent_123"
        assert validate_agent_id("a") == "a"

    def test_invalid_agent_id_empty(self):
        with pytest.raises(ValidationError):
            validate_agent_id("")

    def test_invalid_agent_id_special_chars(self):
        with pytest.raises(ValidationError):
            validate_agent_id("agent@test")

    def test_invalid_agent_id_spaces(self):
        with pytest.raises(ValidationError):
            validate_agent_id("agent test")

    def test_invalid_agent_id_too_long(self):
        with pytest.raises(ValidationError):
            validate_agent_id("a" * 65)

    def test_valid_agent_id_max_length(self):
        assert validate_agent_id("a" * 64) == "a" * 64


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    def test_health_check(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestAgentsCRUD:
    """Tests for agent CRUD operations."""

    def test_list_agents_empty(self, client):
        response = client.get("/agents")
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        assert response.json()["agents"] == {}

    def test_create_agent(self, client):
        response = client.post("/agents", json={
            "agent_id": "test-agent",
            "model": "claude-sonnet-4-20250514",
            "system_prompt": "You are a helpful assistant"
        })
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        assert response.json()["agent_id"] == "test-agent"

    def test_create_agent_invalid_id(self, client):
        response = client.post("/agents", json={
            "agent_id": "invalid agent!",
            "model": "claude-sonnet-4-20250514"
        })
        assert response.status_code == 422  # Validation error

    def test_get_agent(self, client):
        # Create agent first
        client.post("/agents", json={"agent_id": "test-agent"})

        response = client.get("/agents/test-agent")
        assert response.status_code == 200
        assert response.json()["status"] == "success"

    def test_get_agent_not_found(self, client):
        response = client.get("/agents/nonexistent")
        assert response.status_code == 404

    def test_get_agent_invalid_id(self, client):
        response = client.get("/agents/invalid%20agent")
        assert response.status_code == 422

    def test_update_agent(self, client):
        # Create agent first
        client.post("/agents", json={"agent_id": "test-agent"})

        response = client.put("/agents/test-agent", json={
            "model": "claude-opus-4-20250514"
        })
        assert response.status_code == 200
        assert response.json()["status"] == "success"

    def test_update_agent_not_found(self, client):
        response = client.put("/agents/nonexistent", json={
            "model": "claude-opus-4-20250514"
        })
        assert response.status_code == 404

    def test_delete_agent(self, client):
        # Create agent first
        client.post("/agents", json={"agent_id": "test-agent"})

        response = client.delete("/agents/test-agent")
        assert response.status_code == 200
        assert response.json()["status"] == "success"

    def test_delete_agent_not_found(self, client):
        response = client.delete("/agents/nonexistent")
        assert response.status_code == 404


class TestAgentSkills:
    """Tests for agent skills endpoints."""

    def test_get_skills_empty(self, client):
        client.post("/agents", json={"agent_id": "test-agent"})

        response = client.get("/agents/test-agent/skills")
        assert response.status_code == 200
        assert response.json()["skills"] == []

    def test_add_skills(self, client):
        client.post("/agents", json={"agent_id": "test-agent"})

        response = client.post("/agents/test-agent/skills", json={
            "skills": ["coding", "analysis"]
        })
        assert response.status_code == 200
        assert "coding" in response.json()["skills"]

    def test_skills_agent_not_found(self, client):
        response = client.get("/agents/nonexistent/skills")
        assert response.status_code == 404


class TestAgentMemory:
    """Tests for agent memory endpoints."""

    def test_get_memory_empty(self, client):
        client.post("/agents", json={"agent_id": "test-agent"})

        response = client.get("/agents/test-agent/memory")
        assert response.status_code == 200
        assert response.json()["memory"] == []

    def test_add_memory(self, client):
        client.post("/agents", json={"agent_id": "test-agent"})

        response = client.post("/agents/test-agent/memory", json={
            "memory_item": "User prefers Python"
        })
        assert response.status_code == 200
        assert "User prefers Python" in response.json()["memory"]

    def test_memory_agent_not_found(self, client):
        response = client.get("/agents/nonexistent/memory")
        assert response.status_code == 404


class TestAgentConversation:
    """Tests for agent conversation endpoint."""

    def test_get_conversation_empty(self, client):
        client.post("/agents", json={"agent_id": "test-agent"})

        response = client.get("/agents/test-agent/conversation")
        assert response.status_code == 200
        assert response.json()["conversation"] == []

    def test_conversation_agent_not_found(self, client):
        response = client.get("/agents/nonexistent/conversation")
        assert response.status_code == 404


class TestSimulationEndpoints:
    """Tests for simulation endpoints."""

    def test_simulation_status(self, client):
        response = client.get("/simulation/status")
        assert response.status_code == 200
        assert "is_running" in response.json()

    def test_simulation_events(self, client):
        response = client.get("/simulation/events")
        assert response.status_code == 200
        assert "events" in response.json()

    def test_update_clock_speed(self, client):
        response = client.put("/simulation/clock-speed", json={
            "clock_speed": 5.0
        })
        assert response.status_code == 200

    def test_update_clock_speed_invalid(self, client):
        response = client.put("/simulation/clock-speed", json={
            "clock_speed": -1.0
        })
        assert response.status_code == 200
        assert response.json()["status"] == "error"
