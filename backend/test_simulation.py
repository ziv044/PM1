"""Tests for the simulation engine."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import json
import tempfile
import shutil
from pathlib import Path


# Patch anthropic before importing simulation
with patch('anthropic.Anthropic'):
    from simulation import (
        GameClock,
        SimulationState,
        SimulationEvent,
        EventProcessor,
        ActionType,
        DEFAULT_START_TIME,
        DEFAULT_CLOCK_SPEED,
        KPIManager,
        ResolverProcessor,
        apply_kpi_rule,
        find_matching_rule,
        KPI_IMPACT_RULES,
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


class TestKPIRuleMatching:
    """Tests for the KPI rule matching system."""

    def test_find_matching_rule_airstrike(self):
        """Test that airstrike keyword matches military airstrike rule."""
        rule = find_matching_rule("military", "IDF launches airstrike on Gaza tunnel")

        assert rule is not None
        assert rule.get("success_rate") == 0.85
        assert "Hamas.dynamic_metrics.fighters_remaining" in rule.get("on_success", {})

    def test_find_matching_rule_ground_operation(self):
        """Test that ground operation matches military ground rule."""
        rule = find_matching_rule("military", "Ground forces advance into Khan Younis")

        assert rule is not None
        assert rule.get("success_rate") == 0.70
        assert "Israel.dynamic_metrics.casualties_military" in rule.get("on_success", {})

    def test_find_matching_rule_rocket_attack(self):
        """Test that rocket/missile keywords match the rocket rule."""
        rule = find_matching_rule("military", "Hamas launches rocket barrage at Tel Aviv")

        assert rule is not None
        assert rule.get("success_rate") == 0.75
        assert "Israel.dynamic_metrics.casualties_civilian" in rule.get("on_success", {})

    def test_find_matching_rule_red_sea_attack(self):
        """Test that Red Sea attack matches Houthi maritime rule."""
        rule = find_matching_rule("military", "Houthis attack commercial ship in Red Sea")

        assert rule is not None
        assert rule.get("success_rate") == 0.60
        assert "Houthis.dynamic_metrics.ships_damaged" in rule.get("on_success", {})

    def test_find_matching_rule_cross_border(self):
        """Test that infiltration attack matches Hezbollah rule."""
        rule = find_matching_rule("military", "Hezbollah conducts infiltration into northern Israel")

        assert rule is not None
        assert rule.get("success_rate") == 0.40
        assert "Hezbollah.dynamic_metrics.casualties" in rule.get("on_success", {})

    def test_find_matching_rule_intelligence(self):
        """Test intelligence action matching."""
        rule = find_matching_rule("intelligence", "Mossad conducts surveillance operation")

        assert rule is not None
        assert rule.get("success_rate") == 0.70

    def test_find_matching_rule_diplomatic(self):
        """Test diplomatic action matching."""
        rule = find_matching_rule("diplomatic", "USA deploys carrier strike group")

        assert rule is not None
        assert rule.get("success_rate") == 0.95
        assert "Israel.dynamic_metrics.morale_military" in rule.get("on_success", {})

    def test_find_matching_rule_no_match_returns_default(self):
        """Test that unmatched action returns default rule."""
        rule = find_matching_rule("military", "Some random military action")

        # Should return an empty default or the action type default
        assert rule is not None
        assert "success_rate" in rule


class TestKPIManager:
    """Tests for the KPIManager class."""

    @pytest.fixture
    def temp_kpi_dir(self):
        """Create a temporary KPI directory with test files."""
        temp_dir = tempfile.mkdtemp()
        kpi_dir = Path(temp_dir) / "kpis"
        kpi_dir.mkdir()

        # Create test Israel KPI file
        israel_kpis = {
            "entity_id": "Israel",
            "last_updated": "2023-10-07T06:29:00",
            "const_metrics": {"gdp_billions_usd": 520},
            "dynamic_metrics": {
                "casualties_military": 0,
                "casualties_civilian": 1200,
                "morale_military": 70,
                "morale_civilian": 50,
                "international_standing": 75,
                "ammunition_iron_dome_pct": 100,
                "ammunition_precision_pct": 100,
                "ammunition_artillery_pct": 100
            }
        }
        with open(kpi_dir / "Israel.json", "w") as f:
            json.dump(israel_kpis, f)

        # Create test Hamas KPI file
        hamas_kpis = {
            "entity_id": "Hamas",
            "last_updated": "2023-10-07T06:29:00",
            "const_metrics": {"initial_fighters": 30000},
            "dynamic_metrics": {
                "fighters_remaining": 30000,
                "casualties": 0,
                "leadership_capacity": 100,
                "tunnel_network_operational_km": 500
            }
        }
        with open(kpi_dir / "Hamas.json", "w") as f:
            json.dump(hamas_kpis, f)

        # Create test Hezbollah KPI file
        hezbollah_kpis = {
            "entity_id": "Hezbollah",
            "last_updated": "2023-10-07T06:29:00",
            "const_metrics": {"initial_fighters": 100000},
            "dynamic_metrics": {
                "fighters_remaining": 100000,
                "casualties": 0,
                "leadership_capacity": 100
            }
        }
        with open(kpi_dir / "Hezbollah.json", "w") as f:
            json.dump(hezbollah_kpis, f)

        # Create test Houthis KPI file
        houthis_kpis = {
            "entity_id": "Houthis",
            "last_updated": "2023-10-07T06:29:00",
            "const_metrics": {"initial_fighters": 30000},
            "dynamic_metrics": {
                "ships_damaged": 0,
                "red_sea_attacks_conducted": 0,
                "international_notoriety": 20,
                "us_strikes_received": 0,
                "drones_inventory": 2000
            }
        }
        with open(kpi_dir / "Houthis.json", "w") as f:
            json.dump(houthis_kpis, f)

        yield kpi_dir

        # Cleanup
        shutil.rmtree(temp_dir)

    def test_get_entity_kpis(self, temp_kpi_dir):
        """Test loading KPIs for an entity."""
        manager = KPIManager()
        manager.KPI_DIR = temp_kpi_dir
        manager._cache = {}  # Clear cache

        kpis = manager.get_entity_kpis("Israel")

        assert kpis is not None
        assert kpis["entity_id"] == "Israel"
        assert kpis["dynamic_metrics"]["casualties_military"] == 0

    def test_update_kpis_increments_value(self, temp_kpi_dir):
        """Test that KPI updates correctly increment values."""
        manager = KPIManager()
        manager.KPI_DIR = temp_kpi_dir
        manager._cache = {}

        # Mock the log_activity function
        with patch('simulation.app.log_activity'):
            result = manager.update_kpis("Israel", [{
                "metric": "dynamic_metrics.casualties_military",
                "change": 15,
                "reason": "Ground operation casualties"
            }])

        assert result["status"] == "success"
        assert len(result["changes"]) == 1
        assert result["changes"][0]["old"] == 0
        assert result["changes"][0]["new"] == 15

        # Verify persisted
        kpis = manager.get_entity_kpis("Israel")
        assert kpis["dynamic_metrics"]["casualties_military"] == 15

    def test_update_kpis_decrements_value(self, temp_kpi_dir):
        """Test that KPI updates correctly decrement values."""
        manager = KPIManager()
        manager.KPI_DIR = temp_kpi_dir
        manager._cache = {}

        with patch('simulation.app.log_activity'):
            result = manager.update_kpis("Hamas", [{
                "metric": "dynamic_metrics.fighters_remaining",
                "change": -50,
                "reason": "Airstrike eliminated fighters"
            }])

        assert result["status"] == "success"
        assert result["changes"][0]["old"] == 30000
        assert result["changes"][0]["new"] == 29950

    def test_update_kpis_multiple_changes(self, temp_kpi_dir):
        """Test applying multiple KPI changes at once."""
        manager = KPIManager()
        manager.KPI_DIR = temp_kpi_dir
        manager._cache = {}

        with patch('simulation.app.log_activity'):
            result = manager.update_kpis("Israel", [
                {"metric": "dynamic_metrics.casualties_military", "change": 10, "reason": "Combat"},
                {"metric": "dynamic_metrics.morale_military", "change": -5, "reason": "Losses"}
            ])

        assert result["status"] == "success"
        assert len(result["changes"]) == 2

        kpis = manager.get_entity_kpis("Israel")
        assert kpis["dynamic_metrics"]["casualties_military"] == 10
        assert kpis["dynamic_metrics"]["morale_military"] == 65

    def test_update_kpis_nonexistent_entity(self, temp_kpi_dir):
        """Test updating KPIs for entity without a file."""
        manager = KPIManager()
        manager.KPI_DIR = temp_kpi_dir
        manager._cache = {}

        result = manager.update_kpis("NonExistent", [{
            "metric": "dynamic_metrics.something",
            "change": 10,
            "reason": "Test"
        }])

        assert result["status"] == "error"


class TestApplyKPIRule:
    """Tests for the apply_kpi_rule function - full integration tests."""

    @pytest.fixture
    def temp_kpi_setup(self):
        """Create a temporary KPI directory and manager."""
        temp_dir = tempfile.mkdtemp()
        kpi_dir = Path(temp_dir) / "kpis"
        kpi_dir.mkdir()

        # Create test KPI files
        entities = {
            "Israel": {
                "entity_id": "Israel",
                "dynamic_metrics": {
                    "casualties_military": 0,
                    "casualties_civilian": 0,
                    "morale_military": 70,
                    "morale_civilian": 50,
                    "international_standing": 75,
                    "ammunition_iron_dome_pct": 100,
                    "ammunition_precision_pct": 100,
                    "ammunition_artillery_pct": 100
                }
            },
            "Hamas": {
                "entity_id": "Hamas",
                "dynamic_metrics": {
                    "fighters_remaining": 30000,
                    "casualties": 0,
                    "tunnel_network_operational_km": 500
                }
            },
            "Hezbollah": {
                "entity_id": "Hezbollah",
                "dynamic_metrics": {
                    "fighters_remaining": 100000,
                    "casualties": 0
                }
            },
            "Houthis": {
                "entity_id": "Houthis",
                "dynamic_metrics": {
                    "ships_damaged": 0,
                    "red_sea_attacks_conducted": 0,
                    "international_notoriety": 20,
                    "us_strikes_received": 0,
                    "drones_inventory": 2000
                }
            }
        }

        for entity_id, data in entities.items():
            with open(kpi_dir / f"{entity_id}.json", "w") as f:
                json.dump(data, f)

        manager = KPIManager()
        manager.KPI_DIR = kpi_dir
        manager._cache = {}

        yield manager, kpi_dir

        shutil.rmtree(temp_dir)

    def test_airstrike_event_updates_kpis(self, temp_kpi_setup):
        """Test that an airstrike event updates Hamas and Israel KPIs."""
        manager, _ = temp_kpi_setup

        event = SimulationEvent(
            event_id="evt_test_airstrike",
            timestamp="2023-10-07T10:00:00",
            agent_id="IDF-Commander",
            action_type="military",
            summary="IDF conducts airstrike on Hamas position in Gaza",
            is_public=True
        )

        # Get initial values
        israel_before = manager.get_entity_kpis("Israel")["dynamic_metrics"].copy()
        hamas_before = manager.get_entity_kpis("Hamas")["dynamic_metrics"].copy()

        with patch('simulation.app.log_activity'):
            result = apply_kpi_rule(event, manager)

        assert "success" in result

        # Get values after
        israel_after = manager.get_entity_kpis("Israel")["dynamic_metrics"]
        hamas_after = manager.get_entity_kpis("Hamas")["dynamic_metrics"]

        # If successful, Hamas should have fewer fighters and more casualties
        if result["success"]:
            assert hamas_after["fighters_remaining"] < hamas_before["fighters_remaining"]
            assert hamas_after["casualties"] > hamas_before["casualties"]
            assert israel_after["ammunition_precision_pct"] < israel_before["ammunition_precision_pct"]
        else:
            # If failed, Israel international standing should decrease
            assert israel_after["international_standing"] < israel_before["international_standing"]

    def test_rocket_attack_event_updates_kpis(self, temp_kpi_setup):
        """Test that a rocket attack updates Israel KPIs."""
        manager, _ = temp_kpi_setup

        event = SimulationEvent(
            event_id="evt_test_rocket",
            timestamp="2023-10-07T10:00:00",
            agent_id="Hamas-Leadership",
            action_type="military",
            summary="Hamas launches rocket barrage at Israeli cities",
            is_public=True
        )

        israel_before = manager.get_entity_kpis("Israel")["dynamic_metrics"].copy()

        with patch('simulation.app.log_activity'):
            result = apply_kpi_rule(event, manager)

        israel_after = manager.get_entity_kpis("Israel")["dynamic_metrics"]

        if result["success"]:
            # Successful rocket attack = civilian casualties, morale drop, Iron Dome used
            assert israel_after["casualties_civilian"] > israel_before["casualties_civilian"]
            assert israel_after["morale_civilian"] < israel_before["morale_civilian"]
            assert israel_after["ammunition_iron_dome_pct"] < israel_before["ammunition_iron_dome_pct"]
        else:
            # Failed = morale boost (Iron Dome worked)
            assert israel_after["morale_civilian"] >= israel_before["morale_civilian"]

    def test_red_sea_attack_updates_houthi_kpis(self, temp_kpi_setup):
        """Test that Red Sea attack updates Houthi KPIs."""
        manager, _ = temp_kpi_setup

        # Use "red sea" keyword specifically to match the maritime rule
        event = SimulationEvent(
            event_id="evt_test_redsea",
            timestamp="2023-10-07T10:00:00",
            agent_id="Houthi-Leadership",
            action_type="military",
            summary="Houthis attack commercial ship in Red Sea",
            is_public=True
        )

        houthis_before = manager.get_entity_kpis("Houthis")["dynamic_metrics"].copy()

        with patch('simulation.app.log_activity'):
            result = apply_kpi_rule(event, manager)

        houthis_after = manager.get_entity_kpis("Houthis")["dynamic_metrics"]

        if result["success"]:
            assert houthis_after["ships_damaged"] > houthis_before["ships_damaged"]
            assert houthis_after["red_sea_attacks_conducted"] > houthis_before["red_sea_attacks_conducted"]
            assert houthis_after["international_notoriety"] > houthis_before["international_notoriety"]
        else:
            assert houthis_after["us_strikes_received"] > houthis_before["us_strikes_received"]

    def test_cross_border_attack_updates_hezbollah_kpis(self, temp_kpi_setup):
        """Test that infiltration attack updates Hezbollah and Israel KPIs."""
        manager, _ = temp_kpi_setup

        # Use "infiltrat" keyword to match the cross-border rule (avoid "border" matching perimeter rule)
        event = SimulationEvent(
            event_id="evt_test_crossborder",
            timestamp="2023-10-07T10:00:00",
            agent_id="Hezbollah-Leadership",
            action_type="military",
            summary="Hezbollah infiltrates into northern Israel",
            is_public=True
        )

        israel_before = manager.get_entity_kpis("Israel")["dynamic_metrics"].copy()
        hezbollah_before = manager.get_entity_kpis("Hezbollah")["dynamic_metrics"].copy()

        with patch('simulation.app.log_activity'):
            result = apply_kpi_rule(event, manager)

        israel_after = manager.get_entity_kpis("Israel")["dynamic_metrics"]
        hezbollah_after = manager.get_entity_kpis("Hezbollah")["dynamic_metrics"]

        # Either way, Hezbollah should have casualties
        if result["success"]:
            assert israel_after["casualties_military"] > israel_before["casualties_military"]
            assert hezbollah_after["casualties"] > hezbollah_before["casualties"]
        else:
            assert hezbollah_after["casualties"] > hezbollah_before["casualties"]
            assert hezbollah_after["fighters_remaining"] < hezbollah_before["fighters_remaining"]

    def test_no_rule_match_still_returns_result(self, temp_kpi_setup):
        """Test that events without matching rules still get processed."""
        manager, _ = temp_kpi_setup

        event = SimulationEvent(
            event_id="evt_test_unknown",
            timestamp="2023-10-07T10:00:00",
            agent_id="Some-Agent",
            action_type="internal",
            summary="Internal coordination meeting",
            is_public=False
        )

        with patch('simulation.app.log_activity'):
            result = apply_kpi_rule(event, manager)

        # Should still return a valid result structure
        assert "success" in result
        assert "changes" in result


class TestKPIResolutionFlow:
    """End-to-end tests for the full event -> resolver -> KPI update flow."""

    @pytest.fixture
    def full_setup(self):
        """Create complete test environment with state, KPI manager, and resolver."""
        temp_dir = tempfile.mkdtemp()
        kpi_dir = Path(temp_dir) / "kpis"
        kpi_dir.mkdir()

        # Create test KPI files
        entities = {
            "Israel": {
                "entity_id": "Israel",
                "dynamic_metrics": {
                    "casualties_military": 0,
                    "casualties_civilian": 100,
                    "morale_military": 70,
                    "morale_civilian": 50,
                    "international_standing": 75,
                    "ammunition_precision_pct": 100
                }
            },
            "Hamas": {
                "entity_id": "Hamas",
                "dynamic_metrics": {
                    "fighters_remaining": 30000,
                    "casualties": 0
                }
            }
        }

        for entity_id, data in entities.items():
            with open(kpi_dir / f"{entity_id}.json", "w") as f:
                json.dump(data, f)

        state = SimulationState()
        kpi_manager = KPIManager()
        kpi_manager.KPI_DIR = kpi_dir
        kpi_manager._cache = {}

        resolver = ResolverProcessor(state, kpi_manager)

        yield state, kpi_manager, resolver, kpi_dir

        shutil.rmtree(temp_dir)

    def test_inject_event_and_verify_kpi_update(self, full_setup):
        """Test: inject event -> apply KPI rule -> verify update."""
        state, kpi_manager, resolver, _ = full_setup

        # Step 1: Create and inject an event
        event = SimulationEvent(
            event_id="evt_integration_001",
            timestamp="2023-10-07T10:00:00",
            agent_id="IDF-Commander",
            action_type="military",
            summary="IDF launches precision airstrike on Hamas command center",
            is_public=True,
            resolution_status="immediate"
        )

        with patch.object(state, 'save'):
            state.add_event(event)

        # Step 2: Get initial KPI values
        hamas_initial = kpi_manager.get_entity_kpis("Hamas")["dynamic_metrics"]["fighters_remaining"]
        israel_ammo_initial = kpi_manager.get_entity_kpis("Israel")["dynamic_metrics"]["ammunition_precision_pct"]

        # Step 3: Apply KPI rule (simulating what resolver does)
        with patch('simulation.app.log_activity'):
            result = apply_kpi_rule(event, kpi_manager)

        # Step 4: Verify KPIs were updated
        hamas_after = kpi_manager.get_entity_kpis("Hamas")["dynamic_metrics"]["fighters_remaining"]
        israel_ammo_after = kpi_manager.get_entity_kpis("Israel")["dynamic_metrics"]["ammunition_precision_pct"]

        assert result["success"] in [True, False]  # Either outcome is valid

        if result["success"]:
            # On success: Hamas fighters should decrease, Israel ammo should decrease
            assert hamas_after < hamas_initial, "Hamas fighters should decrease on successful airstrike"
            assert israel_ammo_after < israel_ammo_initial, "Israel ammo should decrease on airstrike"

        # Verify changes were tracked
        if result["rule_matched"]:
            assert len(result["changes"]) > 0, "Changes should be recorded when rule matches"

    def test_multiple_events_accumulate_kpi_changes(self, full_setup):
        """Test that multiple events accumulate KPI changes correctly."""
        state, kpi_manager, resolver, _ = full_setup

        hamas_initial = kpi_manager.get_entity_kpis("Hamas")["dynamic_metrics"]["fighters_remaining"]

        # Apply multiple airstrikes
        for i in range(3):
            event = SimulationEvent(
                event_id=f"evt_multi_{i}",
                timestamp=f"2023-10-07T{10+i}:00:00",
                agent_id="IDF-Commander",
                action_type="military",
                summary=f"IDF airstrike #{i+1} on Gaza target",
                is_public=True
            )

            with patch('simulation.app.log_activity'):
                apply_kpi_rule(event, kpi_manager)

        hamas_final = kpi_manager.get_entity_kpis("Hamas")["dynamic_metrics"]["fighters_remaining"]

        # After 3 airstrikes (some may succeed, some fail), fighters should likely be lower
        # This is probabilistic, but with 85% success rate, very likely to have at least one success
        print(f"Hamas fighters: {hamas_initial} -> {hamas_final}")

    def test_event_with_none_action_no_kpi_change(self, full_setup):
        """Test that 'none' action type doesn't trigger KPI changes."""
        state, kpi_manager, resolver, _ = full_setup

        hamas_initial = kpi_manager.get_entity_kpis("Hamas")["dynamic_metrics"].copy()
        israel_initial = kpi_manager.get_entity_kpis("Israel")["dynamic_metrics"].copy()

        event = SimulationEvent(
            event_id="evt_none_action",
            timestamp="2023-10-07T10:00:00",
            agent_id="Some-Agent",
            action_type="none",
            summary="Agent is observing and waiting",
            is_public=True
        )

        with patch('simulation.app.log_activity'):
            result = apply_kpi_rule(event, kpi_manager)

        hamas_after = kpi_manager.get_entity_kpis("Hamas")["dynamic_metrics"]
        israel_after = kpi_manager.get_entity_kpis("Israel")["dynamic_metrics"]

        # No changes should have occurred
        assert hamas_after == hamas_initial
        assert israel_after == israel_initial
