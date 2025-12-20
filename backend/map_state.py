"""
PM1 MapState Module - Spatial/Geographic Awareness for Simulation

This module provides:
- Geographic coordinates and zone management
- Static location tracking (bases, nuclear plants, crossings)
- Dynamic entity tracking (hostages, HVTs, military units)
- GeoEvents for map animations (missiles, airstrikes, movements)
- Spatial clash detection for resolver integration
"""

import json
import threading
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum

from logger import setup_logger

logger = setup_logger("map_state")

# Data directory
DATA_DIR = Path(__file__).parent.parent / "data"


# =============================================================================
# ENUMS
# =============================================================================

class LocationType(Enum):
    """Types of static/permanent locations."""
    MILITARY_BASE = "military_base"
    NUCLEAR_PLANT = "nuclear_plant"
    BORDER_CROSSING = "border_crossing"
    GOVERNMENT_HQ = "government_hq"
    AIRPORT = "airport"
    PORT = "port"
    TUNNEL_ENTRANCE = "tunnel_entrance"
    HOSPITAL = "hospital"
    REFUGEE_CAMP = "refugee_camp"


class EntityCategory(Enum):
    """Categories of trackable entities."""
    HOSTAGE_GROUP = "hostage_group"
    HIGH_VALUE_TARGET = "high_value_target"
    LEADER = "leader"
    MILITARY_UNIT = "military_unit"
    INTELLIGENCE_ASSET = "intelligence_asset"


class GeoEventType(Enum):
    """Types of map animation events."""
    MISSILE_LAUNCH = "missile_launch"
    AIR_STRIKE = "air_strike"
    INTERCEPTOR = "interceptor"
    FORCE_MOVEMENT = "force_movement"
    BATTLE_ZONE = "battle_zone"
    INTEL_OPERATION = "intel_operation"
    FORCE_DEPLOYMENT = "force_deployment"
    HOSTAGE_TRANSFER = "hostage_transfer"
    ASSASSINATION = "assassination"
    ROCKET_BARRAGE = "rocket_barrage"


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class Coordinates:
    """Geographic coordinates with optional uncertainty radius."""
    lat: float
    lon: float
    uncertainty_km: float = 0.0  # 0 = exact, >0 = estimated area

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Coordinates":
        return cls(**data)


@dataclass
class StaticLocation:
    """A fixed, predefined location on the map."""
    location_id: str
    name: str
    location_type: str  # LocationType value
    owner_entity: str  # Entity that controls this location
    coordinates: Coordinates
    is_active: bool = True  # Can be destroyed/disabled
    description: str = ""
    capacity: Optional[int] = None  # For bases, refugee camps

    def to_dict(self) -> dict:
        result = asdict(self)
        result['coordinates'] = self.coordinates.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "StaticLocation":
        data = dict(data)  # Copy to avoid mutation
        data['coordinates'] = Coordinates.from_dict(data['coordinates'])
        return cls(**data)


@dataclass
class TrackedEntity:
    """A movable entity whose location is tracked."""
    entity_id: str
    name: str
    category: str  # EntityCategory value
    owner_entity: str  # Controlling entity (e.g., "Hamas", "Israel")
    current_location: Coordinates
    current_zone: str  # Named zone like "Khan Younis", "Rafah", "Tel Aviv"
    is_moving: bool = False
    destination: Optional[Coordinates] = None
    destination_zone: Optional[str] = None
    movement_started: Optional[str] = None  # ISO timestamp
    movement_eta: Optional[str] = None  # ISO timestamp
    detection_difficulty: float = 0.5  # 0 = easy to find, 1 = very hidden
    last_known_update: str = ""
    metadata: Dict = field(default_factory=dict)  # hostage_count, health, etc.

    def to_dict(self) -> dict:
        result = asdict(self)
        result['current_location'] = self.current_location.to_dict()
        if self.destination:
            result['destination'] = self.destination.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "TrackedEntity":
        data = dict(data)  # Copy to avoid mutation
        data['current_location'] = Coordinates.from_dict(data['current_location'])
        if data.get('destination'):
            data['destination'] = Coordinates.from_dict(data['destination'])
        # Handle missing optional fields
        data.setdefault('is_moving', False)
        data.setdefault('destination', None)
        data.setdefault('destination_zone', None)
        data.setdefault('movement_started', None)
        data.setdefault('movement_eta', None)
        data.setdefault('detection_difficulty', 0.5)
        data.setdefault('last_known_update', "")
        data.setdefault('metadata', {})
        return cls(**data)


