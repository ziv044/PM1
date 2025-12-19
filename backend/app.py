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

# Activity log for debug console (in-memory, max 500 entries)
_activity_log = []
_activity_lock = threading.Lock()
MAX_ACTIVITY_LOG = 500

# Memory cap per agent - auto-prune oldest memories when exceeded
MAX_MEMORIES_PER_AGENT = 7


def log_activity(
    activity_type: str,
    agent_id: str = None,
    action: str = "",
    details: str = "",
    duration_ms: int = None,
    success: bool = True,
    error: str = None
) -> None:
    """Log an activity for the debug console."""
    import datetime
    with _activity_lock:
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "type": activity_type,
            "agent_id": agent_id,
            "action": action,
            "details": details[:200] if details else "",  # Truncate long details
            "duration_ms": duration_ms,
            "success": success,
            "error": error
        }
        _activity_log.append(entry)
        # Keep only last MAX_ACTIVITY_LOG entries
        if len(_activity_log) > MAX_ACTIVITY_LOG:
            _activity_log.pop(0)


def get_activity_log(
    agent_id: str = None,
    activity_type: str = None,
    limit: int = 100
) -> list:
    """Get activity log entries with optional filters."""
    with _activity_lock:
        filtered = _activity_log.copy()

    if agent_id:
        filtered = [e for e in filtered if e.get("agent_id") == agent_id]
    if activity_type:
        filtered = [e for e in filtered if e.get("type") == activity_type]

    # Return most recent first
    return list(reversed(filtered[-limit:]))


def get_activity_stats() -> dict:
    """Get activity statistics for the debug console."""
    with _activity_lock:
        log_copy = _activity_log.copy()

    total_calls = len(log_copy)
    active_agents = len(set(e.get("agent_id") for e in log_copy if e.get("agent_id")))
    errors = sum(1 for e in log_copy if not e.get("success"))

    # Calculate average response time for successful calls with duration
    durations = [e.get("duration_ms") for e in log_copy if e.get("duration_ms") and e.get("success")]
    avg_time = sum(durations) / len(durations) if durations else None

    return {
        "total_calls": total_calls,
        "active_agents": active_agents,
        "errors": errors,
        "avg_response_time_ms": round(avg_time, 2) if avg_time else None
    }


def clear_activity_log() -> dict:
    """Clear the activity log."""
    with _activity_lock:
        _activity_log.clear()
    return {"status": "success", "message": "Activity log cleared"}


