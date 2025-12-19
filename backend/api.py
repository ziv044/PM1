"""FastAPI server for PM1 Agent Admin Panel."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
from pathlib import Path
import app

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


# Pydantic models for request/response
class AgentCreate(BaseModel):
    agent_id: str
    model: str = "claude-sonnet-4-20250514"
    system_prompt: str = ""


class AgentUpdate(BaseModel):
    model: Optional[str] = None
    system_prompt: Optional[str] = None


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
    result = app.get_agent(agent_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@api.post("/agents")
def create_agent(agent: AgentCreate):
    """Create a new agent."""
    result = app.agent_add(
        agent_id=agent.agent_id,
        model=agent.model,
        system_prompt=agent.system_prompt
    )
    return result


@api.put("/agents/{agent_id}")
def update_agent(agent_id: str, agent: AgentUpdate):
    """Update an existing agent."""
    result = app.agent_update(
        agent_id=agent_id,
        model=agent.model,
        system_prompt=agent.system_prompt
    )
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@api.delete("/agents/{agent_id}")
def delete_agent(agent_id: str):
    """Delete an agent."""
    result = app.agent_remove(agent_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@api.get("/agents/{agent_id}/skills")
def get_skills(agent_id: str):
    """Get an agent's skills."""
    result = app.get_skills(agent_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@api.post("/agents/{agent_id}/skills")
def add_skills(agent_id: str, skills: SkillAdd):
    """Add skills to an agent."""
    result = app.add_skills(agent_id, skills.skills)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@api.get("/agents/{agent_id}/memory")
def get_memory(agent_id: str):
    """Get an agent's memory."""
    result = app.get_memory(agent_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@api.post("/agents/{agent_id}/memory")
def add_memory(agent_id: str, memory: MemoryAdd):
    """Add memory to an agent."""
    result = app.add_memory(agent_id, memory.memory_item)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@api.get("/agents/{agent_id}/conversation")
def get_conversation(agent_id: str):
    """Get an agent's conversation history."""
    result = app.get_conversation(agent_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@api.post("/agents/{agent_id}/chat")
def chat_with_agent(agent_id: str, chat: ChatMessage):
    """Send a message to an agent and get a response."""
    result = app.interact_with_claude(
        agent_id=agent_id,
        user_message=chat.message,
        max_tokens=chat.max_tokens,
        temperature=chat.temperature,
        stream=chat.stream
    )
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
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


# Mount static files for frontend (CSS, JS)
if FRONTEND_DIR.exists():
    api.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
    api.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(api, host="0.0.0.0", port=8000, reload=True)