@dataclass
class GeoEvent:
    """A map animation event (missile, airstrike, movement, etc.)."""
    geo_event_id: str
    event_type: str  # GeoEventType value
    source_event_id: str  # Links to SimulationEvent
    timestamp: str  # Game time ISO format

    # Origin/destination for trajectories
    origin: Optional[Coordinates] = None
    origin_zone: Optional[str] = None
    destination: Optional[Coordinates] = None
    destination_zone: Optional[str] = None

    # For area effects
    center: Optional[Coordinates] = None
    radius_km: float = 0.0

    # Animation timing
    duration_seconds: int = 10  # Animation duration for frontend
    status: str = "active"  # active | completed | intercepted | failed

    # Metadata
    description: str = ""
    actor_entity: str = ""
    affected_entities: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        result = asdict(self)
        if self.origin:
            result['origin'] = self.origin.to_dict()
        if self.destination:
            result['destination'] = self.destination.to_dict()
        if self.center:
            result['center'] = self.center.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "GeoEvent":
        data = dict(data)  # Copy to avoid mutation
        if data.get('origin'):
            data['origin'] = Coordinates.from_dict(data['origin'])
        if data.get('destination'):
            data['destination'] = Coordinates.from_dict(data['destination'])
        if data.get('center'):
            data['center'] = Coordinates.from_dict(data['center'])
        # Handle missing optional fields
        data.setdefault('origin', None)
        data.setdefault('origin_zone', None)
        data.setdefault('destination', None)
        data.setdefault('destination_zone', None)
        data.setdefault('center', None)
        data.setdefault('radius_km', 0.0)
        data.setdefault('duration_seconds', 10)
        data.setdefault('status', 'active')
        data.setdefault('description', '')
        data.setdefault('actor_entity', '')
        data.setdefault('affected_entities', [])
        return cls(**data)


@dataclass
class MapState:
    """Complete map state container."""
    last_updated: str
    static_locations: List[StaticLocation] = field(default_factory=list)
    tracked_entities: List[TrackedEntity] = field(default_factory=list)
    active_geo_events: List[GeoEvent] = field(default_factory=list)
    archived_geo_events: List[GeoEvent] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "last_updated": self.last_updated,
            "static_locations": [loc.to_dict() for loc in self.static_locations],
            "tracked_entities": [ent.to_dict() for ent in self.tracked_entities],
            "active_geo_events": [evt.to_dict() for evt in self.active_geo_events],
            "archived_geo_events": [evt.to_dict() for evt in self.archived_geo_events]
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MapState":
        return cls(
            last_updated=data.get("last_updated", ""),
            static_locations=[StaticLocation.from_dict(loc) for loc in data.get("static_locations", [])],
            tracked_entities=[TrackedEntity.from_dict(ent) for ent in data.get("tracked_entities", [])],
            active_geo_events=[GeoEvent.from_dict(evt) for evt in data.get("active_geo_events", [])],
            archived_geo_events=[GeoEvent.from_dict(evt) for evt in data.get("archived_geo_events", [])]
        )


# =============================================================================
# ZONE REGISTRY - Predefined locations with coordinates
# =============================================================================

