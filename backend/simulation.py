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
from map_state import MapStateManager, GeoEventType
from meetings import MeetingOrchestrator

logger = setup_logger("simulation")

# Constants
DATA_DIR = Path(__file__).parent.parent / "data"
DEFAULT_START_TIME = datetime(2023, 10, 7, 6, 29, 0)


# Dynamic path getters for multi-game support
def get_simulation_state_file() -> Path:
    """Get the simulation state file path for current game."""
    try:
        from game_manager import get_game_manager
        return get_game_manager().get_current_data_path() / "simulation_state.json"
    except ImportError:
        return DATA_DIR / "simulation_state.json"


def get_kpi_dir() -> Path:
    """Get the KPI directory path for current game."""
    try:
        from game_manager import get_game_manager
        return get_game_manager().get_current_data_path() / "kpis"
    except ImportError:
        return DATA_DIR / "kpis"


def get_archive_file() -> Path:
    """Get the events archive file path for current game."""
    try:
        from game_manager import get_game_manager
        return get_game_manager().get_current_data_path() / "events_archive.json"
    except ImportError:
        return DATA_DIR / "events_archive.json"


# Legacy constant for backwards compatibility
SIMULATION_STATE_FILE = DATA_DIR / "simulation_state.json"
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
        "Media-Channel-12", "Media-Channel-14", "Hostages-Families-Forum"
    ],
    "USA": ["USA-President", "USA-Secretary-of-State"],
    "UK": ["UK-Prime-Minister"],
    "Russia": ["Russia-President"],
    "Iran": ["Iran-Ayatollah", "Iran-President"],
    "Egypt": ["Egypt-President"],
    "Hamas": ["Hamas-Leadership"],
    "Hezbollah": ["Hezbollah-Leadership"],
    "Houthis": ["Houthi-Leadership"],
    "PLO": ["PLO-Prime-Minister", "PLO-President"],
    "Saudi-Arabia": ["Saudi-Arabia-Crown-Prince"],
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

# Map agents to tracked entities (for relocate actions)
# Only agents that represent movable entities on the map are included
AGENT_TO_TRACKED_ENTITY: Dict[str, str] = {
    "Hamas-Leadership": "hvt-sinwar",
    "Hezbollah-Leadership": "hvt-nasrallah",
    "Houthi-Leadership": "hvt-abdul-malik-houthi",
}

# Default travel times for different entity types (in game minutes)
DEFAULT_TRAVEL_TIME = 60  # 1 hour default


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


