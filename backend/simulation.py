"""
PM1 Simulation Engine - Autonomous Entity Simulation System

This module provides a game simulation engine where entity agents act autonomously
based on configurable intervals, with LLM-driven decision making.
"""

import asyncio
import threading
import json
import uuid
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict, field
from enum import Enum

import app
from logger import setup_logger

logger = setup_logger("simulation")

# Constants
DATA_DIR = Path(__file__).parent.parent / "data"
SIMULATION_STATE_FILE = DATA_DIR / "simulation_state.json"
DEFAULT_START_TIME = datetime(2023, 10, 7, 6, 29, 0)
DEFAULT_CLOCK_SPEED = 2.0  # real seconds per game minute


class ActionType(Enum):
    DIPLOMATIC = "diplomatic"
    MILITARY = "military"
    ECONOMIC = "economic"
    INTELLIGENCE = "intelligence"
    INTERNAL = "internal"
    NONE = "none"


@dataclass
class SimulationEvent:
    """Represents an event/action in the simulation."""
    event_id: str
    timestamp: str  # Game time ISO format
    agent_id: str
    action_type: str
    summary: str  # Brief description of the action
    is_public: bool
    affected_agents: List[str] = field(default_factory=list)
    reasoning: str = ""  # Internal only, not shared

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "SimulationEvent":
        return cls(**data)


class GameClock:
    """Thread-safe game clock with configurable speed."""

    def __init__(self, speed: float = DEFAULT_CLOCK_SPEED):
        self.speed = speed  # real seconds per game minute
        self.game_time: Optional[datetime] = None
        self.is_running: bool = False
        self._start_real_time: Optional[float] = None
        self._start_game_time: Optional[datetime] = None
        self._lock = threading.Lock()

    def start(self, initial_time: datetime = None):
        """Start the clock from initial time or resume."""
        with self._lock:
            if initial_time:
                self.game_time = initial_time
            elif self.game_time is None:
                self.game_time = DEFAULT_START_TIME
            self._start_real_time = time.time()
            self._start_game_time = self.game_time
            self.is_running = True
            logger.info(f"Game clock started at {self.game_time.isoformat()}")

    def stop(self):
        """Pause the clock, preserving current game time."""
        with self._lock:
            if self.is_running:
                self.game_time = self._calculate_current_time()
                self.is_running = False
                logger.info(f"Game clock stopped at {self.game_time.isoformat()}")

    def _calculate_current_time(self) -> datetime:
        """Calculate current game time based on elapsed real time."""
        if not self._start_real_time or not self._start_game_time:
            return self.game_time or DEFAULT_START_TIME

        elapsed_real = time.time() - self._start_real_time

        # Convert real seconds to game minutes
        elapsed_game_minutes = elapsed_real / self.speed
        return self._start_game_time + timedelta(minutes=elapsed_game_minutes)

    def get_game_time(self) -> datetime:
        """Get current game time."""
        with self._lock:
            if self.is_running:
                return self._calculate_current_time()
            return self.game_time or DEFAULT_START_TIME

    def get_game_time_str(self) -> str:
        """Get current game time as ISO string."""
        return self.get_game_time().isoformat()

    def set_speed(self, speed: float):
        """Change clock speed dynamically."""
        with self._lock:
            if self.is_running:
                # Capture current time before changing speed
                self.game_time = self._calculate_current_time()
                self._start_game_time = self.game_time
                self._start_real_time = time.time()
            self.speed = speed
            logger.info(f"Clock speed set to {speed} seconds per game minute")

    def set_game_time(self, new_time: datetime):
        """Set the game clock to a specific time."""
        with self._lock:
            self.game_time = new_time
            if self.is_running:
                self._start_game_time = new_time
                self._start_real_time = time.time()
            logger.info(f"Game clock set to {new_time.isoformat()}")