ZONE_REGISTRY: Dict[str, Coordinates] = {
    # Gaza Strip
    "Gaza City": Coordinates(31.5017, 34.4668),
    "Khan Younis": Coordinates(31.3462, 34.3058),
    "Rafah": Coordinates(31.2834, 34.2525),
    "Jabalia": Coordinates(31.5377, 34.4895),
    "Deir al-Balah": Coordinates(31.4181, 34.3510),
    "Beit Hanoun": Coordinates(31.5453, 34.5335),
    "Shati Camp": Coordinates(31.5290, 34.4430),
    "Nuseirat": Coordinates(31.4500, 34.3900),

    # Israel - Major Cities
    "Tel Aviv": Coordinates(32.0853, 34.7818),
    "Jerusalem": Coordinates(31.7683, 35.2137),
    "Haifa": Coordinates(32.7940, 34.9896),
    "Beer Sheva": Coordinates(31.2529, 34.7915),
    "Eilat": Coordinates(29.5577, 34.9519),

    # Israel - Southern Border Towns
    "Sderot": Coordinates(31.5250, 34.5964),
    "Ashkelon": Coordinates(31.6688, 34.5743),
    "Ashdod": Coordinates(31.8044, 34.6553),
    "Netivot": Coordinates(31.4167, 34.5833),
    "Ofakim": Coordinates(31.3167, 34.6167),

    # Israel - Strategic Sites
    "Dimona": Coordinates(31.0700, 35.0300),  # Near nuclear facility
    "Nevatim": Coordinates(31.2083, 35.0125),  # Airbase

    # West Bank
    "Ramallah": Coordinates(31.9038, 35.2034),
    "Hebron": Coordinates(31.5326, 35.0998),
    "Nablus": Coordinates(32.2211, 35.2544),
    "Jenin": Coordinates(32.4605, 35.2949),
    "Bethlehem": Coordinates(31.7054, 35.2024),

    # Lebanon
    "Beirut": Coordinates(33.8938, 35.5018),
    "South Lebanon": Coordinates(33.2721, 35.2033),
    "Tyre": Coordinates(33.2705, 35.2038),

    # Egypt
    "Cairo": Coordinates(30.0444, 31.2357),
    "Sinai": Coordinates(29.5000, 34.0000),
    "El-Arish": Coordinates(31.1318, 33.8019),

    # Iran
    "Tehran": Coordinates(35.6892, 51.3890),
    "Natanz": Coordinates(33.7244, 51.7275),  # Nuclear facility
    "Isfahan": Coordinates(32.6546, 51.6680),
    "Qom": Coordinates(34.6401, 50.8764),

    # Syria
    "Damascus": Coordinates(33.5138, 36.2765),

    # Jordan
    "Amman": Coordinates(31.9454, 35.9284),

    # Qatar
    "Qatar": Coordinates(25.2867, 51.5333),
    "Doha": Coordinates(25.2867, 51.5333),

    # International Waters
    "Eastern Mediterranean": Coordinates(33.5000, 34.0000),
    "Red Sea": Coordinates(27.0000, 35.0000),
}


# =============================================================================
# SEED DATA - Initial static locations and tracked entities
# =============================================================================

