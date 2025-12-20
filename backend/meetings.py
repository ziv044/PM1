"""
PM1 Meeting Orchestrator - Scheduled Meetings System

This module provides an on-demand meeting system that simulates structured
multi-agent meetings (negotiations, cabinet sessions, bilateral talks).
The orchestrator runs only when triggered, not periodically like entity agents.
"""

import asyncio
import json
import uuid
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, TYPE_CHECKING
from dataclasses import dataclass, asdict, field
from enum import Enum

import app
from logger import setup_logger

if TYPE_CHECKING:
    from simulation import SimulationManager, SimulationEvent

logger = setup_logger("meetings")

# Constants
DATA_DIR = Path(__file__).parent.parent / "data"
MEETINGS_FILE = DATA_DIR / "meetings.json"


# ============================================================================
# ENUMS
# ============================================================================

class MeetingType(Enum):
    NEGOTIATION = "negotiation"           # Multi-party with mediators
    CABINET_WAR_ROOM = "cabinet_war_room" # Israeli internal decisions
    LEADER_TALK = "leader_talk"           # Bilateral diplomacy
    AGENT_TALK = "agent_talk"             # Internal coordination/briefing


class MeetingStatus(Enum):
    SCHEDULED = "scheduled"   # Created, waiting for start time
    PENDING = "pending"       # Ready to start, waiting for player
    ACTIVE = "active"         # Currently in progress
    PAUSED = "paused"         # Player paused the meeting
    CONCLUDED = "concluded"   # Meeting ended normally
    FAILED = "failed"         # Meeting broke down
    ABORTED = "aborted"       # Player aborted


class ParticipantRole(Enum):
    CHAIR = "chair"           # PM in cabinet, lead in negotiations
    PRINCIPAL = "principal"   # Main decision maker
    ADVISOR = "advisor"       # Provides input but doesn't decide
    OBSERVER = "observer"     # Silent participant (intel gathering)
    MEDIATOR = "mediator"     # Neutral party facilitating talks


class TurnActionType(Enum):
    STATEMENT = "statement"
    PROPOSAL = "proposal"
    COUNTEROFFER = "counteroffer"
    DEMAND = "demand"
    ACCEPTANCE = "acceptance"
    REJECTION = "rejection"
    QUESTION = "question"
    BRIEFING = "briefing"
    RECOMMENDATION = "recommendation"
    DISSENT = "dissent"
    SILENCE = "silence"


class MeetingRequestStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class MeetingAgenda:
    """Structured agenda for a meeting."""
    agenda_id: str
    items: List[str]  # Topics to discuss
    current_item_index: int = 0
    item_statuses: Dict[str, str] = field(default_factory=dict)  # item -> resolved|deadlocked|tabled

    def current_item(self) -> Optional[str]:
        if 0 <= self.current_item_index < len(self.items):
            return self.items[self.current_item_index]
        return None

    def advance_item(self) -> Optional[str]:
        """Move to next agenda item, return it or None if done."""
        self.current_item_index += 1
        return self.current_item()

    def mark_item_status(self, status: str):
        """Mark current item with a status."""
        current = self.current_item()
        if current:
            self.item_statuses[current] = status

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "MeetingAgenda":
        return cls(**data)


@dataclass
class MeetingParticipant:
    """A participant in a meeting."""
    agent_id: str
    role: str  # ParticipantRole value
    entity: str  # Which entity they represent
    initial_position: str  # Their starting stance/objectives
    current_position: str  # May evolve during meeting
    has_spoken_this_round: bool = False
    turn_count: int = 0
    is_player: bool = False  # True if this is the PM (player)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "MeetingParticipant":
        data.setdefault("is_player", False)
        return cls(**data)


@dataclass
class MeetingTurn:
    """A single turn/statement in a meeting."""
    turn_id: str
    turn_number: int
    speaker_agent_id: str
    speaker_role: str
    content: str  # What was said
    action_type: str  # TurnActionType value
    timestamp: str  # Game time when this turn occurred
    is_player_input: bool = False  # True if PM player provided this
    addressed_to: List[str] = field(default_factory=list)  # Specific recipients
    private_reasoning: str = ""  # LLM internal reasoning (not shared)
    emotional_tone: str = "neutral"  # calm | firm | aggressive | conciliatory | urgent
    position_update: str = ""  # If position changed this turn

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "MeetingTurn":
        data.setdefault("addressed_to", [])
        data.setdefault("private_reasoning", "")
        data.setdefault("emotional_tone", "neutral")
        data.setdefault("position_update", "")
        return cls(**data)


@dataclass
class MeetingOutcome:
    """Outcomes and agreements from a meeting."""
    outcome_id: str
    meeting_id: str
    outcome_type: str  # agreement | partial_agreement | breakdown | tabled | aborted
    summary: str  # Brief description of what happened
    agreements: List[dict] = field(default_factory=list)  # Specific agreements reached
    commitments: List[dict] = field(default_factory=list)  # Actions participants committed to
    unresolved_items: List[str] = field(default_factory=list)  # Topics not resolved
    follow_up_required: bool = False
    follow_up_details: str = ""
    events_generated: List[str] = field(default_factory=list)  # Event IDs created
    pm_approvals_required: List[str] = field(default_factory=list)  # Approval IDs needed

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "MeetingOutcome":
        data.setdefault("agreements", [])
        data.setdefault("commitments", [])
        data.setdefault("unresolved_items", [])
        data.setdefault("events_generated", [])
        data.setdefault("pm_approvals_required", [])
        return cls(**data)


