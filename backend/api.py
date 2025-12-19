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
    agenda: str = ""
    primary_objectives: str = ""
    hard_rules: str = ""

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
    agenda: Optional[str] = None
    primary_objectives: Optional[str] = None
    hard_rules: Optional[str] = None


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
        agenda=agent.agenda,
        primary_objectives=agent.primary_objectives,
        hard_rules=agent.hard_rules
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
        agenda=agent.agenda,
        primary_objectives=agent.primary_objectives,
        hard_rules=agent.hard_rules
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
    """Get application logs."""
    logs_dir = Path(__file__).parent / "logs"
    if not logs_dir.exists():
        return {"status": "success", "logs": []}

    # Find the most recent log file
    log_files = list(logs_dir.glob("app_logs*.log"))
    if not log_files:
        return {"status": "success", "logs": []}

    log_file = max(log_files, key=lambda f: f.stat().st_mtime)

    with open(log_file, "r", encoding="utf-8") as f:
        lines = f.readlines()[-100:]  # Last 100 lines

    return {"status": "success", "logs": lines}


# Simulation Pydantic models
class SimulationConfig(BaseModel):
    clock_speed: Optional[float] = 2.0


class ClockSpeedUpdate(BaseModel):
    clock_speed: float


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


# Mount static files for frontend (CSS, JS)
if FRONTEND_DIR.exists():
    api.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
    api.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(api, host="0.0.0.0", port=8000, reload=True)