STATIC_LOCATIONS_SEED: List[dict] = [
    # Israeli Military Bases
    {
        "location_id": "base-israel-kirya",
        "name": "Kirya (IDF HQ)",
        "location_type": "military_base",
        "owner_entity": "Israel",
        "coordinates": {"lat": 32.0700, "lon": 34.7900, "uncertainty_km": 0},
        "description": "IDF General Staff headquarters in Tel Aviv"
    },
    {
        "location_id": "base-israel-nevatim",
        "name": "Nevatim Airbase",
        "location_type": "military_base",
        "owner_entity": "Israel",
        "coordinates": {"lat": 31.2083, "lon": 35.0125, "uncertainty_km": 0},
        "description": "Primary F-35 base in southern Israel"
    },
    {
        "location_id": "base-israel-ramat-david",
        "name": "Ramat David Airbase",
        "location_type": "military_base",
        "owner_entity": "Israel",
        "coordinates": {"lat": 32.6653, "lon": 35.1794, "uncertainty_km": 0},
        "description": "Major IAF base in northern Israel"
    },
    {
        "location_id": "base-israel-palmachim",
        "name": "Palmachim Airbase",
        "location_type": "military_base",
        "owner_entity": "Israel",
        "coordinates": {"lat": 31.8975, "lon": 34.6906, "uncertainty_km": 0},
        "description": "Space and missile testing facility"
    },

    # Nuclear Facilities
    {
        "location_id": "nuke-israel-dimona",
        "name": "Dimona Nuclear Research Center",
        "location_type": "nuclear_plant",
        "owner_entity": "Israel",
        "coordinates": {"lat": 31.0025, "lon": 35.1447, "uncertainty_km": 0},
        "description": "Nuclear facility (officially research)"
    },
    {
        "location_id": "nuke-iran-natanz",
        "name": "Natanz Enrichment Facility",
        "location_type": "nuclear_plant",
        "owner_entity": "Iran",
        "coordinates": {"lat": 33.7244, "lon": 51.7275, "uncertainty_km": 0},
        "description": "Primary uranium enrichment facility"
    },
    {
        "location_id": "nuke-iran-fordow",
        "name": "Fordow Fuel Enrichment Plant",
        "location_type": "nuclear_plant",
        "owner_entity": "Iran",
        "coordinates": {"lat": 34.8833, "lon": 50.9833, "uncertainty_km": 0},
        "description": "Underground enrichment facility near Qom"
    },

    # Border Crossings
    {
        "location_id": "border-rafah",
        "name": "Rafah Border Crossing",
        "location_type": "border_crossing",
        "owner_entity": "Egypt",
        "coordinates": {"lat": 31.2486, "lon": 34.2537, "uncertainty_km": 0},
        "description": "Gaza-Egypt border crossing"
    },
    {
        "location_id": "border-erez",
        "name": "Erez Crossing",
        "location_type": "border_crossing",
        "owner_entity": "Israel",
        "coordinates": {"lat": 31.5503, "lon": 34.5574, "uncertainty_km": 0},
        "description": "Gaza-Israel pedestrian crossing"
    },
    {
        "location_id": "border-kerem-shalom",
        "name": "Kerem Shalom Crossing",
        "location_type": "border_crossing",
        "owner_entity": "Israel",
        "coordinates": {"lat": 31.2275, "lon": 34.2656, "uncertainty_km": 0},
        "description": "Main goods crossing into Gaza"
    },

    # Hamas Infrastructure (estimated locations)
    {
        "location_id": "tunnel-jabalia-1",
        "name": "Jabalia Tunnel Complex",
        "location_type": "tunnel_entrance",
        "owner_entity": "Hamas",
        "coordinates": {"lat": 31.5377, "lon": 34.4895, "uncertainty_km": 0.5},
        "description": "Major tunnel network hub in northern Gaza"
    },
    {
        "location_id": "tunnel-khan-younis-1",
        "name": "Khan Younis Tunnel Network",
        "location_type": "tunnel_entrance",
        "owner_entity": "Hamas",
        "coordinates": {"lat": 31.3462, "lon": 34.3058, "uncertainty_km": 1.0},
        "description": "Tunnel complex in central Gaza"
    },
    {
        "location_id": "tunnel-rafah-1",
        "name": "Rafah Cross-Border Tunnels",
        "location_type": "tunnel_entrance",
        "owner_entity": "Hamas",
        "coordinates": {"lat": 31.2834, "lon": 34.2600, "uncertainty_km": 0.8},
        "description": "Smuggling tunnels to Egypt"
    },

    # Government HQs
    {
        "location_id": "gov-israel-knesset",
        "name": "Knesset",
        "location_type": "government_hq",
        "owner_entity": "Israel",
        "coordinates": {"lat": 31.7767, "lon": 35.2053, "uncertainty_km": 0},
        "description": "Israeli Parliament in Jerusalem"
    },
    {
        "location_id": "gov-iran-tehran",
        "name": "Iranian Government Complex",
        "location_type": "government_hq",
        "owner_entity": "Iran",
        "coordinates": {"lat": 35.6997, "lon": 51.4039, "uncertainty_km": 0},
        "description": "Central government buildings in Tehran"
    },
]