@dataclass
class MeetingSession:
    """Complete meeting session state."""
    meeting_id: str
    meeting_type: str  # MeetingType value
    title: str
    description: str
    status: str  # MeetingStatus value

    # Scheduling
    created_at: str  # Real time when scheduled
    scheduled_game_time: str  # Game time when meeting should start
    started_at: Optional[str] = None  # Game time when actually started
    ended_at: Optional[str] = None  # Game time when concluded

    # Participants
    participants: List[MeetingParticipant] = field(default_factory=list)
    chair_agent_id: Optional[str] = None  # Who chairs the meeting

    # Agenda
    agenda: Optional[MeetingAgenda] = None

    # Conversation history
    turns: List[MeetingTurn] = field(default_factory=list)
    current_round: int = 1
    max_rounds: int = 10  # Prevent infinite meetings

    # Context and state
    meeting_context: str = ""  # Background info for participants
    current_state_summary: str = ""  # AI-generated summary of current state
    stakes: str = ""  # What's at stake in this meeting

    # Outcomes
    outcome: Optional[MeetingOutcome] = None

    def get_participant(self, agent_id: str) -> Optional[MeetingParticipant]:
        """Get a participant by agent_id."""
        for p in self.participants:
            if p.agent_id == agent_id:
                return p
        return None

    def get_participants_by_role(self, role: str) -> List[MeetingParticipant]:
        """Get all participants with a specific role."""
        return [p for p in self.participants if p.role == role]

    def reset_round_flags(self):
        """Reset has_spoken_this_round for all participants."""
        for p in self.participants:
            p.has_spoken_this_round = False

    def all_have_spoken(self) -> bool:
        """Check if all non-observer participants have spoken this round."""
        for p in self.participants:
            if p.role != ParticipantRole.OBSERVER.value and not p.has_spoken_this_round:
                return False
        return True

    def to_dict(self) -> dict:
        result = {
            "meeting_id": self.meeting_id,
            "meeting_type": self.meeting_type,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at,
            "scheduled_game_time": self.scheduled_game_time,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "chair_agent_id": self.chair_agent_id,
            "current_round": self.current_round,
            "max_rounds": self.max_rounds,
            "meeting_context": self.meeting_context,
            "current_state_summary": self.current_state_summary,
            "stakes": self.stakes,
        }
        result["participants"] = [p.to_dict() for p in self.participants]
        result["turns"] = [t.to_dict() for t in self.turns]
        result["agenda"] = self.agenda.to_dict() if self.agenda else None
        result["outcome"] = self.outcome.to_dict() if self.outcome else None
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "MeetingSession":
        # Reconstruct nested objects
        participants = [MeetingParticipant.from_dict(p) for p in data.get("participants", [])]
        turns = [MeetingTurn.from_dict(t) for t in data.get("turns", [])]
        agenda = MeetingAgenda.from_dict(data["agenda"]) if data.get("agenda") else None
        outcome = MeetingOutcome.from_dict(data["outcome"]) if data.get("outcome") else None

        return cls(
            meeting_id=data["meeting_id"],
            meeting_type=data["meeting_type"],
            title=data["title"],
            description=data.get("description", ""),
            status=data["status"],
            created_at=data["created_at"],
            scheduled_game_time=data["scheduled_game_time"],
            started_at=data.get("started_at"),
            ended_at=data.get("ended_at"),
            participants=participants,
            chair_agent_id=data.get("chair_agent_id"),
            agenda=agenda,
            turns=turns,
            current_round=data.get("current_round", 1),
            max_rounds=data.get("max_rounds", 10),
            meeting_context=data.get("meeting_context", ""),
            current_state_summary=data.get("current_state_summary", ""),
            stakes=data.get("stakes", ""),
            outcome=outcome,
        )


@dataclass
class MeetingRequest:
    """Request for a meeting (from AI agents or auto-trigger system)."""
    request_id: str
    meeting_type: str  # MeetingType value
    requested_by: str  # agent_id or "system"
    reason: str  # Why this meeting is requested
    title: str  # Suggested title
    suggested_participants: List[str] = field(default_factory=list)
    suggested_agenda: List[str] = field(default_factory=list)
    urgency: str = "normal"  # immediate | high | normal | low
    trigger_event_id: Optional[str] = None  # Event that triggered this request
    status: str = "pending"  # MeetingRequestStatus value
    created_at: str = ""  # Real timestamp
    expires_at: Optional[str] = None  # When request expires

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "MeetingRequest":
        data.setdefault("suggested_participants", [])
        data.setdefault("suggested_agenda", [])
        data.setdefault("urgency", "normal")
        data.setdefault("status", "pending")
        return cls(**data)


# ============================================================================
# MEETING PROMPTS
# ============================================================================

MEETING_TURN_PROMPT = """You are {agent_id} participating in a {meeting_type} meeting.

=== MEETING INFORMATION ===
Title: {title}
Type: {meeting_type_display}
Current Game Time: {game_time}
Your Role: {participant_role}
Round: {current_round} of {max_rounds}

=== PARTICIPANTS ===
{participants_list}

=== CURRENT AGENDA ITEM ===
{current_agenda_item}

=== YOUR POSITION ===
Initial Position: {initial_position}
Current Position: {current_position}

=== CONVERSATION SO FAR (Recent Turns) ===
{recent_turns}

=== YOUR OBJECTIVES ===
{agent_objectives}

=== YOUR MEMORY (Recent Events) ===
{agent_memory}

=== INSTRUCTIONS ===
You are about to speak in this meeting. Consider your role, your entity's interests, and the conversation so far.

Respond ONLY with valid JSON in this exact format:
{{
    "action_type": "<statement|proposal|counteroffer|demand|acceptance|rejection|question|briefing|recommendation|dissent>",
    "content": "<What you say - 2-4 sentences, appropriate diplomatic/professional language>",
    "addressed_to": ["<agent_id>"],
    "emotional_tone": "<calm|firm|aggressive|conciliatory|urgent>",
    "position_update": "<Your updated position if it changed, otherwise empty string>",
    "private_reasoning": "<Your internal strategic reasoning - not visible to others>"
}}

MEETING RULES:
- Stay in character for your role and entity
- Be realistic to your entity's actual positions and constraints
- Proposals should be specific and actionable
- You may conditionally accept ("If X then we agree to Y")
- Reference previous statements when relevant
- {role_specific_rules}
"""

