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


class TestMemoryFlow:
    """Tests for the memory broadcast system."""

    @pytest.fixture
    def setup_two_agents(self):
        """Setup mock agents and memory for testing.

        Uses real agent IDs from ENTITY_AGENT_MAP so relevance-based
        memory distribution works correctly. Both agents are Israeli
        so they're in the same entity (colleagues can see each other's actions).
        """
        # Create mock agents dict - use real agent IDs from ENTITY_AGENT_MAP
        mock_agents = {
            "IDF-Commander": {"entity_type": "Entity", "model": "test"},
            "Defense-Minister": {"entity_type": "Entity", "model": "test"}
        }
        # Create mock memory dict
        mock_memory = {
            "IDF-Commander": [],
            "Defense-Minister": []
        }
        return mock_agents, mock_memory

    def test_actor_remembers_own_action(self, setup_two_agents):
        """Test that the actor gets memory of their own action marked with YOU:"""
        mock_agents, mock_memory = setup_two_agents

        # Create processor
        state = SimulationState()
        processor = EventProcessor(state)

        # Create a public event from IDF-Commander
        event = SimulationEvent(
            event_id="evt_test001",
            timestamp="2023-10-07T08:00:00",
            agent_id="IDF-Commander",
            action_type="diplomatic",
            summary="Made a diplomatic statement",
            is_public=True,
            affected_agents=["Defense-Minister"]
        )

        # Mock app module
        with patch('simulation.app') as mock_app:
            mock_app.agents = mock_agents
            mock_app.agent_memory = mock_memory

            # Track add_memory calls
            def add_memory_side_effect(agent_id, memory_item):
                mock_memory[agent_id].append(memory_item)
                return {"status": "success"}

            mock_app.add_memory = MagicMock(side_effect=add_memory_side_effect)

            # Broadcast the event
            processor.broadcast_event_to_memories(event)

        # Verify IDF-Commander has their own action with "YOU:" prefix
        assert len(mock_memory["IDF-Commander"]) == 1
        assert "YOU:" in mock_memory["IDF-Commander"][0]
        assert "Made a diplomatic statement" in mock_memory["IDF-Commander"][0]

    def test_public_event_broadcast_to_relevant_agents(self, setup_two_agents):
        """Test that public events are broadcast to RELEVANT agents (same entity or affected)."""
        mock_agents, mock_memory = setup_two_agents

        state = SimulationState()
        processor = EventProcessor(state)

        # Create a public event - both agents are Israeli so Defense-Minister should get it
        event = SimulationEvent(
            event_id="evt_test002",
            timestamp="2023-10-07T08:00:00",
            agent_id="IDF-Commander",
            action_type="military",
            summary="Deployed forces to border",
            is_public=True,
            affected_agents=[]  # No explicit affected agents, but same entity = relevant
        )

        with patch('simulation.app') as mock_app:
            mock_app.agents = mock_agents
            mock_app.agent_memory = mock_memory

            def add_memory_side_effect(agent_id, memory_item):
                mock_memory[agent_id].append(memory_item)
                return {"status": "success"}

            mock_app.add_memory = MagicMock(side_effect=add_memory_side_effect)

            processor.broadcast_event_to_memories(event)

        # IDF-Commander should have "YOU:" version
        assert len(mock_memory["IDF-Commander"]) == 1
        assert "YOU:" in mock_memory["IDF-Commander"][0]

        # Defense-Minister should have "IDF-Commander:" version (same entity = relevant)
        assert len(mock_memory["Defense-Minister"]) == 1
        assert "IDF-Commander:" in mock_memory["Defense-Minister"][0]
        assert "YOU:" not in mock_memory["Defense-Minister"][0]
        assert "Deployed forces to border" in mock_memory["Defense-Minister"][0]

    def test_private_event_only_actor_remembers(self, setup_two_agents):
        """Test that private events are only remembered by the actor."""
        mock_agents, mock_memory = setup_two_agents

        state = SimulationState()
        processor = EventProcessor(state)

        # Create a PRIVATE event (intelligence operation)
        event = SimulationEvent(
            event_id="evt_test003",
            timestamp="2023-10-07T08:00:00",
            agent_id="IDF-Commander",
            action_type="intelligence",
            summary="Conducted covert surveillance",
            is_public=False,  # Private!
            affected_agents=["Defense-Minister"]
        )

        with patch('simulation.app') as mock_app:
            mock_app.agents = mock_agents
            mock_app.agent_memory = mock_memory

            def add_memory_side_effect(agent_id, memory_item):
                mock_memory[agent_id].append(memory_item)
                return {"status": "success"}

            mock_app.add_memory = MagicMock(side_effect=add_memory_side_effect)

            processor.broadcast_event_to_memories(event)

        # IDF-Commander should remember their own action
        assert len(mock_memory["IDF-Commander"]) == 1
        assert "YOU:" in mock_memory["IDF-Commander"][0]

        # Defense-Minister should NOT know about the private action
        assert len(mock_memory["Defense-Minister"]) == 0

    def test_memory_used_in_prompt(self, setup_two_agents):
        """Test that memory is correctly included in the prompt."""
        mock_agents, mock_memory = setup_two_agents

        # Pre-populate memory
        mock_memory["IDF-Commander"] = [
            "[2023-10-07T07:00:00] YOU: Made first statement",
            "[2023-10-07T07:30:00] Defense-Minister: Responded to statement"
        ]

        state = SimulationState()
        processor = EventProcessor(state)

        agent = {
            "agenda": "Test agenda",
            "primary_objectives": "Test objectives",
            "hard_rules": "Test rules"
        }

        with patch('simulation.app') as mock_app:
            mock_app.agent_memory = mock_memory

            prompt = processor.build_prompt("IDF-Commander", agent, "2023-10-07T08:00:00")

        # Verify memory content is in the prompt
        assert "YOU: Made first statement" in prompt
        assert "Defense-Minister: Responded to statement" in prompt
        assert "=== MEMORY ===" in prompt

    def test_multiple_turns_memory_accumulation(self, setup_two_agents):
        """Test that memory accumulates correctly over multiple turns."""
        mock_agents, mock_memory = setup_two_agents

        state = SimulationState()
        processor = EventProcessor(state)

        with patch('simulation.app') as mock_app:
            mock_app.agents = mock_agents
            mock_app.agent_memory = mock_memory

            def add_memory_side_effect(agent_id, memory_item):
                mock_memory[agent_id].append(memory_item)
                return {"status": "success"}

            mock_app.add_memory = MagicMock(side_effect=add_memory_side_effect)

            # Turn 1: IDF-Commander acts
            event1 = SimulationEvent(
                event_id="evt_turn1",
                timestamp="2023-10-07T08:00:00",
                agent_id="IDF-Commander",
                action_type="diplomatic",
                summary="Turn 1 action by IDF",
                is_public=True,
                affected_agents=[]  # Same entity = relevant
            )
            processor.broadcast_event_to_memories(event1)

            # Turn 2: Defense-Minister acts
            event2 = SimulationEvent(
                event_id="evt_turn2",
                timestamp="2023-10-07T08:05:00",
                agent_id="Defense-Minister",
                action_type="diplomatic",
                summary="Turn 2 response by Defense",
                is_public=True,
                affected_agents=[]  # Same entity = relevant
            )
            processor.broadcast_event_to_memories(event2)

        # IDF-Commander should have: own action (YOU:) + Defense-Minister's action
        assert len(mock_memory["IDF-Commander"]) == 2
        assert "YOU: Turn 1 action by IDF" in mock_memory["IDF-Commander"][0]
        assert "Defense-Minister: Turn 2 response by Defense" in mock_memory["IDF-Commander"][1]

        # Defense-Minister should have: IDF-Commander's action + own action (YOU:)
        assert len(mock_memory["Defense-Minister"]) == 2
        assert "IDF-Commander: Turn 1 action by IDF" in mock_memory["Defense-Minister"][0]
        assert "YOU: Turn 2 response by Defense" in mock_memory["Defense-Minister"][1]

    def test_system_agents_excluded_from_memory_broadcast(self):
        """Test that System-* agents don't receive memory broadcasts."""
        # Include a System-Resolver agent in mock agents (both Israeli agents + System)
        mock_agents = {
            "IDF-Commander": {"entity_type": "Entity", "model": "test"},
            "Defense-Minister": {"entity_type": "Entity", "model": "test"},
            "System-Resolver": {"entity_type": "System", "model": "test"}
        }
        mock_memory = {
            "IDF-Commander": [],
            "Defense-Minister": [],
            "System-Resolver": []
        }

        state = SimulationState()
        processor = EventProcessor(state)

        # Create a public event from IDF-Commander
        event = SimulationEvent(
            event_id="evt_test_sys",
            timestamp="2023-10-07T08:00:00",
            agent_id="IDF-Commander",
            action_type="diplomatic",
            summary="Made a statement",
            is_public=True,
            affected_agents=[]  # Same entity = Defense-Minister gets it
        )

        with patch('simulation.app') as mock_app:
            mock_app.agents = mock_agents
            mock_app.agent_memory = mock_memory

            def add_memory_side_effect(agent_id, memory_item):
                mock_memory[agent_id].append(memory_item)
                return {"status": "success"}

            mock_app.add_memory = MagicMock(side_effect=add_memory_side_effect)

            processor.broadcast_event_to_memories(event)

        # IDF-Commander should have their own action
        assert len(mock_memory["IDF-Commander"]) == 1
        assert "YOU:" in mock_memory["IDF-Commander"][0]

        # Defense-Minister should have IDF-Commander's action (same entity)
        assert len(mock_memory["Defense-Minister"]) == 1
        assert "IDF-Commander:" in mock_memory["Defense-Minister"][0]

        # System-Resolver should have NO memory (excluded)
        assert len(mock_memory["System-Resolver"]) == 0

    def test_system_agent_events_not_broadcast(self):
        """Test that events from System-* agents don't get broadcast."""
        mock_agents = {
            "IDF-Commander": {"entity_type": "Entity", "model": "test"},
            "System-Resolver": {"entity_type": "System", "model": "test"}
        }
        mock_memory = {
            "IDF-Commander": [],
            "System-Resolver": []
        }

        state = SimulationState()
        processor = EventProcessor(state)

        # Create an event FROM System-Resolver
        event = SimulationEvent(
            event_id="res_test",
            timestamp="2023-10-07T08:00:00",
            agent_id="System-Resolver",
            action_type="resolution",
            summary="Resolved event",
            is_public=True,
            affected_agents=[]
        )

        with patch('simulation.app') as mock_app:
            mock_app.agents = mock_agents
            mock_app.agent_memory = mock_memory

            def add_memory_side_effect(agent_id, memory_item):
                mock_memory[agent_id].append(memory_item)
                return {"status": "success"}

            mock_app.add_memory = MagicMock(side_effect=add_memory_side_effect)

            processor.broadcast_event_to_memories(event)

        # No one should get memory from System-Resolver events
        assert len(mock_memory["IDF-Commander"]) == 0
        assert len(mock_memory["System-Resolver"]) == 0


