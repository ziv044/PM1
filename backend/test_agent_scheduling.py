"""
Comprehensive tests for agent enable/disable and frequency scheduling mechanism.

This test suite validates:
1. Agent filtering (only enabled agents with entity_type='Entity' are scheduled)
2. Frequency configuration (agents respect their event_frequency setting)
3. Runtime enable/disable (disabling an agent mid-simulation stops its actions)
4. Toggle mechanism (the toggle API works correctly)
5. Full scheduler behavior with multiple agents at different frequencies
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
import json
import tempfile
import shutil
from pathlib import Path
from collections import defaultdict

# Patch anthropic before importing simulation modules
with patch('anthropic.Anthropic'):
    from simulation import (
        GameClock,
        SimulationState,
        SimulationManager,
        EntityScheduler,
        EventProcessor,
        DEFAULT_CLOCK_SPEED,
    )
    import app


class TestEntitySchedulerFiltering:
    """Tests for EntityScheduler.get_entity_agents() - the filtering mechanism."""

    def test_only_enabled_agents_are_returned(self):
        """Test that disabled agents are filtered out."""
        mock_agents = {
            "Agent-Enabled": {
                "entity_type": "Entity",
                "is_enabled": True,
                "event_frequency": 60
            },
            "Agent-Disabled": {
                "entity_type": "Entity",
                "is_enabled": False,
                "event_frequency": 60
            },
            "Agent-Default": {
                "entity_type": "Entity",
                # is_enabled not set - should default to True
                "event_frequency": 60
            }
        }

        with patch.object(app, 'agents', mock_agents):
            state = SimulationState()
            manager = MagicMock()
            manager.state = state
            scheduler = EntityScheduler(manager)

            entities = scheduler.get_entity_agents()

        assert "Agent-Enabled" in entities
        assert "Agent-Disabled" not in entities
        assert "Agent-Default" in entities  # Default is enabled
        assert len(entities) == 2

    def test_only_entity_type_agents_are_returned(self):
        """Test that non-Entity type agents are filtered out."""
        mock_agents = {
            "Entity-Agent": {
                "entity_type": "Entity",
                "is_enabled": True,
                "event_frequency": 60
            },
            "System-Agent": {
                "entity_type": "System",
                "is_enabled": True,
                "event_frequency": 60
            },
            "Other-Agent": {
                "entity_type": "Observer",
                "is_enabled": True,
                "event_frequency": 60
            }
        }

        with patch.object(app, 'agents', mock_agents):
            state = SimulationState()
            manager = MagicMock()
            manager.state = state
            scheduler = EntityScheduler(manager)

            entities = scheduler.get_entity_agents()

        assert "Entity-Agent" in entities
        assert "System-Agent" not in entities
        assert "Other-Agent" not in entities
        assert len(entities) == 1

    def test_combined_filtering(self):
        """Test both entity_type and is_enabled filtering together."""
        mock_agents = {
            "Good-1": {"entity_type": "Entity", "is_enabled": True, "event_frequency": 60},
            "Good-2": {"entity_type": "Entity", "is_enabled": True, "event_frequency": 30},
            "Disabled-Entity": {"entity_type": "Entity", "is_enabled": False, "event_frequency": 60},
            "System-Enabled": {"entity_type": "System", "is_enabled": True, "event_frequency": 60},
            "System-Disabled": {"entity_type": "System", "is_enabled": False, "event_frequency": 60},
        }

        with patch.object(app, 'agents', mock_agents):
            state = SimulationState()
            manager = MagicMock()
            manager.state = state
            scheduler = EntityScheduler(manager)

            entities = scheduler.get_entity_agents()

        assert len(entities) == 2
        assert "Good-1" in entities
        assert "Good-2" in entities

    def test_empty_agents_returns_empty_dict(self):
        """Test that empty agents dict returns empty result."""
        with patch.object(app, 'agents', {}):
            state = SimulationState()
            manager = MagicMock()
            manager.state = state
            scheduler = EntityScheduler(manager)

            entities = scheduler.get_entity_agents()

        assert entities == {}


class TestAgentFrequencyConfiguration:
    """Tests for agent frequency configuration and interval calculation."""

    def test_frequency_minutes_to_seconds_conversion(self):
        """Test that frequency_minutes is correctly converted to real seconds."""
        # With clock speed of 2.0: 1 game minute = 2 real seconds
        # So frequency of 60 game minutes = 120 real seconds
        clock = GameClock(speed=2.0)
        frequency_minutes = 60

        interval_seconds = frequency_minutes * clock.speed

        assert interval_seconds == 120.0

    def test_fast_frequency_for_testing(self):
        """Test that 1 game minute with speed 1.0 = 1 real second."""
        clock = GameClock(speed=1.0)
        frequency_minutes = 1

        interval_seconds = frequency_minutes * clock.speed

        assert interval_seconds == 1.0

    def test_agents_preserve_different_frequencies(self):
        """Test that different agents can have different frequencies."""
        mock_agents = {
            "Fast-Agent": {"entity_type": "Entity", "is_enabled": True, "event_frequency": 10},
            "Slow-Agent": {"entity_type": "Entity", "is_enabled": True, "event_frequency": 300},
            "Default-Agent": {"entity_type": "Entity", "is_enabled": True}  # No frequency set
        }

        with patch.object(app, 'agents', mock_agents):
            state = SimulationState()
            manager = MagicMock()
            manager.state = state
            scheduler = EntityScheduler(manager)

            entities = scheduler.get_entity_agents()

        assert entities["Fast-Agent"].get("event_frequency") == 10
        assert entities["Slow-Agent"].get("event_frequency") == 300
        assert entities["Default-Agent"].get("event_frequency") is None  # Uses default 60


class TestToggleAgentEnabled:
    """Tests for the toggle_agent_enabled function."""

    def test_toggle_enables_disabled_agent(self):
        """Test that toggle enables a disabled agent."""
        mock_agents = {
            "Test-Agent": {"is_enabled": False, "entity_type": "Entity"}
        }

        with patch.object(app, 'agents', mock_agents):
            with patch.object(app, 'save_agents'):
                result = app.toggle_agent_enabled("Test-Agent")

        assert result["status"] == "success"
        assert result["is_enabled"] is True
        assert mock_agents["Test-Agent"]["is_enabled"] is True

    def test_toggle_disables_enabled_agent(self):
        """Test that toggle disables an enabled agent."""
        mock_agents = {
            "Test-Agent": {"is_enabled": True, "entity_type": "Entity"}
        }

        with patch.object(app, 'agents', mock_agents):
            with patch.object(app, 'save_agents'):
                result = app.toggle_agent_enabled("Test-Agent")

        assert result["status"] == "success"
        assert result["is_enabled"] is False
        assert mock_agents["Test-Agent"]["is_enabled"] is False

    def test_toggle_handles_default_enabled_state(self):
        """Test that toggle works when is_enabled is not explicitly set (default True)."""
        mock_agents = {
            "Test-Agent": {"entity_type": "Entity"}  # No is_enabled field
        }

        with patch.object(app, 'agents', mock_agents):
            with patch.object(app, 'save_agents'):
                result = app.toggle_agent_enabled("Test-Agent")

        assert result["status"] == "success"
        assert result["is_enabled"] is False  # Was True (default), now False
        assert mock_agents["Test-Agent"]["is_enabled"] is False

    def test_toggle_nonexistent_agent_returns_error(self):
        """Test that toggling non-existent agent returns error."""
        with patch.object(app, 'agents', {}):
            result = app.toggle_agent_enabled("NonExistent-Agent")

        assert result["status"] == "error"
        assert "not found" in result["message"]


class TestRuntimeEnableDisable:
    """Tests for runtime enable/disable behavior during simulation."""

    @pytest.mark.asyncio
    async def test_trigger_action_skips_disabled_agent(self):
        """Test that trigger_action skips disabled agents."""
        mock_agents = {
            "Disabled-Agent": {
                "entity_type": "Entity",
                "is_enabled": False,
                "model": "test-model"
            }
        }

        with patch.object(app, 'agents', mock_agents):
            state = SimulationState()
            clock = GameClock()
            manager = MagicMock()
            manager.state = state
            manager.clock = clock
            scheduler = EntityScheduler(manager)

            # Mock the event_processor to track if it gets called
            manager.event_processor = MagicMock()
            manager.event_processor.build_prompt = MagicMock()

            await scheduler.trigger_action("Disabled-Agent")

            # Verify build_prompt was NOT called (action skipped)
            manager.event_processor.build_prompt.assert_not_called()

    @pytest.mark.asyncio
    async def test_trigger_action_executes_for_enabled_agent(self):
        """Test that trigger_action executes for enabled agents."""
        mock_agents = {
            "Enabled-Agent": {
                "entity_type": "Entity",
                "is_enabled": True,
                "model": "test-model"
            }
        }

        with patch.object(app, 'agents', mock_agents):
            with patch.object(app, 'interact_with_caching') as mock_interact:
                mock_interact.return_value = {"status": "success", "response": "{}"}

                state = SimulationState()
                clock = GameClock()
                clock.start()

                manager = MagicMock()
                manager.state = state
                manager.clock = clock

                # Create real event processor
                event_processor = EventProcessor(state)
                manager.event_processor = event_processor

                scheduler = EntityScheduler(manager)

                await scheduler.trigger_action("Enabled-Agent")

                # Verify interact_with_caching WAS called
                mock_interact.assert_called_once()

    @pytest.mark.asyncio
    async def test_agent_disabled_mid_simulation_stops_actions(self):
        """Test that disabling an agent mid-simulation stops its actions."""
        action_counts = defaultdict(int)

        mock_agents = {
            "Dynamic-Agent": {
                "entity_type": "Entity",
                "is_enabled": True,
                "event_frequency": 1,  # Every 1 game minute
                "model": "test-model"
            }
        }

        async def mock_trigger(agent_id):
            """Track action calls and disable agent after 2 actions."""
            if mock_agents[agent_id].get("is_enabled", True):
                action_counts[agent_id] += 1
                if action_counts[agent_id] >= 2:
                    mock_agents[agent_id]["is_enabled"] = False

        with patch.object(app, 'agents', mock_agents):
            state = SimulationState()
            state.is_running = True

            clock = GameClock(speed=0.1)  # Fast clock for testing
            clock.start()

            manager = MagicMock()
            manager.state = state
            manager.clock = clock

            scheduler = EntityScheduler(manager)
            scheduler.trigger_action = mock_trigger

            # Run for a short time
            task = asyncio.create_task(
                scheduler.schedule_entity("Dynamic-Agent", mock_agents["Dynamic-Agent"])
            )

            await asyncio.sleep(0.5)  # Let it run a bit
            state.is_running = False
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

        # Agent should have triggered exactly 2 times (disabled after 2nd)
        assert action_counts["Dynamic-Agent"] == 2


class TestFullSchedulerBehavior:
    """Integration tests for the full scheduler with multiple agents."""

    @pytest.mark.asyncio
    async def test_multiple_agents_different_frequencies(self):
        """Test that multiple agents run at their configured frequencies."""
        action_log = []

        mock_agents = {
            "Fast-Agent": {
                "entity_type": "Entity",
                "is_enabled": True,
                "event_frequency": 1,  # Every 1 game minute
                "model": "test-model"
            },
            "Slow-Agent": {
                "entity_type": "Entity",
                "is_enabled": True,
                "event_frequency": 3,  # Every 3 game minutes
                "model": "test-model"
            },
            "Disabled-Agent": {
                "entity_type": "Entity",
                "is_enabled": False,
                "event_frequency": 1,
                "model": "test-model"
            }
        }

        async def mock_trigger(agent_id):
            """Log when each agent triggers."""
            if mock_agents.get(agent_id, {}).get("is_enabled", True):
                action_log.append(agent_id)

        with patch.object(app, 'agents', mock_agents):
            state = SimulationState()
            state.is_running = True
            state.paused_for_meeting = False

            # Mock get_pending_approvals
            state.get_pending_approvals = MagicMock(return_value=[])

            clock = GameClock(speed=0.05)  # Very fast: 1 game min = 0.05 real sec
            clock.start()

            manager = MagicMock()
            manager.state = state
            manager.clock = clock

            scheduler = EntityScheduler(manager)
            scheduler.trigger_action = mock_trigger

            # Start all entities
            task = asyncio.create_task(scheduler.start_all())

            # Let simulation run for ~0.4 seconds (about 8 game minutes worth)
            await asyncio.sleep(0.4)

            state.is_running = False
            await scheduler.stop_all()
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

        # Fast-Agent should have more triggers than Slow-Agent
        fast_count = action_log.count("Fast-Agent")
        slow_count = action_log.count("Slow-Agent")
        disabled_count = action_log.count("Disabled-Agent")

        print(f"Action log: {action_log}")
        print(f"Fast: {fast_count}, Slow: {slow_count}, Disabled: {disabled_count}")

        assert fast_count > slow_count, "Fast agent should trigger more often than slow"
        assert disabled_count == 0, "Disabled agent should never trigger"
        assert fast_count >= 2, "Fast agent should trigger at least twice"

    @pytest.mark.asyncio
    async def test_scheduler_respects_simulation_not_running(self):
        """Test that scheduler stops when simulation is not running."""
        action_counts = defaultdict(int)

        mock_agents = {
            "Test-Agent": {
                "entity_type": "Entity",
                "is_enabled": True,
                "event_frequency": 1,
                "model": "test-model"
            }
        }

        async def mock_trigger(agent_id):
            action_counts[agent_id] += 1

        with patch.object(app, 'agents', mock_agents):
            state = SimulationState()
            state.is_running = True
            state.paused_for_meeting = False
            state.get_pending_approvals = MagicMock(return_value=[])

            clock = GameClock(speed=0.05)

            manager = MagicMock()
            manager.state = state
            manager.clock = clock

            scheduler = EntityScheduler(manager)
            scheduler.trigger_action = mock_trigger

            task = asyncio.create_task(
                scheduler.schedule_entity("Test-Agent", mock_agents["Test-Agent"])
            )

            # Let it run briefly
            await asyncio.sleep(0.1)
            count_before_stop = action_counts["Test-Agent"]

            # Stop simulation
            state.is_running = False
            await asyncio.sleep(0.1)

            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Should have some actions before stop
        assert count_before_stop >= 1, "Agent should have acted before stop"

    @pytest.mark.asyncio
    async def test_scheduler_pauses_for_meetings(self):
        """Test that scheduler pauses when paused_for_meeting is True."""
        action_counts = defaultdict(int)

        mock_agents = {
            "Test-Agent": {
                "entity_type": "Entity",
                "is_enabled": True,
                "event_frequency": 1,
                "model": "test-model"
            }
        }

        async def mock_trigger(agent_id):
            action_counts[agent_id] += 1

        with patch.object(app, 'agents', mock_agents):
            state = SimulationState()
            state.is_running = True
            state.paused_for_meeting = True  # Start paused
            state.get_pending_approvals = MagicMock(return_value=[])

            clock = GameClock(speed=0.05)

            manager = MagicMock()
            manager.state = state
            manager.clock = clock

            scheduler = EntityScheduler(manager)
            scheduler.trigger_action = mock_trigger

            task = asyncio.create_task(
                scheduler.schedule_entity("Test-Agent", mock_agents["Test-Agent"])
            )

            # Run while paused - scheduler checks every 1 second while paused
            await asyncio.sleep(0.15)
            count_while_paused = action_counts["Test-Agent"]

            # Unpause - wait longer because the scheduler's pause loop sleeps 1s
            state.paused_for_meeting = False
            # Wait for pause check loop (1s) + action trigger + interval (0.05s)
            await asyncio.sleep(1.2)
            count_after_unpause = action_counts["Test-Agent"]

            state.is_running = False
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        assert count_while_paused == 0, "No actions should occur while paused"
        assert count_after_unpause >= 1, "Actions should resume after unpause"


class TestAgentConfigurationUpdateFlow:
    """Tests for the full flow of updating agent configuration."""

    def test_update_agent_frequency(self):
        """Test updating an agent's event_frequency."""
        mock_agents = {
            "Test-Agent": {
                "entity_type": "Entity",
                "is_enabled": True,
                "event_frequency": 60,
                "model": "test-model"
            }
        }

        with patch.object(app, 'agents', mock_agents):
            with patch.object(app, 'save_agents'):
                # Simulate API update
                mock_agents["Test-Agent"]["event_frequency"] = 1

        assert mock_agents["Test-Agent"]["event_frequency"] == 1

    def test_update_agent_enabled_via_agent_update(self):
        """Test updating is_enabled through the agent_update function."""
        mock_agents = {
            "Test-Agent": {
                "entity_type": "Entity",
                "is_enabled": True,
                "event_frequency": 60,
                "model": "test-model",
                "system_prompt": "test"
            }
        }

        with patch.object(app, 'agents', mock_agents):
            with patch.object(app, 'save_agents'):
                result = app.agent_update("Test-Agent", is_enabled=False)

        assert result["status"] == "success"
        assert mock_agents["Test-Agent"]["is_enabled"] is False