class SimulationState:
    """Manages simulation state and persistence."""

    def __init__(self):
        self.is_running: bool = False
        self.clock_speed: float = DEFAULT_CLOCK_SPEED
        self.game_clock: str = DEFAULT_START_TIME.isoformat()
        self.events: List[SimulationEvent] = []
        self.agent_last_action: Dict[str, str] = {}  # agent_id -> ISO timestamp

    def load(self):
        """Load state from file."""
        if SIMULATION_STATE_FILE.exists():
            try:
                with open(SIMULATION_STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.is_running = data.get("is_running", False)
                self.clock_speed = data.get("clock_speed", DEFAULT_CLOCK_SPEED)
                self.game_clock = data.get("game_clock", DEFAULT_START_TIME.isoformat())
                self.events = [SimulationEvent.from_dict(e) for e in data.get("events", [])]
                self.agent_last_action = data.get("agent_last_action", {})
                logger.info(f"Loaded simulation state: {len(self.events)} events")
            except Exception as e:
                logger.error(f"Error loading simulation state: {e}")
        else:
            logger.info("No simulation state file found, starting fresh")

    def save(self):
        """Save state to file."""
        DATA_DIR.mkdir(exist_ok=True)
        data = {
            "is_running": self.is_running,
            "clock_speed": self.clock_speed,
            "game_clock": self.game_clock,
            "events": [e.to_dict() for e in self.events],
            "agent_last_action": self.agent_last_action
        }
        try:
            with open(SIMULATION_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.debug("Simulation state saved")
        except Exception as e:
            logger.error(f"Error saving simulation state: {e}")

    def add_event(self, event: SimulationEvent):
        """Add an event and save state."""
        self.events.append(event)
        self.agent_last_action[event.agent_id] = event.timestamp
        self.save()

    def get_recent_events(self, limit: int = 50, public_only: bool = False) -> List[SimulationEvent]:
        """Get recent events, optionally filtered."""
        events = self.events
        if public_only:
            events = [e for e in events if e.is_public]
        return events[-limit:]

    def get_agent_events(self, agent_id: str, limit: int = 10) -> List[SimulationEvent]:
        """Get events for a specific agent."""
        return [e for e in self.events if e.agent_id == agent_id][-limit:]


# LLM Prompt Template
ENTITY_ACTION_PROMPT = """You are {agent_id}, acting as an autonomous entity in a geopolitical simulation.

CURRENT GAME TIME: {game_time}

=== YOUR PROFILE ===
AGENDA: {agenda}

PRIMARY OBJECTIVES:
{primary_objectives}

HARD RULES (You MUST follow these):
{hard_rules}

=== MEMORY ===
Recent events (YOUR actions marked with "YOU:"):
{memory}

=== INSTRUCTIONS ===
Based on your agenda, objectives, and the current situation, decide on your next action.

Respond ONLY with valid JSON in this EXACT format (no other text):
{{
    "action_type": "diplomatic|military|economic|intelligence|internal|none",
    "summary": "ONE sentence describing your action (max 100 characters)",
    "is_public": true,
    "affected_entities": ["entity_id1", "entity_id2"],
    "reasoning": "Brief internal reasoning (not visible to others)"
}}

If you choose action_type "none", it means you are waiting/observing.
Keep summaries VERY SHORT - they are headlines, not articles.
is_public should be true for public actions (diplomatic statements, military movements) and false for covert actions (intelligence operations).
"""


class EventProcessor:
    """Processes entity actions into structured events using LLM."""

    def __init__(self, state: SimulationState):
        self.state = state

    def build_prompt(self, agent_id: str, agent: dict, game_time: str) -> str:
        """Build the LLM prompt for an entity action."""
        # Get agent's memory (last 20 entries) - contains both own actions and world events
        memory = app.agent_memory.get(agent_id, [])
        memory_str = "\n".join(memory[-20:]) or "No events yet."

        return ENTITY_ACTION_PROMPT.format(
            agent_id=agent_id,
            game_time=game_time,
            agenda=agent.get("agenda", "Not specified"),
            primary_objectives=agent.get("primary_objectives", "Not specified"),
            hard_rules=agent.get("hard_rules", "None"),
            memory=memory_str
        )

    def parse_llm_response(self, agent_id: str, response: str, game_time: str) -> Optional[SimulationEvent]:
        """Parse LLM response into a SimulationEvent."""
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response)
            if not json_match:
                logger.error(f"No JSON found in LLM response for {agent_id}")
                return None

            data = json.loads(json_match.group())

            # Validate and create event
            summary = data.get("summary", "No action taken")
            event = SimulationEvent(
                event_id=f"evt_{uuid.uuid4().hex[:8]}",
                timestamp=game_time,
                agent_id=agent_id,
                action_type=data.get("action_type", "none"),
                summary=summary,
                is_public=data.get("is_public", True),
                affected_agents=data.get("affected_entities", []),
                reasoning=data.get("reasoning", "")
            )
            return event

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error for {agent_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing LLM response for {agent_id}: {e}")
            return None

    def broadcast_event_to_memories(self, event: SimulationEvent):
        """Add event to relevant agents' memories."""
        # 1. Actor ALWAYS remembers their own action
        own_memory = f"[{event.timestamp}] YOU: {event.summary}"
        app.add_memory(event.agent_id, own_memory)
        logger.info(f"Memory added to {event.agent_id}: '{own_memory}'")

        # 2. If public, ALL other agents learn about it
        if event.is_public:
            memory_entry = f"[{event.timestamp}] {event.agent_id}: {event.summary}"
            for other_id in app.agents:
                if other_id != event.agent_id:
                    app.add_memory(other_id, memory_entry)
            logger.info(f"Public event broadcast to all agents: '{memory_entry}'")


class EntityScheduler:
    """Async scheduler for entity actions based on event_frequency."""

    def __init__(self, manager: "SimulationManager"):
        self.manager = manager
        self._tasks: Dict[str, asyncio.Task] = {}

    def get_entity_agents(self) -> Dict[str, dict]:
        """Get all agents with entity_type='Entity'."""
        entities = {}
        for agent_id, agent in app.agents.items():
            if agent.get("entity_type") == "Entity":
                entities[agent_id] = agent
        return entities

    async def schedule_entity(self, agent_id: str, agent: dict, initial_delay: float = 0):
        """Schedule an entity to act at intervals."""
        frequency_minutes = agent.get("event_frequency", 60)
        # Convert game minutes to real seconds
        interval_seconds = frequency_minutes * self.manager.clock.speed

        logger.info(f"Scheduling {agent_id} to act every {frequency_minutes} game minutes ({interval_seconds}s real)")

        # Staggered initial delay so entities don't all fire at once
        if initial_delay > 0:
            await asyncio.sleep(initial_delay)

        while self.manager.state.is_running:
            try:
                # Trigger action first, then wait
                await self.trigger_action(agent_id)
                if not self.manager.state.is_running:
                    break
                # Recalculate interval in case clock speed changed
                interval_seconds = frequency_minutes * self.manager.clock.speed
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in entity {agent_id} scheduler: {e}")

    async def trigger_action(self, agent_id: str):
        """Trigger an entity to take an action via LLM."""
        if agent_id not in app.agents:
            logger.warning(f"Agent {agent_id} no longer exists")
            return

        agent = app.agents[agent_id]
        game_time = self.manager.clock.get_game_time_str()

        logger.info(f"Triggering action for {agent_id} at {game_time}")

        # Build prompt
        prompt = self.manager.event_processor.build_prompt(agent_id, agent, game_time)

        # Call LLM in thread pool to avoid blocking the event loop
        result = await asyncio.to_thread(
            app.interact_simple, prompt, model=agent.get("model", "claude-sonnet-4-20250514")
        )

        if result.get("status") == "error":
            logger.error(f"LLM error for {agent_id}: {result.get('message')}")
            return

        response = result.get("response", "")

        # Parse response into event
        event = self.manager.event_processor.parse_llm_response(agent_id, response, game_time)

        if event:
            # Skip "none" actions
            if event.action_type != "none":
                # Store event
                self.manager.state.add_event(event)
                # Broadcast event to all agents' memories
                self.manager.event_processor.broadcast_event_to_memories(event)
                logger.info(f"Event created: [{event.agent_id}] {event.summary} (public={event.is_public})")
            else:
                logger.debug(f"{agent_id} chose to take no action")

    async def start_all(self):
        """Start scheduling all entities."""
        entities = self.get_entity_agents()
        logger.info(f"Starting scheduler for {len(entities)} entities")

        # Stagger entity starts by 5 seconds each to avoid LLM rate limits
        delay = 0
        for agent_id, agent in entities.items():
            task = asyncio.create_task(self.schedule_entity(agent_id, agent, initial_delay=delay))
            self._tasks[agent_id] = task
            delay += 5  # 5 second stagger between entity first actions

    async def stop_all(self):
        """Stop all entity schedulers."""
        for agent_id, task in self._tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()
        logger.info("All entity schedulers stopped")


class SimulationManager:
    """Main simulation orchestrator - singleton pattern."""

    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "SimulationManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self):
        if SimulationManager._instance is not None:
            raise RuntimeError("Use get_instance() instead")
        self.clock = GameClock()
        self.state = SimulationState()
        self.event_processor = EventProcessor(self.state)
        self.scheduler = EntityScheduler(self)
        self._simulation_task: Optional[asyncio.Task] = None
        self._save_task: Optional[asyncio.Task] = None

        # Load existing state
        self.state.load()
        if self.state.game_clock:
            self.clock.game_time = datetime.fromisoformat(self.state.game_clock)
        self.clock.speed = self.state.clock_speed

    async def start_game(self) -> dict:
        """Start the simulation."""
        if self.state.is_running:
            return {"status": "error", "message": "Simulation already running"}

        # Start clock
        self.clock.start()
        self.state.is_running = True
        self.state.game_clock = self.clock.get_game_time_str()
        self.state.save()

        # Start entity scheduler
        await self.scheduler.start_all()

        # Start periodic save task
        self._save_task = asyncio.create_task(self._periodic_save())

        logger.info("Simulation started")
        return {
            "status": "success",
            "message": "Simulation started",
            "game_time": self.clock.get_game_time_str()
        }

    async def stop_game(self) -> dict:
        """Stop the simulation and save state."""
        if not self.state.is_running:
            return {"status": "error", "message": "Simulation not running"}

        # Stop scheduler
        await self.scheduler.stop_all()

        # Stop clock
        self.clock.stop()

        # Stop save task
        if self._save_task:
            self._save_task.cancel()
            try:
                await self._save_task
            except asyncio.CancelledError:
                pass

        # Update and save state
        self.state.is_running = False
        self.state.game_clock = self.clock.get_game_time_str()
        self.state.save()

        logger.info("Simulation stopped")
        return {
            "status": "success",
            "message": "Simulation stopped",
            "game_time": self.clock.get_game_time_str()
        }

    async def _periodic_save(self):
        """Periodically save state (every 30 seconds)."""
        while self.state.is_running:
            try:
                await asyncio.sleep(30)
                self.state.game_clock = self.clock.get_game_time_str()
                self.state.save()
            except asyncio.CancelledError:
                break

    def get_status(self) -> dict:
        """Get current simulation status."""
        entities = self.scheduler.get_entity_agents()
        return {
            "status": "success",
            "is_running": self.state.is_running,
            "game_time": self.clock.get_game_time_str() if self.state.is_running else self.state.game_clock,
            "clock_speed": self.clock.speed,
            "entity_count": len(entities),
            "event_count": len(self.state.events)
        }

    def get_events(self, since: str = None, agent_id: str = None, limit: int = 100) -> List[dict]:
        """Get events with optional filters."""
        events = self.state.events

        if agent_id:
            events = [e for e in events if e.agent_id == agent_id]

        if since:
            try:
                since_dt = datetime.fromisoformat(since)
                events = [e for e in events if datetime.fromisoformat(e.timestamp) > since_dt]
            except ValueError:
                pass

        return [e.to_dict() for e in events[-limit:]]

    def set_clock_speed(self, speed: float) -> dict:
        """Set the clock speed."""
        if speed <= 0:
            return {"status": "error", "message": "Speed must be positive"}
        self.clock.set_speed(speed)
        self.state.clock_speed = speed
        self.state.game_clock = self.clock.get_game_time_str()
        self.state.save()
        return {"status": "success", "clock_speed": speed, "game_time": self.state.game_clock}

    def set_game_time(self, game_time_str: str) -> dict:
        """Set the game clock to a specific time."""
        try:
            new_time = datetime.fromisoformat(game_time_str)
            self.clock.set_game_time(new_time)
            self.state.game_clock = self.clock.get_game_time_str()
            self.state.save()
            return {"status": "success", "game_time": self.state.game_clock}
        except ValueError as e:
            return {"status": "error", "message": f"Invalid datetime format: {e}"}

    def save_state(self) -> dict:
        """Manually save the current simulation state."""
        self.state.game_clock = self.clock.get_game_time_str()
        self.state.save()
        return {"status": "success", "message": "State saved", "game_time": self.state.game_clock}


# Module-level functions for API access

async def start_game() -> dict:
    """Start the simulation."""
    manager = SimulationManager.get_instance()
    return await manager.start_game()


async def stop_game() -> dict:
    """Stop the simulation."""
    manager = SimulationManager.get_instance()
    return await manager.stop_game()


def get_status() -> dict:
    """Get simulation status."""
    manager = SimulationManager.get_instance()
    return manager.get_status()


def get_events(since: str = None, agent_id: str = None, limit: int = 100) -> List[dict]:
    """Get events with optional filters."""
    manager = SimulationManager.get_instance()
    return manager.get_events(since, agent_id, limit)


def set_clock_speed(speed: float) -> dict:
    """Set the clock speed."""
    manager = SimulationManager.get_instance()
    return manager.set_clock_speed(speed)


def set_game_time(game_time_str: str) -> dict:
    """Set the game clock to a specific time."""
    manager = SimulationManager.get_instance()
    return manager.set_game_time(game_time_str)


def save_state() -> dict:
    """Manually save the current simulation state."""
    manager = SimulationManager.get_instance()
    return manager.save_state()
