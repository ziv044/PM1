/**
 * Tactical Map Component - Leaflet-based interactive map
 * Replaces SVG-based drawing with real geographic tiles
 */

const TacticalMap = {
    container: null,
    map: null,
    currentStyle: 'dark',
    regionMarkers: {},
    entityMarkers: [],
    prevRocketsReceived: 0,

    /**
     * Initialize the tactical map
     */
    init() {
        this.container = document.getElementById('mapContent');
        if (!this.container) {
            console.warn('[TacticalMap] Container not found');
            return;
        }

        // Check if Leaflet is loaded
        if (typeof L === 'undefined') {
            console.error('[TacticalMap] Leaflet (L) not loaded - cannot initialize map');
            this.container.innerHTML = '<div class="text-game-danger text-sm p-4">Map library failed to load</div>';
            return;
        }

        // Check if RegionData is loaded
        if (typeof RegionData === 'undefined' || !RegionData.MAP_CONFIG) {
            console.error('[TacticalMap] RegionData not loaded - cannot initialize map');
            this.container.innerHTML = '<div class="text-game-danger text-sm p-4">Map data failed to load</div>';
            return;
        }

        // Clear loading state
        this.container.innerHTML = '';

        // Create map container div
        const mapDiv = document.createElement('div');
        mapDiv.id = 'leaflet-map';
        mapDiv.style.width = '100%';
        mapDiv.style.height = '100%';
        this.container.appendChild(mapDiv);

        // Initialize Leaflet map
        const config = RegionData.MAP_CONFIG;
        this.map = L.map('leaflet-map', {
            center: config.center,
            zoom: config.zoom,
            minZoom: config.minZoom,
            maxZoom: config.maxZoom,
            zoomControl: true,
            attributionControl: false,
        });

        // Add initial tile layer
        this.tileLayer = L.tileLayer(
            RegionData.TILE_LAYERS[this.currentStyle].url,
            { maxZoom: RegionData.TILE_LAYERS[this.currentStyle].maxZoom }
        ).addTo(this.map);

        // Add style selector
        this.addStyleSelector();

        // Fix map size after render
        setTimeout(() => this.map.invalidateSize(), 100);

        // Handle container resize
        const resizeObserver = new ResizeObserver(() => {
            if (this.map) this.map.invalidateSize();
        });
        resizeObserver.observe(this.container);

        console.log('[TacticalMap] Initialized with Leaflet');
    },

    /**
     * Add map style selector control
     */
    addStyleSelector() {
        const selector = document.createElement('div');
        selector.className = 'map-style-selector';
        selector.innerHTML = `
            <button class="map-style-btn ${this.currentStyle === 'dark' ? 'active' : ''}" data-style="dark">Dark</button>
            <button class="map-style-btn ${this.currentStyle === 'voyager' ? 'active' : ''}" data-style="voyager">Classic</button>
            <button class="map-style-btn ${this.currentStyle === 'terrain' ? 'active' : ''}" data-style="terrain">Terrain</button>
            <button class="map-style-btn ${this.currentStyle === 'watercolor' ? 'active' : ''}" data-style="watercolor">Painted</button>
        `;

        selector.addEventListener('click', (e) => {
            if (e.target.classList.contains('map-style-btn')) {
                const style = e.target.dataset.style;
                this.setMapStyle(style);

                // Update active button
                selector.querySelectorAll('.map-style-btn').forEach(btn => {
                    btn.classList.toggle('active', btn.dataset.style === style);
                });
            }
        });

        this.container.appendChild(selector);
    },

    /**
     * Set map tile style
     */
    setMapStyle(style) {
        if (!RegionData.TILE_LAYERS[style]) return;

        this.currentStyle = style;
        const layer = RegionData.TILE_LAYERS[style];

        this.map.removeLayer(this.tileLayer);
        this.tileLayer = L.tileLayer(layer.url, { maxZoom: layer.maxZoom }).addTo(this.map);
    },

    /**
     * Create troop icon (kept for future use)
     */
    createTroopIcon(count, type) {
        const color = type === 'idf' ? '#4a9eff' : '#ef4444';
        const emoji = type === 'idf' ? '\u{1F6E1}' : '\u{1F480}';
        const displayCount = count >= 1000 ? Math.floor(count/1000) + 'k' : count;

        return L.divIcon({
            className: 'troop-marker',
            html: `
                <div style="
                    background: linear-gradient(145deg, ${color}ee, ${color}aa);
                    border: 2px solid ${type === 'idf' ? '#60a5fa' : '#f87171'};
                    border-radius: 50%;
                    width: 28px;
                    height: 28px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.5);
                    font-size: 12px;
                    position: relative;
                ">
                    ${emoji}
                    <span style="
                        position: absolute;
                        bottom: -5px;
                        right: -5px;
                        background: #1a1a2e;
                        color: #fff;
                        font-size: 8px;
                        font-weight: bold;
                        padding: 1px 3px;
                        border-radius: 6px;
                        border: 1px solid ${color};
                    ">${displayCount}</span>
                </div>
            `,
            iconSize: [28, 28],
            iconAnchor: [14, 14],
        });
    },

    /**
     * Create rocket impact icon
     */
    createRocketIcon(count) {
        const displayCount = count >= 1000 ? Math.floor(count/1000) + 'k' : count;

        return L.divIcon({
            className: 'rocket-marker pulse-animation',
            html: `
                <div style="
                    background: linear-gradient(145deg, #f97316ee, #ea580caa);
                    border: 2px solid #fb923c;
                    border-radius: 6px;
                    padding: 3px 6px;
                    display: flex;
                    align-items: center;
                    gap: 3px;
                    box-shadow: 0 2px 8px rgba(249,115,22,0.5);
                ">
                    <span style="font-size: 12px;">\u{1F680}</span>
                    <span style="color: #fff; font-size: 10px; font-weight: bold;">${displayCount}</span>
                </div>
            `,
            iconSize: [50, 24],
            iconAnchor: [25, 12],
        });
    },

    /**
     * Render map with current state
     * @param {Object} mapState - Map state from API (static_locations, tracked_entities, active_geo_events)
     */
    render(mapState) {
        if (!this.map) return;

        // Clear previous entity markers
        this.entityMarkers.forEach(m => this.map.removeLayer(m));
        this.entityMarkers = [];

        if (!mapState) return;

        // Render static locations (military bases, border crossings, etc.)
        if (mapState.static_locations) {
            for (const loc of mapState.static_locations) {
                this.renderStaticLocation(loc);
            }
        }

        // Render tracked entities with fog of war
        if (mapState.tracked_entities) {
            for (const entity of mapState.tracked_entities) {
                this.renderTrackedEntity(entity);
            }
        }

        // Animate active geo events
        if (mapState.active_geo_events) {
            for (const event of mapState.active_geo_events) {
                this.renderGeoEvent(event);
            }
        }
    },

    /**
     * Render a static location on the map
     */
    renderStaticLocation(loc) {
        if (!loc.coordinates) return;

        const coords = loc.coordinates;
        const isEnemy = loc.owner_entity !== 'Israel' &&
                        ['Hamas', 'Hezbollah', 'Houthis', 'Iran'].includes(loc.owner_entity);
        const isFriendly = loc.owner_entity === 'Israel';

        const icon = this.createStaticLocationIcon(loc.location_type, loc.owner_entity, loc.name);
        const marker = L.marker([coords.lat, coords.lon], { icon })
            .bindPopup(this.createStaticLocationPopup(loc))
            .addTo(this.map);

        this.entityMarkers.push(marker);
    },

    /**
     * Create icon for static location
     */
    createStaticLocationIcon(locType, owner, name) {
        const isIsrael = owner === 'Israel';
        const color = isIsrael ? '#4a9eff' :
                     ['Hamas', 'Hezbollah', 'Houthis'].includes(owner) ? '#ef4444' :
                     owner === 'Iran' ? '#a855f7' : '#6b7280';

        const emoji = this.getLocationEmoji(locType, owner);

        return L.divIcon({
            className: 'game-marker',
            html: `<div style="
                width: 28px; height: 28px;
                background: linear-gradient(145deg, ${color}dd, ${color}88);
                border: 2px solid ${isIsrael ? '#60a5fa' : '#f87171'};
                border-radius: 6px;
                display: flex; align-items: center; justify-content: center;
                box-shadow: 0 2px 8px rgba(0,0,0,0.4);
                font-size: 14px;
            ">${emoji}</div>`,
            iconSize: [28, 28],
            iconAnchor: [14, 14],
            popupAnchor: [0, -14],
        });
    },

    /**
     * Get emoji for location type
     */
    getLocationEmoji(locType, owner) {
        const types = {
            military_base: '\u{1F3F0}',      // Castle
            nuclear_plant: '\u{2622}',       // Radioactive
            border_crossing: '\u{1F6A7}',    // Construction
            tunnel_entrance: '\u{1F573}',    // Hole
            government_hq: '\u{1F3DB}',      // Classical building
            command_center: '\u{1F4CD}',     // Pin
            strategic_waterway: '\u{2693}',  // Anchor
        };
        return types[locType] || '\u{1F4CD}';
    },

    /**
     * Create popup for static location
     */
    createStaticLocationPopup(loc) {
        return `
            <div class="region-popup">
                <div class="region-popup-title">${loc.name}</div>
                <div class="region-popup-row">
                    <span style="color: #9ca3af;">Type:</span>
                    <span style="text-transform: capitalize;">${loc.location_type.replace(/_/g, ' ')}</span>
                </div>
                <div class="region-popup-row">
                    <span style="color: #9ca3af;">Owner:</span>
                    <span style="color: ${loc.owner_entity === 'Israel' ? '#4a9eff' : '#ef4444'};">${loc.owner_entity}</span>
                </div>
                ${loc.description ? `<div class="region-popup-row" style="color: #9ca3af; font-size: 10px;">${loc.description}</div>` : ''}
            </div>
        `;
    },

    /**
     * Render a tracked entity with fog of war
     */
    renderTrackedEntity(entity) {
        if (!entity.current_location) return;

        const coords = entity.current_location;
        const uncertainty = coords.uncertainty_km || 0;
        const isEnemy = !['Israel', 'USA'].includes(entity.owner_entity);

        // For enemy entities with high uncertainty, show fog of war circle
        if (isEnemy && uncertainty > 0.5) {
            const circle = L.circle([coords.lat, coords.lon], {
                radius: uncertainty * 1000, // km to meters
                fillColor: '#ef4444',
                fillOpacity: 0.15,
                color: '#ef4444',
                opacity: 0.3,
                weight: 1,
                dashArray: '4,4',
            }).addTo(this.map);
            this.entityMarkers.push(circle);
        }

        // Create entity icon
        const icon = this.createTrackedEntityIcon(entity, isEnemy, uncertainty);
        const marker = L.marker([coords.lat, coords.lon], { icon })
            .bindPopup(this.createTrackedEntityPopup(entity))
            .addTo(this.map);

        this.entityMarkers.push(marker);
    },

    /**
     * Create icon for tracked entity
     */
    createTrackedEntityIcon(entity, isEnemy, uncertainty) {
        const category = entity.category || 'unknown';
        const highUncertainty = isEnemy && uncertainty > 2;

        // Choose color based on ownership
        const color = !isEnemy ? '#4a9eff' : '#ef4444';
        const borderColor = !isEnemy ? '#60a5fa' : '#f87171';

        // Choose emoji based on category
        const emojis = {
            hostage_group: '\u{1F465}',      // People
            high_value_target: '\u{1F3AF}',  // Target
            military_unit: '\u{1F6E1}',      // Shield
        };
        const emoji = emojis[category] || '\u{2753}';

        // For high uncertainty enemies, show question mark
        const displayEmoji = highUncertainty ? '?' : emoji;
        const opacity = highUncertainty ? 0.6 : 1;

        return L.divIcon({
            className: 'game-marker',
            html: `<div style="
                width: 24px; height: 24px;
                background: ${color};
                opacity: ${opacity};
                border: 2px solid ${borderColor};
                border-radius: 50%;
                display: flex; align-items: center; justify-content: center;
                box-shadow: 0 0 ${highUncertainty ? 4 : 8}px ${color}80;
                font-size: 12px;
                color: white;
                font-weight: bold;
            ">${displayEmoji}</div>`,
            iconSize: [24, 24],
            iconAnchor: [12, 12],
            popupAnchor: [0, -12],
        });
    },

    /**
     * Create popup for tracked entity
     */
    createTrackedEntityPopup(entity) {
        const isEnemy = !['Israel', 'USA'].includes(entity.owner_entity);
        const color = isEnemy ? '#ef4444' : '#4a9eff';
        const uncertainty = entity.current_location?.uncertainty_km || 0;

        let html = `
            <div class="region-popup">
                <div class="region-popup-title" style="color: ${color};">${entity.name}</div>
                <div class="region-popup-row">
                    <span style="color: #9ca3af;">Owner:</span>
                    <span style="color: ${color};">${entity.owner_entity}</span>
                </div>
                <div class="region-popup-row">
                    <span style="color: #9ca3af;">Zone:</span>
                    <span>${entity.current_zone || 'Unknown'}</span>
                </div>
        `;

        if (uncertainty > 0) {
            html += `<div class="region-popup-row">
                <span style="color: #f59e0b;">\u{26A0} Uncertainty: ${uncertainty.toFixed(1)} km</span>
            </div>`;
        }

        if (entity.metadata) {
            if (entity.metadata.hostage_count) {
                html += `<div class="region-popup-row" style="color: #22c55e;">\u{1F465} Hostages: ${entity.metadata.hostage_count}</div>`;
            }
            if (entity.metadata.role) {
                html += `<div class="region-popup-row" style="color: #9ca3af; font-size: 10px;">${entity.metadata.role}</div>`;
            }
        }

        html += '</div>';
        return html;
    },

    /**
     * Render active geo event
     */
    renderGeoEvent(event) {
        if (!event.destination) return;

        const dest = event.destination;
        const color = this.getGeoEventColor(event.event_type);

        // Draw event marker
        const icon = L.divIcon({
            className: 'rocket-marker pulse-animation',
            html: `<div style="
                background: ${color};
                border: 2px solid white;
                border-radius: 50%;
                width: 16px; height: 16px;
                box-shadow: 0 0 12px ${color};
            "></div>`,
            iconSize: [16, 16],
            iconAnchor: [8, 8],
        });

        const marker = L.marker([dest.lat, dest.lon], { icon })
            .bindPopup(`<b>${event.event_type.replace(/_/g, ' ')}</b><br>${event.description || ''}`)
            .addTo(this.map);

        this.entityMarkers.push(marker);

        // Draw line from origin if exists
        if (event.origin) {
            const line = L.polyline(
                [[event.origin.lat, event.origin.lon], [dest.lat, dest.lon]],
                { color: color, weight: 2, dashArray: '5,5', opacity: 0.6 }
            ).addTo(this.map);
            this.entityMarkers.push(line);
        }
    },

    /**
     * Get color for geo event type
     */
    getGeoEventColor(eventType) {
        const colors = {
            missile_launch: '#ef4444',
            air_strike: '#f97316',
            force_deployment: '#4a9eff',
            intel_operation: '#a855f7',
            interceptor: '#22c55e',
        };
        return colors[eventType] || '#f59e0b';
    },

    /**
     * Trigger flash effect for rocket impacts
     */
    triggerFlashEffect() {
        this.container.classList.add('map-shake');

        const flash = document.createElement('div');
        flash.className = 'map-flash-overlay';
        this.container.appendChild(flash);

        setTimeout(() => {
            this.container.classList.remove('map-shake');
            flash.remove();
        }, 600);
    },

    /**
     * Animate event at location
     */
    animateEvent(lat, lon) {
        if (!this.map) return;

        // Create expanding ring effect
        let radius = 1000;
        let opacity = 0.8;

        const circle = L.circle([lat, lon], {
            radius: radius,
            fillColor: '#f59e0b',
            fillOpacity: 0,
            color: '#f59e0b',
            opacity: opacity,
            weight: 3,
        }).addTo(this.map);

        const animate = () => {
            radius += 500;
            opacity -= 0.02;

            if (opacity > 0) {
                circle.setRadius(radius);
                circle.setStyle({ opacity: opacity });
                requestAnimationFrame(animate);
            } else {
                this.map.removeLayer(circle);
            }
        };
        requestAnimationFrame(animate);
    },
};

// Export
window.TacticalMap = TacticalMap;