@dataclass
class ScheduledEvent:
    """Event scheduled for future execution at a specific game time."""
    schedule_id: str
    event_type: str  # military_action | diplomatic_action | follow_up
    agent_id: str
    due_game_time: str  # ISO format - when to trigger
    payload: dict  # Context for when event triggers
    source_approval_id: str  # Links back to PM approval that created this
    status: str  # pending | triggered | cancelled
    created_at: str  # ISO format

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ScheduledEvent":
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
        self.scheduled_events: List[ScheduledEvent] = []
        # Meeting system state
        self.paused_for_meeting: bool = False
        self.active_meeting_id: Optional[str] = None

    def load(self):
        """Load state from file."""
        state_file = get_simulation_state_file()
        if state_file.exists():
            try:
                with open(state_file, "r", encoding="utf-8") as f:
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
                self.scheduled_events = [
                    ScheduledEvent.from_dict(e) for e in data.get("scheduled_events", [])
                ]
                # Meeting system state
                self.paused_for_meeting = data.get("paused_for_meeting", False)
                self.active_meeting_id = data.get("active_meeting_id", None)
                logger.info(f"Loaded simulation state: {len(self.events)} events, "
                           f"{len(self.ongoing_situations)} ongoing situations, "
                           f"{len(self.pm_approval_queue)} PM approvals pending, "
                           f"{len(self.scheduled_events)} scheduled events")
            except Exception as e:
                logger.error(f"Error loading simulation state: {e}")
        else:
            logger.info("No simulation state file found, starting fresh")

    def save(self):
        """Save state to file."""
        state_file = get_simulation_state_file()
        state_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "is_running": self.is_running,
            "clock_speed": self.clock_speed,
            "game_clock": self.game_clock,
            "events": [e.to_dict() for e in self.events],
            "agent_last_action": self.agent_last_action,
            "ongoing_situations": [s.to_dict() for s in self.ongoing_situations],
            "pm_approval_queue": [r.to_dict() for r in self.pm_approval_queue],
            "scheduled_events": [e.to_dict() for e in self.scheduled_events],
            # Meeting system state
            "paused_for_meeting": self.paused_for_meeting,
            "active_meeting_id": self.active_meeting_id
        }
        try:
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.debug(f"Simulation state saved to {state_file}")
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

    def process_pm_decision(self, approval_id: str, decision: str, game_time: str,
                            modified_summary: str = None, pm_notes: str = None,
                            due_game_time: str = None) -> dict:
        """Process a PM decision on an approval request with enhanced follow-up logic.

        Args:
            approval_id: The approval request ID
            decision: 'approve' or 'reject'
            game_time: Current game time ISO string
            modified_summary: Optional modified summary text
            pm_notes: Optional PM notes
            due_game_time: Optional ISO datetime for scheduled execution

        Returns:
            dict with success status and created event IDs
        """
        for r in self.pm_approval_queue:
            if r.approval_id == approval_id and r.status == "pending":
                r.status = "approved" if decision == "approve" else "rejected"
                r.pm_decision = decision
                r.pm_decision_time = game_time

                result = {
                    "success": True,
                    "follow_up_event_id": None,
                    "scheduled_event_id": None
                }

                # Add memory to requesting agent
                decision_text = "APPROVED" if decision == "approve" else "REJECTED"
                summary_text = modified_summary if modified_summary else r.summary
                memory_entry = f"[PM DECISION] {decision_text}: {summary_text}"
                if pm_notes:
                    memory_entry += f" (PM Note: {pm_notes})"

                try:
                    app.add_memory(r.requesting_agent, memory_entry)
                    logger.info(f"Added PM decision memory to agent {r.requesting_agent}")
                except Exception as e:
                    logger.error(f"Failed to add memory to agent {r.requesting_agent}: {e}")

                # Create follow-up event from agent acknowledging the decision
                action_type_map = {
                    "military_major": "military",
                    "diplomatic": "diplomatic",
                    "budget": "economic",
                    "international": "diplomatic"
                }
                follow_up_action = action_type_map.get(r.request_type, "internal")

                follow_up = SimulationEvent(
                    event_id=f"pm_resp_{uuid.uuid4().hex[:8]}",
                    timestamp=game_time,
                    agent_id=r.requesting_agent,
                    action_type=follow_up_action,
                    summary=f"Acknowledged PM {decision}: {summary_text}",
                    is_public=True,
                    parent_event_id=r.event_id,
                    resolution_status="immediate"
                )
                self.add_event(follow_up)
                result["follow_up_event_id"] = follow_up.event_id
                logger.info(f"Created follow-up event {follow_up.event_id} for PM decision")

                # Create scheduled event if due date provided and approved
                if decision == "approve" and due_game_time:
                    scheduled = ScheduledEvent(
                        schedule_id=f"sch_{uuid.uuid4().hex[:8]}",
                        event_type=r.request_type,
                        agent_id=r.requesting_agent,
                        due_game_time=due_game_time,
                        payload={
                            "original_summary": r.summary,
                            "modified_summary": modified_summary,
                            "pm_notes": pm_notes,
                            "original_event_id": r.event_id
                        },
                        source_approval_id=approval_id,
                        status="pending",
                        created_at=game_time
                    )
                    self.add_scheduled_event(scheduled)
                    result["scheduled_event_id"] = scheduled.schedule_id
                    logger.info(f"Created scheduled event {scheduled.schedule_id} for {due_game_time}")

                self.save()
                return result

        return {"success": False, "message": "Approval not found or already processed"}

    # === Scheduled Events Management ===

    def add_scheduled_event(self, event: ScheduledEvent):
        """Add a scheduled event and save state."""
        self.scheduled_events.append(event)
        self.save()
        logger.info(f"Added scheduled event {event.schedule_id} for agent {event.agent_id}")

    def get_pending_scheduled_events(self) -> List[ScheduledEvent]:
        """Get all pending scheduled events."""
        return [e for e in self.scheduled_events if e.status == "pending"]

    def get_scheduled_event_by_id(self, schedule_id: str) -> Optional[ScheduledEvent]:
        """Get a specific scheduled event by ID."""
        for e in self.scheduled_events:
            if e.schedule_id == schedule_id:
                return e
        return None

    def get_due_events(self, game_time: str) -> List[ScheduledEvent]:
        """Get all pending scheduled events that are due (game_time >= due_game_time)."""
        try:
            current_time = datetime.fromisoformat(game_time)
        except ValueError:
            logger.error(f"Invalid game_time format: {game_time}")
            return []

        due = []
        for event in self.scheduled_events:
            if event.status != "pending":
                continue
            try:
                due_time = datetime.fromisoformat(event.due_game_time)
                if current_time >= due_time:
                    due.append(event)
            except ValueError:
                logger.error(f"Invalid due_game_time for event {event.schedule_id}")
        return due

    def trigger_scheduled_event(self, schedule_id: str, game_time: str) -> bool:
        """Mark a scheduled event as triggered."""
        for e in self.scheduled_events:
            if e.schedule_id == schedule_id and e.status == "pending":
                e.status = "triggered"
                self.save()
                logger.info(f"Triggered scheduled event {schedule_id}")
                return True
        return False

    def cancel_scheduled_event(self, schedule_id: str) -> bool:
        """Cancel a scheduled event."""
        for e in self.scheduled_events:
            if e.schedule_id == schedule_id and e.status == "pending":
                e.status = "cancelled"
                self.save()
                logger.info(f"Cancelled scheduled event {schedule_id}")
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
        archive_file = get_archive_file()

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
        if archive_file.exists():
            try:
                with open(archive_file, "r", encoding="utf-8") as f:
                    archived_events = json.load(f)
            except Exception as e:
                logger.error(f"Error loading archive file: {e}")

        # Append new archived events
        archived_events.extend([e.to_dict() for e in to_archive])

        # Save archive
        try:
            with open(archive_file, "w", encoding="utf-8") as f:
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

    def __init__(self):
        self._cache: Dict[str, dict] = {}
        self._lock = threading.Lock()
        # Ensure KPI directory exists
        self._get_kpi_dir().mkdir(parents=True, exist_ok=True)

    def _get_kpi_dir(self) -> Path:
        """Get the KPI directory path (dynamic for multi-game support)."""
        return get_kpi_dir()

    def _get_entity_kpis_unlocked(self, entity_id: str) -> dict:
        """Load KPIs for an entity (internal, no lock)."""
        # Check cache first
        if entity_id in self._cache:
            return self._cache[entity_id]

        kpi_file = self._get_kpi_dir() / f"{entity_id}.json"
        if kpi_file.exists():
            try:
                with open(kpi_file, "r", encoding="utf-8") as f:
                    kpis = json.load(f)
                self._cache[entity_id] = kpis
                return kpis
            except Exception as e:
                logger.error(f"Error loading KPIs for {entity_id}: {e}")
        return {}

    def get_entity_kpis(self, entity_id: str) -> dict:
        """Load KPIs for an entity."""
        with self._lock:
            return self._get_entity_kpis_unlocked(entity_id)

    def update_kpis(self, entity_id: str, updates: List[dict]) -> dict:
        """Update specific KPI values for an entity.

        Args:
            entity_id: The entity to update
            updates: List of {"metric": "path.to.metric", "change": value, "reason": "why"}
        """
        with self._lock:
            kpis = self._get_entity_kpis_unlocked(entity_id)
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
        kpi_dir = self._get_kpi_dir()
        kpi_dir.mkdir(parents=True, exist_ok=True)
        kpi_file = kpi_dir / f"{entity_id}.json"
        try:
            with open(kpi_file, "w", encoding="utf-8") as f:
                json.dump(kpis, f, indent=2, ensure_ascii=False)
            self._cache[entity_id] = kpis
        except Exception as e:
            logger.error(f"Error saving KPIs for {entity_id}: {e}")

    def get_all_kpis(self) -> Dict[str, dict]:
        """Get KPIs for all entities."""
        with self._lock:
            all_kpis = {}
            kpi_dir = self._get_kpi_dir()
            if kpi_dir.exists():
                for kpi_file in kpi_dir.glob("*.json"):
                    entity_id = kpi_file.stem
                    all_kpis[entity_id] = self._get_entity_kpis_unlocked(entity_id)
            return all_kpis

    def clear_cache(self):
        """Clear the KPI cache (used when switching games)."""
        with self._lock:
            self._cache.clear()

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


# LLM Prompt Templates - Split for caching efficiency
# Static system prompt is cached, dynamic user prompt changes per call