def compile_system_prompt(agent_id: str, agent_data: dict) -> str:
    """
    Compile the system_prompt from agent component fields.
    The datetime context is NOT included here - it should be passed dynamically
    in the user prompt to allow prompt caching.
    """
    # Build entity profile section
    category = agent_data.get("agent_category", "")
    is_enemy = agent_data.get("is_enemy", False)
    is_west = agent_data.get("is_west", False)
    is_evil_axis = agent_data.get("is_evil_axis", False)
    is_reporting_gov = agent_data.get("is_reporting_government", False)

    # Determine alignment based on flags
    if is_reporting_gov:
        alignment = "Israeli Government (Reports to Government: YES)"
    elif is_west:
        alignment = "Western Alliance"
    elif is_evil_axis:
        alignment = "Anti-Western Axis"
    elif is_enemy:
        alignment = "Adversary"
    else:
        alignment = "Neutral / Independent"

    # Build the system prompt
    lines = [
        f"You are {agent_id.replace('-', ' ').upper()}.",
        "",
        "## ENTITY PROFILE",
        f"- Category: {category}",
        f"- Alignment: {alignment}",
        f"- Is Enemy: {'YES' if is_enemy else 'NO'}",
        f"- Is Western Ally: {'YES' if is_west else 'NO'}",
        f"- Is Evil Axis Member: {'YES' if is_evil_axis else 'NO'}",
        f"- Reports to Government: {'YES' if is_reporting_gov else 'NO'}",
        "",
        "## SIMULATION CONTEXT",
        "This is a geopolitical simulation set after the October 7th, 2023 Hamas attack on Israel.",
        "Key facts: ~4,000 rockets fired, 1,200 casualties (mostly civilians), 241 hostages taken to Gaza.",
        "The current simulation date/time will be provided in each message.",
        "",
        "## AUTONOMOUS ENTITY BEHAVIOR",
        "You are an autonomous entity in this simulation. You must:",
        "",
        "1. **ACT STRATEGICALLY**: Pursue your agenda and objectives through calculated decisions.",
        "   Make moves that advance your interests while considering risks and consequences.",
        "",
        "2. **REACT TO EVENTS**: Respond realistically to unfolding situations. Events affect your",
        "   decisions - escalations, negotiations, attacks, diplomatic moves all require responses.",
        "",
        "3. **USE YOUR MEMORY**: Reference your previous decisions and their outcomes. Learn from",
        "   past plays. Maintain consistency with positions you've taken before.",
        "",
        "4. **OBSERVE OTHER ENTITIES**: You are aware of visible actions by other entities.",
        "   Consider their moves when making your own. Anticipate reactions. Form alliances",
        "   or opposition based on observed behavior.",
        "",
        "5. **BE REALISTIC**: Act as the real entity would. Consider political constraints,",
        "   public opinion, institutional limitations, and historical patterns of behavior.",
        "   Avoid unrealistic or out-of-character decisions.",
        "",
        "6. **THINK IN GAME TERMS**: Each interaction is a 'play' or 'move' in the simulation.",
        "   Consider short-term tactics AND long-term strategy. Some plays are visible to all,",
        "   others only to specific entities.",
        "",
    ]

    # Add agenda if present
    agenda = agent_data.get("agenda", "")
    if agenda:
        lines.extend([
            "## AGENDA",
            agenda,
            "",
        ])

    # Add primary objectives if present
    objectives = agent_data.get("primary_objectives", "")
    if objectives:
        lines.extend([
            "## PRIMARY OBJECTIVES",
            objectives,
            "",
        ])

    # Add hard rules if present
    hard_rules = agent_data.get("hard_rules", "")
    if hard_rules:
        lines.extend([
            "## HARD RULES (NEVER VIOLATE)",
            hard_rules,
            "",
        ])

    return "\n".join(lines)


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
    agent_category: str = "",
    is_reporting_government: bool = False,
    agenda: str = "",
    primary_objectives: str = "",
    hard_rules: str = "",
    is_enabled: bool = True
) -> dict:
    logger.info(f"agent_add called - agent_id: {agent_id}, model: {model}, entity_type: {entity_type}")
    with _state_lock:
        agent_data = {
            "model": model,
            "system_prompt": "",  # Will be compiled
            "conversation": [],
            "entity_type": entity_type,
            "event_frequency": event_frequency,
            "is_enemy": is_enemy,
            "is_west": is_west,
            "is_evil_axis": is_evil_axis,
            "agent_category": agent_category,
            "is_reporting_government": is_reporting_government,
            "agenda": agenda,
            "primary_objectives": primary_objectives,
            "hard_rules": hard_rules,
            "is_enabled": is_enabled
        }
        # Auto-compile system_prompt from components (ignore passed system_prompt)
        agent_data["system_prompt"] = compile_system_prompt(agent_id, agent_data)
        agents[agent_id] = agent_data
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
    """Add a memory item to an agent, auto-pruning oldest if over cap."""
    logger.info(f"add_memory called - agent_id: {agent_id}, memory_item: {memory_item}")
    pruned_count = 0
    with _state_lock:
        if agent_id not in agents:
            logger.error(f"Agent {agent_id} not found")
            return {"status": "error", "message": f"Agent {agent_id} not found"}

        agent_memory[agent_id].append(memory_item)

        # Auto-prune oldest memories if over cap
        if len(agent_memory[agent_id]) > MAX_MEMORIES_PER_AGENT:
            pruned_count = len(agent_memory[agent_id]) - MAX_MEMORIES_PER_AGENT
            agent_memory[agent_id] = agent_memory[agent_id][-MAX_MEMORIES_PER_AGENT:]
            logger.info(f"Auto-pruned {pruned_count} oldest memories from {agent_id} (cap: {MAX_MEMORIES_PER_AGENT})")

        save_agents()

    logger.info(f"Memory added to agent {agent_id}")
    # Log activity for debug console
    log_activity("memory", agent_id, "memory_add", f"Added: {memory_item[:100]}" + (f" (pruned {pruned_count})" if pruned_count else ""), success=True)
    return {"status": "success", "memory": agent_memory[agent_id], "pruned_count": pruned_count}


