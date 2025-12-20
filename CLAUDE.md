# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PM1 is a geopolitical simulation engine set after October 7th, 2023. It features LLM-powered autonomous entity agents (world leaders, military commanders, intelligence chiefs) that make decisions, interact through meetings, and affect game state through events and KPIs.

## Commands

### Run Backend Server
```bash
cd backend
uvicorn api:api --reload --port 8000
```

### Run Tests
```bash
cd backend
pytest                           # Run all tests
pytest test_simulation.py        # Run specific test file
pytest test_simulation.py -k "test_name"  # Run specific test
pytest -v                        # Verbose output
```

### Dependencies
```bash
pip install -r backend/requirements.txt
```

## Architecture

### Backend (Python/FastAPI)

**Core Modules:**
- `api.py` - FastAPI REST server, routes, request validation, serves frontend
- `app.py` - Agent management, Anthropic client, memory system (max 7 memories per agent), activity logging
- `simulation.py` - Game engine with GameClock, SimulationManager, EventProcessor, KPIManager, ResolverProcessor
- `game_manager.py` - Multi-game save system (create/switch/backup games), singleton pattern
- `map_state.py` - Geographic tracking: static locations, dynamic entities (hostages, HVTs), GeoEvents for map animations
- `meetings.py` - Meeting orchestration: negotiations, cabinet sessions, leader talks with turn-based LLM conversations

**Entity-Agent Mapping:** Agents are grouped by entity (Israel, Hamas, USA, etc.) in `ENTITY_AGENT_MAP`. Events propagate memories to relevant agents based on entity relationships.

**LLM Integration Points:**
1. Agent actions (`simulation.py`) - Agents decide actions based on system prompt + memory + context
2. Meeting turns (`meetings.py`) - Participants respond in structured meetings
3. Meeting outcomes (`meetings.py`) - Generate meeting summaries
4. Event resolution (`simulation.py`) - Batch resolve pending events

### Frontend (Vanilla JavaScript)

**Two Modes:**
- **Admin Panel** (`frontend/index.html`) - Agent configuration, simulation control, debug console
- **Player Mode** (`frontend/play/play.html`) - Game interface with events feed, KPI panel, tactical map, PM decisions

**Key Components (in `frontend/play/js/components/`):**
- `events-feed.js` - Real-time event display
- `kpi-panel.js` - Entity KPI visualization
- `tactical-map.js` - Geographic visualization with animations
- `pm-decisions.js` - Player decision interface
- `entity-panel.js` - Entity status display

**State Management:** `player-state.js` manages client state and polling; `api-adapter.js` handles API communication.

### Data Structure

```
data/
├── active_game.json           # Currently active game reference
├── agents.json                # Default agent definitions
├── simulation_state.json      # Default simulation state
├── games/                     # Saved games (each is a complete state copy)
│   └── {game_id}/
│       ├── game_meta.json
│       ├── agents.json
│       ├── simulation_state.json
│       ├── map_state.json
│       ├── meetings.json
│       ├── events_archive.json
│       └── kpis/              # Per-entity KPI files
├── templates/                 # Game templates for new games
│   └── october7/
└── kpis/                      # Default entity KPIs
```

## Key Patterns

**Dynamic Path Resolution:** All data modules use `get_*_file()` functions that resolve paths through `game_manager.get_current_data_path()` for multi-game support.

**Thread Safety:** Global state uses `threading.Lock()` for concurrent access (agents dict, activity log, simulation state).

**Agent System Prompts:** Compiled from components: entity profile, simulation context, agenda, objectives, hard rules. DateTime is passed dynamically in user prompts for caching.

**Action Types:** DIPLOMATIC, MILITARY, ECONOMIC, INTELLIGENCE, INTERNAL, NONE

**Event Flow:** Agent produces action -> EventProcessor creates SimulationEvent -> ResolverProcessor batches and resolves -> KPIs updated -> Memories distributed to relevant agents

## Testing Notes

Tests mock `anthropic.Anthropic` before importing simulation modules. Use `patch('anthropic.Anthropic')` context manager pattern.

The `GameManager` is a singleton - use `GameManager.reset_instance()` in test teardown.