ENTITY_ACTION_SYSTEM_PROMPT = """You are an autonomous entity in a geopolitical simulation.
Your task is to decide on your next action based on your profile, current context, and objectives.

=== OUTPUT FORMAT ===
Respond ONLY with valid JSON in this EXACT format (no other text):
{
    "action_type": "diplomatic|military|economic|intelligence|internal|relocate|none",
    "summary": "ONE sentence describing your action (max 100 characters)",
    "is_public": true,
    "affected_entities": ["entity_id1", "entity_id2"],
    "target_zone": "zone name if action targets a specific location (optional)",
    "relocate_to": "zone name if action_type is relocate (required for relocate)",
    "reasoning": "Brief internal reasoning (not visible to others)"
}

=== RULES ===
- If action_type is "relocate", you MUST specify "relocate_to" with a valid zone name.
- If your action targets a specific location (military strike, intel op), specify "target_zone".
- Keep summaries VERY SHORT - they are headlines, not articles.
- is_public should be true for public actions, false for covert actions.
- If you choose action_type "none", it means you are waiting/observing.
- Consider your skill levels when choosing actions. Actions aligned with your strengths are more likely to succeed.
"""

ENTITY_ACTION_USER_PROMPT = """You are {agent_id}.

CURRENT GAME TIME: {game_time}

=== YOUR PROFILE ===
AGENDA: {agenda}

PRIMARY OBJECTIVES:
{primary_objectives}

HARD RULES (You MUST follow these):
{hard_rules}

=== YOUR CAPABILITIES ===
{skills}

=== SPATIAL CONTEXT ===
{location_context}
{known_locations}

VALID ZONES: {valid_zones}

=== MEMORY ===
Recent events (YOUR actions marked with "YOU:"):
{memory}

Based on your agenda, objectives, and the current situation, decide on your next action.
"""

# Legacy combined prompt for backwards compatibility
ENTITY_ACTION_PROMPT = """You are {agent_id}, acting as an autonomous entity in a geopolitical simulation.

CURRENT GAME TIME: {game_time}

=== YOUR PROFILE ===
AGENDA: {agenda}

PRIMARY OBJECTIVES:
{primary_objectives}

HARD RULES (You MUST follow these):
{hard_rules}

=== YOUR CAPABILITIES ===
{skills}
Consider your skill levels when choosing actions. Actions aligned with your strengths are more likely to succeed.

=== SPATIAL CONTEXT ===
{location_context}

{known_locations}

=== MEMORY ===
Recent events (YOUR actions marked with "YOU:"):
{memory}

=== INSTRUCTIONS ===
Based on your agenda, objectives, and the current situation, decide on your next action.

Respond ONLY with valid JSON in this EXACT format (no other text):
{{
    "action_type": "diplomatic|military|economic|intelligence|internal|relocate|none",
    "summary": "ONE sentence describing your action (max 100 characters)",
    "is_public": true,
    "affected_entities": ["entity_id1", "entity_id2"],
    "target_zone": "zone name if action targets a specific location (optional)",
    "relocate_to": "zone name if action_type is relocate (required for relocate)",
    "reasoning": "Brief internal reasoning (not visible to others)"
}}

VALID ZONES: {valid_zones}

NOTES:
- If action_type is "relocate", you MUST specify "relocate_to" with a valid zone name.
- If your action targets a specific location (military strike, intel op), specify "target_zone".
- Keep summaries VERY SHORT - they are headlines, not articles.
- is_public should be true for public actions, false for covert actions.
- If you choose action_type "none", it means you are waiting/observing.
"""


# Role-based zone relevance for token optimization
ROLE_ZONE_FILTERS = {
    # Military agents - combat zones, strategic sites
    "IDF-Commander": ["Gaza City", "Khan Younis", "Rafah", "Jabalia", "South Lebanon", "Sderot", "Ashkelon", "Nevatim", "Dimona"],
    "Defense-Minister": ["Gaza City", "Khan Younis", "Rafah", "Tel Aviv", "Jerusalem", "South Lebanon", "Beirut", "Nevatim"],

    # Intelligence agents - all major zones (they need full picture)
    "Head-Of-Mossad": None,  # None = all zones
    "Head-Of-Shabak": ["Gaza City", "Khan Younis", "Rafah", "Ramallah", "Hebron", "Jenin", "Nablus", "Jerusalem", "Tel Aviv"],

    # Diplomatic agents - capitals and major cities
    "Foreign-Minister": ["Tel Aviv", "Jerusalem", "Cairo", "Tehran", "Beirut", "Washington DC", "London", "Moscow", "New York"],
    "PM-Netanyahu": ["Tel Aviv", "Jerusalem", "Cairo", "Washington DC", "London", "Gaza City", "Beirut"],

    # Economic agents - financial centers
    "Treasury-Minister": ["Tel Aviv", "Jerusalem", "Haifa", "Washington DC"],

    # Adversary agents - their territories + targets
    "Hamas-Leadership": ["Gaza City", "Khan Younis", "Rafah", "Jabalia", "Tel Aviv", "Jerusalem", "Sderot", "Ashkelon"],
    "Hezbollah-Leadership": ["Beirut", "South Lebanon", "Tyre", "Tehran", "Haifa", "Tel Aviv", "Jerusalem"],
    "Houthi-Leadership": ["Sanaa", "Red Sea", "Eilat", "Suez Canal"],

    # Regional actors - their capitals + conflict zones
    "Iran-Supreme-Leader": ["Tehran", "Natanz", "Qom", "Beirut", "Gaza City", "Sanaa"],
    "Egypt-President": ["Cairo", "Sinai", "El-Arish", "Rafah", "Gaza City", "Jerusalem"],
    "US-President": ["Washington DC", "Tel Aviv", "Jerusalem", "Cairo", "Beirut"],
}

# Default zones for agents not in the filter list
DEFAULT_ZONES = ["Gaza City", "Tel Aviv", "Jerusalem", "Cairo", "Washington DC"]


def get_role_relevant_zones(agent_id: str, all_zones: list, max_zones: int = 8) -> str:
    """Get zones relevant to an agent's role for token efficiency."""
    role_zones = ROLE_ZONE_FILTERS.get(agent_id)

    if role_zones is None:
        # Full access (intelligence agents)
        return ", ".join(all_zones[:12]) + "..."

    if role_zones:
        # Filter to role-relevant zones that actually exist
        relevant = [z for z in role_zones if z in all_zones][:max_zones]
        if relevant:
            return ", ".join(relevant) + " (and others)"

    # Fallback to defaults
    return ", ".join(DEFAULT_ZONES)


