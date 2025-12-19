"""Tests for the app module - agent management functionality."""
import pytest
from unittest.mock import patch, MagicMock
import json
import os
import tempfile


# Patch anthropic before importing app
with patch('anthropic.Anthropic'):
    import app


class TestAgentCRUD:
    """Tests for agent create, read, update, delete operations."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Reset agents state before each test."""
        # Clear state
        app.agents.clear()
        app.agent_skills.clear()
        app.agent_memory.clear()
        yield
        # Clean up after test
        app.agents.clear()
        app.agent_skills.clear()
        app.agent_memory.clear()

    def test_agent_add_default_values(self):
        """Test creating an agent with default values."""
        with patch.object(app, 'save_agents'):
            result = app.agent_add("test-agent")

        assert result["status"] == "success"
        assert result["agent_id"] == "test-agent"
        assert "test-agent" in app.agents
        assert app.agents["test-agent"]["model"] == "claude-sonnet-4-20250514"
        assert app.agents["test-agent"]["is_enabled"] is True

    def test_agent_add_custom_values(self):
        """Test creating an agent with custom values."""
        with patch.object(app, 'save_agents'):
            result = app.agent_add(
                agent_id="custom-agent",
                model="claude-opus-4-20250514",
                entity_type="Entity",
                event_frequency=30,
                is_enemy=True,
                is_west=False,
                agent_category="Security Services",
                agenda="Test agenda",
                is_enabled=False
            )

        assert result["status"] == "success"
        agent = app.agents["custom-agent"]
        assert agent["model"] == "claude-opus-4-20250514"
        assert agent["entity_type"] == "Entity"
        assert agent["event_frequency"] == 30
        assert agent["is_enemy"] is True
        assert agent["agent_category"] == "Security Services"
        assert agent["agenda"] == "Test agenda"
        assert agent["is_enabled"] is False

    def test_agent_add_compiles_system_prompt(self):
        """Test that system prompt is auto-compiled from components."""
        with patch.object(app, 'save_agents'):
            app.agent_add(
                agent_id="prompt-test",
                agent_category="Media",
                agenda="Report the news",
                primary_objectives="1. Be objective\n2. Report facts",
                hard_rules="Never lie"
            )

        agent = app.agents["prompt-test"]
        # Agent name has hyphens replaced with spaces
        assert "PROMPT TEST" in agent["system_prompt"]
        assert "Media" in agent["system_prompt"]
        assert "Report the news" in agent["system_prompt"]
        assert "Be objective" in agent["system_prompt"]
        assert "Never lie" in agent["system_prompt"]

    def test_agent_remove_success(self):
        """Test removing an existing agent."""
        with patch.object(app, 'save_agents'):
            app.agent_add("to-remove")
            result = app.agent_remove("to-remove")

        assert result["status"] == "success"
        assert "to-remove" not in app.agents

    def test_agent_remove_not_found(self):
        """Test removing a non-existent agent."""
        result = app.agent_remove("nonexistent")

        assert result["status"] == "error"
        assert "not found" in result["message"]

    def test_get_all_agents(self):
        """Test getting all agents."""
        with patch.object(app, 'save_agents'):
            app.agent_add("agent-1")
            app.agent_add("agent-2")

        result = app.get_all_agents()

        assert "agent-1" in result
        assert "agent-2" in result
        assert len(result) == 2

    def test_get_agent_success(self):
        """Test getting a single agent."""
        with patch.object(app, 'save_agents'):
            app.agent_add("single-agent")

        result = app.get_agent("single-agent")

        assert result["status"] == "success"
        assert "agent" in result
        assert result["agent"]["model"] == "claude-sonnet-4-20250514"

    def test_get_agent_not_found(self):
        """Test getting a non-existent agent."""
        result = app.get_agent("nonexistent")

        assert result["status"] == "error"


