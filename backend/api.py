"""FastAPI server for PM1 Agent Admin Panel."""
import re
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, field_validator
from typing import Optional, List
from pathlib import Path
import app


# === Centralized Error Handling ===

class APIError(Exception):
    """Base API error with status code and message."""
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(APIError):
    """Resource not found error."""
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=404)


class ValidationError(APIError):
    """Input validation error."""
    def __init__(self, message: str = "Invalid input"):
        super().__init__(message, status_code=422)


# Agent ID validation pattern: alphanumeric, hyphens, underscores, 1-64 chars
AGENT_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{1,64}$')


def validate_agent_id(agent_id: str) -> str:
    """Validate agent ID format. Raises ValidationError if invalid."""
    if not agent_id or not AGENT_ID_PATTERN.match(agent_id):
        raise ValidationError(
            f"Invalid agent_id: must be 1-64 alphanumeric characters, hyphens, or underscores"
        )
    return agent_id

# Create FastAPI app
api = FastAPI(title="PM1 Agent Admin API", version="1.0.0")

# Frontend directory
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

# Enable CORS for frontend
api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === Global Exception Handler ===

@api.exception_handler(APIError)
async def api_error_handler(request: Request, exc: APIError):
    """Handle all APIError subclasses with consistent JSON response."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "message": exc.message}
    )


@api.exception_handler(Exception)
async def general_error_handler(request: Request, exc: Exception):
    """Handle unexpected errors with consistent JSON response."""
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "Internal server error"}
    )


# Pydantic models for request/response
class AgentCreate(BaseModel):
    agent_id: str
    model: str = "claude-sonnet-4-20250514"
    system_prompt: str = ""
    entity_type: str = "System"
    event_frequency: int = 60
    is_enemy: bool = False
    is_west: bool = False
    is_evil_axis: bool = False
    agent_category: str = ""
    is_reporting_government: bool = False
    agenda: str = ""
    primary_objectives: str = ""
    hard_rules: str = ""
    is_enabled: bool = True

    @field_validator('agent_id')
    @classmethod
    def validate_agent_id_field(cls, v: str) -> str:
        if not v or not AGENT_ID_PATTERN.match(v):
            raise ValueError('agent_id must be 1-64 alphanumeric characters, hyphens, or underscores')
        return v


class AgentUpdate(BaseModel):
    model: Optional[str] = None
    system_prompt: Optional[str] = None
    entity_type: Optional[str] = None
    event_frequency: Optional[int] = None
    is_enemy: Optional[bool] = None
    is_west: Optional[bool] = None
    is_evil_axis: Optional[bool] = None
    agent_category: Optional[str] = None
    is_reporting_government: Optional[bool] = None
    agenda: Optional[str] = None
    primary_objectives: Optional[str] = None
    hard_rules: Optional[str] = None
    is_enabled: Optional[bool] = None


class SkillAdd(BaseModel):
    skills: List[str]


class MemoryAdd(BaseModel):
    memory_item: str


class ChatMessage(BaseModel):
    message: str
    max_tokens: int = 1024
    temperature: float = 1.0
    stream: bool = False


# Routes

@api.get("/")
def root():
    """Serve the main page."""
    return FileResponse(FRONTEND_DIR / "main.html")


@api.get("/admin")
def admin():
    """Serve the admin panel frontend."""
    return FileResponse(FRONTEND_DIR / "index.html")


@api.get("/api/health")
def health():
    """API health check."""
    return {"status": "ok", "message": "PM1 Agent Admin API"}


@api.get("/agents")
def list_agents():
    """Get all agents."""
    agents = app.get_all_agents()
    return {"status": "success", "agents": agents}


@api.get("/agents/{agent_id}")
def get_agent(agent_id: str):
    """Get a single agent by ID."""
    validate_agent_id(agent_id)
    result = app.get_agent(agent_id)
    if result.get("status") == "error":
        raise NotFoundError(result["message"])
    return result


@api.post("/agents")
def create_agent(agent: AgentCreate):
    """Create a new agent."""
    result = app.agent_add(
        agent_id=agent.agent_id,
        model=agent.model,
        system_prompt=agent.system_prompt,
        entity_type=agent.entity_type,
        event_frequency=agent.event_frequency,
        is_enemy=agent.is_enemy,
        is_west=agent.is_west,
        is_evil_axis=agent.is_evil_axis,
        agent_category=agent.agent_category,
        is_reporting_government=agent.is_reporting_government,
        agenda=agent.agenda,
        primary_objectives=agent.primary_objectives,
        hard_rules=agent.hard_rules,
        is_enabled=agent.is_enabled
    )
    return result


@api.put("/agents/{agent_id}")
def update_agent(agent_id: str, agent: AgentUpdate):
    """Update an existing agent."""
    validate_agent_id(agent_id)
    result = app.agent_update(
        agent_id=agent_id,
        model=agent.model,
        system_prompt=agent.system_prompt,
        entity_type=agent.entity_type,
        event_frequency=agent.event_frequency,
        is_enemy=agent.is_enemy,
        is_west=agent.is_west,
        is_evil_axis=agent.is_evil_axis,
        agent_category=agent.agent_category,
        is_reporting_government=agent.is_reporting_government,
        agenda=agent.agenda,
        primary_objectives=agent.primary_objectives,
        hard_rules=agent.hard_rules,
        is_enabled=agent.is_enabled
    )
    if result.get("status") == "error":
        raise NotFoundError(result["message"])
    return result


@api.delete("/agents/{agent_id}")
def delete_agent(agent_id: str):
    """Delete an agent."""
    validate_agent_id(agent_id)
    result = app.agent_remove(agent_id)
    if result.get("status") == "error":
        raise NotFoundError(result["message"])
    return result


@api.post("/agents/{agent_id}/toggle-enabled")
def toggle_agent_enabled(agent_id: str):
    """Toggle an agent's enabled status."""
    validate_agent_id(agent_id)
    result = app.toggle_agent_enabled(agent_id)
    if result.get("status") == "error":
        raise NotFoundError(result["message"])
    return result