def build_location_context(agent_id: str, map_manager) -> str:
    """Build location context string for agent prompt."""
    if not map_manager:
        return "Location tracking not available."

    # Get agent's entity
    actor_entity = get_entity_for_agent(agent_id)
    if not actor_entity:
        return "Your location is not tracked."

    # Check if this agent is associated with tracked entities
    lines = []

    # Check for tracked HVTs/leaders belonging to this entity
    for category in ["high_value_target", "leader"]:
        tracked = map_manager.get_entities_by_category(category)
        for entity in tracked:
            if entity.owner_entity == actor_entity:
                if entity.is_moving:
                    lines.append(
                        f"You are currently in transit from {entity.current_zone} "
                        f"to {entity.destination_zone}. "
                        f"WARNING: Moving entities are more vulnerable to detection."
                    )
                else:
                    lines.append(f"You are currently located in {entity.current_zone}.")

    if lines:
        return "\n".join(lines)

    # For non-tracked entities, provide home base info
    home_zones = {
        "Israel": "Tel Aviv",
        "Hamas": "Gaza City",
        "USA": "Washington DC",
        "Iran": "Tehran",
        "Egypt": "Cairo",
        "PLO": "Ramallah",
        "UK": "London",
        "Russia": "Moscow",
        "UN": "New York",
        "North-Korea": "Pyongyang",
        "Hezbollah": "Dahieh (Beirut)",
        "Houthis": "Sanaa",
        "Saudi-Arabia": "Riyadh",
    }
    home = home_zones.get(actor_entity, "unknown location")
    return f"You operate from {actor_entity}'s territory ({home})."


def build_known_locations_context(agent_id: str, map_manager) -> str:
    """Build known locations string based on agent's intel access."""
    if not map_manager:
        return ""

    actor_entity = get_entity_for_agent(agent_id)
    lines = []

    # Intel agents (Mossad, Shabak) get more info about tracked targets
    intel_agents = ["Head-Of-Mossad", "Head-Of-Shabak"]

    if agent_id in intel_agents:
        lines.append("INTELLIGENCE BRIEFING:")

        # Hostage groups
        hostages = map_manager.get_entities_by_category("hostage_group")
        if hostages:
            for h in hostages:
                conf = "HIGH" if h.detection_difficulty < 0.7 else "LOW"
                status = "IN TRANSIT" if h.is_moving else "STATIONARY"
                count = h.metadata.get("hostage_count", "unknown")
                lines.append(f"  - {h.name}: {count} hostages, {h.current_zone} ({conf} confidence, {status})")

        # HVTs
        hvts = map_manager.get_entities_by_category("high_value_target")
        if hvts:
            for hvt in hvts:
                conf = "HIGH" if hvt.detection_difficulty < 0.8 else "LOW"
                status = "MOVING" if hvt.is_moving else "STATIC"
                lines.append(f"  - {hvt.name}: Last seen in {hvt.current_zone} ({conf} confidence, {status})")

    # Military commanders get info about force deployments
    military_agents = ["IDF-Commander", "Defense-Minister"]
    if agent_id in military_agents:
        lines.append("FORCE POSITIONS:")
        units = map_manager.get_entities_by_category("military_unit")
        for unit in units:
            if unit.owner_entity == actor_entity:
                status = "DEPLOYING" if unit.is_moving else "POSITIONED"
                lines.append(f"  - {unit.name}: {unit.current_zone} ({status})")

    if lines:
        return "\n".join(lines)
    return ""


class EventProcessor:
    """Processes entity actions into structured events using LLM."""

    def __init__(self, state: SimulationState, map_manager: "MapStateManager" = None):
        self.state = state
        self.map_manager = map_manager

    def build_prompt(self, agent_id: str, agent: dict, game_time: str) -> tuple:
        """Build the LLM prompts for an entity action.

        Returns:
            tuple: (system_prompt, user_prompt) for cached LLM interaction
        """
        # Get agent's memory (last 10 entries) - reduced from 20 for token optimization
        # Memory contains both own actions and world events relevant to this agent
        memory = app.agent_memory.get(agent_id, [])
        memory_str = "\n".join(memory[-10:]) or "No events yet."

        # Build location context
        location_context = build_location_context(agent_id, self.map_manager)
        known_locations = build_known_locations_context(agent_id, self.map_manager)

        # Get valid zones for reference - filtered by agent role for token efficiency
        if self.map_manager:
            all_zones = self.map_manager.get_all_zones()
            valid_zones = get_role_relevant_zones(agent_id, all_zones)
        else:
            valid_zones = "Gaza City, Khan Younis, Rafah, Tel Aviv, Jerusalem, Tehran..."

        # Get agent's skills and format them
        skills_list = app.agent_skills.get(agent_id, [])
        if skills_list:
            skills_str = "Your capabilities: " + ", ".join(skills_list)
        else:
            skills_str = "General operational capabilities."

        # Return split prompts for caching - system prompt is cached, user prompt is dynamic
        user_prompt = ENTITY_ACTION_USER_PROMPT.format(
            agent_id=agent_id,
            game_time=game_time,
            agenda=agent.get("agenda", "Not specified"),
            primary_objectives=agent.get("primary_objectives", "Not specified"),
            hard_rules=agent.get("hard_rules", "None"),
            skills=skills_str,
            memory=memory_str,
            location_context=location_context,
            known_locations=known_locations,
            valid_zones=valid_zones
        )

        return (ENTITY_ACTION_SYSTEM_PROMPT, user_prompt)

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

            # Extract location fields
            target_zone = data.get("target_zone")
            relocate_to = data.get("relocate_to")

            # Validate zones if provided
            if self.map_manager:
                if target_zone and not self.map_manager.validate_zone(target_zone):
                    logger.warning(f"Invalid target_zone '{target_zone}' from {agent_id}, ignoring")
                    target_zone = None

                if relocate_to and not self.map_manager.validate_zone(relocate_to):
                    logger.warning(f"Invalid relocate_to '{relocate_to}' from {agent_id}, ignoring")
                    relocate_to = None

            # Handle relocate action type
            if action_type == "relocate":
                if not relocate_to:
                    logger.warning(f"Relocate action without valid relocate_to for {agent_id}, converting to 'none'")
                    action_type = "none"
                    summary = "Attempted relocation but no valid destination"
                else:
                    # Initiate movement on the map if agent has a tracked entity
                    tracked_entity_id = AGENT_TO_TRACKED_ENTITY.get(agent_id)
                    if tracked_entity_id and self.map_manager:
                        movement_started = self.map_manager.start_entity_movement(
                            entity_id=tracked_entity_id,
                            destination_zone=relocate_to,
                            travel_time_minutes=DEFAULT_TRAVEL_TIME,
                            game_time=game_time
                        )
                        if movement_started:
                            logger.info(f"Started movement for {tracked_entity_id} to {relocate_to}")
                        else:
                            logger.warning(f"Failed to start movement for {tracked_entity_id} to {relocate_to}")
                    elif not tracked_entity_id:
                        # Agent doesn't have a tracked entity - just log the intent
                        logger.info(f"Agent {agent_id} relocating to {relocate_to} (no tracked entity)")

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

            # Initialize pending_data with location info if present
            location_data = {}
            if target_zone:
                location_data["target_zone"] = target_zone
            if relocate_to:
                location_data["relocate_to"] = relocate_to

            # Check if this event should be pending resolution
            is_pending, pending_type, expected_minutes = self._check_pending(event)
            if is_pending:
                event.resolution_status = "pending"
                event.pending_data = {
                    "type": pending_type,
                    "created_at": game_time,
                    "expected_resolution_minutes": expected_minutes,
                    **location_data
                }
                logger.info(f"Event marked as pending: {event.event_id} ({pending_type}, {expected_minutes} min)")
            elif location_data:
                # Store location data even for immediate events
                event.pending_data = location_data

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
# Resolver prompts - split for caching efficiency
RESOLVER_SYSTEM_PROMPT = """You are the GAME MASTER for a geopolitical simulation (Israel-Hamas conflict, October 7 2023).

=== YOUR JOB ===
For each event, provide a brief narrative outcome. KPI calculations are handled automatically.

**PM APPROVAL REQUIRED** for Israeli government agents proposing:
- Ground invasions, large-scale assaults, assassinations
- Ceasefires, hostage deals, prisoner exchanges
- Major budget items (billions)
- Foreign troop involvement

=== OUTPUT FORMAT ===
{
  "resolutions": [
    {
      "event_id": "evt_xxx",
      "outcome": "Brief description of what happened (1-2 sentences)",
      "requires_pm": false
    }
  ],
  "pm_requests": [
    {
      "event_id": "evt_xxx",
      "summary": "What needs PM approval",
      "options": ["Approve", "Modify", "Reject"],
      "recommendation": "What the agent recommends"
    }
  ]
}

Return ONLY valid JSON.
"""