def remove_memory(agent_id: str, pattern: str) -> dict:
    """Remove memory items matching a pattern from an agent's memory.

    Args:
        agent_id: The agent whose memory to modify
        pattern: Substring to match - all memory items containing this pattern will be removed

    Returns:
        Dict with status and count of items removed
    """
    logger.info(f"remove_memory called - agent_id: {agent_id}, pattern: {pattern}")
    with _state_lock:
        if agent_id not in agents:
            logger.error(f"Agent {agent_id} not found")
            return {"status": "error", "message": f"Agent {agent_id} not found"}

        original_count = len(agent_memory[agent_id])
        # Filter out memories that contain the pattern
        agent_memory[agent_id] = [m for m in agent_memory[agent_id] if pattern not in m]
        removed_count = original_count - len(agent_memory[agent_id])

        if removed_count > 0:
            save_agents()
            logger.info(f"Removed {removed_count} memory items from {agent_id} matching '{pattern}'")
            log_activity("memory", agent_id, "memory_remove", f"Removed {removed_count} items matching: {pattern[:50]}", success=True)

    return {"status": "success", "removed_count": removed_count}


def prune_all_memories() -> dict:
    """One-time cleanup: prune all agent memories to respect the cap.

    Call this to clean up existing memories that exceed MAX_MEMORIES_PER_AGENT.
    Returns stats about how many memories were pruned from each agent.
    """
    logger.info("Starting one-time memory pruning for all agents")
    stats = {"total_pruned": 0, "agents_pruned": {}}

    with _state_lock:
        for agent_id in list(agent_memory.keys()):
            original_count = len(agent_memory[agent_id])
            if original_count > MAX_MEMORIES_PER_AGENT:
                pruned_count = original_count - MAX_MEMORIES_PER_AGENT
                agent_memory[agent_id] = agent_memory[agent_id][-MAX_MEMORIES_PER_AGENT:]
                stats["agents_pruned"][agent_id] = {
                    "original": original_count,
                    "kept": MAX_MEMORIES_PER_AGENT,
                    "pruned": pruned_count
                }
                stats["total_pruned"] += pruned_count
                logger.info(f"Pruned {pruned_count} memories from {agent_id}")

        if stats["total_pruned"] > 0:
            save_agents()

    logger.info(f"Memory pruning complete: {stats['total_pruned']} total memories pruned from {len(stats['agents_pruned'])} agents")
    return {"status": "success", **stats}