TRACKED_ENTITIES_SEED: List[dict] = [
    # Hostage Groups
    {
        "entity_id": "hostage-group-1",
        "name": "Hostage Group Alpha",
        "category": "hostage_group",
        "owner_entity": "Hamas",
        "current_location": {"lat": 31.3462, "lon": 34.3058, "uncertainty_km": 2.0},
        "current_zone": "Khan Younis",
        "detection_difficulty": 0.8,
        "metadata": {"hostage_count": 45, "includes_foreign_nationals": True, "condition": "unknown"}
    },
    {
        "entity_id": "hostage-group-2",
        "name": "Hostage Group Beta",
        "category": "hostage_group",
        "owner_entity": "Hamas",
        "current_location": {"lat": 31.2834, "lon": 34.2525, "uncertainty_km": 3.0},
        "current_zone": "Rafah",
        "detection_difficulty": 0.9,
        "metadata": {"hostage_count": 80, "includes_soldiers": True, "condition": "unknown"}
    },
    {
        "entity_id": "hostage-group-3",
        "name": "Hostage Group Gamma",
        "category": "hostage_group",
        "owner_entity": "Hamas",
        "current_location": {"lat": 31.5017, "lon": 34.4668, "uncertainty_km": 2.5},
        "current_zone": "Gaza City",
        "detection_difficulty": 0.85,
        "metadata": {"hostage_count": 35, "includes_elderly": True, "condition": "critical"}
    },

    # High Value Targets
    {
        "entity_id": "hvt-sinwar",
        "name": "Yahya Sinwar",
        "category": "high_value_target",
        "owner_entity": "Hamas",
        "current_location": {"lat": 31.3500, "lon": 34.3100, "uncertainty_km": 5.0},
        "current_zone": "Khan Younis",
        "detection_difficulty": 0.95,
        "metadata": {"role": "Hamas Leader in Gaza", "priority": "highest"}
    },
    {
        "entity_id": "hvt-deif",
        "name": "Mohammed Deif",
        "category": "high_value_target",
        "owner_entity": "Hamas",
        "current_location": {"lat": 31.5017, "lon": 34.4668, "uncertainty_km": 10.0},
        "current_zone": "Gaza City",
        "detection_difficulty": 0.98,
        "metadata": {"role": "Qassam Brigades Commander", "priority": "highest"}
    },
    {
        "entity_id": "hvt-haniyeh",
        "name": "Ismail Haniyeh",
        "category": "high_value_target",
        "owner_entity": "Hamas",
        "current_location": {"lat": 25.2867, "lon": 51.5333, "uncertainty_km": 1.0},
        "current_zone": "Qatar",  # Adding Qatar to registry would be needed
        "detection_difficulty": 0.3,  # Easier to track, public figure
        "metadata": {"role": "Hamas Political Leader", "priority": "high", "location_type": "abroad"}
    },

    # Military Units (examples)
    {
        "entity_id": "unit-idf-36div",
        "name": "IDF 36th Division",
        "category": "military_unit",
        "owner_entity": "Israel",
        "current_location": {"lat": 31.5250, "lon": 34.5964, "uncertainty_km": 0.5},
        "current_zone": "Sderot",
        "detection_difficulty": 0.1,  # Not hiding
        "metadata": {"unit_type": "armored", "strength": "division", "status": "deployed"}
    },
    {
        "entity_id": "unit-hamas-qassam-north",
        "name": "Qassam Northern Brigade",
        "category": "military_unit",
        "owner_entity": "Hamas",
        "current_location": {"lat": 31.5377, "lon": 34.4895, "uncertainty_km": 3.0},
        "current_zone": "Jabalia",
        "detection_difficulty": 0.7,
        "metadata": {"unit_type": "infantry", "strength": "brigade", "status": "active"}
    },
]


# =============================================================================
# MAP STATE MANAGER
# =============================================================================