MEETING_OUTCOME_PROMPT = """Analyze this completed meeting and extract the outcomes.

=== MEETING INFORMATION ===
Type: {meeting_type}
Title: {title}
Participants: {participants}
Agenda Items: {agenda_items}

=== FULL CONVERSATION ===
{all_turns}

=== ANALYSIS INSTRUCTIONS ===
Based on the meeting transcript, provide a structured analysis:

{{
    "outcome_type": "<agreement|partial_agreement|breakdown|tabled>",
    "summary": "<One paragraph summary of what happened and key outcomes>",
    "agreements": [
        {{
            "topic": "<What was agreed>",
            "parties": ["<agent_id1>", "<agent_id2>"],
            "terms": "<Specific terms of agreement>",
            "binding": <true|false>,
            "implementation_notes": "<How/when to implement>"
        }}
    ],
    "commitments": [
        {{
            "agent_id": "<Who committed>",
            "action": "<What they will do>",
            "deadline": "<When, if specified>"
        }}
    ],
    "unresolved_items": ["<Topic 1>", "<Topic 2>"],
    "follow_up_required": <true|false>,
    "follow_up_description": "<What follow-up is needed>",
    "requires_pm_approval": [
        {{
            "topic": "<What needs PM approval>",
            "request_type": "<military_major|diplomatic|budget|international>",
            "urgency": "<immediate|high|normal>",
            "summary": "<Brief description for PM>"
        }}
    ],
    "events_to_generate": [
        {{
            "action_type": "<diplomatic|military|economic|internal|intelligence>",
            "summary": "<Event summary>",
            "agent_id": "<Who takes action>",
            "is_public": <true|false>,
            "affected_agents": ["<agent_id1>"]
        }}
    ],
    "memory_injections": [
        {{
            "agent_id": "<Who receives memory>",
            "memory_text": "<What they should remember>"
        }}
    ]
}}
"""

MEETING_SUMMARY_PROMPT = """Summarize the current state of this meeting in 2-3 sentences.

Meeting Type: {meeting_type}
Current Round: {current_round}
Participants: {participants}

Recent Turns:
{recent_turns}

Provide a brief, neutral summary of:
1. What has been discussed
2. Current positions of key parties
3. Any progress or deadlocks

Summary:"""

# Role-specific rules injected into turn prompts
ROLE_SPECIFIC_RULES = {
    ParticipantRole.CHAIR.value: "As chair, you should facilitate discussion, call on participants, and summarize progress.",
    ParticipantRole.PRINCIPAL.value: "As a principal party, you represent your entity's core interests and can make binding commitments.",
    ParticipantRole.ADVISOR.value: "As an advisor, provide expert input and recommendations but defer final decisions to principals.",
    ParticipantRole.OBSERVER.value: "As an observer, you typically remain silent. Only speak if directly addressed or if critical information must be shared.",
    ParticipantRole.MEDIATOR.value: "As mediator, remain neutral, facilitate compromise, and help parties find common ground.",
}


# ============================================================================
# MEETING TYPE CONFIGURATIONS
# ============================================================================

MEETING_TYPE_CONFIG = {
    MeetingType.CABINET_WAR_ROOM.value: {
        "display_name": "Cabinet War Room",
        "description": "Internal Israeli government decision-making session",
        "default_chair": "PM",  # Player
        "default_participants": [
            {"agent_id": "Defense-Minister", "role": "principal"},
            {"agent_id": "Head-Of-Mossad", "role": "advisor"},
            {"agent_id": "Head-Of-Shabak", "role": "advisor"},
            {"agent_id": "IDF-Commander", "role": "advisor"},
            {"agent_id": "Treasury-Minister", "role": "principal"},
        ],
        "max_rounds": 8,
        "requires_pm": True,
    },
    MeetingType.NEGOTIATION.value: {
        "display_name": "Multi-Party Negotiation",
        "description": "Negotiation with multiple parties, potentially including mediators",
        "default_chair": None,  # Mediator or strongest party
        "default_participants": [],  # Must be specified
        "max_rounds": 12,
        "requires_pm": False,  # PM can participate or delegate
    },
    MeetingType.LEADER_TALK.value: {
        "display_name": "Leader-to-Leader Talk",
        "description": "Bilateral diplomatic conversation between heads of state/government",
        "default_chair": None,  # No chair in bilateral
        "default_participants": [],  # Must specify the other leader
        "max_rounds": 6,
        "requires_pm": True,
    },
    MeetingType.AGENT_TALK.value: {
        "display_name": "Agent Briefing",
        "description": "One-on-one briefing or consultation with an official",
        "default_chair": "PM",
        "default_participants": [],  # Must specify the agent
        "max_rounds": 5,
        "requires_pm": True,
    },
}


# ============================================================================
# AUTO-TRIGGER RULES
# ============================================================================

