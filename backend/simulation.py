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


# Entity-Agent Mapping for relevance-based memory distribution
# Agents are grouped by the entity they represent
ENTITY_AGENT_MAP: Dict[str, List[str]] = {
    "Israel": [
        "Head-Of-Shabak", "Head-Of-Mossad", "IDF-Commander", "Defense-Minister",
        "Treasury-Minister", "Foreign-Minister", "Bank-of-Israel",
        "Media-Channel-12", "Media-Channel-14"
    ],
    "USA": ["USA-President", "USA-Secretary-of-State"],
    "UK": ["UK-Prime-Minister"],
    "Russia": ["Russia-President"],
    "Iran": ["Iran-Ayatollah", "Iran-President"],
    "Egypt": ["Egypt-President"],
    "Hamas": ["Hamas-Leader", "Hamas-Gaza"],
    "PLO": ["PLO-Prime-Minister", "PLO-President"],
    "North-Korea": ["North-Korea-Supreme-Leader"],
    "UN": ["UN-Secretary-General"],
    "Gaza": [],  # Region, not an actor with agents
    "IDF": [],   # Subsumed under Israel agents
}

# Reverse map: agent_id -> entity
AGENT_ENTITY_MAP: Dict[str, str] = {}
for entity, agents in ENTITY_AGENT_MAP.items():
    for agent in agents:
        AGENT_ENTITY_MAP[agent] = entity


def get_entity_for_agent(agent_id: str) -> Optional[str]:
    """Get the entity that an agent belongs to."""
    return AGENT_ENTITY_MAP.get(agent_id)


def get_agents_for_entity(entity: str) -> List[str]:
    """Get all agents that belong to an entity."""
    return ENTITY_AGENT_MAP.get(entity, [])


def get_relevant_agents_for_event(event: "SimulationEvent") -> set:
    """Determine which agents should receive memory of this event.

    Returns agents based on:
    1. Same entity as the actor (colleagues see each other's actions)
    2. Agents listed in affected_agents (direct targets)
    3. All agents of affected entities

    Excludes:
    - The actor themselves (handled separately with YOU: prefix)
    - System-* agents (internal system components)
    """
    relevant = set()

    # 1. Agents from same entity as actor (colleagues)
    actor_entity = get_entity_for_agent(event.agent_id)
    if actor_entity:
        relevant.update(get_agents_for_entity(actor_entity))

    # 2. Process affected_agents - can be agent IDs or entity names
    for affected in event.affected_agents:
        if affected in AGENT_ENTITY_MAP:
            # It's an agent ID - add directly
            relevant.add(affected)
        elif affected in ENTITY_AGENT_MAP:
            # It's an entity name - add all its agents
            relevant.update(get_agents_for_entity(affected))

    # 3. Remove actor (added separately with YOU: prefix) and system agents
    relevant.discard(event.agent_id)
    relevant = {a for a in relevant if not a.startswith("System-")}

    return relevant


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
    # Resolution system fields
    resolution_status: str = "immediate"  # immediate | pending | resolved | failed
    parent_event_id: Optional[str] = None  # Links resolution to original event
    resolution_event_id: Optional[str] = None  # Points to the resolving event
    pending_data: Optional[dict] = None  # Context for pending resolution

    def to_dict(self) -> dict:
        result = asdict(self)
        # Handle None values for optional fields
        if result.get("pending_data") is None:
            result["pending_data"] = None
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "SimulationEvent":
        # Handle missing optional fields for backwards compatibility
        data.setdefault("resolution_status", "immediate")
        data.setdefault("parent_event_id", None)
        data.setdefault("resolution_event_id", None)
        data.setdefault("pending_data", None)
        return cls(**data)


@dataclass
class OngoingSituation:
    """Represents a situation that spans time (siege, negotiation, intel op, blockade)."""
    situation_id: str
    situation_type: str  # siege | negotiation | intel_op | blockade | hostage_deal
    created_at: str  # Game time ISO format
    expected_duration_minutes: int
    current_phase: str  # initiated | active | resolving | completed | failed
    initiating_agent: str
    participating_entities: List[str]
    description: str
    cumulative_effects: List[dict]  # Effects accumulated over time
    resolution_conditions: dict  # What triggers resolution
    parent_event_id: str  # Original event that started this
    last_updated: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "OngoingSituation":
        return cls(**data)


