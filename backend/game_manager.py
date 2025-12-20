"""
Game Manager Module - Multi-game save management for PM1 simulation.

Provides functionality to:
- List available games
- Create new games from templates
- Switch active game (update file paths)
- Backup/restore games
- Delete games
"""

import json
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass, asdict

from logger import setup_logger

logger = setup_logger("game_manager")

# Directory structure
DATA_DIR = Path(__file__).parent.parent / "data"
GAMES_DIR = DATA_DIR / "games"
TEMPLATES_DIR = DATA_DIR / "templates"
ACTIVE_GAME_FILE = DATA_DIR / "active_game.json"
BACKUP_PREFIX = "data_backup_"


@dataclass
class GameInfo:
    """Metadata about a saved game."""
    game_id: str
    display_name: str
    created_at: str
    last_played: str
    template: str
    description: str = ""
    game_clock: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "GameInfo":
        # Handle missing optional fields
        return cls(
            game_id=data.get("game_id", ""),
            display_name=data.get("display_name", ""),
            created_at=data.get("created_at", ""),
            last_played=data.get("last_played", ""),
            template=data.get("template", "october7"),
            description=data.get("description", ""),
            game_clock=data.get("game_clock", "")
        )


class GameManager:
    """Manages multiple game saves and active game switching."""

    _instance = None
    _lock = threading.Lock()

    # Files that comprise a game save
    GAME_FILES = [
        "agents.json",
        "simulation_state.json",
        "map_state.json",
        "meetings.json",
        "events_archive.json",
    ]
    GAME_DIRS = [
        "kpis",
    ]

    @classmethod
    def get_instance(cls) -> "GameManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset_instance(cls):
        """Reset singleton for testing."""
        with cls._lock:
            cls._instance = None

    def __init__(self):
        if GameManager._instance is not None:
            raise RuntimeError("Use get_instance() instead")
        self._current_game: Optional[str] = None
        self._initialize_directories()
        self._load_active_game()

    def _initialize_directories(self):
        """Create required directory structure."""
        GAMES_DIR.mkdir(parents=True, exist_ok=True)
        TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

    def _load_active_game(self):
        """Load the currently active game from config."""
        if ACTIVE_GAME_FILE.exists():
            try:
                with open(ACTIVE_GAME_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._current_game = data.get("active_game_id")
                logger.info(f"Active game loaded: {self._current_game}")
            except Exception as e:
                logger.error(f"Error loading active game config: {e}")
                self._current_game = None
        else:
            self._current_game = None

    def _save_active_game(self):
        """Save the currently active game to config."""
        try:
            with open(ACTIVE_GAME_FILE, "w", encoding="utf-8") as f:
                json.dump({"active_game_id": self._current_game}, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving active game config: {e}")

    def get_current_game(self) -> Optional[str]:
        """Get the currently active game ID."""
        return self._current_game

    def get_game_path(self, game_id: str) -> Path:
        """Get the path to a specific game's directory."""
        return GAMES_DIR / game_id

    def get_current_data_path(self) -> Path:
        """Get the data path for the current game, or legacy path if no game active."""
        if self._current_game:
            game_path = self.get_game_path(self._current_game)
            if game_path.exists():
                return game_path
        return DATA_DIR  # Legacy fallback

    def list_games(self) -> List[GameInfo]:
        """List all available saved games."""
        games = []
        if not GAMES_DIR.exists():
            return games

        for game_dir in GAMES_DIR.iterdir():
            if game_dir.is_dir():
                meta_file = game_dir / "game_meta.json"
                if meta_file.exists():
                    try:
                        with open(meta_file, "r", encoding="utf-8") as f:
                            data = json.load(f)

                        # Update game_clock from simulation_state if available
                        sim_state_file = game_dir / "simulation_state.json"
                        if sim_state_file.exists():
                            try:
                                with open(sim_state_file, "r", encoding="utf-8") as sf:
                                    sim_data = json.load(sf)
                                data["game_clock"] = sim_data.get("game_clock", "")
                            except Exception:
                                pass

                        games.append(GameInfo.from_dict(data))
                    except Exception as e:
                        logger.error(f"Error loading game meta for {game_dir.name}: {e}")

        return sorted(games, key=lambda g: g.last_played, reverse=True)

    def list_templates(self) -> List[dict]:
        """List available game templates."""
        templates = []
        if not TEMPLATES_DIR.exists():
            return templates

        for template_dir in TEMPLATES_DIR.iterdir():
            if template_dir.is_dir():
                meta_file = template_dir / "template_meta.json"
                if meta_file.exists():
                    try:
                        with open(meta_file, "r", encoding="utf-8") as f:
                            templates.append(json.load(f))
                    except Exception as e:
                        logger.error(f"Error loading template meta: {e}")

        return templates

    def create_game(self, game_id: str, display_name: str,
                    template: str = "october7", description: str = "") -> dict:
        """Create a new game from a template."""
        game_path = self.get_game_path(game_id)
        template_path = TEMPLATES_DIR / template

        # Validate game_id format
        if not game_id or not game_id.replace("-", "").replace("_", "").isalnum():
            return {"status": "error", "message": "Game ID must be alphanumeric with hyphens/underscores only"}

        if game_path.exists():
            return {"status": "error", "message": f"Game '{game_id}' already exists"}

        if not template_path.exists():
            return {"status": "error", "message": f"Template '{template}' not found. Run migration first to create templates."}

        try:
            # Copy template to new game directory
            shutil.copytree(template_path, game_path)

            # Remove template_meta.json if copied
            template_meta = game_path / "template_meta.json"
            if template_meta.exists():
                template_meta.unlink()

            # Create game metadata
            now = datetime.now().isoformat()
            meta = GameInfo(
                game_id=game_id,
                display_name=display_name,
                created_at=now,
                last_played=now,
                template=template,
                description=description,
                game_clock="2023-10-07T06:29:00"
            )

            with open(game_path / "game_meta.json", "w", encoding="utf-8") as f:
                json.dump(meta.to_dict(), f, indent=2, ensure_ascii=False)

            logger.info(f"Created new game: {game_id} from template {template}")
            return {"status": "success", "game": meta.to_dict()}

        except Exception as e:
            logger.error(f"Error creating game: {e}")
            if game_path.exists():
                shutil.rmtree(game_path)
            return {"status": "error", "message": str(e)}

    def load_game(self, game_id: str) -> dict:
        """Switch to a different game. Returns status dict.

        Note: Caller must ensure simulation is stopped and handle reloading.
        """
        game_path = self.get_game_path(game_id)

        if not game_path.exists():
            return {"status": "error", "message": f"Game '{game_id}' not found"}

        try:
            # Update active game
            self._current_game = game_id
            self._save_active_game()

            # Update last_played
            meta_file = game_path / "game_meta.json"
            if meta_file.exists():
                with open(meta_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                meta["last_played"] = datetime.now().isoformat()
                with open(meta_file, "w", encoding="utf-8") as f:
                    json.dump(meta, f, indent=2, ensure_ascii=False)

            logger.info(f"Switched to game: {game_id}")
            return {"status": "success", "message": f"Game '{game_id}' loaded"}

        except Exception as e:
            logger.error(f"Error loading game: {e}")
            return {"status": "error", "message": str(e)}

    def backup_current_data(self) -> dict:
        """Backup the current data directory before migration."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = DATA_DIR.parent / f"{BACKUP_PREFIX}{timestamp}"

        try:
            # Don't backup games and templates directories if they exist
            def ignore_patterns(directory, files):
                if Path(directory) == DATA_DIR:
                    return [f for f in files if f in ['games', 'templates', 'active_game.json']]
                return []

            shutil.copytree(DATA_DIR, backup_path, ignore=ignore_patterns)
            logger.info(f"Backed up data to {backup_path}")
            return {"status": "success", "backup_path": str(backup_path)}
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return {"status": "error", "message": str(e)}

    def migrate_legacy_to_default(self) -> dict:
        """Migrate existing data/ files to data/games/default/."""
        default_game_path = GAMES_DIR / "default"

        if default_game_path.exists():
            return {"status": "skip", "message": "Default game already exists"}

        try:
            # Create default game directory
            default_game_path.mkdir(parents=True)

            # Copy game files
            for file_name in self.GAME_FILES:
                src = DATA_DIR / file_name
                if src.exists():
                    shutil.copy2(src, default_game_path / file_name)
                    logger.info(f"Copied {file_name} to default game")

            # Copy kpis directory
            src_kpis = DATA_DIR / "kpis"
            if src_kpis.exists():
                shutil.copytree(src_kpis, default_game_path / "kpis")
                logger.info("Copied kpis directory to default game")

            # Get game clock from simulation state
            game_clock = "2023-10-07T06:29:00"
            sim_state_file = default_game_path / "simulation_state.json"
            if sim_state_file.exists():
                try:
                    with open(sim_state_file, "r", encoding="utf-8") as f:
                        sim_data = json.load(f)
                    game_clock = sim_data.get("game_clock", game_clock)
                except Exception:
                    pass

            # Create game metadata
            now = datetime.now().isoformat()
            meta = GameInfo(
                game_id="default",
                display_name="Default Game (Migrated)",
                created_at=now,
                last_played=now,
                template="october7",
                description="Original game state migrated from legacy data",
                game_clock=game_clock
            )

            with open(default_game_path / "game_meta.json", "w", encoding="utf-8") as f:
                json.dump(meta.to_dict(), f, indent=2, ensure_ascii=False)

            # Set as active game
            self._current_game = "default"
            self._save_active_game()

            logger.info("Successfully migrated legacy data to default game")
            return {"status": "success", "message": "Migrated to default game"}

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return {"status": "error", "message": str(e)}

    def create_october7_template(self) -> dict:
        """Create the October 7th scenario template from clean initial state."""
        template_path = TEMPLATES_DIR / "october7"

        if template_path.exists():
            return {"status": "skip", "message": "Template already exists"}

        try:
            template_path.mkdir(parents=True)

            # Create template metadata
            template_meta = {
                "template_id": "october7",
                "display_name": "October 7th Scenario",
                "description": "Israel-Hamas conflict starting October 7, 2023",
                "start_date": "2023-10-07T06:29:00",
                "scenario_notes": "Hamas attack begins. 4,000 rockets, 1,200 casualties, 241 hostages."
            }

            with open(template_path / "template_meta.json", "w", encoding="utf-8") as f:
                json.dump(template_meta, f, indent=2, ensure_ascii=False)

            # Copy current data files as template (we'll clean them up)
            for file_name in self.GAME_FILES:
                src = DATA_DIR / file_name
                if src.exists():
                    if file_name == "simulation_state.json":
                        # Create clean simulation state
                        self._create_clean_simulation_state(template_path / file_name)
                    elif file_name == "events_archive.json":
                        # Empty archive
                        with open(template_path / file_name, "w", encoding="utf-8") as f:
                            json.dump([], f)
                    elif file_name == "meetings.json":
                        # Empty meetings
                        self._create_clean_meetings(template_path / file_name)
                    else:
                        shutil.copy2(src, template_path / file_name)

            # Copy kpis directory and reset to initial values
            src_kpis = DATA_DIR / "kpis"
            if src_kpis.exists():
                shutil.copytree(src_kpis, template_path / "kpis")
                # Reset KPIs to initial values
                self._reset_kpis_to_initial(template_path / "kpis")

            logger.info("Created October 7th template")
            return {"status": "success", "message": "Template created"}

        except Exception as e:
            logger.error(f"Template creation failed: {e}")
            if template_path.exists():
                shutil.rmtree(template_path)
            return {"status": "error", "message": str(e)}

    def _create_clean_simulation_state(self, path: Path):
        """Create a clean simulation state for new games."""
        clean_state = {
            "is_running": False,
            "clock_speed": 2.0,
            "game_clock": "2023-10-07T06:29:00",
            "events": [],
            "agent_last_action": {},
            "ongoing_situations": [],
            "pm_approval_queue": [],
            "scheduled_events": [],
            "paused_for_meeting": False,
            "active_meeting_id": None
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(clean_state, f, indent=2, ensure_ascii=False)

    def _create_clean_meetings(self, path: Path):
        """Create clean meetings state for new games."""
        clean_meetings = {
            "meetings": [],
            "requests": [],
            "active_meeting_id": None
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(clean_meetings, f, indent=2, ensure_ascii=False)

    def _reset_kpis_to_initial(self, kpis_dir: Path):
        """Reset KPI files to initial values (dynamic = const)."""
        if not kpis_dir.exists():
            return

        for kpi_file in kpis_dir.glob("*.json"):
            try:
                with open(kpi_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Reset dynamic metrics based on const metrics where applicable
                const = data.get("const_metrics", {})
                dynamic = data.get("dynamic_metrics", {})

                # Map const to dynamic values
                mapping = {
                    "initial_fighters": "fighters_remaining",
                    "initial_tunnel_network_km": "tunnel_network_operational_km",
                    "initial_rocket_inventory": "rocket_inventory",
                }

                for const_key, dynamic_key in mapping.items():
                    if const_key in const and dynamic_key in dynamic:
                        dynamic[dynamic_key] = const[const_key]

                # Reset common dynamic metrics
                reset_values = {
                    "casualties": 0,
                    "casualties_military": 0,
                    "casualties_civilian": 0,
                    "hostages_rescued": 0,
                    "leadership_eliminated": 0,
                    "tunnel_km_destroyed": 0,
                    "enemy_fighters_eliminated": 0,
                    "infrastructure_damage_pct": 0,
                }

                for key, value in reset_values.items():
                    if key in dynamic:
                        dynamic[key] = value

                # Clear pending operations
                data["pending_operations"] = []
                data["last_updated"] = "2023-10-07T06:29:00"

                with open(kpi_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

            except Exception as e:
                logger.warning(f"Could not reset KPI file {kpi_file.name}: {e}")

    def delete_game(self, game_id: str) -> dict:
        """Delete a saved game."""
        if game_id == self._current_game:
            return {"status": "error", "message": "Cannot delete active game"}

        game_path = self.get_game_path(game_id)
        if not game_path.exists():
            return {"status": "error", "message": f"Game '{game_id}' not found"}

        try:
            shutil.rmtree(game_path)
            logger.info(f"Deleted game: {game_id}")
            return {"status": "success", "message": f"Game '{game_id}' deleted"}
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return {"status": "error", "message": str(e)}


# Global accessor
def get_game_manager() -> GameManager:
    return GameManager.get_instance()