class TestAgentUpdate:
    """Tests for agent update functionality."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Reset agents state before each test."""
        app.agents.clear()
        app.agent_skills.clear()
        app.agent_memory.clear()
        yield
        app.agents.clear()
        app.agent_skills.clear()
        app.agent_memory.clear()

    def test_agent_update_model(self):
        """Test updating agent model."""
        with patch.object(app, 'save_agents'):
            app.agent_add("update-test")
            result = app.agent_update("update-test", model="claude-opus-4-20250514")

        assert result["status"] == "success"
        assert app.agents["update-test"]["model"] == "claude-opus-4-20250514"

    def test_agent_update_is_enabled(self):
        """Test updating agent enabled status."""
        with patch.object(app, 'save_agents'):
            app.agent_add("enabled-test")
            assert app.agents["enabled-test"]["is_enabled"] is True

            result = app.agent_update("enabled-test", is_enabled=False)

        assert result["status"] == "success"
        assert app.agents["enabled-test"]["is_enabled"] is False

    def test_agent_update_recompiles_prompt_on_component_change(self):
        """Test that system prompt is recompiled when components change."""
        with patch.object(app, 'save_agents'):
            app.agent_add("recompile-test", agenda="Original agenda")
            original_prompt = app.agents["recompile-test"]["system_prompt"]

            app.agent_update("recompile-test", agenda="Updated agenda")

        new_prompt = app.agents["recompile-test"]["system_prompt"]
        assert new_prompt != original_prompt
        assert "Updated agenda" in new_prompt
        assert "Original agenda" not in new_prompt

    def test_agent_update_not_found(self):
        """Test updating a non-existent agent."""
        result = app.agent_update("nonexistent", model="test")

        assert result["status"] == "error"

    def test_agent_update_multiple_fields(self):
        """Test updating multiple fields at once."""
        with patch.object(app, 'save_agents'):
            app.agent_add("multi-update")
            result = app.agent_update(
                "multi-update",
                model="claude-opus-4-20250514",
                entity_type="Entity",
                is_enemy=True,
                is_enabled=False,
                agenda="New agenda"
            )

        assert result["status"] == "success"
        agent = app.agents["multi-update"]
        assert agent["model"] == "claude-opus-4-20250514"
        assert agent["entity_type"] == "Entity"
        assert agent["is_enemy"] is True
        assert agent["is_enabled"] is False
        assert "New agenda" in agent["system_prompt"]


class TestAgentEnableDisable:
    """Tests for agent enable/disable functionality."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Reset agents state before each test."""
        app.agents.clear()
        app.agent_skills.clear()
        app.agent_memory.clear()
        yield
        app.agents.clear()
        app.agent_skills.clear()
        app.agent_memory.clear()

    def test_toggle_agent_enabled_from_true_to_false(self):
        """Test toggling from enabled to disabled."""
        with patch.object(app, 'save_agents'):
            app.agent_add("toggle-test", is_enabled=True)
            result = app.toggle_agent_enabled("toggle-test")

        assert result["status"] == "success"
        assert result["is_enabled"] is False
        assert app.agents["toggle-test"]["is_enabled"] is False

    def test_toggle_agent_enabled_from_false_to_true(self):
        """Test toggling from disabled to enabled."""
        with patch.object(app, 'save_agents'):
            app.agent_add("toggle-test", is_enabled=False)
            result = app.toggle_agent_enabled("toggle-test")

        assert result["status"] == "success"
        assert result["is_enabled"] is True
        assert app.agents["toggle-test"]["is_enabled"] is True

    def test_toggle_agent_not_found(self):
        """Test toggling a non-existent agent."""
        result = app.toggle_agent_enabled("nonexistent")

        assert result["status"] == "error"
        assert "not found" in result["message"]

    def test_toggle_agent_default_enabled_state(self):
        """Test toggling agent that doesn't have is_enabled set (defaults to True)."""
        with patch.object(app, 'save_agents'):
            app.agent_add("default-test")
            # Manually remove is_enabled to simulate old data
            del app.agents["default-test"]["is_enabled"]

            result = app.toggle_agent_enabled("default-test")

        assert result["status"] == "success"
        # Should toggle from default True to False
        assert result["is_enabled"] is False

    def test_set_all_agents_enabled_true(self):
        """Test enabling all agents."""
        with patch.object(app, 'save_agents'):
            app.agent_add("agent-1", is_enabled=False)
            app.agent_add("agent-2", is_enabled=False)
            app.agent_add("agent-3", is_enabled=True)

            result = app.set_all_agents_enabled(True)

        assert result["status"] == "success"
        assert result["count"] == 3
        assert result["is_enabled"] is True
        assert app.agents["agent-1"]["is_enabled"] is True
        assert app.agents["agent-2"]["is_enabled"] is True
        assert app.agents["agent-3"]["is_enabled"] is True

    def test_set_all_agents_enabled_false(self):
        """Test disabling all agents."""
        with patch.object(app, 'save_agents'):
            app.agent_add("agent-1", is_enabled=True)
            app.agent_add("agent-2", is_enabled=True)
            app.agent_add("agent-3", is_enabled=False)

            result = app.set_all_agents_enabled(False)

        assert result["status"] == "success"
        assert result["count"] == 3
        assert result["is_enabled"] is False
        assert app.agents["agent-1"]["is_enabled"] is False
        assert app.agents["agent-2"]["is_enabled"] is False
        assert app.agents["agent-3"]["is_enabled"] is False

    def test_set_all_agents_enabled_empty(self):
        """Test setting enabled on empty agents list."""
        result = app.set_all_agents_enabled(True)

        assert result["status"] == "success"
        assert result["count"] == 0


