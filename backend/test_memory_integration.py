"""
Integration test for memory flow with 2 real agents.
Runs simulation at maximum speed and verifies memory accumulates correctly.

Usage:
    python test_memory_integration.py
"""
import asyncio
import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

import app
from simulation import SimulationManager, DEFAULT_CLOCK_SPEED


# Test configuration
TEST_AGENTS = {
    "Test-Agent-A": {
        "model": "claude-sonnet-4-20250514",
        "entity_type": "Entity",
        "event_frequency": 1,  # Act every 1 game minute (fast!)
        "is_enemy": False,
        "is_west": True,
        "is_evil_axis": False,
        "agent_category": "Test",
        "is_reporting_government": False,
        "agenda": "Test agenda for Agent A. Cooperate with Agent B.",
        "primary_objectives": "1. Make diplomatic statements. 2. Respond to Agent B.",
        "hard_rules": "ALWAYS act diplomatically. NEVER use military action."
    },
    "Test-Agent-B": {
        "model": "claude-sonnet-4-20250514",
        "entity_type": "Entity",
        "event_frequency": 1,  # Act every 1 game minute (fast!)
        "is_enemy": False,
        "is_west": True,
        "is_evil_axis": False,
        "agent_category": "Test",
        "is_reporting_government": False,
        "agenda": "Test agenda for Agent B. Cooperate with Agent A.",
        "primary_objectives": "1. Make diplomatic statements. 2. Respond to Agent A.",
        "hard_rules": "ALWAYS act diplomatically. NEVER use military action."
    }
}

# Fastest possible speed: 0.1 real seconds = 1 game minute
FAST_CLOCK_SPEED = 0.1


def setup_test_agents():
    """Replace all agents with just our 2 test agents."""
    print("\n=== Setting up test agents ===")

    # Clear existing agents
    app.agents.clear()
    app.agent_skills.clear()
    app.agent_memory.clear()

    # Add test agents
    for agent_id, agent_data in TEST_AGENTS.items():
        # Compile system prompt
        agent_data["system_prompt"] = app.compile_system_prompt(agent_id, agent_data)
        agent_data["conversation"] = []

        app.agents[agent_id] = agent_data
        app.agent_skills[agent_id] = []
        app.agent_memory[agent_id] = []

        print(f"  Created: {agent_id}")

    print(f"  Total agents: {len(app.agents)}")


def print_memory_state():
    """Print current memory state for all agents."""
    print("\n=== Current Memory State ===")
    for agent_id in app.agents:
        memory = app.agent_memory.get(agent_id, [])
        print(f"\n{agent_id} ({len(memory)} items):")
        for i, item in enumerate(memory):
            print(f"  [{i+1}] {item[:100]}{'...' if len(item) > 100 else ''}")


def verify_memory_flow():
    """Verify that memory is flowing correctly."""
    print("\n=== Verifying Memory Flow ===")

    errors = []

    for agent_id in app.agents:
        memory = app.agent_memory.get(agent_id, [])

        # Check that agent has some memory
        if len(memory) == 0:
            errors.append(f"{agent_id} has no memory!")
            continue

        # Check that agent has "YOU:" entries (their own actions)
        own_actions = [m for m in memory if "YOU:" in m]
        if len(own_actions) == 0:
            errors.append(f"{agent_id} has no 'YOU:' entries (own actions)")
        else:
            print(f"  {agent_id}: {len(own_actions)} own actions (YOU:)")

        # Check that agent has entries from other agents
        other_id = "Test-Agent-B" if agent_id == "Test-Agent-A" else "Test-Agent-A"
        other_actions = [m for m in memory if f"{other_id}:" in m]
        if len(other_actions) == 0:
            errors.append(f"{agent_id} has no entries from {other_id}")
        else:
            print(f"  {agent_id}: {len(other_actions)} actions from {other_id}")

    if errors:
        print("\n❌ ERRORS:")
        for e in errors:
            print(f"  - {e}")
        return False
    else:
        print("\n✅ Memory flow verified successfully!")
        return True


async def run_test():
    """Run the integration test."""
    print("=" * 60)
    print("MEMORY FLOW INTEGRATION TEST")
    print("=" * 60)

    # Setup
    setup_test_agents()

    # Get simulation manager
    manager = SimulationManager.get_instance()

    # Set fastest possible speed
    print(f"\n=== Setting clock speed to {FAST_CLOCK_SPEED}s per game minute ===")
    manager.clock.set_speed(FAST_CLOCK_SPEED)

    # Clear any existing events
    manager.state.events.clear()

    # Start simulation
    print("\n=== Starting simulation ===")
    result = await manager.start_game()
    print(f"  Result: {result}")

    # Wait for a few turns (each agent should act multiple times)
    # With event_frequency=1 and speed=0.1, each agent acts every 0.1 seconds
    # Wait 3 seconds = ~30 game minutes = multiple turns per agent
    wait_time = 3
    print(f"\n=== Waiting {wait_time} seconds for agents to act... ===")
    await asyncio.sleep(wait_time)

    # Stop simulation
    print("\n=== Stopping simulation ===")
    result = await manager.stop_game()
    print(f"  Result: {result}")

    # Print results
    print(f"\n=== Simulation Results ===")
    print(f"  Events created: {len(manager.state.events)}")

    print_memory_state()

    # Verify
    success = verify_memory_flow()

    print("\n" + "=" * 60)
    if success:
        print("TEST PASSED ✅")
    else:
        print("TEST FAILED ❌")
    print("=" * 60)

    return success


if __name__ == "__main__":
    success = asyncio.run(run_test())
    sys.exit(0 if success else 1)