class TestResolverFiltering:
    """Tests for the resolver's event filtering logic."""

    def test_get_events_filters_by_status(self):
        """Test that resolver only gets events with immediate/pending status."""
        state = SimulationState()

        # Add events with different statuses
        with patch.object(state, 'save'):
            # Event 1: immediate (should be included)
            event1 = SimulationEvent(
                event_id="evt_1",
                timestamp="2023-10-07T08:00:00",
                agent_id="Agent-A",
                action_type="diplomatic",
                summary="Immediate event",
                is_public=True,
                resolution_status="immediate"
            )
            state.add_event(event1)

            # Event 2: resolved (should be excluded)
            event2 = SimulationEvent(
                event_id="evt_2",
                timestamp="2023-10-07T08:01:00",
                agent_id="Agent-A",
                action_type="diplomatic",
                summary="Resolved event",
                is_public=True,
                resolution_status="resolved"
            )
            state.add_event(event2)

            # Event 3: pending (should be included)
            event3 = SimulationEvent(
                event_id="evt_3",
                timestamp="2023-10-07T08:02:00",
                agent_id="Agent-A",
                action_type="intelligence",
                summary="Pending event",
                is_public=False,
                resolution_status="pending"
            )
            state.add_event(event3)

            # Event 4: failed (should be excluded)
            event4 = SimulationEvent(
                event_id="evt_4",
                timestamp="2023-10-07T08:03:00",
                agent_id="Agent-A",
                action_type="military",
                summary="Failed event",
                is_public=True,
                resolution_status="failed"
            )
            state.add_event(event4)

        # Create resolver and get events to resolve
        from simulation import ResolverProcessor, KPIManager
        kpi_manager = KPIManager()
        resolver = ResolverProcessor(state, kpi_manager)

        events = resolver.get_events_to_resolve()

        # Should only include immediate and pending
        event_ids = [e.event_id for e in events]
        assert "evt_1" in event_ids  # immediate
        assert "evt_2" not in event_ids  # resolved - excluded
        assert "evt_3" in event_ids  # pending
        assert "evt_4" not in event_ids  # failed - excluded

    def test_events_with_resolution_event_id_excluded(self):
        """Test that events already linked to a resolution are excluded."""
        state = SimulationState()

        with patch.object(state, 'save'):
            # Event with resolution_event_id set (already resolved)
            event = SimulationEvent(
                event_id="evt_linked",
                timestamp="2023-10-07T08:00:00",
                agent_id="Agent-A",
                action_type="diplomatic",
                summary="Already linked",
                is_public=True,
                resolution_status="immediate",  # Status says immediate but...
                resolution_event_id="res_123"  # ...it has a resolution link
            )
            state.add_event(event)

        from simulation import ResolverProcessor, KPIManager
        kpi_manager = KPIManager()
        resolver = ResolverProcessor(state, kpi_manager)

        events = resolver.get_events_to_resolve()

        # Should be empty - the only event has resolution_event_id
        assert len(events) == 0