class BulkEnabledUpdate(BaseModel):
    enabled: bool


@api.post("/agents/bulk-enabled")
def set_all_agents_enabled(update: BulkEnabledUpdate):
    """Enable or disable all agents."""
    result = app.set_all_agents_enabled(update.enabled)
    return result


@api.get("/agents/{agent_id}/skills")
def get_skills(agent_id: str):
    """Get an agent's skills."""
    validate_agent_id(agent_id)
    result = app.get_skills(agent_id)
    if result.get("status") == "error":
        raise NotFoundError(result["message"])
    return result


@api.post("/agents/{agent_id}/skills")
def add_skills(agent_id: str, skills: SkillAdd):
    """Add skills to an agent."""
    validate_agent_id(agent_id)
    result = app.add_skills(agent_id, skills.skills)
    if result.get("status") == "error":
        raise NotFoundError(result["message"])
    return result


@api.get("/agents/{agent_id}/memory")
def get_memory(agent_id: str):
    """Get an agent's memory."""
    validate_agent_id(agent_id)
    result = app.get_memory(agent_id)
    if result.get("status") == "error":
        raise NotFoundError(result["message"])
    return result


@api.post("/agents/{agent_id}/memory")
def add_memory(agent_id: str, memory: MemoryAdd):
    """Add memory to an agent."""
    validate_agent_id(agent_id)
    result = app.add_memory(agent_id, memory.memory_item)
    if result.get("status") == "error":
        raise NotFoundError(result["message"])
    return result


@api.get("/agents/{agent_id}/conversation")
def get_conversation(agent_id: str):
    """Get an agent's conversation history."""
    validate_agent_id(agent_id)
    result = app.get_conversation(agent_id)
    if result.get("status") == "error":
        raise NotFoundError(result["message"])
    return result


@api.post("/agents/{agent_id}/chat")
def chat_with_agent(agent_id: str, chat: ChatMessage):
    """Send a message to an agent and get a response."""
    validate_agent_id(agent_id)
    result = app.interact_with_claude(
        agent_id=agent_id,
        user_message=chat.message,
        max_tokens=chat.max_tokens,
        temperature=chat.temperature,
        stream=chat.stream
    )
    if result.get("status") == "error":
        raise NotFoundError(result["message"])
    return result


