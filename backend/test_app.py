import pytest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

with patch('anthropic.Anthropic'):
    from app import (
        agent_add,
        agent_remove,
        agent_update,
        add_skills,
        add_memory,
        get_all_agents,
        get_agent,
        get_skills,
        get_memory,
        get_conversation,
        prompt_caching,
        interact_with_claude,
        interact_simple,
        agents,
        agent_skills,
        agent_memory
    )


@pytest.fixture(autouse=True)
def clear_agents():
    agents.clear()
    agent_skills.clear()
    agent_memory.clear()
    yield


class TestAgentAdd:
    def test_agent_add_success(self):
        result = agent_add("test_agent")
        assert result["status"] == "success"
        assert result["agent_id"] == "test_agent"
        assert "test_agent" in agents

    def test_agent_add_with_custom_model(self):
        result = agent_add("test_agent", model="claude-opus-4-20250514")
        assert result["status"] == "success"
        assert agents["test_agent"]["model"] == "claude-opus-4-20250514"

    def test_agent_add_with_system_prompt(self):
        result = agent_add("test_agent", system_prompt="You are helpful")
        assert result["status"] == "success"
        assert agents["test_agent"]["system_prompt"] == "You are helpful"


class TestAgentRemove:
    def test_agent_remove_success(self):
        agent_add("test_agent")
        result = agent_remove("test_agent")
        assert result["status"] == "success"
        assert "test_agent" not in agents

    def test_agent_remove_not_found(self):
        result = agent_remove("nonexistent")
        assert result["status"] == "error"
        assert "not found" in result["message"]


class TestAddSkills:
    def test_add_skills_success(self):
        agent_add("test_agent")
        result = add_skills("test_agent", ["coding", "math"])
        assert result["status"] == "success"
        assert "coding" in result["skills"]
        assert "math" in result["skills"]

    def test_add_skills_agent_not_found(self):
        result = add_skills("nonexistent", ["skill"])
        assert result["status"] == "error"


class TestAddMemory:
    def test_add_memory_success(self):
        agent_add("test_agent")
        result = add_memory("test_agent", "User likes Python")
        assert result["status"] == "success"
        assert "User likes Python" in result["memory"]

    def test_add_memory_agent_not_found(self):
        result = add_memory("nonexistent", "memory")
        assert result["status"] == "error"


class TestPromptCaching:
    def test_prompt_caching_success(self):
        agent_add("test_agent")
        result = prompt_caching("test_agent", "This is a cached prompt")
        assert result["status"] == "success"
        assert "cached_prompt" in agents["test_agent"]

    def test_prompt_caching_agent_not_found(self):
        result = prompt_caching("nonexistent", "cached")
        assert result["status"] == "error"


class TestInteractWithClaude:
    def test_interact_agent_not_found(self):
        result = interact_with_claude("nonexistent", "Hello")
        assert result["status"] == "error"

    @patch('app.client')
    def test_interact_success(self, mock_client):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Hello there!")]
        mock_client.messages.create.return_value = mock_response

        agent_add("test_agent")
        result = interact_with_claude("test_agent", "Hello")
        assert result["status"] == "success"
        assert result["response"] == "Hello there!"

    @patch('app.client')
    def test_interact_with_error(self, mock_client):
        mock_client.messages.create.side_effect = Exception("API Error")
        agent_add("test_agent")
        result = interact_with_claude("test_agent", "Hello")
        assert result["status"] == "error"


class TestInteractSimple:
    @patch('app.client')
    def test_interact_simple_success(self, mock_client):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Response")]
        mock_client.messages.create.return_value = mock_response

        result = interact_simple("Hello")
        assert result["status"] == "success"

    @patch('app.client')
    def test_interact_simple_error(self, mock_client):
        mock_client.messages.create.side_effect = Exception("Error")
        result = interact_simple("Hello")
        assert result["status"] == "error"


class TestAgentUpdate:
    def test_agent_update_success(self):
        agent_add("test_agent")
        result = agent_update("test_agent", model="claude-opus-4-20250514")
        assert result["status"] == "success"
        assert result["agent"]["model"] == "claude-opus-4-20250514"

    def test_agent_update_multiple_fields(self):
        agent_add("test_agent")
        result = agent_update(
            "test_agent",
            model="claude-opus-4-20250514",
            system_prompt="Updated prompt",
            entity_type="Entity",
            event_frequency=30
        )
        assert result["status"] == "success"
        assert result["agent"]["model"] == "claude-opus-4-20250514"
        assert result["agent"]["system_prompt"] == "Updated prompt"
        assert result["agent"]["entity_type"] == "Entity"
        assert result["agent"]["event_frequency"] == 30

    def test_agent_update_not_found(self):
        result = agent_update("nonexistent", model="claude-opus-4-20250514")
        assert result["status"] == "error"
        assert "not found" in result["message"]


class TestGetAllAgents:
    def test_get_all_agents_empty(self):
        result = get_all_agents()
        assert result == {}

    def test_get_all_agents_with_data(self):
        agent_add("agent1")
        agent_add("agent2")
        add_skills("agent1", ["skill1"])
        add_memory("agent2", "memory1")

        result = get_all_agents()
        assert "agent1" in result
        assert "agent2" in result
        assert result["agent1"]["skills"] == ["skill1"]
        assert result["agent2"]["memory"] == ["memory1"]


class TestGetAgent:
    def test_get_agent_success(self):
        agent_add("test_agent", system_prompt="Test prompt")
        result = get_agent("test_agent")
        assert result["status"] == "success"
        assert result["agent"]["system_prompt"] == "Test prompt"

    def test_get_agent_not_found(self):
        result = get_agent("nonexistent")
        assert result["status"] == "error"
        assert "not found" in result["message"]


class TestGetSkills:
    def test_get_skills_success(self):
        agent_add("test_agent")
        add_skills("test_agent", ["skill1", "skill2"])
        result = get_skills("test_agent")
        assert result["status"] == "success"
        assert "skill1" in result["skills"]
        assert "skill2" in result["skills"]

    def test_get_skills_not_found(self):
        result = get_skills("nonexistent")
        assert result["status"] == "error"


class TestGetMemory:
    def test_get_memory_success(self):
        agent_add("test_agent")
        add_memory("test_agent", "memory item")
        result = get_memory("test_agent")
        assert result["status"] == "success"
        assert "memory item" in result["memory"]

    def test_get_memory_not_found(self):
        result = get_memory("nonexistent")
        assert result["status"] == "error"


class TestGetConversation:
    def test_get_conversation_empty(self):
        agent_add("test_agent")
        result = get_conversation("test_agent")
        assert result["status"] == "success"
        assert result["conversation"] == []

    def test_get_conversation_not_found(self):
        result = get_conversation("nonexistent")
        assert result["status"] == "error"