AUTO_TRIGGER_RULES = [
    {
        "name": "hostage_escalation",
        "trigger_keywords": ["hostage", "captive", "kidnapped"],
        "trigger_action_types": ["military", "intelligence"],
        "meeting_type": MeetingType.NEGOTIATION.value,
        "suggested_participants": ["Hamas-Leadership", "Egypt-President"],
        "urgency": "high",
        "reason": "Hostage situation requires negotiation",
    },
    {
        "name": "ceasefire_proposal",
        "trigger_keywords": ["ceasefire", "truce", "pause", "humanitarian"],
        "trigger_action_types": ["diplomatic"],
        "meeting_type": MeetingType.NEGOTIATION.value,
        "suggested_participants": [],  # Determined by affected parties
        "urgency": "high",
        "reason": "Ceasefire proposal requires multi-party negotiation",
    },
    {
        "name": "major_military_decision",
        "trigger_keywords": ["invasion", "ground operation", "major offensive", "airstrike campaign"],
        "trigger_action_types": ["military"],
        "meeting_type": MeetingType.CABINET_WAR_ROOM.value,
        "suggested_participants": [],  # Uses defaults
        "urgency": "immediate",
        "reason": "Major military decision requires cabinet discussion",
    },
    {
        "name": "foreign_leader_request",
        "trigger_keywords": ["requests meeting", "proposes talks", "seeks dialogue"],
        "trigger_action_types": ["diplomatic"],
        "meeting_type": MeetingType.LEADER_TALK.value,
        "suggested_participants": [],  # The requesting leader
        "urgency": "normal",
        "reason": "Foreign leader has requested direct talks",
    },
    {
        "name": "critical_intel",
        "trigger_keywords": ["critical intelligence", "urgent intel", "breakthrough discovery"],
        "trigger_action_types": ["intelligence"],
        "meeting_type": MeetingType.AGENT_TALK.value,
        "suggested_participants": [],  # The intel agent
        "urgency": "high",
        "reason": "Critical intelligence requires PM briefing",
    },
]


# ============================================================================
# MEETING ORCHESTRATOR
# ============================================================================

