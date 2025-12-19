"""Tests for the simulation engine."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import json


# Patch anthropic before importing simulation
with patch('anthropic.Anthropic'):
    from simulation import (
        GameClock,
        SimulationState,
        SimulationEvent,
        EventProcessor,
        ActionType,
        DEFAULT_START_TIME,
        DEFAULT_CLOCK_SPEED
    )


class TestGameClock:
    """Tests for the GameClock class."""

    def test_init_defaults(self):
        clock = GameClock()
        assert clock.speed == DEFAULT_CLOCK_SPEED
        assert clock.is_running is False

    def test_init_custom_speed(self):
        clock = GameClock(speed=5.0)
        assert clock.speed == 5.0

    def test_start_with_initial_time(self):
        clock = GameClock()
        start_time = datetime(2024, 1, 1, 12, 0, 0)
        clock.start(initial_time=start_time)

        assert clock.is_running is True
        assert clock.game_time == start_time

    def test_start_default_time(self):
        clock = GameClock()
        clock.start()

        assert clock.is_running is True
        assert clock.game_time == DEFAULT_START_TIME

    def test_stop(self):
        clock = GameClock()
        clock.start()
        clock.stop()

        assert clock.is_running is False

    def test_get_game_time_str(self):
        clock = GameClock()
        clock.start()
        time_str = clock.get_game_time_str()

        assert isinstance(time_str, str)
        assert "T" in time_str  # ISO format

    def test_set_speed(self):
        clock = GameClock()
        clock.set_speed(10.0)

        assert clock.speed == 10.0


class TestSimulationEvent:
    """Tests for the SimulationEvent dataclass."""

    def test_create_event(self):
        event = SimulationEvent(
            event_id="evt_12345678",
            timestamp="2023-10-07T06:30:00",
            agent_id="test-agent",
            action_type="diplomatic",
            summary="Test action",
            is_public=True,
            affected_agents=["agent2"],
            reasoning="Test reasoning"
        )

        assert event.event_id == "evt_12345678"
        assert event.agent_id == "test-agent"
        assert event.action_type == "diplomatic"
        assert event.is_public is True

    def test_to_dict(self):
        event = SimulationEvent(
            event_id="evt_12345678",
            timestamp="2023-10-07T06:30:00",
            agent_id="test-agent",
            action_type="diplomatic",
            summary="Test action",
            is_public=True
        )

        result = event.to_dict()
        assert isinstance(result, dict)
        assert result["event_id"] == "evt_12345678"
        assert result["agent_id"] == "test-agent"

    def test_from_dict(self):
        data = {
            "event_id": "evt_12345678",
            "timestamp": "2023-10-07T06:30:00",
            "agent_id": "test-agent",
            "action_type": "diplomatic",
            "summary": "Test action",
            "is_public": True,
            "affected_agents": [],
            "reasoning": ""
        }

        event = SimulationEvent.from_dict(data)
        assert event.event_id == "evt_12345678"
        assert event.agent_id == "test-agent"


class TestSimulationState:
    """Tests for the SimulationState class."""

    def test_init(self):
        state = SimulationState()
        assert state.is_running is False
        assert state.clock_speed == DEFAULT_CLOCK_SPEED
        assert state.events == []

    def test_add_event(self):
        state = SimulationState()
        event = SimulationEvent(
            event_id="evt_12345678",
            timestamp="2023-10-07T06:30:00",
            agent_id="test-agent",
            action_type="diplomatic",
            summary="Test action",
            is_public=True
        )

        # Mock save to avoid file I/O
        with patch.object(state, 'save'):
            state.add_event(event)

        assert len(state.events) == 1
        assert state.agent_last_action["test-agent"] == "2023-10-07T06:30:00"

    def test_get_recent_events(self):
        state = SimulationState()

        # Add multiple events
        with patch.object(state, 'save'):
            for i in range(10):
                event = SimulationEvent(
                    event_id=f"evt_{i}",
                    timestamp=f"2023-10-07T06:{i:02d}:00",
                    agent_id="test-agent",
                    action_type="diplomatic",
                    summary=f"Event {i}",
                    is_public=(i % 2 == 0)  # Alternating public/private
                )
                state.add_event(event)

        # Get last 5 events
        recent = state.get_recent_events(limit=5)
        assert len(recent) == 5

        # Get only public events
        public = state.get_recent_events(public_only=True)
        assert all(e.is_public for e in public)

    def test_get_agent_events(self):
        state = SimulationState()

        with patch.object(state, 'save'):
            for i in range(5):
                event = SimulationEvent(
                    event_id=f"evt_{i}",
                    timestamp=f"2023-10-07T06:{i:02d}:00",
                    agent_id="agent-1" if i % 2 == 0 else "agent-2",
                    action_type="diplomatic",
                    summary=f"Event {i}",
                    is_public=True
                )
                state.add_event(event)

        agent1_events = state.get_agent_events("agent-1")
        assert len(agent1_events) == 3
        assert all(e.agent_id == "agent-1" for e in agent1_events)


class TestEventProcessor:
    """Tests for the EventProcessor class."""

    @pytest.fixture
    def processor(self):
        state = SimulationState()
        return EventProcessor(state)

    def test_build_prompt(self, processor):
        agent = {
            "agenda": "Test agenda",
            "primary_objectives": "Objective 1",
            "hard_rules": "Rule 1"
        }

        prompt = processor.build_prompt("test-agent", agent, "2023-10-07T06:30:00")

        assert "test-agent" in prompt
        assert "Test agenda" in prompt
        assert "Objective 1" in prompt
        assert "Rule 1" in prompt
        assert "2023-10-07T06:30:00" in prompt

    def test_parse_llm_response_valid(self, processor):
        response = json.dumps({
            "action_type": "diplomatic",
            "summary": "Made a statement",
            "is_public": True,
            "affected_entities": ["agent-2"],
            "reasoning": "Strategic"
        })

        event = processor.parse_llm_response("test-agent", response, "2023-10-07T06:30:00")

        assert event is not None
        assert event.agent_id == "test-agent"
        assert event.action_type == "diplomatic"
        assert event.summary == "Made a statement"
        assert event.is_public is True

    def test_parse_llm_response_with_extra_text(self, processor):
        response = """Here is my response:
        {
            "action_type": "military",
            "summary": "Deployed forces",
            "is_public": true,
            "affected_entities": [],
            "reasoning": "Defense"
        }
        That's my decision."""

        event = processor.parse_llm_response("test-agent", response, "2023-10-07T06:30:00")

        assert event is not None
        assert event.action_type == "military"

    def test_parse_llm_response_invalid_json(self, processor):
        response = "This is not valid JSON"

        event = processor.parse_llm_response("test-agent", response, "2023-10-07T06:30:00")

        assert event is None

    def test_parse_llm_response_no_json(self, processor):
        response = "No JSON here at all"

        event = processor.parse_llm_response("test-agent", response, "2023-10-07T06:30:00")

        assert event is None


class TestActionType:
    """Tests for the ActionType enum."""

    def test_action_types(self):
        assert ActionType.DIPLOMATIC.value == "diplomatic"
        assert ActionType.MILITARY.value == "military"
        assert ActionType.ECONOMIC.value == "economic"
        assert ActionType.INTELLIGENCE.value == "intelligence"
        assert ActionType.INTERNAL.value == "internal"
        assert ActionType.NONE.value == "none"
