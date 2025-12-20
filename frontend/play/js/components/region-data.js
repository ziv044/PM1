/**
 * Region Data Configuration for Leaflet Map
 * Adapted from PM3 for PM1's play interface
 */

const RegionData = {
    // Region geographic data
    REGIONS: {
        gaza: {
            id: 'gaza',
            name: 'Gaza Strip',
            center: [31.45, 34.4],
            coordinates: [
                [31.59, 34.22],
                [31.59, 34.56],
                [31.22, 34.56],
                [31.22, 34.22],
            ],
        },
        southern_israel: {
            id: 'southern_israel',
            name: 'Southern Israel',
            center: [31.0, 34.8],
            coordinates: [
                [31.55, 34.25],
                [31.55, 35.4],
                [29.5, 35.0],
                [29.5, 34.25],
            ],
        },
        central_israel: {
            id: 'central_israel',
            name: 'Central Israel',
            center: [32.0, 34.85],
            coordinates: [
                [32.35, 34.65],
                [32.35, 35.15],
                [31.55, 35.15],
                [31.55, 34.65],
            ],
        },
        northern_israel: {
            id: 'northern_israel',
            name: 'Northern Israel',
            center: [32.75, 35.3],
            coordinates: [
                [33.1, 34.9],
                [33.1, 35.7],
                [32.35, 35.7],
                [32.35, 34.9],
            ],
        },
        northern_border: {
            id: 'northern_border',
            name: 'Northern Border',
            center: [33.1, 35.5],
            coordinates: [
                [33.35, 35.1],
                [33.35, 35.9],
                [33.0, 35.9],
                [33.0, 35.1],
            ],
        },
        lebanon: {
            id: 'lebanon',
            name: 'Lebanon',
            center: [33.85, 35.86],
            coordinates: [
                [34.7, 35.1],
                [34.7, 36.6],
                [33.05, 36.6],
                [33.05, 35.1],
            ],
        },
        west_bank: {
            id: 'west_bank',
            name: 'West Bank',
            center: [31.9, 35.25],
            coordinates: [
                [32.55, 34.95],
                [32.55, 35.57],
                [31.35, 35.57],
                [31.35, 34.95],
            ],
        },
    },

    // Map center and zoom configuration
    MAP_CONFIG: {
        center: [31.8, 35.0],
        zoom: 7,
        minZoom: 6,
        maxZoom: 12,
    },

    // Tile layer URLs - various styles
    TILE_LAYERS: {
        // Dark strategic - default for PM1 dark theme
        dark: {
            url: 'https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
            maxZoom: 19,
        },
        // Clean stylized - like board game maps
        voyager: {
            url: 'https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png',
            maxZoom: 19,
        },
        // Watercolor - painted/artistic style
        watercolor: {
            url: 'https://tiles.stadiamaps.com/tiles/stamen_watercolor/{z}/{x}/{y}.jpg',
            maxZoom: 16,
        },
        // Terrain - topographic style
        terrain: {
            url: 'https://tiles.stadiamaps.com/tiles/stamen_terrain/{z}/{x}/{y}.png',
            maxZoom: 18,
        },
    },

    // Control colors by faction
    CONTROL_COLORS: {
        israel: '#4a9eff',   // PM1 game-accent blue
        hamas: '#22c55e',     // Green (Islamic)
        hezbollah: '#f59e0b', // Warning orange
        contested: '#a855f7', // Purple
    },

    // Status colors
    STATUS_COLORS: {
        normal: '#22c55e',       // game-success
        tense: '#f59e0b',        // game-warning
        under_attack: '#ef4444', // game-danger
        hostile: '#dc2626',
        active_operations_source: '#f97316',
    },

    // War status colors
    WAR_STATUS_COLORS: {
        none: '#22c55e',
        tension: '#f59e0b',
        active_conflict: '#f97316',
        full_war: '#ef4444',
        ceasefire: '#4a9eff',
    },

    // Get emoji for region based on control/type
    getRegionEmoji(control, name) {
        const nameLower = name.toLowerCase();
        if (nameLower.includes('gaza')) return '\u{1F3DA}';      // Derelict house
        if (nameLower.includes('lebanon')) return '\u{1F3D4}';   // Mountain
        if (nameLower.includes('west bank')) return '\u{1F3DB}'; // Classical building
        if (control === 'israel') return '\u{1F3F0}';            // Castle
        if (control === 'hamas') return '\u{2694}';              // Crossed swords
        if (control === 'hezbollah') return '\u{1F5E1}';         // Dagger
        return '\u{1F3D8}';                                       // Buildings
    },
};

// Export
window.RegionData = RegionData;
