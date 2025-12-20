/**
 * API Adapter - Transforms PM1 backend responses to component-ready format
 * The backend is the load-bearing wall. The frontend adapts to its structure.
 */

const API_BASE = '';  // Same origin

const ApiAdapter = {
    /**
     * Fetch simulation status
     * @returns {Promise<{running: boolean, paused: boolean, game_time: string, current_turn: number}>}
     */
    async getSimulationStatus() {
        try {
            const response = await fetch(`${API_BASE}/simulation/status`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            console.log('[ApiAdapter] Raw simulation status:', data);
            return {
                running: data.is_running || data.running || false,
                paused: data.paused || false,
                game_time: data.game_time || '--:--:--',
                current_turn: data.current_turn || 0,
                clock_speed: data.clock_speed || 1.0,
                event_count: data.event_count || 0,
                raw: data
            };
        } catch (error) {
            console.error('Failed to fetch simulation status:', error);
            return { running: false, paused: false, game_time: '--:--:--', current_turn: 0 };
        }
    },

    /**
     * Fetch all events and transform to component format
     * @returns {Promise<Array<{id, type, priority, title, description, timestamp, agentId, isPublic}>>}
     */
    async getEvents() {
        try {
            const response = await fetch(`${API_BASE}/simulation/events`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            const events = data.events || data || [];

            return events.map(event => this.transformEvent(event));
        } catch (error) {
            console.error('Failed to fetch events:', error);
            return [];
        }
    },

    /**
     * Transform a single PM1 event to component format
     */
    transformEvent(event) {
        const typeMap = {
            'military': { type: 'military', priority: 'high', color: 'danger' },
            'diplomatic': { type: 'diplomatic', priority: 'medium', color: 'accent' },
            'intelligence': { type: 'intelligence', priority: 'high', color: 'purple' },
            'media': { type: 'media', priority: 'low', color: 'warning' },
            'economic': { type: 'economic', priority: 'medium', color: 'success' },
            'political': { type: 'political', priority: 'medium', color: 'accent' },
            'public': { type: 'public', priority: 'low', color: 'gray' },
            'security': { type: 'security', priority: 'high', color: 'danger' },
            'communication': { type: 'communication', priority: 'low', color: 'gray' }
        };

        const actionType = (event.action_type || 'unknown').toLowerCase();
        const typeInfo = typeMap[actionType] || { type: actionType, priority: 'low', color: 'gray' };

        return {
            id: event.event_id || event.id || `evt_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
            type: typeInfo.type,
            priority: typeInfo.priority,
            color: typeInfo.color,
            title: this.generateEventTitle(event),
            description: event.summary || event.description || '',
            timestamp: event.timestamp || new Date().toISOString(),
            agentId: event.agent_id || null,
            agentName: event.agent_name || event.agent_id || 'Unknown',
            isPublic: event.is_public !== false,
            kpiChanges: this.transformKPIChanges(event.kpi_changes),
            raw: event
        };
    },

    /**
     * Transform KPI changes array to display-friendly format
     * @param {Array|null} kpiChanges - Raw KPI changes from backend
     * @returns {Array} Formatted KPI changes for display
     */
    transformKPIChanges(kpiChanges) {
        if (!kpiChanges || !Array.isArray(kpiChanges) || kpiChanges.length === 0) {
            return [];
        }

        // Metric label mappings for readable display
        const metricLabels = {
            'casualties_military': 'Military Casualties',
            'casualties_civilian': 'Civilian Casualties',
            'casualties': 'Casualties',
            'fighters_remaining': 'Fighters',
            'hostages_held_by_enemy': 'Hostages Held',
            'hostages_rescued': 'Hostages Rescued',
            'morale_military': 'Military Morale',
            'morale_civilian': 'Civilian Morale',
            'international_standing': 'Int\'l Standing',
            'ammunition_iron_dome_pct': 'Iron Dome Ammo',
            'ammunition_precision_pct': 'Precision Ammo',
            'ammunition_artillery_pct': 'Artillery Ammo',
            'infrastructure_damage_pct': 'Infrastructure Damage',
            'tunnel_km_destroyed': 'Tunnels Destroyed',
            'tunnel_network_operational_km': 'Tunnel Network',
            'intel_accuracy': 'Intel Accuracy',
            'leadership_cohesion': 'Leadership',
            'leadership_capacity': 'Leadership Capacity',
            'intel_capability': 'Intel Capability',
            'economic_stability': 'Economic Stability',
            'hostages_released': 'Hostages Released',
            'ships_damaged': 'Ships Damaged',
            'red_sea_attacks_conducted': 'Red Sea Attacks',
            'international_notoriety': 'Int\'l Notoriety',
            'us_strikes_received': 'US Strikes',
            'drones_inventory': 'Drones'
        };

        return kpiChanges.map(change => {
            // Extract metric name from path (e.g., "dynamic_metrics.casualties_military" -> "casualties_military")
            const metricPath = change.metric || '';
            const metricName = metricPath.split('.').pop();
            const label = metricLabels[metricName] || metricName.replace(/_/g, ' ');

            // Handle both old format {old, new} and new format {change, old_value, new_value}
            let changeValue;
            let oldValue = change.old_value ?? change.old;
            let newValue = change.new_value ?? change.new;

            if (change.change !== undefined) {
                changeValue = change.change;
            } else if (oldValue !== undefined && newValue !== undefined) {
                // Fallback: calculate from old/new for legacy data
                changeValue = newValue - oldValue;
            } else {
                changeValue = 0;
            }

            const isPositive = changeValue > 0;

            return {
                entity: change.entity_id || 'Unknown',
                metric: metricName,
                label: label,
                change: changeValue,
                displayChange: isPositive ? `+${changeValue}` : `${changeValue}`,
                isPositive: isPositive,
                oldValue: oldValue,
                newValue: newValue
            };
        });
    },

    /**
     * Generate a title from event data
     */
    generateEventTitle(event) {
        if (event.title) return event.title;

        const actionType = (event.action_type || '').toLowerCase();
        const agentName = event.agent_name || event.agent_id || 'Unknown';

        const titleTemplates = {
            'military': `Military Operation - ${agentName}`,
            'diplomatic': `Diplomatic Action - ${agentName}`,
            'intelligence': `Intel Report - ${agentName}`,
            'media': `Media Broadcast - ${agentName}`,
            'security': `Security Alert - ${agentName}`,
            'economic': `Economic Update - ${agentName}`,
            'political': `Political Development - ${agentName}`
        };

        return titleTemplates[actionType] || `${actionType.charAt(0).toUpperCase() + actionType.slice(1)} - ${agentName}`;
    },

    /**
     * Fetch KPIs for Israel and transform to category format
     * @returns {Promise<Object>} Category-grouped KPIs
     */
    async getKPIs() {
        try {
            const response = await fetch(`${API_BASE}/kpis/Israel`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();

            return this.transformKPIs(data);
        } catch (error) {
            console.error('Failed to fetch KPIs:', error);
            return {};
        }
    },

    /**
     * Transform PM1 entity KPIs to category-grouped format
     */
    transformKPIs(data) {
        // KPIs are nested: data.kpis.dynamic_metrics
        const kpiData = data.kpis || data;
        const kpis = kpiData.dynamic_metrics || kpiData || {};
        console.log('[ApiAdapter] KPI metrics:', Object.keys(kpis));

        // Category groupings for player view
        const categories = {
            'Security': {
                icon: '&#128737;',  // shield
                metrics: {}
            },
            'Casualties': {
                icon: '&#9760;',  // skull
                metrics: {}
            },
            'Morale': {
                icon: '&#128170;',  // flexed bicep
                metrics: {}
            },
            'Diplomacy': {
                icon: '&#127760;',  // globe
                metrics: {}
            },
            'Infrastructure': {
                icon: '&#127959;',  // building
                metrics: {}
            },
            'Resources': {
                icon: '&#128176;',  // money bag
                metrics: {}
            }
        };

        // Map PM1 metrics to categories (matching actual API field names)
        const metricMappings = {
            // Casualties
            'casualties_military': { category: 'Casualties', label: 'Military Casualties', inverse: true },
            'casualties_civilian': { category: 'Casualties', label: 'Civilian Casualties', inverse: true },
            'enemy_fighters_eliminated': { category: 'Casualties', label: 'Enemy Eliminated', inverse: false },

            // Security
            'hostages_held_by_enemy': { category: 'Security', label: 'Hostages Held', inverse: true },
            'hostages_rescued': { category: 'Security', label: 'Hostages Rescued', inverse: false },
            'tunnel_km_destroyed': { category: 'Security', label: 'Tunnels Destroyed (km)', inverse: false },

            // Morale
            'morale_military': { category: 'Morale', label: 'Military Morale', inverse: false },
            'morale_civilian': { category: 'Morale', label: 'Civilian Morale', inverse: false },

            // Diplomacy
            'international_standing': { category: 'Diplomacy', label: 'International Standing', inverse: false },

            // Infrastructure
            'infrastructure_damage_pct': { category: 'Infrastructure', label: 'Infrastructure Damage', inverse: true, suffix: '%' },

            // Resources
            'ammunition_iron_dome_pct': { category: 'Resources', label: 'Iron Dome Ammo', inverse: false, suffix: '%' },
            'ammunition_precision_pct': { category: 'Resources', label: 'Precision Ammo', inverse: false, suffix: '%' },
            'ammunition_artillery_pct': { category: 'Resources', label: 'Artillery Ammo', inverse: false, suffix: '%' }
        };

        // Process each metric
        for (const [key, value] of Object.entries(kpis)) {
            const mapping = metricMappings[key];
            if (mapping && categories[mapping.category]) {
                const numValue = typeof value === 'number' ? value : parseFloat(value) || 0;
                categories[mapping.category].metrics[key] = {
                    label: mapping.label,
                    value: numValue,
                    displayValue: mapping.suffix ? `${numValue}${mapping.suffix}` : numValue.toString(),
                    trend: this.calculateTrend(numValue, mapping.inverse),
                    inverse: mapping.inverse || false
                };
            }
        }

        // Remove empty categories
        for (const cat of Object.keys(categories)) {
            if (Object.keys(categories[cat].metrics).length === 0) {
                delete categories[cat];
            }
        }

        return categories;
    },

    /**
     * Calculate trend indicator based on value and whether lower is better
     */
    calculateTrend(value, inverse = false) {
        // For now, use thresholds. In future, compare to previous values.
        if (inverse) {
            // Lower is better (casualties, damage)
            if (value > 50) return 'critical';
            if (value > 20) return 'warning';
            return 'good';
        } else {
            // Higher is better (morale, standing)
            if (value < 30) return 'critical';
            if (value < 60) return 'warning';
            return 'good';
        }
    },

    /**
     * Fetch all agents and filter for player view
     * @returns {Promise<Object>} Category-grouped friendly agents
     */
    async getAgents() {
        try {
            const response = await fetch(`${API_BASE}/agents`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            console.log('[ApiAdapter] Raw agents data type:', typeof data.agents);

            // Handle both array and dict formats
            let agents = data.agents || data || [];
            if (!Array.isArray(agents)) {
                // API returns dict keyed by agent_id - convert to array
                agents = Object.values(agents);
            }
            console.log('[ApiAdapter] Agents count:', agents.length);

            return this.transformAgents(agents);
        } catch (error) {
            console.error('Failed to fetch agents:', error);
            return {};
        }
    },

    /**
     * Transform agents to player-visible categories
     */
    transformAgents(agents) {
        const categories = {
            'security': {
                label: 'Security Services',
                agents: []
            },
            'government': {
                label: 'Government',
                agents: []
            },
            'media': {
                label: 'Media',
                agents: []
            },
            'international': {
                label: 'International Allies',
                agents: []
            }
        };

        // Category mappings
        const categoryMap = {
            'security': 'security',
            'military': 'security',
            'intelligence': 'security',
            'government': 'government',
            'political': 'government',
            'economic': 'government',
            'media': 'media',
            'international': 'international',
            'diplomatic': 'international'
        };

        for (const agent of agents) {
            // Skip enemies - player doesn't see enemy agent details
            if (agent.is_enemy === true) continue;

            // Skip System agents - not interactive
            const entityType = (agent.entity_type || '').toLowerCase();
            if (entityType === 'system') continue;

            // Determine category
            const agentCategory = (agent.agent_category || agent.category || '').toLowerCase();
            const mappedCategory = categoryMap[agentCategory] || 'government';

            // For international, only show western allies
            if (mappedCategory === 'international' && agent.is_west === false) continue;

            if (categories[mappedCategory]) {
                categories[mappedCategory].agents.push({
                    id: agent.agent_id || agent.id,
                    name: agent.agent_name || agent.name || agent.agent_id,
                    role: agent.role || agentCategory,
                    status: agent.status || 'active',
                    avatar: this.getAgentAvatar(agent),
                    category: mappedCategory,
                    isReporting: agent.is_reporting_government === true,
                    raw: agent
                });
            }
        }

        return categories;
    },

    /**
     * Get avatar/icon for agent
     */
    getAgentAvatar(agent) {
        const avatarMap = {
            'Head-Of-Shabak': '&#128373;',  // detective
            'Head-Of-Mossad': '&#128065;',  // eye
            'IDF-Commander': '&#9876;',     // crossed swords
            'Defense-Minister': '&#128737;', // shield
            'Treasury-Minister': '&#128176;', // money bag
            'Media-Channel-12': '&#128250;',  // TV
            'Media-Channel-14': '&#128250;',
            'USA-President': '&#127482;&#127480;',  // US flag
            'UK-PM': '&#127468;&#127463;'  // UK flag
        };

        return avatarMap[agent.agent_id] || '&#128100;';  // default: bust silhouette
    },

    /**
     * Fetch map state
     * @returns {Promise<Object>} Map data with entities and locations
     */
    async getMapState() {
        try {
            const response = await fetch(`${API_BASE}/map/state`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            return this.transformMapState(data);
        } catch (error) {
            console.error('Failed to fetch map state:', error);
            return { static_locations: [], tracked_entities: [], active_geo_events: [] };
        }
    },

    /**
     * Transform map state for tactical display
     * Returns the raw map_state structure that TacticalMap.render() expects
     */
    transformMapState(data) {
        // Handle nested map_state structure from API
        const mapState = data.map_state || data;

        // Return the raw structure that TacticalMap expects:
        // - static_locations: array of location objects with coordinates
        // - tracked_entities: array of entity objects with current_location
        // - active_geo_events: array of geo event objects for animations
        return {
            static_locations: mapState.static_locations || [],
            tracked_entities: mapState.tracked_entities || [],
            active_geo_events: mapState.active_geo_events || [],
            archived_geo_events: mapState.archived_geo_events || [],
            last_updated: mapState.last_updated || null
        };
    },

    /**
     * Fetch PM approval requests
     * @returns {Promise<Array>} Pending approval requests
     */
    async getPMApprovals() {
        try {
            const response = await fetch(`${API_BASE}/simulation/pm-approvals`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            console.log('[ApiAdapter] PM approvals raw response:', data);
            const approvals = data.pending_approvals || data.approvals || data || [];
            console.log('[ApiAdapter] PM approvals extracted array:', approvals);

            return approvals.map(approval => ({
                id: approval.approval_id || approval.request_id || approval.id,
                agentId: approval.requesting_agent || approval.agent_id,
                agentName: approval.requesting_agent || approval.agent_name || approval.agent_id,
                requestType: approval.request_type || 'action',
                summary: approval.summary || approval.description || '',
                urgency: approval.urgency || 'medium',
                options: approval.options || ['Approve', 'Deny'],
                timestamp: approval.timestamp || new Date().toISOString(),
                raw: approval
            }));
        } catch (error) {
            console.error('Failed to fetch PM approvals:', error);
            return [];
        }
    },

    /**
     * Submit PM approval decision
     * @param {string} approvalId
     * @param {string} decision
     * @returns {Promise<boolean>}
     */
    async submitPMDecision(approvalId, decision) {
        try {
            const response = await fetch(`${API_BASE}/simulation/pm-approve/${approvalId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ decision })
            });
            return response.ok;
        } catch (error) {
            console.error('Failed to submit PM decision:', error);
            return false;
        }
    },

    /**
     * Send chat message to agent
     * @param {string} agentId
     * @param {string} message
     * @returns {Promise<Object>}
     */
    async sendAgentChat(agentId, message) {
        try {
            const response = await fetch(`${API_BASE}/agents/${agentId}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message })
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('Failed to send chat:', error);
            return null;
        }
    },

    /**
     * Start the simulation
     * @param {number} clockSpeed - Speed multiplier (default 2.0)
     * @returns {Promise<boolean>}
     */
    async startSimulation(clockSpeed = 2.0) {
        try {
            const response = await fetch(`${API_BASE}/simulation/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ clock_speed: clockSpeed })
            });
            const data = await response.json();
            console.log('[ApiAdapter] Start simulation response:', data);
            return response.ok;
        } catch (error) {
            console.error('Failed to start simulation:', error);
            return false;
        }
    },

    /**
     * Stop the simulation
     * @returns {Promise<boolean>}
     */
    async stopSimulation() {
        try {
            const response = await fetch(`${API_BASE}/simulation/stop`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await response.json();
            console.log('[ApiAdapter] Stop simulation response:', data);
            return response.ok;
        } catch (error) {
            console.error('Failed to stop simulation:', error);
            return false;
        }
    }
};

// Export for use in other modules
window.ApiAdapter = ApiAdapter;