class MapStateManager:
    """Thread-safe manager for map state and geographic operations."""

    MAP_STATE_FILE = DATA_DIR / "map_state.json"

    def __init__(self):
        self._lock = threading.Lock()
        self._state: Optional[MapState] = None
        self.load()

    # ===== PERSISTENCE =====

    def load(self):
        """Load map state from file, or initialize with seed data."""
        with self._lock:
            if self.MAP_STATE_FILE.exists():
                try:
                    with open(self.MAP_STATE_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self._state = MapState.from_dict(data)
                    logger.info(f"Loaded map state: {len(self._state.static_locations)} locations, "
                               f"{len(self._state.tracked_entities)} entities, "
                               f"{len(self._state.active_geo_events)} active events")
                except Exception as e:
                    logger.error(f"Error loading map state: {e}")
                    self._initialize_default()
            else:
                self._initialize_default()

    def _initialize_default(self):
        """Initialize with seed data."""
        self._state = MapState(
            last_updated=datetime.now().isoformat(),
            static_locations=[StaticLocation.from_dict(loc) for loc in STATIC_LOCATIONS_SEED],
            tracked_entities=[TrackedEntity.from_dict(ent) for ent in TRACKED_ENTITIES_SEED],
            active_geo_events=[],
            archived_geo_events=[]
        )
        self._save()
        logger.info(f"Initialized map state with seed data: {len(STATIC_LOCATIONS_SEED)} locations, "
                   f"{len(TRACKED_ENTITIES_SEED)} entities")

    def _save(self):
        """Save map state to file (must be called with lock held)."""
        DATA_DIR.mkdir(exist_ok=True)
        try:
            with open(self.MAP_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(self._state.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving map state: {e}")

    def save(self):
        """Public save method (acquires lock)."""
        with self._lock:
            self._save()

    # ===== ZONE OPERATIONS =====

    def get_zone_coordinates(self, zone_name: str) -> Optional[Coordinates]:
        """Get coordinates for a named zone."""
        if zone_name in ZONE_REGISTRY:
            return ZONE_REGISTRY[zone_name]
        # Fuzzy match - case insensitive
        zone_lower = zone_name.lower()
        for name, coords in ZONE_REGISTRY.items():
            if zone_lower == name.lower():
                return coords
            if zone_lower in name.lower() or name.lower() in zone_lower:
                return coords
        return None

    def validate_zone(self, zone_name: str) -> bool:
        """Check if a zone name is valid."""
        return self.get_zone_coordinates(zone_name) is not None

    def get_all_zones(self) -> List[str]:
        """Get list of all valid zone names."""
        return list(ZONE_REGISTRY.keys())

    # ===== STATIC LOCATIONS =====

    def get_static_location(self, location_id: str) -> Optional[StaticLocation]:
        """Get a static location by ID."""
        with self._lock:
            for loc in self._state.static_locations:
                if loc.location_id == location_id:
                    return loc
        return None

    def get_static_locations(self, owner_entity: str = None,
                             location_type: str = None) -> List[dict]:
        """Get static locations with optional filters."""
        with self._lock:
            locations = self._state.static_locations
            if owner_entity:
                locations = [l for l in locations if l.owner_entity == owner_entity]
            if location_type:
                locations = [l for l in locations if l.location_type == location_type]
            return [l.to_dict() for l in locations]

    # ===== ENTITY TRACKING =====

    def get_tracked_entity(self, entity_id: str) -> Optional[TrackedEntity]:
        """Get a tracked entity by ID."""
        with self._lock:
            for entity in self._state.tracked_entities:
                if entity.entity_id == entity_id:
                    return entity
        return None

    def get_entities_in_zone(self, zone_name: str) -> List[TrackedEntity]:
        """Get all tracked entities in a zone."""
        with self._lock:
            return [e for e in self._state.tracked_entities
                    if e.current_zone.lower() == zone_name.lower()]

    def get_entities_by_category(self, category: str) -> List[TrackedEntity]:
        """Get all tracked entities of a category."""
        with self._lock:
            return [e for e in self._state.tracked_entities
                    if e.category == category]

    def get_entities_by_owner(self, owner_entity: str) -> List[TrackedEntity]:
        """Get all tracked entities owned by an entity."""
        with self._lock:
            return [e for e in self._state.tracked_entities
                    if e.owner_entity == owner_entity]

    def update_entity_location(self, entity_id: str,
                               new_zone: str,
                               uncertainty_km: float = 0.0,
                               game_time: str = None) -> bool:
        """Update an entity's location immediately."""
        coords = self.get_zone_coordinates(new_zone)
        if not coords:
            logger.warning(f"Invalid zone: {new_zone}")
            return False

        with self._lock:
            for entity in self._state.tracked_entities:
                if entity.entity_id == entity_id:
                    entity.current_location = Coordinates(
                        lat=coords.lat,
                        lon=coords.lon,
                        uncertainty_km=uncertainty_km
                    )
                    entity.current_zone = new_zone
                    entity.is_moving = False
                    entity.destination = None
                    entity.destination_zone = None
                    entity.movement_started = None
                    entity.movement_eta = None
                    entity.last_known_update = game_time or datetime.now().isoformat()
                    self._state.last_updated = game_time or datetime.now().isoformat()
                    self._save()
                    logger.info(f"Entity {entity_id} moved to {new_zone}")
                    return True
        return False

    def start_entity_movement(self, entity_id: str,
                              destination_zone: str,
                              travel_time_minutes: int,
                              game_time: str) -> bool:
        """Start an entity moving toward a destination."""
        dest_coords = self.get_zone_coordinates(destination_zone)
        if not dest_coords:
            logger.warning(f"Invalid destination zone: {destination_zone}")
            return False

        with self._lock:
            for entity in self._state.tracked_entities:
                if entity.entity_id == entity_id:
                    entity.is_moving = True
                    entity.destination = Coordinates(
                        lat=dest_coords.lat,
                        lon=dest_coords.lon,
                        uncertainty_km=dest_coords.uncertainty_km
                    )
                    entity.destination_zone = destination_zone
                    entity.movement_started = game_time
                    # Calculate ETA
                    start_dt = datetime.fromisoformat(game_time)
                    eta_dt = start_dt + timedelta(minutes=travel_time_minutes)
                    entity.movement_eta = eta_dt.isoformat()
                    entity.last_known_update = game_time
                    self._state.last_updated = game_time
                    self._save()
                    logger.info(f"Entity {entity_id} moving from {entity.current_zone} to {destination_zone}, "
                               f"ETA: {travel_time_minutes} minutes")
                    return True
        return False

    def complete_entity_movements(self, game_time: str) -> List[str]:
        """Check for entities that have arrived at destinations."""
        completed = []
        try:
            current_time = datetime.fromisoformat(game_time)
        except ValueError:
            logger.error(f"Invalid game_time format: {game_time}")
            return []

        with self._lock:
            for entity in self._state.tracked_entities:
                if entity.is_moving and entity.movement_eta:
                    try:
                        eta = datetime.fromisoformat(entity.movement_eta)
                        if current_time >= eta:
                            # Arrived at destination
                            entity.current_location = entity.destination
                            entity.current_zone = entity.destination_zone
                            entity.is_moving = False
                            entity.destination = None
                            entity.destination_zone = None
                            entity.movement_started = None
                            entity.movement_eta = None
                            entity.last_known_update = game_time
                            completed.append(entity.entity_id)
                            logger.info(f"Entity {entity.entity_id} arrived at {entity.current_zone}")
                    except ValueError:
                        pass

            if completed:
                self._state.last_updated = game_time
                self._save()

        return completed

    def get_moving_entities(self) -> List[TrackedEntity]:
        """Get all entities currently in transit (vulnerable to detection)."""
        with self._lock:
            return [e for e in self._state.tracked_entities if e.is_moving]

    # ===== GEO EVENTS =====

    def create_geo_event(self,
                        event_type: str,
                        source_event_id: str,
                        game_time: str,
                        origin_zone: str = None,
                        destination_zone: str = None,
                        center_zone: str = None,
                        radius_km: float = 0.0,
                        duration_seconds: int = 10,
                        description: str = "",
                        actor_entity: str = "",
                        affected_entities: List[str] = None) -> GeoEvent:
        """Create and register a new geo event for map animation."""

        geo_event = GeoEvent(
            geo_event_id=f"geo_{uuid.uuid4().hex[:8]}",
            event_type=event_type,
            source_event_id=source_event_id,
            timestamp=game_time,
            origin=self.get_zone_coordinates(origin_zone) if origin_zone else None,
            origin_zone=origin_zone,
            destination=self.get_zone_coordinates(destination_zone) if destination_zone else None,
            destination_zone=destination_zone,
            center=self.get_zone_coordinates(center_zone) if center_zone else None,
            radius_km=radius_km,
            duration_seconds=duration_seconds,
            description=description,
            actor_entity=actor_entity,
            affected_entities=affected_entities or []
        )

        with self._lock:
            self._state.active_geo_events.append(geo_event)
            self._state.last_updated = game_time
            self._save()

        logger.info(f"Created geo event: {event_type} from {origin_zone} to {destination_zone}")
        return geo_event

    def update_geo_event_status(self, geo_event_id: str, status: str) -> bool:
        """Update a geo event's status (e.g., intercepted, completed)."""
        with self._lock:
            for event in self._state.active_geo_events:
                if event.geo_event_id == geo_event_id:
                    event.status = status
                    self._save()
                    return True
        return False

    def archive_expired_geo_events(self, game_time: str, max_age_seconds: int = 60) -> int:
        """Move completed geo events to archive."""
        try:
            current_time = datetime.fromisoformat(game_time)
        except ValueError:
            return 0

        archived_count = 0

        with self._lock:
            still_active = []
            for event in self._state.active_geo_events:
                try:
                    event_time = datetime.fromisoformat(event.timestamp)
                    age_seconds = (current_time - event_time).total_seconds()

                    if age_seconds > max_age_seconds or event.status in ("completed", "intercepted", "failed"):
                        event.status = event.status if event.status != "active" else "completed"
                        self._state.archived_geo_events.append(event)
                        archived_count += 1
                    else:
                        still_active.append(event)
                except ValueError:
                    still_active.append(event)

            self._state.active_geo_events = still_active
            if archived_count > 0:
                # Keep only last 200 archived events
                self._state.archived_geo_events = self._state.archived_geo_events[-200:]
                self._state.last_updated = game_time
                self._save()

        if archived_count > 0:
            logger.debug(f"Archived {archived_count} geo events")
        return archived_count

    def get_active_events(self) -> List[dict]:
        """Get active geo events for frontend animation."""
        with self._lock:
            return [e.to_dict() for e in self._state.active_geo_events]

    # ===== SPATIAL CLASH DETECTION =====

    def check_spatial_clash(self,
                           action_zone: str,
                           target_categories: List[str] = None) -> List[TrackedEntity]:
        """Find tracked entities in a zone that match target categories.

        Used by resolver to determine if an operation intersects with
        tracked entities (e.g., IDF raid in zone where hostages are located).
        """
        entities_in_zone = self.get_entities_in_zone(action_zone)

        if target_categories:
            entities_in_zone = [e for e in entities_in_zone
                               if e.category in target_categories]

        return entities_in_zone

    def calculate_detection_chance(self,
                                   entity: TrackedEntity,
                                   searcher_capability: float = 0.5) -> float:
        """Calculate probability of detecting an entity.

        Args:
            entity: The entity being searched for
            searcher_capability: 0 = poor intel, 1 = excellent intel

        Returns:
            Probability 0.0 to 1.0
        """
        base_chance = 1.0 - entity.detection_difficulty

        # Moving entities are easier to detect (+20%)
        if entity.is_moving:
            base_chance += 0.2

        # Adjust by searcher capability
        detection_chance = base_chance * (0.5 + 0.5 * searcher_capability)

        return min(1.0, max(0.0, detection_chance))

    def refine_entity_location(self, entity_id: str,
                               new_uncertainty_km: float,
                               game_time: str) -> bool:
        """Reduce uncertainty radius for an entity (intel success)."""
        with self._lock:
            for entity in self._state.tracked_entities:
                if entity.entity_id == entity_id:
                    old_uncertainty = entity.current_location.uncertainty_km
                    entity.current_location.uncertainty_km = new_uncertainty_km
                    entity.last_known_update = game_time
                    self._state.last_updated = game_time
                    self._save()
                    logger.info(f"Refined location for {entity_id}: uncertainty {old_uncertainty} -> {new_uncertainty_km} km")
                    return True
        return False

    # ===== API METHODS =====

    def get_full_state(self) -> dict:
        """Get complete map state for API response."""
        with self._lock:
            return self._state.to_dict()

    def get_tracked_entities_api(self,
                                 owner_entity: str = None,
                                 category: str = None,
                                 zone: str = None) -> List[dict]:
        """Get tracked entities with optional filters for API."""
        with self._lock:
            entities = self._state.tracked_entities
            if owner_entity:
                entities = [e for e in entities if e.owner_entity == owner_entity]
            if category:
                entities = [e for e in entities if e.category == category]
            if zone:
                entities = [e for e in entities if e.current_zone.lower() == zone.lower()]
            return [e.to_dict() for e in entities]