@api.get("/logs")
def get_logs():
    """Get application logs including simulation/resolver logs."""
    logs_dir = Path(__file__).parent / "logs"
    if not logs_dir.exists():
        return {"status": "success", "logs": []}

    # Find log files from both app_logs and simulation
    all_lines = []

    # Get app_logs
    app_log_files = list(logs_dir.glob("app_logs*.log"))
    if app_log_files:
        app_log_file = max(app_log_files, key=lambda f: f.stat().st_mtime)
        with open(app_log_file, "r", encoding="utf-8", errors="replace") as f:
            all_lines.extend(f.readlines()[-50:])  # Last 50 from app logs

    # Get simulation logs (includes resolver activity)
    sim_log_files = list(logs_dir.glob("simulation*.log"))
    if sim_log_files:
        sim_log_file = max(sim_log_files, key=lambda f: f.stat().st_mtime)
        with open(sim_log_file, "r", encoding="utf-8", errors="replace") as f:
            all_lines.extend(f.readlines()[-50:])  # Last 50 from simulation logs

    if not all_lines:
        return {"status": "success", "logs": []}

    # Sort by timestamp (logs format: 2025-12-20 00:42:24,819 - ...)
    # Lines with timestamps sort correctly as strings
    all_lines.sort()

    # Return last 100 combined
    return {"status": "success", "logs": all_lines[-100:]}


# Simulation Pydantic models
class SimulationConfig(BaseModel):
    clock_speed: Optional[float] = 2.0


class ClockSpeedUpdate(BaseModel):
    clock_speed: float


class GameTimeUpdate(BaseModel):
    game_time: str  # ISO format datetime string


# Simulation endpoints
@api.post("/simulation/start")
async def start_simulation(config: SimulationConfig = None):
    """Start the game simulation."""
    import simulation
    if config and config.clock_speed:
        simulation.set_clock_speed(config.clock_speed)
    result = await simulation.start_game()
    return result


@api.post("/simulation/stop")
async def stop_simulation():
    """Stop the game simulation."""
    import simulation
    result = await simulation.stop_game()
    return result


@api.get("/simulation/status")
def get_simulation_status():
    """Get current simulation status."""
    import simulation
    return simulation.get_status()


@api.get("/simulation/events")
def get_simulation_events(
    since: Optional[str] = None,
    agent_id: Optional[str] = None,
    limit: int = 100
):
    """Get simulation events with optional filters."""
    import simulation
    events = simulation.get_events(since, agent_id, limit)
    return {"status": "success", "events": events}


@api.put("/simulation/clock-speed")
def update_clock_speed(update: ClockSpeedUpdate):
    """Update the simulation clock speed."""
    import simulation
    return simulation.set_clock_speed(update.clock_speed)


@api.put("/simulation/game-time")
def update_game_time(update: GameTimeUpdate):
    """Set the simulation game clock to a specific time."""
    import simulation
    return simulation.set_game_time(update.game_time)


@api.post("/simulation/save")
def save_simulation_state():
    """Manually save the current simulation state."""
    import simulation
    return simulation.save_state()


# Debug Console endpoints

@api.get("/debug/activity")
def get_debug_activity(
    agent_id: Optional[str] = None,
    activity_type: Optional[str] = None,
    limit: int = 100
):
    """Get activity log for the debug console."""
    activities = app.get_activity_log(agent_id, activity_type, limit)
    return {"status": "success", "activities": activities}


@api.get("/debug/stats")
def get_debug_stats():
    """Get activity statistics for the debug console."""
    stats = app.get_activity_stats()
    return {"status": "success", "stats": stats}


@api.delete("/debug/activity")
def clear_debug_activity():
    """Clear the activity log."""
    return app.clear_activity_log()


@api.post("/admin/cleanup")
def run_memory_and_event_cleanup():
    """One-time cleanup: prune all memories and archive resolved events.

    This endpoint:
    1. Prunes all agent memories to respect MAX_MEMORIES_PER_AGENT (7)
    2. Archives all resolved/failed events older than 60 game-minutes

    Use this to clean up accumulated data from previous runs.
    """
    import simulation

    # 1. Prune memories
    memory_result = app.prune_all_memories()

    # 2. Archive old events
    manager = simulation.SimulationManager.get_instance()
    game_time = manager.state.game_clock
    archived_count = manager.state.archive_resolved_events(game_time, archive_after_minutes=60)

    return {
        "status": "success",
        "memory_cleanup": memory_result,
        "events_archived": archived_count
    }