@dataclass
class PMApprovalRequest:
    """Request requiring Prime Minister (player) approval."""
    approval_id: str
    event_id: str  # The event requiring approval
    request_type: str  # military_major | diplomatic | budget | international
    summary: str
    requesting_agent: str
    timestamp: str  # Game time when request was made
    urgency: str  # immediate | high | normal | low
    options: List[dict]  # Possible decisions for the PM
    context: str  # Background information for decision
    recommendation: str  # What the requesting agent recommends
    status: str  # pending | approved | rejected | expired
    pm_decision: Optional[str] = None
    pm_decision_time: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PMApprovalRequest":
        data.setdefault("pm_decision", None)
        data.setdefault("pm_decision_time", None)
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
        self.ongoing_situations: List[OngoingSituation] = []
        self.pm_approval_queue: List[PMApprovalRequest] = []

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
                self.ongoing_situations = [
                    OngoingSituation.from_dict(s) for s in data.get("ongoing_situations", [])
                ]
                self.pm_approval_queue = [
                    PMApprovalRequest.from_dict(r) for r in data.get("pm_approval_queue", [])
                ]
                logger.info(f"Loaded simulation state: {len(self.events)} events, "
                           f"{len(self.ongoing_situations)} ongoing situations, "
                           f"{len(self.pm_approval_queue)} PM approvals pending")
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
            "agent_last_action": self.agent_last_action,
            "ongoing_situations": [s.to_dict() for s in self.ongoing_situations],
            "pm_approval_queue": [r.to_dict() for r in self.pm_approval_queue]
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

    def get_pending_events(self) -> List[SimulationEvent]:
        """Get all events with pending resolution status."""
        return [e for e in self.events if e.resolution_status == "pending"]

    def get_unresolved_events(self) -> List[SimulationEvent]:
        """Get events that need resolution (immediate actions with impacts)."""
        # Events that are immediate but haven't been processed by resolver yet
        return [e for e in self.events
                if e.resolution_status == "immediate"
                and e.action_type != "none"
                and not hasattr(e, '_resolved')]

    # === Ongoing Situations Management ===

    def add_situation(self, situation: OngoingSituation):
        """Add an ongoing situation and save state."""
        self.ongoing_situations.append(situation)
        self.save()

    def get_active_situations(self) -> List[OngoingSituation]:
        """Get all active (non-completed, non-failed) ongoing situations."""
        return [s for s in self.ongoing_situations
                if s.current_phase not in ("completed", "failed")]

    def get_situation_by_id(self, situation_id: str) -> Optional[OngoingSituation]:
        """Get a specific situation by ID."""
        for s in self.ongoing_situations:
            if s.situation_id == situation_id:
                return s
        return None

    def update_situation(self, situation_id: str, updates: dict):
        """Update a situation's fields and save state."""
        for s in self.ongoing_situations:
            if s.situation_id == situation_id:
                for key, value in updates.items():
                    if hasattr(s, key):
                        setattr(s, key, value)
                self.save()
                return True
        return False

    # === PM Approval Queue Management ===

    def add_pm_approval(self, request: PMApprovalRequest):
        """Add a PM approval request and save state."""
        self.pm_approval_queue.append(request)
        self.save()

    def get_pending_approvals(self) -> List[PMApprovalRequest]:
        """Get all pending PM approval requests."""
        return [r for r in self.pm_approval_queue if r.status == "pending"]

    def get_approval_by_id(self, approval_id: str) -> Optional[PMApprovalRequest]:
        """Get a specific approval request by ID."""
        for r in self.pm_approval_queue:
            if r.approval_id == approval_id:
                return r
        return None

    def process_pm_decision(self, approval_id: str, decision: str, game_time: str) -> bool:
        """Process a PM decision on an approval request."""
        for r in self.pm_approval_queue:
            if r.approval_id == approval_id and r.status == "pending":
                r.status = "approved" if decision == "approve" else "rejected"
                r.pm_decision = decision
                r.pm_decision_time = game_time
                self.save()
                return True
        return False

    # === Event Archival System ===

    def archive_resolved_events(self, game_time: str, archive_after_minutes: int = 60) -> int:
        """Move fully resolved events to archive file after X game-minutes.

        Args:
            game_time: Current game time ISO string
            archive_after_minutes: Archive events resolved more than this many game-minutes ago

        Returns:
            Number of events archived
        """
        ARCHIVE_FILE = DATA_DIR / "events_archive.json"

        try:
            current_time = datetime.fromisoformat(game_time)
        except ValueError:
            logger.error(f"Invalid game_time format: {game_time}")
            return 0

        to_archive = []
        to_keep = []

        for event in self.events:
            # Only archive resolved or failed events
            if event.resolution_status in ("resolved", "failed"):
                try:
                    event_time = datetime.fromisoformat(event.timestamp)
                    age_minutes = (current_time - event_time).total_seconds() / 60

                    if age_minutes > archive_after_minutes:
                        to_archive.append(event)
                    else:
                        to_keep.append(event)
                except ValueError:
                    to_keep.append(event)  # Keep if timestamp is invalid
            else:
                to_keep.append(event)

        if not to_archive:
            return 0

        # Load existing archive
        archived_events = []
        if ARCHIVE_FILE.exists():
            try:
                with open(ARCHIVE_FILE, "r", encoding="utf-8") as f:
                    archived_events = json.load(f)
            except Exception as e:
                logger.error(f"Error loading archive file: {e}")

        # Append new archived events
        archived_events.extend([e.to_dict() for e in to_archive])

        # Save archive
        try:
            with open(ARCHIVE_FILE, "w", encoding="utf-8") as f:
                json.dump(archived_events, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving archive file: {e}")
            return 0

        # Update live events
        self.events = to_keep
        self.save()

        logger.info(f"Archived {len(to_archive)} resolved events (total archived: {len(archived_events)})")
        return len(to_archive)


class KPIManager:
    """Manages per-entity KPI files."""

    KPI_DIR = DATA_DIR / "kpis"

    def __init__(self):
        self.KPI_DIR.mkdir(exist_ok=True)
        self._cache: Dict[str, dict] = {}
        self._lock = threading.Lock()

    def get_entity_kpis(self, entity_id: str) -> dict:
        """Load KPIs for an entity."""
        with self._lock:
            # Check cache first
            if entity_id in self._cache:
                return self._cache[entity_id]

            kpi_file = self.KPI_DIR / f"{entity_id}.json"
            if kpi_file.exists():
                try:
                    with open(kpi_file, "r", encoding="utf-8") as f:
                        kpis = json.load(f)
                    self._cache[entity_id] = kpis
                    return kpis
                except Exception as e:
                    logger.error(f"Error loading KPIs for {entity_id}: {e}")
            return {}

    def update_kpis(self, entity_id: str, updates: List[dict]) -> dict:
        """Update specific KPI values for an entity.

        Args:
            entity_id: The entity to update
            updates: List of {"metric": "path.to.metric", "change": value, "reason": "why"}
        """
        with self._lock:
            kpis = self.get_entity_kpis(entity_id)
            if not kpis:
                logger.warning(f"No KPI file found for {entity_id}")
                return {"status": "error", "message": f"No KPIs for {entity_id}"}

            changes_made = []
            for update in updates:
                metric = update.get("metric", "")
                change = update.get("change", 0)
                reason = update.get("reason", "")

                # Navigate to the metric (supports nested paths like "dynamic_metrics.casualties_military")
                parts = metric.split(".")
                target = kpis
                for part in parts[:-1]:
                    if part in target:
                        target = target[part]
                    else:
                        logger.warning(f"Invalid metric path: {metric}")
                        continue

                final_key = parts[-1]
                if final_key in target:
                    old_value = target[final_key]
                    # Handle different change types
                    if isinstance(change, (int, float)) and isinstance(old_value, (int, float)):
                        target[final_key] = old_value + change
                    else:
                        target[final_key] = change  # Direct assignment for non-numeric
                    changes_made.append({
                        "metric": metric,
                        "old": old_value,
                        "new": target[final_key],
                        "reason": reason
                    })
                    logger.info(f"KPI updated: {entity_id}.{metric}: {old_value} -> {target[final_key]} ({reason})")
                    # Log to admin debug console
                    change_str = f"+{change}" if isinstance(change, (int, float)) and change > 0 else str(change)
                    app.log_activity(
                        "kpi",
                        entity_id,
                        "kpi_update",
                        f"{metric}: {old_value} → {target[final_key]} ({change_str}) - {reason}",
                        success=True
                    )

            # Update timestamp and save
            kpis["last_updated"] = datetime.now().isoformat()
            self._save_kpis(entity_id, kpis)

            return {"status": "success", "changes": changes_made}

    def _save_kpis(self, entity_id: str, kpis: dict):
        """Save KPIs to file."""
        kpi_file = self.KPI_DIR / f"{entity_id}.json"
        try:
            with open(kpi_file, "w", encoding="utf-8") as f:
                json.dump(kpis, f, indent=2, ensure_ascii=False)
            self._cache[entity_id] = kpis
        except Exception as e:
            logger.error(f"Error saving KPIs for {entity_id}: {e}")

    def get_all_kpis(self) -> Dict[str, dict]:
        """Get KPIs for all entities."""
        all_kpis = {}
        for kpi_file in self.KPI_DIR.glob("*.json"):
            entity_id = kpi_file.stem
            all_kpis[entity_id] = self.get_entity_kpis(entity_id)
        return all_kpis

    def get_kpis_summary(self) -> str:
        """Get a text summary of key KPIs for the resolver prompt."""
        all_kpis = self.get_all_kpis()
        summary_lines = []
        for entity_id, kpis in all_kpis.items():
            dynamic = kpis.get("dynamic_metrics", {})
            # Extract key metrics
            key_metrics = []
            for k, v in dynamic.items():
                if isinstance(v, (int, float)):
                    key_metrics.append(f"{k}={v}")
            if key_metrics:
                summary_lines.append(f"{entity_id}: {', '.join(key_metrics[:5])}")
        return "\n".join(summary_lines)


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
            action_type = data.get("action_type", "none")

            event = SimulationEvent(
                event_id=f"evt_{uuid.uuid4().hex[:8]}",
                timestamp=game_time,
                agent_id=agent_id,
                action_type=action_type,
                summary=summary,
                is_public=data.get("is_public", True),
                affected_agents=data.get("affected_entities", []),
                reasoning=data.get("reasoning", "")
            )

            # Check if this event should be pending resolution
            is_pending, pending_type, expected_minutes = self._check_pending(event)
            if is_pending:
                event.resolution_status = "pending"
                event.pending_data = {
                    "type": pending_type,
                    "created_at": game_time,
                    "expected_resolution_minutes": expected_minutes
                }
                logger.info(f"Event marked as pending: {event.event_id} ({pending_type}, {expected_minutes} min)")

            return event

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error for {agent_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing LLM response for {agent_id}: {e}")
            return None

    def _check_pending(self, event: SimulationEvent) -> tuple:
        """Check if an event should be marked as pending resolution.

        Returns: (is_pending, pending_type, expected_minutes)
        """
        action_type = event.action_type
        summary_lower = event.summary.lower()

        if action_type in PENDING_KEYWORDS:
            config = PENDING_KEYWORDS[action_type]
            for keyword in config["keywords"]:
                if keyword in summary_lower:
                    return (True, action_type, config["default_minutes"])

        return (False, None, 0)

    def broadcast_event_to_memories(self, event: SimulationEvent):
        """Add event to RELEVANT agents' memories only.

        Relevance is determined by:
        1. Same entity as actor (colleagues see each other's actions)
        2. Affected agents/entities (targets of the action)

        Note: System-* agents are excluded as they are internal system components.
        """
        # Skip if actor is a system agent (they don't need memory)
        if event.agent_id.startswith("System-"):
            return

        # 1. Actor ALWAYS remembers their own action
        own_memory = f"[{event.timestamp}] YOU: {event.summary}"
        app.add_memory(event.agent_id, own_memory)
        logger.info(f"Memory added to {event.agent_id}: '{own_memory}'")

        # 2. If public, only RELEVANT agents learn about it (not all agents)
        if event.is_public:
            memory_entry = f"[{event.timestamp}] {event.agent_id}: {event.summary}"
            relevant_agents = get_relevant_agents_for_event(event)

            for other_id in relevant_agents:
                # Only add if agent exists in system
                if other_id in app.agents:
                    app.add_memory(other_id, memory_entry)

            logger.info(f"Event broadcast to {len(relevant_agents)} relevant agents: '{memory_entry}'")


# =============================================================================
# SIMPLIFIED RESOLVER - LLM only generates narrative, code handles KPIs
# =============================================================================
RESOLVER_PROMPT_SIMPLE = """You are the GAME MASTER for a geopolitical simulation (Israel-Hamas conflict, October 7 2023).

GAME TIME: {game_time}

=== EVENTS TO RESOLVE ===
{events_json}

=== ONGOING SITUATIONS ===
{ongoing_situations}

=== YOUR JOB ===
For each event, provide a brief narrative outcome. KPI calculations are handled automatically.

**PM APPROVAL REQUIRED** for Israeli government agents proposing:
- Ground invasions, large-scale assaults, assassinations
- Ceasefires, hostage deals, prisoner exchanges
- Major budget items (billions)
- Foreign troop involvement

=== OUTPUT FORMAT ===
{{
  "resolutions": [
    {{
      "event_id": "evt_xxx",
      "outcome": "Brief description of what happened (1-2 sentences)",
      "requires_pm": false
    }}
  ],
  "pm_requests": [
    {{
      "event_id": "evt_xxx",
      "summary": "What needs PM approval",
      "options": ["Approve", "Modify", "Reject"],
      "recommendation": "What the agent recommends"
    }}
  ]
}}

Return ONLY valid JSON.
"""

# Keep old prompt for reference but use simplified version
RESOLVER_PROMPT = RESOLVER_PROMPT_SIMPLE

# Keywords that indicate an event should be pending resolution
PENDING_KEYWORDS = {
    "intelligence": {
        "keywords": ["operation", "surveillance", "monitor", "infiltrate", "gather intel", "locate", "track"],
        "default_minutes": 120  # 2 hours game time
    },
    "diplomatic": {
        "keywords": ["negotiate", "talks", "propose", "request", "contact", "discuss"],
        "default_minutes": 60
    },
    "military": {
        "keywords": ["prepare assault", "position forces", "siege", "mobilize", "deploy reserve"],
        "default_minutes": 30
    }
}

# =============================================================================
# RULE-BASED KPI IMPACT ENGINE
# =============================================================================
# Instead of LLM calculating KPI changes, we use deterministic rules.
# LLM only decides success/failure and provides narrative.
# =============================================================================

import random

def roll_range(min_val: int, max_val: int) -> int:
    """Roll a random value in range."""
    return random.randint(min_val, max_val)

# KPI impact rules by action type and keywords
# Format: {"keyword": {"entity.metric": (min, max) or fixed_value, ...}, "success_rate": 0.0-1.0}
KPI_IMPACT_RULES = {
    "military": {
        "airstrike": {
            "success_rate": 0.85,
            "on_success": {
                "Hamas.dynamic_metrics.fighters_remaining": (-30, -10),
                "Hamas.dynamic_metrics.casualties": (10, 30),
                "Israel.dynamic_metrics.ammunition_precision_pct": (-2, -1),
            },
            "on_failure": {
                "Israel.dynamic_metrics.international_standing": (-5, -2),
            }
        },
        "ground": {
            "success_rate": 0.70,
            "on_success": {
                "Israel.dynamic_metrics.casualties_military": (5, 20),
                "Hamas.dynamic_metrics.fighters_remaining": (-80, -30),
                "Hamas.dynamic_metrics.casualties": (30, 80),
                "Israel.dynamic_metrics.ammunition_artillery_pct": (-3, -1),
            },
            "on_failure": {
                "Israel.dynamic_metrics.casualties_military": (15, 40),
                "Israel.dynamic_metrics.morale_military": (-10, -5),
            }
        },
        "tunnel": {
            "success_rate": 0.60,
            "on_success": {
                "Hamas.dynamic_metrics.tunnel_network_operational_km": (-20, -5),
                "Israel.dynamic_metrics.casualties_military": (2, 8),
            },
            "on_failure": {
                "Israel.dynamic_metrics.casualties_military": (5, 15),
            }
        },
        "humanitarian": {
            "success_rate": 0.95,
            "on_success": {
                "Israel.dynamic_metrics.international_standing": (2, 5),
            },
            "on_failure": {}
        },
        "perimeter|border|secure": {
            "success_rate": 0.90,
            "on_success": {
                "Israel.dynamic_metrics.morale_civilian": (1, 3),
            },
            "on_failure": {}
        },
        "reserve|mobiliz": {
            "success_rate": 0.95,
            "on_success": {},
            "on_failure": {}
        },
    },
    "intelligence": {
        "surveillance|monitor": {
            "success_rate": 0.70,
            "on_success": {},
            "on_failure": {}
        },
        "hostage|locate": {
            "success_rate": 0.40,
            "on_success": {},
            "on_failure": {}
        },
        "infiltrat|asset|channel": {
            "success_rate": 0.50,
            "on_success": {},
            "on_failure": {}
        },
        "counter-intelligence|collaborator": {
            "success_rate": 0.60,
            "on_success": {},
            "on_failure": {}
        },
    },
    "diplomatic": {
        "statement|affirm|condemn|support": {
            "success_rate": 0.95,
            "on_success": {},
            "on_failure": {}
        },
        "negotiat|mediat|hostage": {
            "success_rate": 0.30,
            "on_success": {},
            "on_failure": {}
        },
        "carrier|deploy|military aid": {
            "success_rate": 0.95,
            "on_success": {
                "Israel.dynamic_metrics.morale_military": (2, 5),
            },
            "on_failure": {}
        },
    },
    "economic": {
        "budget|fund|emergency": {
            "success_rate": 0.90,
            "on_success": {},
            "on_failure": {}
        },
        "aid|package": {
            "success_rate": 0.80,
            "on_success": {},
            "on_failure": {}
        },
    },
    "internal": {
        "default": {
            "success_rate": 0.95,
            "on_success": {},
            "on_failure": {}
        }
    }
}


def find_matching_rule(action_type: str, summary: str) -> dict:
    """Find the best matching KPI rule for an event."""
    summary_lower = summary.lower()
    rules = KPI_IMPACT_RULES.get(action_type, {})

    for keyword_pattern, rule in rules.items():
        # Split pattern by | for OR matching
        keywords = keyword_pattern.split("|")
        for keyword in keywords:
            if keyword in summary_lower:
                return rule

    # Return default rule if exists, otherwise empty
    return rules.get("default", {"success_rate": 0.80, "on_success": {}, "on_failure": {}})


def apply_kpi_rule(event: "SimulationEvent", kpi_manager: "KPIManager") -> dict:
    """Apply rule-based KPI changes for an event.

    Returns dict with success status and changes made.
    """
    rule = find_matching_rule(event.action_type, event.summary)

    # Determine success/failure
    success_rate = rule.get("success_rate", 0.80)
    success = random.random() < success_rate

    # Get appropriate impacts
    impacts = rule.get("on_success", {}) if success else rule.get("on_failure", {})

    changes_made = []
    for metric_path, value_spec in impacts.items():
        # Parse "Entity.category.metric" format
        parts = metric_path.split(".", 2)
        if len(parts) < 3:
            continue

        entity_id = parts[0]
        metric = f"{parts[1]}.{parts[2]}"

        # Calculate change value
        if isinstance(value_spec, tuple):
            change = roll_range(value_spec[0], value_spec[1])
        else:
            change = value_spec

        # Apply the change
        result = kpi_manager.update_kpis(entity_id, [{
            "metric": metric,
            "change": change,
            "reason": f"{event.summary} ({'success' if success else 'failed'})"
        }])

        if result.get("status") == "success":
            changes_made.extend(result.get("changes", []))

    return {
        "success": success,
        "changes": changes_made,
        "rule_matched": bool(impacts)
    }

# Patterns for events that require Prime Minister (player) approval
# Only checked for agents with is_reporting_government: true
PM_APPROVAL_PATTERNS = {
    "military_major": {
        "action_types": ["military"],
        "keywords": ["ground invasion", "ground assault", "large-scale", "full-scale",
                     "assassination", "targeted killing", "deploy troops",
                     "air strike on", "bomb", "special forces raid"],
        "urgency": "immediate"
    },
    "diplomatic": {
        "action_types": ["diplomatic"],
        "keywords": ["ceasefire", "hostage deal", "prisoner exchange", "peace agreement",
                     "formal alliance", "treaty", "surrender terms", "ultimatum"],
        "urgency": "high"
    },
    "budget": {
        "action_types": ["economic", "military"],
        "keywords": ["billion", "emergency fund", "war bonds", "reserve mobilization",
                     "emergency budget", "military procurement"],
        "urgency": "normal"
    },
    "international": {
        "action_types": ["diplomatic", "military"],
        "keywords": ["foreign troops", "international force", "UN", "NATO",
                     "coalition", "joint operation with"],
        "urgency": "high"
    }
}


class ResolverProcessor:
    """LLM-powered resolver that processes events and determines outcomes."""

    def __init__(self, state: SimulationState, kpi_manager: KPIManager):
        self.state = state
        self.kpi_manager = kpi_manager

    def get_events_to_resolve(self) -> List[SimulationEvent]:
        """Get events that need resolution.

        Uses status-based filtering instead of index tracking to survive restarts.
        Only returns events with resolution_status 'immediate' or 'pending'
        that haven't been resolved yet (no resolution_event_id).
        """
        events_to_resolve = []

        for event in self.state.events:
            # Skip "none" actions
            if event.action_type == "none":
                continue

            # Skip already resolved/failed events
            if event.resolution_status in ("resolved", "failed", "awaiting_pm"):
                continue

            # Skip events that already have a resolution event linked
            if event.resolution_event_id:
                continue

            # Include pending events that might be ready for resolution
            if event.resolution_status == "pending":
                events_to_resolve.append(event)
            # Include immediate events that have impacts
            elif event.resolution_status == "immediate":
                events_to_resolve.append(event)

        return events_to_resolve[-20:]  # Limit to last 20 to avoid huge prompts

    def should_be_pending(self, event: SimulationEvent) -> tuple:
        """Check if an event should be marked as pending.

        Returns: (is_pending, pending_type, expected_minutes)
        """
        action_type = event.action_type
        summary_lower = event.summary.lower()

        if action_type in PENDING_KEYWORDS:
            config = PENDING_KEYWORDS[action_type]
            for keyword in config["keywords"]:
                if keyword in summary_lower:
                    return (True, action_type, config["default_minutes"])

        return (False, None, 0)

    def get_full_kpi_context(self) -> str:
        """Get full KPI data for all entities formatted for the prompt."""
        all_kpis = self.kpi_manager.get_all_kpis()
        return json.dumps(all_kpis, indent=2)

    def get_ongoing_situations_context(self) -> str:
        """Get active ongoing situations formatted for the prompt."""
        active = self.state.get_active_situations()
        if not active:
            return "No ongoing situations."

        situations_data = []
        for sit in active:
            situations_data.append({
                "situation_id": sit.situation_id,
                "type": sit.situation_type,
                "phase": sit.current_phase,
                "description": sit.description,
                "started": sit.created_at,
                "expected_duration_minutes": sit.expected_duration_minutes,
                "participating_entities": sit.participating_entities,
                "cumulative_effects": sit.cumulative_effects
            })
        return json.dumps(situations_data, indent=2)

    def check_requires_pm_approval(self, event: SimulationEvent) -> Optional[dict]:
        """Check if an event requires PM approval based on patterns.

        Returns approval info dict if required, None otherwise.
        """
        # Get the agent to check if they report to government
        agent = app.agents.get(event.agent_id, {})
        if not agent.get("is_reporting_government", False):
            return None

        action_type = event.action_type
        summary_lower = event.summary.lower()

        for request_type, config in PM_APPROVAL_PATTERNS.items():
            if action_type not in config["action_types"]:
                continue

            for keyword in config["keywords"]:
                if keyword in summary_lower:
                    return {
                        "request_type": request_type,
                        "urgency": config["urgency"],
                        "matched_keyword": keyword
                    }

        return None

    def build_resolver_prompt(self, events: List[SimulationEvent], game_time: str) -> str:
        """Build the SIMPLIFIED LLM prompt - no KPI data needed."""
        events_data = []
        for event in events:
            # Only include essential info for narrative generation
            event_dict = {
                "event_id": event.event_id,
                "agent_id": event.agent_id,
                "action_type": event.action_type,
                "summary": event.summary,
            }
            # Flag if this might need PM approval
            pm_check = self.check_requires_pm_approval(event)
            if pm_check:
                event_dict["may_need_pm"] = True

            events_data.append(event_dict)

        return RESOLVER_PROMPT_SIMPLE.format(
            game_time=game_time,
            events_json=json.dumps(events_data, indent=2),
            ongoing_situations=self.get_ongoing_situations_context()
        )

    def parse_resolver_response(self, response: str) -> dict:
        """Parse the SIMPLIFIED resolver LLM response."""
        try:
            # Find JSON object in response
            json_match = re.search(r'\{[\s\S]*\}', response)
            if not json_match:
                logger.error("No JSON found in resolver response")
                return {"resolutions": [], "pm_requests": []}

            result = json.loads(json_match.group())

            # Ensure expected keys exist (simplified format)
            result.setdefault("resolutions", [])
            result.setdefault("pm_requests", [])

            return result

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error in resolver response: {e}")
            return {"resolutions": [], "pm_requests": []}

    def apply_resolutions(self, resolver_output: dict, events: List[SimulationEvent], game_time: str) -> dict:
        """Apply resolutions using RULE-BASED KPI engine + LLM narrative.

        Args:
            resolver_output: Dict with resolutions[] and pm_requests[] from LLM
            events: Original events being resolved
            game_time: Current game time
        Returns:
            Summary of what was applied
        """
        stats = {
            "events_resolved": 0,
            "events_awaiting_pm": 0,
            "pm_approvals_queued": 0,
            "kpi_changes": 0,
            "memory_injections": 0
        }

        # Build lookup of LLM resolutions by event_id
        llm_resolutions = {r.get("event_id"): r for r in resolver_output.get("resolutions", [])}
        pm_event_ids = {r.get("event_id") for r in resolver_output.get("pm_requests", [])}

        # === Process Each Event ===
        for event in events:
            event_id = event.event_id

            # Check if PM approval needed
            if event_id in pm_event_ids:
                event.resolution_status = "awaiting_pm"
                stats["events_awaiting_pm"] += 1
                logger.info(f"Event {event_id} requires PM approval")
                continue

            # Apply RULE-BASED KPI changes
            kpi_result = apply_kpi_rule(event, self.kpi_manager)
            success = kpi_result.get("success", True)
            stats["kpi_changes"] += len(kpi_result.get("changes", []))

            # Get LLM narrative (or generate default)
            llm_res = llm_resolutions.get(event_id, {})
            outcome = llm_res.get("outcome", f"Action {'succeeded' if success else 'failed'}")

            # Mark event as resolved
            event.resolution_status = "resolved" if success else "failed"

            # Create resolution event for history
            resolution_event = SimulationEvent(
                event_id=f"res_{uuid.uuid4().hex[:8]}",
                timestamp=game_time,
                agent_id="System-Resolver",
                action_type="resolution",
                summary=outcome,
                is_public=True,
                parent_event_id=event_id,
                resolution_status="immediate"
            )
            self.state.add_event(resolution_event)
            event.resolution_event_id = resolution_event.event_id
            stats["events_resolved"] += 1

            # Inject memory to relevant agents
            memory_text = f"[RESULT] {outcome}"
            relevant_agents = get_relevant_agents_for_event(event)
            for agent_id in relevant_agents:
                if agent_id in app.agents:
                    app.add_memory(agent_id, memory_text)
                    stats["memory_injections"] += 1

            # Also inject to the actor
            app.add_memory(event.agent_id, f"[RESULT] YOUR ACTION: {outcome}")
            stats["memory_injections"] += 1

            logger.info(f"Event {event_id} resolved: {outcome} (success={success}, kpi_changes={len(kpi_result.get('changes', []))})")

        # === Process PM Approval Requests ===
        for pm_req in resolver_output.get("pm_requests", []):
            event_id = pm_req.get("event_id")
            # Find the original event for context
            original_event = next((e for e in events if e.event_id == event_id), None)

            approval = PMApprovalRequest(
                approval_id=f"apr_{uuid.uuid4().hex[:8]}",
                event_id=event_id or "",
                request_type="military_major",  # Default type
                summary=pm_req.get("summary", "Requires PM decision"),
                requesting_agent=original_event.agent_id if original_event else "unknown",
                timestamp=game_time,
                urgency="high",
                options=[{"option_id": opt.lower().replace(" ", "_"), "label": opt} for opt in pm_req.get("options", ["Approve", "Reject"])],
                context=original_event.summary if original_event else "",
                recommendation=pm_req.get("recommendation", ""),
                status="pending"
            )
            self.state.add_pm_approval(approval)
            stats["pm_approvals_queued"] += 1
            logger.info(f"PM approval queued: {approval.summary}")

        return stats

    async def run_resolution_cycle(self, game_time: str) -> dict:
        """Run a complete resolution cycle - processes ALL pending events in batches of 5."""
        all_events = self.get_events_to_resolve()
        if not all_events:
            logger.debug("Resolver: No events to resolve")
            return {"status": "success", "message": "No events to resolve", "events_resolved": 0}

        BATCH_SIZE = 5
        total_stats = {
            "events_resolved": 0,
            "events_awaiting_pm": 0,
            "pm_approvals_queued": 0,
            "kpi_changes": 0,
            "memory_injections": 0
        }
        total_processed = 0
        batch_num = 0

        logger.info(f"Resolver: {len(all_events)} events to resolve, processing in batches of {BATCH_SIZE}")

        # Process ALL events in batches
        while all_events:
            batch_num += 1
            events = all_events[:BATCH_SIZE]
            all_events = all_events[BATCH_SIZE:]  # Remove processed events

            logger.info(f"Resolver batch {batch_num}: processing {len(events)} events")

            # Build SIMPLIFIED prompt (no KPI data needed)
            prompt = self.build_resolver_prompt(events, game_time)

            # Call LLM - simplified response needs only 1024 tokens for 5 events
            result = await asyncio.to_thread(
                app.interact_simple, prompt, model="claude-sonnet-4-20250514", max_tokens=1024
            )

            if result.get("status") == "error":
                logger.error(f"Resolver batch {batch_num} LLM error: {result.get('message')}")
                continue  # Skip this batch, try next

            response = result.get("response", "")
            logger.info(f"Resolver batch {batch_num}: LLM response ({len(response)} chars)")

            # Parse simplified response
            resolver_output = self.parse_resolver_response(response)

            # Apply using rule-based KPI engine
            stats = self.apply_resolutions(resolver_output, events, game_time)

            # Accumulate stats
            for key in total_stats:
                total_stats[key] += stats.get(key, 0)
            total_processed += len(events)

            logger.info(f"Resolver batch {batch_num} done: {stats.get('events_resolved', 0)} resolved, {stats.get('kpi_changes', 0)} KPI changes")

        logger.info(f"Resolver cycle complete: {total_processed} events processed, {total_stats}")

        return {
            "status": "success",
            "events_processed": total_processed,
            "batches": batch_num,
            **total_stats
        }


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
        self.kpi_manager = KPIManager()
        self.event_processor = EventProcessor(self.state)
        self.resolver = ResolverProcessor(self.state, self.kpi_manager)
        self.scheduler = EntityScheduler(self)
        self._simulation_task: Optional[asyncio.Task] = None
        self._save_task: Optional[asyncio.Task] = None
        self._resolver_task: Optional[asyncio.Task] = None

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

        # Start resolver loop
        self._resolver_task = asyncio.create_task(self._resolver_loop())

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

        # Stop resolver task
        if self._resolver_task:
            self._resolver_task.cancel()
            try:
                await self._resolver_task
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

    async def _resolver_loop(self):
        """Run the resolver periodically to process events."""
        # Start resolving after 15 seconds to let some events accumulate
        await asyncio.sleep(15)

        while self.state.is_running:
            try:
                game_time = self.clock.get_game_time_str()
                logger.info(f"Resolver cycle starting at {game_time}")
                result = await self.resolver.run_resolution_cycle(game_time)

                # Log results
                events_resolved = result.get("events_resolved", 0)
                kpi_changes = result.get("kpi_changes", 0)
                if events_resolved > 0 or kpi_changes > 0:
                    logger.info(f"Resolver: {events_resolved} events resolved, {kpi_changes} KPI changes")
                else:
                    logger.debug(f"Resolver cycle complete: {result.get('message', 'no changes')}")

                # Archive old resolved events to keep main state file lean
                archived_count = self.state.archive_resolved_events(game_time, archive_after_minutes=60)
                if archived_count > 0:
                    logger.info(f"Archived {archived_count} old resolved events")

                # Run every 30 seconds (real time) to keep up with events
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in resolver loop: {e}")
                await asyncio.sleep(60)  # Wait before retrying

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