class MeetingOrchestrator:
    """
    On-demand orchestrator for multi-agent meetings.
    NOT scheduled periodically - only activated when player initiates or
    when auto-triggers fire based on game events.
    """

    def __init__(self, simulation_manager: "SimulationManager" = None):
        self.sim = simulation_manager
        self.active_meeting: Optional[MeetingSession] = None
        self.meetings: List[MeetingSession] = []
        self.meeting_requests: List[MeetingRequest] = []
        self._load_state()

    def _load_state(self):
        """Load meetings state from file."""
        if MEETINGS_FILE.exists():
            try:
                with open(MEETINGS_FILE, 'r') as f:
                    data = json.load(f)
                self.meetings = [MeetingSession.from_dict(m) for m in data.get("meetings", [])]
                self.meeting_requests = [MeetingRequest.from_dict(r) for r in data.get("requests", [])]

                # Restore active meeting if any
                active_id = data.get("active_meeting_id")
                if active_id:
                    self.active_meeting = self.get_meeting(active_id)

                logger.info(f"Loaded {len(self.meetings)} meetings and {len(self.meeting_requests)} requests")
            except Exception as e:
                logger.error(f"Error loading meetings state: {e}")
                self.meetings = []
                self.meeting_requests = []
        else:
            self._save_state()

    def _save_state(self):
        """Save meetings state to file."""
        try:
            data = {
                "meetings": [m.to_dict() for m in self.meetings],
                "requests": [r.to_dict() for r in self.meeting_requests],
                "active_meeting_id": self.active_meeting.meeting_id if self.active_meeting else None,
            }
            with open(MEETINGS_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving meetings state: {e}")

    def get_meeting(self, meeting_id: str) -> Optional[MeetingSession]:
        """Get a meeting by ID."""
        for m in self.meetings:
            if m.meeting_id == meeting_id:
                return m
        return None

    def get_meetings_by_status(self, status: str) -> List[MeetingSession]:
        """Get all meetings with a specific status."""
        return [m for m in self.meetings if m.status == status]

    def get_pending_requests(self) -> List[MeetingRequest]:
        """Get all pending meeting requests."""
        return [r for r in self.meeting_requests if r.status == MeetingRequestStatus.PENDING.value]

    # -------------------------------------------------------------------------
    # Meeting Lifecycle
    # -------------------------------------------------------------------------

    async def create_meeting(
        self,
        meeting_type: str,
        title: str,
        participant_configs: List[dict],  # [{"agent_id": str, "role": str, "initial_position": str}]
        agenda_items: List[str],
        scheduled_game_time: str,
        description: str = "",
        chair_agent_id: str = None,
        stakes: str = "",
        meeting_context: str = "",
    ) -> MeetingSession:
        """Create a new scheduled meeting."""
        meeting_id = f"mtg_{uuid.uuid4().hex[:8]}"

        # Build participants
        participants = []
        for config in participant_configs:
            agent_id = config["agent_id"]
            # Get entity from agent data
            agent_data = app.agents.get(agent_id, {})
            entity = agent_data.get("entity_name", agent_id.split("-")[0] if "-" in agent_id else agent_id)

            participant = MeetingParticipant(
                agent_id=agent_id,
                role=config.get("role", ParticipantRole.PRINCIPAL.value),
                entity=entity,
                initial_position=config.get("initial_position", ""),
                current_position=config.get("initial_position", ""),
                is_player=config.get("is_player", False),
            )
            participants.append(participant)

        # Build agenda
        agenda = MeetingAgenda(
            agenda_id=f"agd_{uuid.uuid4().hex[:8]}",
            items=agenda_items,
        ) if agenda_items else None

        # Get meeting type config
        type_config = MEETING_TYPE_CONFIG.get(meeting_type, {})

        meeting = MeetingSession(
            meeting_id=meeting_id,
            meeting_type=meeting_type,
            title=title,
            description=description or type_config.get("description", ""),
            status=MeetingStatus.SCHEDULED.value,
            created_at=datetime.now().isoformat(),
            scheduled_game_time=scheduled_game_time,
            participants=participants,
            chair_agent_id=chair_agent_id,
            agenda=agenda,
            max_rounds=type_config.get("max_rounds", 10),
            meeting_context=meeting_context,
            stakes=stakes,
        )

        self.meetings.append(meeting)
        self._save_state()

        logger.info(f"Created meeting {meeting_id}: {title} ({meeting_type})")
        return meeting

    async def start_meeting(self, meeting_id: str) -> dict:
        """
        Start a scheduled meeting.
        Pauses the main simulation and activates the meeting.
        """
        meeting = self.get_meeting(meeting_id)
        if not meeting:
            raise ValueError(f"Meeting {meeting_id} not found")

        if meeting.status not in [MeetingStatus.SCHEDULED.value, MeetingStatus.PENDING.value]:
            raise ValueError(f"Meeting {meeting_id} cannot be started (status: {meeting.status})")

        if self.active_meeting:
            raise ValueError(f"Another meeting is already active: {self.active_meeting.meeting_id}")

        # Pause simulation
        if self.sim:
            await self._pause_simulation(meeting_id)

        # Update meeting state
        game_time = self.sim.state.game_clock.get_game_time().isoformat() if self.sim else datetime.now().isoformat()
        meeting.status = MeetingStatus.ACTIVE.value
        meeting.started_at = game_time
        self.active_meeting = meeting

        # Build initial context for participants
        await self._build_participant_contexts(meeting)

        self._save_state()

        logger.info(f"Started meeting {meeting_id}: {meeting.title}")

        return {
            "meeting_id": meeting_id,
            "status": "active",
            "participants": [p.to_dict() for p in meeting.participants],
            "agenda": meeting.agenda.to_dict() if meeting.agenda else None,
            "current_round": meeting.current_round,
        }

    async def conclude_meeting(self, meeting_id: str, forced: bool = False) -> MeetingOutcome:
        """
        End meeting and generate outcomes/events.
        Resumes the main simulation.
        """
        meeting = self.get_meeting(meeting_id)
        if not meeting:
            raise ValueError(f"Meeting {meeting_id} not found")

        if meeting.status != MeetingStatus.ACTIVE.value and not forced:
            raise ValueError(f"Meeting {meeting_id} is not active")

        # Extract outcomes
        outcome = await self._extract_outcomes(meeting)
        meeting.outcome = outcome

        # Update meeting state
        game_time = self.sim.state.game_clock.get_game_time().isoformat() if self.sim else datetime.now().isoformat()
        meeting.status = MeetingStatus.CONCLUDED.value
        meeting.ended_at = game_time

        # Generate events from outcomes
        if self.sim:
            await self._generate_events_from_outcome(meeting, outcome)
            await self._inject_memories_from_outcome(meeting, outcome)

        # Resume simulation
        if self.sim:
            await self._resume_simulation(meeting_id)

        self.active_meeting = None
        self._save_state()

        logger.info(f"Concluded meeting {meeting_id}: {outcome.outcome_type}")

        return outcome

    async def abort_meeting(self, meeting_id: str) -> MeetingOutcome:
        """Abort meeting without proper conclusion."""
        meeting = self.get_meeting(meeting_id)
        if not meeting:
            raise ValueError(f"Meeting {meeting_id} not found")

        game_time = self.sim.state.game_clock.get_game_time().isoformat() if self.sim else datetime.now().isoformat()

        outcome = MeetingOutcome(
            outcome_id=f"out_{uuid.uuid4().hex[:8]}",
            meeting_id=meeting_id,
            outcome_type="aborted",
            summary="Meeting was aborted by the player without reaching any conclusions.",
        )

        meeting.outcome = outcome
        meeting.status = MeetingStatus.ABORTED.value
        meeting.ended_at = game_time

        # Resume simulation
        if self.sim:
            await self._resume_simulation(meeting_id)

        self.active_meeting = None
        self._save_state()

        logger.info(f"Aborted meeting {meeting_id}")
        return outcome

    # -------------------------------------------------------------------------
    # Turn Management
    # -------------------------------------------------------------------------

    async def execute_turn(self, speaker_agent_id: str) -> MeetingTurn:
        """Execute one turn for a specific participant using LLM."""
        if not self.active_meeting:
            raise ValueError("No active meeting")

        meeting = self.active_meeting
        participant = meeting.get_participant(speaker_agent_id)

        if not participant:
            raise ValueError(f"Agent {speaker_agent_id} is not a participant")

        if participant.is_player:
            raise ValueError("Use player_interject for player turns")

        # Build prompt
        prompt = await self._build_turn_prompt(meeting, participant)

        # Call LLM
        response = await self._call_llm_for_turn(speaker_agent_id, prompt)

        # Parse response and create turn
        turn = self._parse_turn_response(meeting, participant, response)

        # Update participant state
        participant.has_spoken_this_round = True
        participant.turn_count += 1
        if turn.position_update:
            participant.current_position = turn.position_update

        # Add turn to meeting
        meeting.turns.append(turn)
        self._save_state()

        logger.info(f"Turn executed: {speaker_agent_id} in meeting {meeting.meeting_id}")

        return turn

    async def player_interject(
        self,
        content: str,
        action_type: str = "statement",
        addressed_to: List[str] = None,
        emotional_tone: str = "calm",
    ) -> MeetingTurn:
        """Handle player (PM) interjection during meeting."""
        if not self.active_meeting:
            raise ValueError("No active meeting")

        meeting = self.active_meeting
        game_time = self.sim.state.game_clock.get_game_time().isoformat() if self.sim else datetime.now().isoformat()

        turn = MeetingTurn(
            turn_id=f"turn_{uuid.uuid4().hex[:8]}",
            turn_number=len(meeting.turns) + 1,
            speaker_agent_id="PM",
            speaker_role=ParticipantRole.CHAIR.value,
            content=content,
            action_type=action_type,
            timestamp=game_time,
            is_player_input=True,
            addressed_to=addressed_to or [],
            emotional_tone=emotional_tone,
        )

        meeting.turns.append(turn)
        self._save_state()

        logger.info(f"PM interjection in meeting {meeting.meeting_id}")

        return turn

    async def advance_round(self) -> List[MeetingTurn]:
        """
        Execute a full round where all non-player participants speak.
        Returns all turns from this round.
        """
        if not self.active_meeting:
            raise ValueError("No active meeting")

        meeting = self.active_meeting

        if meeting.current_round >= meeting.max_rounds:
            raise ValueError(f"Meeting has reached max rounds ({meeting.max_rounds})")

        # Reset round flags
        meeting.reset_round_flags()
        meeting.current_round += 1

        # Determine speaking order
        speaking_order = self._determine_speaking_order(meeting)

        # Execute turns for each participant
        round_turns = []
        for agent_id in speaking_order:
            participant = meeting.get_participant(agent_id)
            if participant and not participant.is_player and participant.role != ParticipantRole.OBSERVER.value:
                try:
                    turn = await self.execute_turn(agent_id)
                    round_turns.append(turn)
                except Exception as e:
                    logger.error(f"Error executing turn for {agent_id}: {e}")

        # Update state summary
        meeting.current_state_summary = await self._generate_state_summary(meeting)

        self._save_state()

        return round_turns

    def _determine_speaking_order(self, meeting: MeetingSession) -> List[str]:
        """Determine the order in which participants speak."""
        order = []

        if meeting.meeting_type == MeetingType.CABINET_WAR_ROOM.value:
            # Advisors brief first, then principals
            advisors = meeting.get_participants_by_role(ParticipantRole.ADVISOR.value)
            principals = meeting.get_participants_by_role(ParticipantRole.PRINCIPAL.value)
            order = [p.agent_id for p in advisors] + [p.agent_id for p in principals]

        elif meeting.meeting_type == MeetingType.NEGOTIATION.value:
            # Mediators first (if any), then principals alternating
            mediators = meeting.get_participants_by_role(ParticipantRole.MEDIATOR.value)
            principals = meeting.get_participants_by_role(ParticipantRole.PRINCIPAL.value)
            order = [p.agent_id for p in mediators] + [p.agent_id for p in principals]

        else:
            # Default: non-player, non-observer participants
            order = [
                p.agent_id for p in meeting.participants
                if not p.is_player and p.role != ParticipantRole.OBSERVER.value
            ]

        return order

    # -------------------------------------------------------------------------
    # Meeting Request Handling
    # -------------------------------------------------------------------------

    def create_meeting_request(
        self,
        meeting_type: str,
        requested_by: str,
        reason: str,
        title: str,
        suggested_participants: List[str] = None,
        suggested_agenda: List[str] = None,
        urgency: str = "normal",
        trigger_event_id: str = None,
    ) -> MeetingRequest:
        """Create a new meeting request (from AI or system)."""
        request = MeetingRequest(
            request_id=f"req_{uuid.uuid4().hex[:8]}",
            meeting_type=meeting_type,
            requested_by=requested_by,
            reason=reason,
            title=title,
            suggested_participants=suggested_participants or [],
            suggested_agenda=suggested_agenda or [],
            urgency=urgency,
            trigger_event_id=trigger_event_id,
            status=MeetingRequestStatus.PENDING.value,
            created_at=datetime.now().isoformat(),
        )

        self.meeting_requests.append(request)
        self._save_state()

        logger.info(f"Meeting request created: {request.request_id} by {requested_by}")

        return request

    def check_auto_triggers(self, event: "SimulationEvent"):
        """Check if an event should trigger a meeting request."""
        event_text = f"{event.summary} {event.action_type}".lower()

        for rule in AUTO_TRIGGER_RULES:
            # Check action type match
            if rule["trigger_action_types"] and event.action_type not in rule["trigger_action_types"]:
                continue

            # Check keyword match
            keyword_match = any(kw in event_text for kw in rule["trigger_keywords"])
            if not keyword_match:
                continue

            # Check if we already have a similar pending request
            existing = [
                r for r in self.meeting_requests
                if r.status == MeetingRequestStatus.PENDING.value
                and r.meeting_type == rule["meeting_type"]
            ]
            if existing:
                continue

            # Determine participants
            participants = rule["suggested_participants"].copy()
            if not participants:
                # Add affected agents
                participants = event.affected_agents.copy()
            if event.agent_id not in participants:
                participants.append(event.agent_id)

            # Create the request
            self.create_meeting_request(
                meeting_type=rule["meeting_type"],
                requested_by="system",
                reason=rule["reason"],
                title=f"Auto-triggered: {rule['name']}",
                suggested_participants=participants,
                urgency=rule["urgency"],
                trigger_event_id=event.event_id,
            )

            logger.info(f"Auto-trigger fired: {rule['name']} for event {event.event_id}")

    def approve_request(self, request_id: str) -> MeetingRequest:
        """Approve a meeting request."""
        for req in self.meeting_requests:
            if req.request_id == request_id:
                req.status = MeetingRequestStatus.APPROVED.value
                self._save_state()
                return req
        raise ValueError(f"Request {request_id} not found")

    def reject_request(self, request_id: str) -> MeetingRequest:
        """Reject a meeting request."""
        for req in self.meeting_requests:
            if req.request_id == request_id:
                req.status = MeetingRequestStatus.REJECTED.value
                self._save_state()
                return req
        raise ValueError(f"Request {request_id} not found")

    # -------------------------------------------------------------------------
    # Private Helper Methods
    # -------------------------------------------------------------------------

    async def _pause_simulation(self, meeting_id: str):
        """Pause the main simulation for a meeting."""
        if self.sim and self.sim.state:
            self.sim.state.paused_for_meeting = True
            self.sim.state.active_meeting_id = meeting_id
            logger.info(f"Simulation paused for meeting {meeting_id}")

    async def _resume_simulation(self, meeting_id: str):
        """Resume the main simulation after a meeting."""
        if self.sim and self.sim.state:
            self.sim.state.paused_for_meeting = False
            self.sim.state.active_meeting_id = None
            logger.info(f"Simulation resumed after meeting {meeting_id}")

    async def _build_participant_contexts(self, meeting: MeetingSession):
        """Build initial context for all participants."""
        for participant in meeting.participants:
            if participant.is_player:
                continue

            # Get agent data
            agent_data = app.agents.get(participant.agent_id, {})

            # Build context from agent's agenda, objectives, etc.
            context_parts = []
            if agent_data.get("agenda"):
                context_parts.append(f"Your agenda: {agent_data['agenda']}")
            if agent_data.get("primary_objectives"):
                context_parts.append(f"Your objectives: {agent_data['primary_objectives']}")

            if not participant.initial_position:
                participant.initial_position = " ".join(context_parts) if context_parts else "Represent your entity's interests."
                participant.current_position = participant.initial_position

    async def _build_turn_prompt(self, meeting: MeetingSession, participant: MeetingParticipant) -> str:
        """Build the prompt for a participant's turn."""
        # Get recent turns (last 7)
        recent_turns = meeting.turns[-7:] if meeting.turns else []
        turns_text = self._format_turns_for_prompt(recent_turns)

        # Get agent memory
        agent_memory = app.agent_memory.get(participant.agent_id, [])
        memory_text = "\n".join(agent_memory[-5:]) if agent_memory else "No recent memories."

        # Get agent objectives
        agent_data = app.agents.get(participant.agent_id, {})
        objectives = agent_data.get("primary_objectives", agent_data.get("agenda", ""))

        # Build participants list
        participants_list = "\n".join([
            f"- {p.agent_id} ({p.role}): {p.entity}"
            for p in meeting.participants
        ])

        # Get current agenda item
        current_item = meeting.agenda.current_item() if meeting.agenda else "General discussion"

        # Get role-specific rules
        role_rules = ROLE_SPECIFIC_RULES.get(participant.role, "")

        # Format prompt
        prompt = MEETING_TURN_PROMPT.format(
            agent_id=participant.agent_id,
            meeting_type=meeting.meeting_type,
            meeting_type_display=MEETING_TYPE_CONFIG.get(meeting.meeting_type, {}).get("display_name", meeting.meeting_type),
            title=meeting.title,
            game_time=meeting.started_at,
            participant_role=participant.role,
            current_round=meeting.current_round,
            max_rounds=meeting.max_rounds,
            participants_list=participants_list,
            current_agenda_item=current_item,
            initial_position=participant.initial_position,
            current_position=participant.current_position,
            recent_turns=turns_text,
            agent_objectives=objectives,
            agent_memory=memory_text,
            role_specific_rules=role_rules,
        )

        return prompt

    def _format_turns_for_prompt(self, turns: List[MeetingTurn]) -> str:
        """Format turns for inclusion in prompts."""
        if not turns:
            return "No previous turns in this meeting."

        lines = []
        for turn in turns:
            speaker = turn.speaker_agent_id
            if turn.is_player_input:
                speaker = "PM (Player)"

            tone_indicator = f"[{turn.emotional_tone}]" if turn.emotional_tone != "neutral" else ""
            addressed = f" (to {', '.join(turn.addressed_to)})" if turn.addressed_to else ""

            lines.append(f"**{speaker}** {tone_indicator}{addressed}: {turn.content}")

        return "\n\n".join(lines)

    async def _call_llm_for_turn(self, agent_id: str, prompt: str) -> str:
        """Call LLM to generate a turn response."""
        agent_data = app.agents.get(agent_id, {})
        model = agent_data.get("model", "claude-sonnet-4-20250514")
        system_prompt = agent_data.get("system_prompt", "You are a participant in a diplomatic meeting.")

        try:
            response = app.client.messages.create(
                model=model,
                max_tokens=500,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"LLM call failed for {agent_id}: {e}")
            raise

    def _parse_turn_response(self, meeting: MeetingSession, participant: MeetingParticipant, response: str) -> MeetingTurn:
        """Parse LLM response into a MeetingTurn."""
        game_time = self.sim.state.game_clock.get_game_time().isoformat() if self.sim else datetime.now().isoformat()

        # Try to extract JSON from response
        try:
            # Find JSON in response
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
            else:
                # Fallback: treat entire response as content
                data = {
                    "action_type": "statement",
                    "content": response,
                    "emotional_tone": "neutral",
                }
        except json.JSONDecodeError:
            data = {
                "action_type": "statement",
                "content": response,
                "emotional_tone": "neutral",
            }

        turn = MeetingTurn(
            turn_id=f"turn_{uuid.uuid4().hex[:8]}",
            turn_number=len(meeting.turns) + 1,
            speaker_agent_id=participant.agent_id,
            speaker_role=participant.role,
            content=data.get("content", response),
            action_type=data.get("action_type", "statement"),
            timestamp=game_time,
            addressed_to=data.get("addressed_to", []),
            private_reasoning=data.get("private_reasoning", ""),
            emotional_tone=data.get("emotional_tone", "neutral"),
            position_update=data.get("position_update", ""),
        )

        return turn

    async def _extract_outcomes(self, meeting: MeetingSession) -> MeetingOutcome:
        """Use LLM to extract outcomes from meeting transcript."""
        if not meeting.turns:
            return MeetingOutcome(
                outcome_id=f"out_{uuid.uuid4().hex[:8]}",
                meeting_id=meeting.meeting_id,
                outcome_type="tabled",
                summary="Meeting concluded without any discussion.",
            )

        # Format all turns
        all_turns = self._format_turns_for_prompt(meeting.turns)

        # Build participants string
        participants = ", ".join([f"{p.agent_id} ({p.role})" for p in meeting.participants])

        # Build agenda string
        agenda_items = ", ".join(meeting.agenda.items) if meeting.agenda else "General discussion"

        prompt = MEETING_OUTCOME_PROMPT.format(
            meeting_type=meeting.meeting_type,
            title=meeting.title,
            participants=participants,
            agenda_items=agenda_items,
            all_turns=all_turns,
        )

        try:
            response = app.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )
            response_text = response.content[0].text

            # Parse JSON response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = {"outcome_type": "tabled", "summary": "Could not extract outcomes."}

            outcome = MeetingOutcome(
                outcome_id=f"out_{uuid.uuid4().hex[:8]}",
                meeting_id=meeting.meeting_id,
                outcome_type=data.get("outcome_type", "tabled"),
                summary=data.get("summary", ""),
                agreements=data.get("agreements", []),
                commitments=data.get("commitments", []),
                unresolved_items=data.get("unresolved_items", []),
                follow_up_required=data.get("follow_up_required", False),
                follow_up_details=data.get("follow_up_description", ""),
            )

            # Store events and approvals for later generation
            outcome._events_to_generate = data.get("events_to_generate", [])
            outcome._memory_injections = data.get("memory_injections", [])
            outcome._pm_approvals = data.get("requires_pm_approval", [])

            return outcome

        except Exception as e:
            logger.error(f"Outcome extraction failed: {e}")
            return MeetingOutcome(
                outcome_id=f"out_{uuid.uuid4().hex[:8]}",
                meeting_id=meeting.meeting_id,
                outcome_type="tabled",
                summary=f"Error extracting outcomes: {str(e)}",
            )

    async def _generate_events_from_outcome(self, meeting: MeetingSession, outcome: MeetingOutcome):
        """Generate SimulationEvents from meeting outcomes."""
        from simulation import SimulationEvent

        events_to_generate = getattr(outcome, '_events_to_generate', [])

        for event_data in events_to_generate:
            game_time = self.sim.state.game_clock.get_game_time().isoformat()

            event = SimulationEvent(
                event_id=f"mtg_evt_{uuid.uuid4().hex[:8]}",
                timestamp=game_time,
                agent_id=event_data.get("agent_id", "System-Meeting"),
                action_type=event_data.get("action_type", "diplomatic"),
                summary=event_data.get("summary", ""),
                is_public=event_data.get("is_public", True),
                affected_agents=event_data.get("affected_agents", []),
                reasoning=f"Generated from meeting {meeting.meeting_id}",
                resolution_status="immediate",
            )

            self.sim.state.add_event(event)
            outcome.events_generated.append(event.event_id)

            logger.info(f"Generated event {event.event_id} from meeting {meeting.meeting_id}")

    async def _inject_memories_from_outcome(self, meeting: MeetingSession, outcome: MeetingOutcome):
        """Inject meeting outcome memories to participants."""
        # Get memory injections from outcome extraction
        memory_injections = getattr(outcome, '_memory_injections', [])

        # Always inject a summary to all participants
        summary_memory = f"[MEETING] {meeting.title}: {outcome.summary}"

        for participant in meeting.participants:
            if not participant.is_player:
                app.add_memory(participant.agent_id, summary_memory)

        # Inject specific memories
        for injection in memory_injections:
            agent_id = injection.get("agent_id")
            memory_text = injection.get("memory_text")
            if agent_id and memory_text:
                app.add_memory(agent_id, f"[MEETING] {memory_text}")

    async def _generate_state_summary(self, meeting: MeetingSession) -> str:
        """Generate a summary of current meeting state."""
        if not meeting.turns:
            return "Meeting has just begun."

        recent_turns = meeting.turns[-5:]
        turns_text = self._format_turns_for_prompt(recent_turns)
        participants = ", ".join([p.agent_id for p in meeting.participants])

        prompt = MEETING_SUMMARY_PROMPT.format(
            meeting_type=meeting.meeting_type,
            current_round=meeting.current_round,
            participants=participants,
            recent_turns=turns_text,
        )

        try:
            response = app.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"State summary generation failed: {e}")
            return "Unable to generate summary."

    # -------------------------------------------------------------------------
    # State Accessors for API
    # -------------------------------------------------------------------------

    def get_state(self) -> dict:
        """Get complete meeting system state for API."""
        return {
            "active_meeting": self.active_meeting.to_dict() if self.active_meeting else None,
            "scheduled_meetings": [m.to_dict() for m in self.get_meetings_by_status(MeetingStatus.SCHEDULED.value)],
            "pending_meetings": [m.to_dict() for m in self.get_meetings_by_status(MeetingStatus.PENDING.value)],
            "concluded_meetings": [m.to_dict() for m in self.get_meetings_by_status(MeetingStatus.CONCLUDED.value)][-10:],
            "meeting_requests": [r.to_dict() for r in self.get_pending_requests()],
            "meeting_types": {k: v for k, v in MEETING_TYPE_CONFIG.items()},
        }