@api.delete("/agents/{agent_id}/conversation")
def clear_agent_conversation(agent_id: str):
    """Clear an agent's conversation history."""
    validate_agent_id(agent_id)
    result = app.clear_conversation(agent_id)
    if result.get("status") == "error":
        raise NotFoundError(result["message"])
    return result


@api.post("/agents/regenerate-prompts")
def regenerate_all_prompts():
    """Regenerate system_prompt for all agents from their component fields."""
    result = app.regenerate_all_system_prompts()
    return result


# KPI endpoints

@api.get("/kpis")
def get_all_kpis():
    """Get KPIs for all entities."""
    import simulation
    manager = simulation.SimulationManager.get_instance()
    all_kpis = manager.kpi_manager.get_all_kpis()
    return {"status": "success", "kpis": all_kpis}


@api.get("/kpis/{entity_id}")
def get_entity_kpis(entity_id: str):
    """Get KPIs for a specific entity."""
    import simulation
    manager = simulation.SimulationManager.get_instance()
    kpis = manager.kpi_manager.get_entity_kpis(entity_id)
    if not kpis:
        raise NotFoundError(f"No KPIs found for entity: {entity_id}")
    return {"status": "success", "entity_id": entity_id, "kpis": kpis}


@api.get("/simulation/pending-events")
def get_pending_events():
    """Get all events with pending resolution status."""
    import simulation
    manager = simulation.SimulationManager.get_instance()
    pending = manager.state.get_pending_events()
    return {
        "status": "success",
        "count": len(pending),
        "events": [e.to_dict() for e in pending]
    }


@api.post("/simulation/resolve")
async def trigger_resolution():
    """Manually trigger a resolution cycle."""
    import simulation
    manager = simulation.SimulationManager.get_instance()
    game_time = manager.clock.get_game_time_str()
    result = await manager.resolver.run_resolution_cycle(game_time)
    return result


# PM Approval endpoints

class PMDecision(BaseModel):
    decision: str  # approve | reject | modify
    notes: Optional[str] = None


@api.get("/simulation/pm-approvals")
def get_pm_approvals():
    """Get pending PM approval requests for the player."""
    import simulation
    manager = simulation.SimulationManager.get_instance()
    pending = manager.state.get_pending_approvals()
    return {
        "status": "success",
        "count": len(pending),
        "approvals": [r.to_dict() for r in pending]
    }


@api.post("/simulation/pm-approve/{approval_id}")
def process_pm_approval(approval_id: str, decision: PMDecision):
    """Process player's decision on an approval request."""
    import simulation
    manager = simulation.SimulationManager.get_instance()
    game_time = manager.clock.get_game_time_str()

    # Validate decision
    if decision.decision not in ["approve", "reject", "modify"]:
        raise ValidationError("Decision must be 'approve', 'reject', or 'modify'")

    success = manager.state.process_pm_decision(approval_id, decision.decision, game_time)
    if not success:
        raise NotFoundError(f"Approval request {approval_id} not found or already processed")

    return {
        "status": "success",
        "message": f"Decision '{decision.decision}' recorded for {approval_id}",
        "approval_id": approval_id,
        "decision": decision.decision
    }


@api.get("/simulation/ongoing-situations")
def get_ongoing_situations():
    """Get all active ongoing situations."""
    import simulation
    manager = simulation.SimulationManager.get_instance()
    active = manager.state.get_active_situations()
    return {
        "status": "success",
        "count": len(active),
        "situations": [s.to_dict() for s in active]
    }


@api.get("/simulation/situations")
def get_all_situations():
    """Get all ongoing situations (including completed)."""
    import simulation
    manager = simulation.SimulationManager.get_instance()
    all_situations = manager.state.ongoing_situations
    return {
        "status": "success",
        "count": len(all_situations),
        "situations": [s.to_dict() for s in all_situations]
    }


# Mount static files for frontend (CSS, JS)
if FRONTEND_DIR.exists():
    api.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
    api.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(api, host="0.0.0.0", port=8000, reload=True)