RESOLVER_USER_PROMPT = """GAME TIME: {game_time}

=== EVENTS TO RESOLVE ===
{events_json}

=== ONGOING SITUATIONS ===
{ongoing_situations}

Resolve each event above with a brief narrative outcome.
"""

# Legacy combined prompt for backwards compatibility
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
    """Roll a random value in range, auto-correcting order if needed."""
    if min_val > max_val:
        min_val, max_val = max_val, min_val
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
            "on_failure": {
                "Israel.dynamic_metrics.international_standing": (-2, -1),
            }
        },
        "perimeter|border|secure": {
            "success_rate": 0.90,
            "on_success": {
                "Israel.dynamic_metrics.morale_civilian": (1, 3),
            },
            "on_failure": {
                "Israel.dynamic_metrics.morale_civilian": (-2, -1),
            }
        },
        "reserve|mobiliz": {
            "success_rate": 0.95,
            "on_success": {
                "Israel.dynamic_metrics.morale_military": (2, 4),
            },
            "on_failure": {
                "Israel.dynamic_metrics.morale_military": (-2, -1),
            }
        },
        "rocket|missile|launch|barrage": {
            "success_rate": 0.75,
            "on_success": {
                "Israel.dynamic_metrics.casualties_civilian": (1, 10),
                "Israel.dynamic_metrics.morale_civilian": (-5, -2),
                "Israel.dynamic_metrics.ammunition_iron_dome_pct": (-1, -1),
            },
            "on_failure": {
                "Israel.dynamic_metrics.morale_civilian": (1, 3),
            }
        },
        "cross-border|infiltrat|raid": {
            "success_rate": 0.40,
            "on_success": {
                "Israel.dynamic_metrics.casualties_military": (2, 8),
                "Hezbollah.dynamic_metrics.casualties": (5, 15),
            },
            "on_failure": {
                "Hezbollah.dynamic_metrics.casualties": (10, 30),
                "Hezbollah.dynamic_metrics.fighters_remaining": (-20, -5),
            }
        },
        "red sea|ship|vessel|maritime": {
            "success_rate": 0.60,
            "on_success": {
                "Houthis.dynamic_metrics.ships_damaged": (1, 1),
                "Houthis.dynamic_metrics.red_sea_attacks_conducted": (1, 1),
                "Houthis.dynamic_metrics.international_notoriety": (2, 5),
            },
            "on_failure": {
                "Houthis.dynamic_metrics.us_strikes_received": (1, 2),
            }
        },
        "drone|uav": {
            "success_rate": 0.50,
            "on_success": {
                "Houthis.dynamic_metrics.drones_inventory": (-5, -1),
            },
            "on_failure": {
                "Houthis.dynamic_metrics.drones_inventory": (-10, -3),
            }
        },
    },
    "intelligence": {
        "surveillance|monitor": {
            "success_rate": 0.70,
            "on_success": {
                "Israel.dynamic_metrics.intel_accuracy": (2, 5),
            },
            "on_failure": {
                "Israel.dynamic_metrics.intel_accuracy": (-2, -1),
            }
        },
        "hostage|locate": {
            "success_rate": 0.40,
            "on_success": {
                "Israel.dynamic_metrics.intel_accuracy": (5, 10),
                "Israel.dynamic_metrics.morale_civilian": (1, 3),
            },
            "on_failure": {
                "Israel.dynamic_metrics.intel_accuracy": (-5, -2),
            }
        },
        "infiltrat|asset|channel": {
            "success_rate": 0.50,
            "on_success": {
                "Israel.dynamic_metrics.intel_accuracy": (3, 7),
                "Hamas.dynamic_metrics.leadership_cohesion": (-3, -1),
            },
            "on_failure": {
                "Israel.dynamic_metrics.intel_accuracy": (-4, -2),
            }
        },
        "counter-intelligence|collaborator": {
            "success_rate": 0.60,
            "on_success": {
                "Hamas.dynamic_metrics.intel_capability": (-6, -3),
            },
            "on_failure": {
                "Israel.dynamic_metrics.intel_accuracy": (-3, -1),
            }
        },
    },
    "diplomatic": {
        "statement|affirm|condemn|support": {
            "success_rate": 0.95,
            "on_success": {
                "Israel.dynamic_metrics.international_standing": (1, 3),
            },
            "on_failure": {
                "Israel.dynamic_metrics.international_standing": (-2, -1),
            }
        },
        "negotiat|mediat|hostage": {
            "success_rate": 0.30,
            "on_success": {
                "Israel.dynamic_metrics.hostages_released": (1, 5),
                "Israel.dynamic_metrics.morale_civilian": (5, 10),
                "Israel.dynamic_metrics.international_standing": (3, 7),
            },
            "on_failure": {
                "Israel.dynamic_metrics.morale_civilian": (-5, -2),
            }
        },
        "carrier|deploy|military aid": {
            "success_rate": 0.95,
            "on_success": {
                "Israel.dynamic_metrics.morale_military": (2, 5),
                "Israel.dynamic_metrics.ammunition_precision_pct": (3, 8),
            },
            "on_failure": {
                "Israel.dynamic_metrics.morale_military": (-3, -1),
            }
        },
    },
    "economic": {
        "budget|fund|emergency": {
            "success_rate": 0.90,
            "on_success": {
                "Israel.dynamic_metrics.economic_stability": (2, 5),
            },
            "on_failure": {
                "Israel.dynamic_metrics.economic_stability": (-3, -1),
            }
        },
        "aid|package": {
            "success_rate": 0.80,
            "on_success": {
                "Israel.dynamic_metrics.economic_stability": (3, 6),
                "Israel.dynamic_metrics.morale_civilian": (1, 3),
            },
            "on_failure": {
                "Israel.dynamic_metrics.international_standing": (-2, -1),
            }
        },
    },
    "internal": {
        "default": {
            "success_rate": 0.95,
            "on_success": {
                "Israel.dynamic_metrics.morale_civilian": (1, 2),
            },
            "on_failure": {
                "Israel.dynamic_metrics.morale_civilian": (-2, -1),
            }
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
    logger.info(f"apply_kpi_rule: event={event.event_id}, action_type={event.action_type}, summary={event.summary[:60]}...")
    rule = find_matching_rule(event.action_type, event.summary)
    logger.info(f"apply_kpi_rule: matched rule success_rate={rule.get('success_rate')}, on_success={len(rule.get('on_success', {}))}, on_failure={len(rule.get('on_failure', {}))}")

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


# =============================================================================
# SPATIAL CLASH RULES - Outcomes when actions intersect tracked entities
# =============================================================================

SPATIAL_CLASH_RULES = {
    "military": {
        "hostage_group": {
            "success_modifier": -0.3,  # Harder to succeed without casualties
            "collateral_risk": 0.4,    # Risk of hostage casualties
            "intel_gain": 0.2,         # May gain intel on hostages
            "on_success": {
                "Israel.dynamic_metrics.hostages_rescued": (1, 10),
                "Israel.dynamic_metrics.international_standing": (-3, -1),
            },
            "on_failure": {
                "Israel.dynamic_metrics.hostages_held_by_enemy": (-5, -1),  # Casualties
                "Israel.dynamic_metrics.international_standing": (-8, -3),
            }
        },
        "high_value_target": {
            "success_modifier": -0.2,
            "intel_gain": 0.3,
            "on_success": {
                "Hamas.dynamic_metrics.leadership_capacity": (-20, -10),
            },
            "on_failure": {
                "Israel.dynamic_metrics.international_standing": (-5, -2),
            }
        },
        "military_unit": {
            "success_modifier": 0.0,
            "on_success": {
                "Hamas.dynamic_metrics.fighters_remaining": (-50, -20),
            },
            "on_failure": {
                "Israel.dynamic_metrics.casualties_military": (10, 30),
            }
        }
    },
    "intelligence": {
        "hostage_group": {
            "success_modifier": 0.1,  # Intel ops slightly easier than military
            "intel_gain": 0.6,        # High chance to refine location
            "on_success": {},         # No direct KPI, but updates entity uncertainty
            "on_failure": {}
        },
        "high_value_target": {
            "success_modifier": -0.1,
            "intel_gain": 0.4,
            "on_success": {},
            "on_failure": {}
        }
    }
}


def apply_spatial_clash(event: "SimulationEvent",
                        map_manager: "MapStateManager",
                        kpi_manager: "KPIManager",
                        game_time: str) -> dict:
    """Check for and apply spatial clash effects when action intersects tracked entities.

    Returns dict with clash outcomes.
    """
    import random

    results = {
        "clashes_detected": 0,
        "entities_affected": [],
        "intel_updates": [],
        "kpi_changes": [],
        "geo_events_created": []
    }

    if not map_manager or not event.pending_data:
        return results

    target_zone = event.pending_data.get("target_zone")
    if not target_zone:
        return results

    # Find entities in the target zone
    all_categories = ["hostage_group", "high_value_target", "military_unit"]
    clashing_entities = map_manager.check_spatial_clash(target_zone, all_categories)

    if not clashing_entities:
        return results

    results["clashes_detected"] = len(clashing_entities)
    action_rules = SPATIAL_CLASH_RULES.get(event.action_type, {})

    for entity in clashing_entities:
        category_rules = action_rules.get(entity.category, {})
        if not category_rules:
            continue

        # Calculate modified success chance
        base_success = 0.7
        success_mod = category_rules.get("success_modifier", 0.0)
        detection_chance = map_manager.calculate_detection_chance(entity, searcher_capability=0.6)

        effective_success = (base_success + success_mod) * detection_chance
        success = random.random() < effective_success

        # Apply KPI changes
        impacts = category_rules.get("on_success" if success else "on_failure", {})
        for metric_path, value_spec in impacts.items():
            parts = metric_path.split(".", 2)
            if len(parts) < 3:
                continue
            entity_id = parts[0]
            metric = f"{parts[1]}.{parts[2]}"
            change = roll_range(value_spec[0], value_spec[1]) if isinstance(value_spec, tuple) else value_spec

            kpi_result = kpi_manager.update_kpis(entity_id, [{
                "metric": metric,
                "change": change,
                "reason": f"Spatial clash at {target_zone}: {event.summary}"
            }])
            if kpi_result.get("status") == "success":
                results["kpi_changes"].extend(kpi_result.get("changes", []))

        # Update entity intel on success (reduce uncertainty)
        intel_gain = category_rules.get("intel_gain", 0)
        if success and intel_gain > 0 and random.random() < intel_gain:
            new_uncertainty = max(0.5, entity.current_location.uncertainty_km * 0.5)
            map_manager.refine_entity_location(entity.entity_id, new_uncertainty, game_time)
            results["intel_updates"].append({
                "entity_id": entity.entity_id,
                "new_uncertainty_km": new_uncertainty
            })

        results["entities_affected"].append({
            "entity_id": entity.entity_id,
            "category": entity.category,
            "zone": entity.current_zone,
            "success": success,
            "action_type": event.action_type
        })

    return results


def create_geo_event_for_action(event: "SimulationEvent",
                                 map_manager: "MapStateManager",
                                 success: bool,
                                 game_time: str) -> Optional[dict]:
    """Create appropriate geo event for map visualization based on action."""
    if not map_manager or not event.pending_data:
        return None

    target_zone = event.pending_data.get("target_zone")
    relocate_to = event.pending_data.get("relocate_to")

    if not target_zone and not relocate_to:
        return None

    actor_entity = get_entity_for_agent(event.agent_id)
    summary_lower = event.summary.lower()

    # Determine geo event type based on action
    geo_type = None
    origin_zone = None
    dest_zone = target_zone or relocate_to
    duration = 15

    # Home zones for trajectory origin
    home_zones = {
        "Israel": "Tel Aviv",
        "Hamas": "Gaza City",
        "Iran": "Tehran",
        "USA": "Eastern Mediterranean",
    }
    origin_zone = home_zones.get(actor_entity)

    if event.action_type == "military":
        if any(kw in summary_lower for kw in ["missile", "rocket", "launch"]):
            geo_type = GeoEventType.MISSILE_LAUNCH.value
            duration = 20
        elif any(kw in summary_lower for kw in ["airstrike", "air strike", "bomb", "strike"]):
            geo_type = GeoEventType.AIR_STRIKE.value
            duration = 15
        elif any(kw in summary_lower for kw in ["intercept", "iron dome"]):
            geo_type = GeoEventType.INTERCEPTOR.value
            duration = 10
        elif any(kw in summary_lower for kw in ["deploy", "position", "mobiliz"]):
            geo_type = GeoEventType.FORCE_DEPLOYMENT.value
            duration = 30
        elif any(kw in summary_lower for kw in ["ground", "assault", "raid", "advance"]):
            geo_type = GeoEventType.FORCE_MOVEMENT.value
            duration = 25
        elif any(kw in summary_lower for kw in ["battle", "engag", "combat", "fight"]):
            geo_type = GeoEventType.BATTLE_ZONE.value
            duration = 45
    elif event.action_type == "intelligence":
        geo_type = GeoEventType.INTEL_OPERATION.value
        duration = 30
    elif event.action_type == "relocate":
        geo_type = GeoEventType.HOSTAGE_TRANSFER.value if "hostage" in summary_lower else GeoEventType.FORCE_MOVEMENT.value
        duration = 40

    if not geo_type:
        return None

    geo_event = map_manager.create_geo_event(
        event_type=geo_type,
        source_event_id=event.event_id,
        game_time=game_time,
        origin_zone=origin_zone,
        destination_zone=dest_zone,
        duration_seconds=duration,
        description=event.summary,
        actor_entity=actor_entity,
        affected_entities=event.affected_agents
    )

    return geo_event.to_dict() if geo_event else None


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

    def __init__(self, state: SimulationState, kpi_manager: KPIManager, map_manager: "MapStateManager" = None):
        self.state = state
        self.kpi_manager = kpi_manager
        self.map_manager = map_manager

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

    def build_resolver_prompt(self, events: List[SimulationEvent], game_time: str) -> tuple:
        """Build the SIMPLIFIED LLM prompts for event resolution.

        Returns:
            tuple: (system_prompt, user_prompt) for cached LLM interaction
        """
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

        user_prompt = RESOLVER_USER_PROMPT.format(
            game_time=game_time,
            events_json=json.dumps(events_data, indent=2),
            ongoing_situations=self.get_ongoing_situations_context()
        )

        return (RESOLVER_SYSTEM_PROMPT, user_prompt)

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

            # Apply spatial clash detection (if event targets a zone)
            if self.map_manager:
                clash_result = apply_spatial_clash(event, self.map_manager, self.kpi_manager, game_time)
                if clash_result.get("clashes_detected", 0) > 0:
                    stats["kpi_changes"] += len(clash_result.get("kpi_changes", []))
                    logger.info(f"Spatial clash detected for {event_id}: {clash_result['entities_affected']}")

                # Create geo event for map visualization
                geo_event = create_geo_event_for_action(event, self.map_manager, success, game_time)
                if geo_event:
                    logger.debug(f"Created geo event for {event_id}: {geo_event.get('event_type')}")

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

        # Group events by action_type for more coherent resolution
        events_by_type = {}
        for event in all_events:
            action_type = event.action_type or "none"
            if action_type not in events_by_type:
                events_by_type[action_type] = []
            events_by_type[action_type].append(event)

        # Flatten back into ordered list (grouped by type)
        grouped_events = []
        for action_type in ["military", "intelligence", "diplomatic", "economic", "internal", "relocate", "none"]:
            if action_type in events_by_type:
                grouped_events.extend(events_by_type[action_type])
        # Add any types we missed
        for action_type, events_list in events_by_type.items():
            if action_type not in ["military", "intelligence", "diplomatic", "economic", "internal", "relocate", "none"]:
                grouped_events.extend(events_list)

        logger.info(f"Resolver: {len(grouped_events)} events to resolve, grouped by action_type, batches of {BATCH_SIZE}")

        # Process ALL events in batches (now grouped by type)
        while grouped_events:
            batch_num += 1
            events = grouped_events[:BATCH_SIZE]
            grouped_events = grouped_events[BATCH_SIZE:]  # Remove processed events

            # Log the action types in this batch for debugging
            batch_types = set(e.action_type for e in events)
            logger.info(f"Resolver batch {batch_num}: processing {len(events)} events (types: {batch_types})")

            # Build SIMPLIFIED prompts (split for caching efficiency)
            system_prompt, user_prompt = self.build_resolver_prompt(events, game_time)

            # Call LLM with caching - simplified response needs only 1024 tokens for 5 events
            result = await asyncio.to_thread(
                app.interact_with_caching, system_prompt, user_prompt, model="claude-sonnet-4-20250514", max_tokens=1024
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
                # Check if simulation is paused for a meeting
                if self.manager.state.paused_for_meeting:
                    await asyncio.sleep(1)  # Check every second while paused
                    continue

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

        # Build prompts (split for caching efficiency)
        system_prompt, user_prompt = self.manager.event_processor.build_prompt(agent_id, agent, game_time)

        # Call LLM with caching in thread pool to avoid blocking the event loop
        result = await asyncio.to_thread(
            app.interact_with_caching, system_prompt, user_prompt, model=agent.get("model", "claude-sonnet-4-20250514")
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
        self.map_manager = MapStateManager()  # MapState for spatial awareness
        self.event_processor = EventProcessor(self.state, self.map_manager)
        self.resolver = ResolverProcessor(self.state, self.kpi_manager, self.map_manager)
        self.scheduler = EntityScheduler(self)
        self.meeting_orchestrator = MeetingOrchestrator(self)  # Meeting system
        self._simulation_task: Optional[asyncio.Task] = None
        self._save_task: Optional[asyncio.Task] = None
        self._resolver_task: Optional[asyncio.Task] = None

        # Load existing state
        self.state.load()
        if self.state.game_clock:
            self.clock.game_time = datetime.fromisoformat(self.state.game_clock)
        self.clock.speed = self.state.clock_speed

    def reload_for_game_switch(self):
        """Reload all state after switching to a different game.

        This reinitializes all components to load data from the new game's directory.
        Should only be called when simulation is stopped.
        """
        logger.info("Reloading simulation state for game switch...")

        # Clear KPI cache
        self.kpi_manager.clear_cache()

        # Reinitialize state from new game's files
        self.state = SimulationState()
        self.state.load()

        # Reinitialize KPI manager (will read from new directory)
        self.kpi_manager = KPIManager()

        # Reinitialize map manager
        self.map_manager = MapStateManager()

        # Reinitialize processors with new state
        self.event_processor = EventProcessor(self.state, self.map_manager)
        self.resolver = ResolverProcessor(self.state, self.kpi_manager, self.map_manager)

        # Reinitialize meeting orchestrator
        self.meeting_orchestrator = MeetingOrchestrator(self)

        # Update clock from loaded state
        if self.state.game_clock:
            self.clock.game_time = datetime.fromisoformat(self.state.game_clock)
        else:
            self.clock.game_time = DEFAULT_START_TIME
        self.clock.speed = self.state.clock_speed

        # Reload agents
        app.load_agents()

        logger.info("Simulation state reloaded for game switch")

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

    def _trigger_scheduled_event(self, scheduled: ScheduledEvent, game_time: str):
        """Trigger a scheduled event by creating a SimulationEvent from it."""
        try:
            # Mark as triggered first
            self.state.trigger_scheduled_event(scheduled.schedule_id, game_time)

            # Map event type to action type
            action_type_map = {
                "military_major": "military",
                "diplomatic": "diplomatic",
                "budget": "economic",
                "international": "diplomatic"
            }
            action_type = action_type_map.get(scheduled.event_type, "internal")

            # Build summary from payload
            summary = scheduled.payload.get("modified_summary") or scheduled.payload.get("original_summary", "Scheduled action executed")

            # Create the simulation event
            event = SimulationEvent(
                event_id=f"sch_exec_{uuid.uuid4().hex[:8]}",
                timestamp=game_time,
                agent_id=scheduled.agent_id,
                action_type=action_type,
                summary=f"[SCHEDULED] {summary}",
                is_public=True,
                parent_event_id=scheduled.payload.get("original_event_id"),
                resolution_status="immediate"
            )
            self.state.add_event(event)
            logger.info(f"Triggered scheduled event {scheduled.schedule_id} -> created event {event.event_id}")

            # Add memory to agent about the execution
            memory_entry = f"[SCHEDULED EVENT EXECUTED] {summary}"
            try:
                app.add_memory(scheduled.agent_id, memory_entry)
            except Exception as e:
                logger.error(f"Failed to add memory for scheduled event: {e}")

        except Exception as e:
            logger.error(f"Error triggering scheduled event {scheduled.schedule_id}: {e}")

    async def _process_situation_lifecycles(self, game_time: str):
        """Process ongoing situations and update their phases based on time."""
        from datetime import datetime, timedelta

        try:
            current_time = datetime.fromisoformat(game_time)
        except ValueError:
            return

        for situation in self.state.ongoing_situations:
            try:
                # Skip already completed/failed situations
                if situation.current_phase in ["completed", "failed"]:
                    continue

                # Parse start time
                started_at = datetime.fromisoformat(situation.started_at)
                elapsed_minutes = (current_time - started_at).total_seconds() / 60

                # Progress through phases based on time
                expected_duration = situation.expected_duration_minutes

                if situation.current_phase == "initiated":
                    # Move to active after 10% of expected duration
                    if elapsed_minutes > expected_duration * 0.1:
                        self.state.update_situation(situation.situation_id, {
                            "current_phase": "active"
                        })
                        logger.info(f"Situation {situation.situation_id} progressed to 'active'")

                elif situation.current_phase == "active":
                    # Move to resolving when duration exceeded
                    if elapsed_minutes >= expected_duration:
                        self.state.update_situation(situation.situation_id, {
                            "current_phase": "resolving"
                        })
                        logger.info(f"Situation {situation.situation_id} progressed to 'resolving'")

                elif situation.current_phase == "resolving":
                    # Complete after 10% more time for resolution
                    if elapsed_minutes >= expected_duration * 1.1:
                        self.state.update_situation(situation.situation_id, {
                            "current_phase": "completed"
                        })
                        logger.info(f"Situation {situation.situation_id} completed")

            except Exception as e:
                logger.error(f"Error processing situation {situation.situation_id}: {e}")

    async def _resolver_loop(self):
        """Run the resolver periodically to process events."""
        # Start resolving after 15 seconds to let some events accumulate
        await asyncio.sleep(15)

        while self.state.is_running:
            try:
                # Skip resolver cycle if simulation is paused for a meeting
                if self.state.paused_for_meeting:
                    await asyncio.sleep(1)
                    continue

                game_time = self.clock.get_game_time_str()
                logger.info(f"Resolver cycle starting at {game_time}")

                # Check for completed entity movements (MapState)
                if self.map_manager:
                    completed_movements = self.map_manager.complete_entity_movements(game_time)
                    if completed_movements:
                        logger.info(f"Entity movements completed: {completed_movements}")

                    # Archive old geo events
                    archived_geo = self.map_manager.archive_expired_geo_events(game_time)
                    if archived_geo > 0:
                        logger.debug(f"Archived {archived_geo} geo events")

                # Check for due scheduled events and trigger them
                due_events = self.state.get_due_events(game_time)
                for scheduled in due_events:
                    self._trigger_scheduled_event(scheduled, game_time)

                result = await self.resolver.run_resolution_cycle(game_time)

                # Process ongoing situation lifecycles
                await self._process_situation_lifecycles(game_time)

                # Check for meeting auto-triggers on recently resolved events
                if self.meeting_orchestrator:
                    for event in self.state.get_recent_events(limit=10):
                        if event.resolution_status in ["resolved", "immediate"]:
                            self.meeting_orchestrator.check_auto_triggers(event)

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