class TestAgentSkillsAndMemory:
    """Tests for agent skills and memory management."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Reset agents state before each test."""
        app.agents.clear()
        app.agent_skills.clear()
        app.agent_memory.clear()
        yield
        app.agents.clear()
        app.agent_skills.clear()
        app.agent_memory.clear()

    def test_add_skills(self):
        """Test adding skills to an agent."""
        with patch.object(app, 'save_agents'):
            app.agent_add("skills-test")
            result = app.add_skills("skills-test", ["skill1", "skill2"])

        assert result["status"] == "success"
        assert "skill1" in app.agent_skills["skills-test"]
        assert "skill2" in app.agent_skills["skills-test"]

    def test_get_skills(self):
        """Test getting agent skills."""
        with patch.object(app, 'save_agents'):
            app.agent_add("skills-test")
            app.add_skills("skills-test", ["skill1"])

        result = app.get_skills("skills-test")

        assert result["status"] == "success"
        assert "skill1" in result["skills"]

    def test_add_memory(self):
        """Test adding memory to an agent."""
        with patch.object(app, 'save_agents'):
            app.agent_add("memory-test")
            result = app.add_memory("memory-test", "Test memory item")

        assert result["status"] == "success"
        assert "Test memory item" in app.agent_memory["memory-test"]

    def test_remove_memory(self):
        """Test removing memory by pattern."""
        with patch.object(app, 'save_agents'):
            app.agent_add("memory-test")
            app.add_memory("memory-test", "Keep this memory")
            app.add_memory("memory-test", "Remove this memory")
            app.add_memory("memory-test", "Also Remove this")

            result = app.remove_memory("memory-test", "Remove")

        assert result["status"] == "success"
        assert result["removed_count"] == 2
        assert len(app.agent_memory["memory-test"]) == 1
        assert "Keep this memory" in app.agent_memory["memory-test"]


class TestConversation:
    """Tests for agent conversation management."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Reset agents state before each test."""
        app.agents.clear()
        app.agent_skills.clear()
        app.agent_memory.clear()
        yield
        app.agents.clear()
        app.agent_skills.clear()
        app.agent_memory.clear()

    def test_get_conversation(self):
        """Test getting agent conversation."""
        with patch.object(app, 'save_agents'):
            app.agent_add("conv-test")
            app.agents["conv-test"]["conversation"] = [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there"}
            ]

        result = app.get_conversation("conv-test")

        assert result["status"] == "success"
        assert len(result["conversation"]) == 2

    def test_clear_conversation(self):
        """Test clearing agent conversation."""
        with patch.object(app, 'save_agents'):
            app.agent_add("conv-test")
            app.agents["conv-test"]["conversation"] = [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there"}
            ]

            result = app.clear_conversation("conv-test")

        assert result["status"] == "success"
        assert len(app.agents["conv-test"]["conversation"]) == 0