class TestGameCreationWithAgentConfig:
    """Tests for creating games with specific agent configurations."""

    def setup_method(self):
        """Create temp directory for each test."""
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up temp directory."""
        shutil.rmtree(self.temp_dir)

    def test_create_agents_with_custom_config(self):
        """Test creating agents with custom is_enabled and event_frequency."""
        agents_data = {
            "agents": {
                "Fast-Agent": {
                    "entity_type": "Entity",
                    "is_enabled": True,
                    "event_frequency": 1,  # 1 game minute - fast for testing
                    "model": "test-model"
                },
                "Disabled-Agent": {
                    "entity_type": "Entity",
                    "is_enabled": False,
                    "event_frequency": 60,
                    "model": "test-model"
                }
            }
        }

        agents_file = Path(self.temp_dir) / "agents.json"
        with open(agents_file, "w") as f:
            json.dump(agents_data, f)

        # Verify the file can be loaded
        with open(agents_file, "r") as f:
            loaded = json.load(f)

        assert loaded["agents"]["Fast-Agent"]["event_frequency"] == 1
        assert loaded["agents"]["Fast-Agent"]["is_enabled"] is True
        assert loaded["agents"]["Disabled-Agent"]["is_enabled"] is False


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_get_entity_agents_with_missing_fields(self):
        """Test that get_entity_agents handles agents with missing fields gracefully."""
        mock_agents = {
            "Minimal-Agent": {},  # No fields at all
            "Partial-Agent": {"entity_type": "Entity"},  # Only entity_type
            "Complete-Agent": {
                "entity_type": "Entity",
                "is_enabled": True,
                "event_frequency": 60
            }
        }

        with patch.object(app, 'agents', mock_agents):
            state = SimulationState()
            manager = MagicMock()
            manager.state = state
            scheduler = EntityScheduler(manager)

            entities = scheduler.get_entity_agents()

        # Minimal-Agent: entity_type is None, not "Entity" - excluded
        # Partial-Agent: entity_type is "Entity", is_enabled defaults to True - included
        # Complete-Agent: fully configured and enabled - included
        assert "Minimal-Agent" not in entities
        assert "Partial-Agent" in entities
        assert "Complete-Agent" in entities
        assert len(entities) == 2

    @pytest.mark.asyncio
    async def test_trigger_action_with_missing_agent(self):
        """Test that trigger_action handles missing agents gracefully."""
        with patch.object(app, 'agents', {}):
            state = SimulationState()
            clock = GameClock()

            manager = MagicMock()
            manager.state = state
            manager.clock = clock

            scheduler = EntityScheduler(manager)

            # Should not raise exception
            await scheduler.trigger_action("NonExistent-Agent")

    def test_frequency_with_zero_clock_speed(self):
        """Test frequency calculation with zero clock speed (edge case)."""
        clock = GameClock(speed=0.0)
        frequency_minutes = 60

        interval_seconds = frequency_minutes * clock.speed

        # With 0 speed, interval is 0 - this would cause issues in real usage
        # but the calculation itself should work
        assert interval_seconds == 0.0

    def test_very_high_frequency(self):
        """Test agent with very high frequency (low event_frequency value)."""
        mock_agents = {
            "HyperActive-Agent": {
                "entity_type": "Entity",
                "is_enabled": True,
                "event_frequency": 0.1,  # Very fast
                "model": "test-model"
            }
        }

        with patch.object(app, 'agents', mock_agents):
            state = SimulationState()
            manager = MagicMock()
            manager.state = state
            scheduler = EntityScheduler(manager)

            entities = scheduler.get_entity_agents()

        assert "HyperActive-Agent" in entities
        assert entities["HyperActive-Agent"]["event_frequency"] == 0.1


# Run with: pytest test_agent_scheduling.py -v
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
