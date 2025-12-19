import os
import json
import threading
from pathlib import Path
from dotenv import load_dotenv
import anthropic
from typing import Optional
from logger import setup_logger

load_dotenv()

logger = setup_logger("app_logs")

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Data file path
DATA_DIR = Path(__file__).parent.parent / "data"
AGENTS_FILE = DATA_DIR / "agents.json"

# Thread-safe global state
_state_lock = threading.Lock()
agents = {}
agent_skills = {}
agent_memory = {}


def save_agents() -> None:
    """Save agents, skills, and memory to JSON file."""
    DATA_DIR.mkdir(exist_ok=True)
    data = {
        "agents": agents,
        "skills": agent_skills,
        "memory": agent_memory
    }
    with open(AGENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info("Agents saved to file")


def load_agents() -> None:
    """Load agents, skills, and memory from JSON file."""
    global agents, agent_skills, agent_memory
    if AGENTS_FILE.exists():
        with open(AGENTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        agents = data.get("agents", {})
        agent_skills = data.get("skills", {})
        agent_memory = data.get("memory", {})
        logger.info(f"Loaded {len(agents)} agents from file")
    else:
        logger.info("No agents file found, starting fresh")


# Load agents on module import
load_agents()


def agent_add(
    agent_id: str,
    model: str = "claude-sonnet-4-20250514",
    system_prompt: str = "",
    entity_type: str = "System",
    event_frequency: int = 60,
    is_enemy: bool = False,
    is_west: bool = False,
    is_evil_axis: bool = False,
    agenda: str = "",
    primary_objectives: str = "",
    hard_rules: str = ""
) -> dict:
    logger.info(f"agent_add called - agent_id: {agent_id}, model: {model}, entity_type: {entity_type}")
    with _state_lock:
        agents[agent_id] = {
            "model": model,
            "system_prompt": system_prompt,
            "conversation": [],
            "entity_type": entity_type,
            "event_frequency": event_frequency,
            "is_enemy": is_enemy,
            "is_west": is_west,
            "is_evil_axis": is_evil_axis,
            "agenda": agenda,
            "primary_objectives": primary_objectives,
            "hard_rules": hard_rules
        }
        agent_skills[agent_id] = []
        agent_memory[agent_id] = []
        save_agents()
    logger.info(f"Agent {agent_id} created successfully")
    return {"status": "success", "agent_id": agent_id}


def agent_remove(agent_id: str) -> dict:
    logger.info(f"agent_remove called - agent_id: {agent_id}")
    with _state_lock:
        if agent_id not in agents:
            logger.warning(f"Agent {agent_id} not found")
            return {"status": "error", "message": f"Agent {agent_id} not found"}
        del agents[agent_id]
        agent_skills.pop(agent_id, None)  # Safe delete, no KeyError
        agent_memory.pop(agent_id, None)  # Safe delete, no KeyError
        save_agents()
    logger.info(f"Agent {agent_id} removed successfully")
    return {"status": "success", "message": f"Agent {agent_id} removed"}


def add_skills(agent_id: str, skills: list) -> dict:
    logger.info(f"add_skills called - agent_id: {agent_id}, skills: {skills}")
    with _state_lock:
        if agent_id not in agents:
            logger.error(f"Agent {agent_id} not found")
            return {"status": "error", "message": f"Agent {agent_id} not found"}
        agent_skills[agent_id].extend(skills)
        save_agents()
    logger.info(f"Skills added to agent {agent_id}: {skills}")
    return {"status": "success", "skills": agent_skills[agent_id]}


def add_memory(agent_id: str, memory_item: str) -> dict:
    logger.info(f"add_memory called - agent_id: {agent_id}, memory_item: {memory_item}")
    with _state_lock:
        if agent_id not in agents:
            logger.error(f"Agent {agent_id} not found")
            return {"status": "error", "message": f"Agent {agent_id} not found"}
        agent_memory[agent_id].append(memory_item)
        save_agents()
    logger.info(f"Memory added to agent {agent_id}")
    return {"status": "success", "memory": agent_memory[agent_id]}


def get_all_agents() -> dict:
    """Get all agents with their details."""
    result = {}
    for agent_id in agents:
        result[agent_id] = {
            **agents[agent_id],
            "skills": agent_skills.get(agent_id, []),
            "memory": agent_memory.get(agent_id, [])
        }
    return result


def get_agent(agent_id: str) -> dict:
    """Get a single agent's details."""
    if agent_id not in agents:
        return {"status": "error", "message": f"Agent {agent_id} not found"}
    return {
        "status": "success",
        "agent": {
            **agents[agent_id],
            "skills": agent_skills.get(agent_id, []),
            "memory": agent_memory.get(agent_id, [])
        }
    }


def get_skills(agent_id: str) -> dict:
    """Get an agent's skills."""
    if agent_id not in agents:
        return {"status": "error", "message": f"Agent {agent_id} not found"}
    return {"status": "success", "skills": agent_skills.get(agent_id, [])}


def get_memory(agent_id: str) -> dict:
    """Get an agent's memory."""
    if agent_id not in agents:
        return {"status": "error", "message": f"Agent {agent_id} not found"}
    return {"status": "success", "memory": agent_memory.get(agent_id, [])}


def get_conversation(agent_id: str) -> dict:
    """Get an agent's conversation history."""
    if agent_id not in agents:
        return {"status": "error", "message": f"Agent {agent_id} not found"}
    return {"status": "success", "conversation": agents[agent_id].get("conversation", [])}


def agent_update(
    agent_id: str,
    model: str = None,
    system_prompt: str = None,
    entity_type: str = None,
    event_frequency: int = None,
    is_enemy: bool = None,
    is_west: bool = None,
    is_evil_axis: bool = None,
    agenda: str = None,
    primary_objectives: str = None,
    hard_rules: str = None
) -> dict:
    """Update an existing agent's properties."""
    logger.info(f"agent_update called - agent_id: {agent_id}")
    with _state_lock:
        if agent_id not in agents:
            logger.error(f"Agent {agent_id} not found")
            return {"status": "error", "message": f"Agent {agent_id} not found"}
        if model is not None:
            agents[agent_id]["model"] = model
        if system_prompt is not None:
            agents[agent_id]["system_prompt"] = system_prompt
        if entity_type is not None:
            agents[agent_id]["entity_type"] = entity_type
        if event_frequency is not None:
            agents[agent_id]["event_frequency"] = event_frequency
        if is_enemy is not None:
            agents[agent_id]["is_enemy"] = is_enemy
        if is_west is not None:
            agents[agent_id]["is_west"] = is_west
        if is_evil_axis is not None:
            agents[agent_id]["is_evil_axis"] = is_evil_axis
        if agenda is not None:
            agents[agent_id]["agenda"] = agenda
        if primary_objectives is not None:
            agents[agent_id]["primary_objectives"] = primary_objectives
        if hard_rules is not None:
            agents[agent_id]["hard_rules"] = hard_rules
        save_agents()
        agent_copy = dict(agents[agent_id])
    logger.info(f"Agent {agent_id} updated successfully")
    return {"status": "success", "agent": agent_copy}


def prompt_caching(agent_id: str, cached_prompt: str) -> dict:
    logger.info(f"prompt_caching called - agent_id: {agent_id}")
    if agent_id not in agents:
        logger.error(f"Agent {agent_id} not found")
        return {"status": "error", "message": f"Agent {agent_id} not found"}
    agents[agent_id]["cached_prompt"] = {
        "type": "text",
        "text": cached_prompt,
        "cache_control": {"type": "ephemeral"}
    }
    save_agents()
    logger.info(f"Cached prompt set for agent {agent_id}")
    return {"status": "success", "message": "Prompt cached"}


def interact_with_claude(
    agent_id: str,
    user_message: str,
    max_tokens: int = 1024,
    temperature: float = 1.0,
    stream: bool = False
) -> dict:
    logger.info(f"interact_with_claude called - agent_id: {agent_id}, stream: {stream}")
    if agent_id not in agents:
        logger.error(f"Agent {agent_id} not found")
        return {"status": "error", "message": f"Agent {agent_id} not found"}

    agent = agents[agent_id]
    agent["conversation"].append({"role": "user", "content": user_message})

    system_content = agent.get("system_prompt", "")
    if agent_memory[agent_id]:
        system_content += f"\n\nMemory: {agent_memory[agent_id]}"
    if agent_skills[agent_id]:
        system_content += f"\n\nSkills: {agent_skills[agent_id]}"

    messages = agent["conversation"]
    if "cached_prompt" in agent:
        messages = [{"role": "user", "content": [agent["cached_prompt"], {"type": "text", "text": user_message}]}]

    try:
        if stream:
            logger.info("Streaming response...")
            response_text = ""
            with client.messages.stream(
                model=agent["model"],
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_content,
                messages=messages
            ) as stream_response:
                for text in stream_response.text_stream:
                    response_text += text
            response = response_text
        else:
            api_response = client.messages.create(
                model=agent["model"],
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_content,
                messages=messages
            )
            response = api_response.content[0].text

        agent["conversation"].append({"role": "assistant", "content": response})
        logger.info(f"Response received for agent {agent_id}")
        return {"status": "success", "response": response}

    except Exception as e:
        logger.error(f"Error interacting with Claude: {str(e)}")
        return {"status": "error", "message": str(e)}


def interact_simple(prompt: str, model: str = "claude-sonnet-4-20250514", max_tokens: int = 1024) -> dict:
    logger.info(f"interact_simple called - model: {model}")
    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        logger.info("Simple interaction completed")
        return {"status": "success", "response": response.content[0].text}
    except Exception as e:
        logger.error(f"Error in simple interaction: {str(e)}")
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    print("STARTED")
    logger.info("Application started")