class TestSystemPromptCompilation:
    """Tests for system prompt compilation."""

    def test_compile_with_all_fields(self):
        """Test compiling system prompt with all fields."""
        agent_data = {
            "agent_category": "Security Services",
            "is_enemy": False,
            "is_west": True,
            "is_evil_axis": False,
            "is_reporting_government": True,
            "agenda": "Protect national security",
            "primary_objectives": "1. Gather intelligence\n2. Prevent attacks",
            "hard_rules": "Never reveal sources"
        }

        prompt = app.compile_system_prompt("Test-Agent", agent_data)

        # Agent name has hyphens replaced with spaces
        assert "TEST AGENT" in prompt
        assert "Security Services" in prompt
        assert "Western Alliance" in prompt or "Israeli Government" in prompt
        assert "Protect national security" in prompt
        assert "Gather intelligence" in prompt
        assert "Never reveal sources" in prompt

    def test_compile_with_minimal_fields(self):
        """Test compiling system prompt with minimal fields."""
        agent_data = {
            "agent_category": "",
            "is_enemy": False,
            "is_west": False,
            "is_evil_axis": False,
            "is_reporting_government": False,
            "agenda": "",
            "primary_objectives": "",
            "hard_rules": ""
        }

        prompt = app.compile_system_prompt("Minimal-Agent", agent_data)

        # Agent name has hyphens replaced with spaces
        assert "MINIMAL AGENT" in prompt
        assert "Neutral / Independent" in prompt

    def test_regenerate_all_system_prompts(self):
        """Test regenerating all system prompts."""
        with patch.object(app, 'save_agents'):
            app.agent_add("agent-1", agenda="Agenda 1")
            app.agent_add("agent-2", agenda="Agenda 2")

            # Manually corrupt prompts
            app.agents["agent-1"]["system_prompt"] = "corrupted"
            app.agents["agent-2"]["system_prompt"] = "corrupted"

            result = app.regenerate_all_system_prompts()

        assert result["status"] == "success"
        assert result["message"] == "Regenerated system prompts for 2 agents"
        assert "Agenda 1" in app.agents["agent-1"]["system_prompt"]
        assert "Agenda 2" in app.agents["agent-2"]["system_prompt"]


class TestActivityLog:
    """Tests for activity logging."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Reset activity log before each test."""
        app.clear_activity_log()
        yield
        app.clear_activity_log()

    def test_log_activity(self):
        """Test logging an activity."""
        app.log_activity(
            activity_type="chat",
            agent_id="test-agent",
            action="chat_response",
            details="Test details",
            duration_ms=100,
            success=True
        )

        log = app.get_activity_log(limit=1)
        assert len(log) == 1
        assert log[0]["type"] == "chat"
        assert log[0]["agent_id"] == "test-agent"
        assert log[0]["success"] is True

    def test_get_activity_log_with_filters(self):
        """Test getting activity log with filters."""
        app.log_activity("chat", "agent-1", "action1")
        app.log_activity("memory", "agent-1", "action2")
        app.log_activity("chat", "agent-2", "action3")

        # Filter by agent
        agent1_log = app.get_activity_log(agent_id="agent-1")
        assert len(agent1_log) == 2

        # Filter by type
        chat_log = app.get_activity_log(activity_type="chat")
        assert len(chat_log) == 2

    def test_get_activity_stats(self):
        """Test getting activity statistics."""
        app.log_activity("chat", "agent-1", "action1", duration_ms=100, success=True)
        app.log_activity("chat", "agent-2", "action2", duration_ms=200, success=True)
        app.log_activity("chat", "agent-1", "action3", success=False, error="Test error")

        stats = app.get_activity_stats()

        assert stats["total_calls"] == 3
        assert stats["active_agents"] == 2
        assert stats["errors"] == 1
        assert stats["avg_response_time_ms"] == 150.0

    def test_clear_activity_log(self):
        """Test clearing activity log."""
        app.log_activity("chat", "agent-1", "action1")
        app.log_activity("chat", "agent-2", "action2")

        result = app.clear_activity_log()

        assert result["status"] == "success"
        assert len(app.get_activity_log()) == 0