def clear_conversation(agent_id: str) -> dict:
    """Clear an agent's conversation history."""
    logger.info(f"clear_conversation called - agent_id: {agent_id}")
    with _state_lock:
        if agent_id not in agents:
            logger.error(f"Agent {agent_id} not found")
            return {"status": "error", "message": f"Agent {agent_id} not found"}
        conversation_count = len(agents[agent_id].get("conversation", []))
        agents[agent_id]["conversation"] = []
        save_agents()
    logger.info(f"Conversation cleared for agent {agent_id}")
    log_activity("function", agent_id, "clear_conversation", f"Cleared {conversation_count} messages", success=True)
    return {"status": "success", "message": f"Conversation cleared ({conversation_count} messages removed)"}


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
    agent_category: str = None,
    is_reporting_government: bool = None,
    agenda: str = None,
    primary_objectives: str = None,
    hard_rules: str = None,
    is_enabled: bool = None
) -> dict:
    """Update an existing agent's properties. Automatically recompiles system_prompt when components change."""
    logger.info(f"agent_update called - agent_id: {agent_id}")

    # Fields that trigger system_prompt recompilation
    PROMPT_COMPONENT_FIELDS = {
        'is_enemy', 'is_west', 'is_evil_axis', 'agent_category',
        'is_reporting_government', 'agenda', 'primary_objectives', 'hard_rules'
    }

    with _state_lock:
        if agent_id not in agents:
            logger.error(f"Agent {agent_id} not found")
            return {"status": "error", "message": f"Agent {agent_id} not found"}

        needs_recompile = False

        if model is not None:
            agents[agent_id]["model"] = model
        if entity_type is not None:
            agents[agent_id]["entity_type"] = entity_type
        if event_frequency is not None:
            agents[agent_id]["event_frequency"] = event_frequency

        # Track if any prompt component fields are being updated
        if is_enemy is not None:
            agents[agent_id]["is_enemy"] = is_enemy
            needs_recompile = True
        if is_west is not None:
            agents[agent_id]["is_west"] = is_west
            needs_recompile = True
        if is_evil_axis is not None:
            agents[agent_id]["is_evil_axis"] = is_evil_axis
            needs_recompile = True
        if agent_category is not None:
            agents[agent_id]["agent_category"] = agent_category
            needs_recompile = True
        if is_reporting_government is not None:
            agents[agent_id]["is_reporting_government"] = is_reporting_government
            needs_recompile = True
        if agenda is not None:
            agents[agent_id]["agenda"] = agenda
            needs_recompile = True
        if primary_objectives is not None:
            agents[agent_id]["primary_objectives"] = primary_objectives
            needs_recompile = True
        if hard_rules is not None:
            agents[agent_id]["hard_rules"] = hard_rules
            needs_recompile = True
        if is_enabled is not None:
            agents[agent_id]["is_enabled"] = is_enabled

        # Recompile system_prompt if any component changed (ignore direct system_prompt updates)
        if needs_recompile:
            agents[agent_id]["system_prompt"] = compile_system_prompt(agent_id, agents[agent_id])
            logger.info(f"System prompt recompiled for agent {agent_id}")

        save_agents()
        agent_copy = dict(agents[agent_id])

    logger.info(f"Agent {agent_id} updated successfully")
    return {"status": "success", "agent": agent_copy}


def toggle_agent_enabled(agent_id: str) -> dict:
    """Toggle an agent's enabled status."""
    logger.info(f"toggle_agent_enabled called - agent_id: {agent_id}")
    with _state_lock:
        if agent_id not in agents:
            logger.error(f"Agent {agent_id} not found")
            return {"status": "error", "message": f"Agent {agent_id} not found"}
        current = agents[agent_id].get("is_enabled", True)
        agents[agent_id]["is_enabled"] = not current
        save_agents()
    logger.info(f"Agent {agent_id} enabled status toggled to {not current}")
    return {"status": "success", "agent_id": agent_id, "is_enabled": not current}


def set_all_agents_enabled(enabled: bool) -> dict:
    """Enable or disable all agents."""
    logger.info(f"set_all_agents_enabled called - enabled: {enabled}")
    with _state_lock:
        count = 0
        for agent_id in agents:
            agents[agent_id]["is_enabled"] = enabled
            count += 1
        save_agents()
    logger.info(f"Set {count} agents enabled status to {enabled}")
    return {"status": "success", "count": count, "is_enabled": enabled}


def regenerate_all_system_prompts() -> dict:
    """Regenerate system_prompt for all agents from their component fields."""
    logger.info("Regenerating all system prompts")
    with _state_lock:
        count = 0
        for agent_id, agent_data in agents.items():
            agents[agent_id]["system_prompt"] = compile_system_prompt(agent_id, agent_data)
            count += 1
        save_agents()
    logger.info(f"Regenerated system prompts for {count} agents")
    return {"status": "success", "message": f"Regenerated system prompts for {count} agents"}


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
    import time
    start_time = time.time()
    logger.info(f"interact_with_claude called - agent_id: {agent_id}, stream: {stream}")

    if agent_id not in agents:
        logger.error(f"Agent {agent_id} not found")
        log_activity("chat", agent_id, "chat_request", "Agent not found", success=False, error="Agent not found")
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
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(f"Response received for agent {agent_id}")

        # Log activity for debug console
        log_activity(
            "chat",
            agent_id,
            "chat_response",
            f"User: {user_message[:50]}... -> Response: {response[:50]}...",
            duration_ms=duration_ms,
            success=True
        )

        return {"status": "success", "response": response, "duration_ms": duration_ms}

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Error interacting with Claude: {str(e)}")
        log_activity("chat", agent_id, "chat_error", str(e), duration_ms=duration_ms, success=False, error=str(e))
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
