/**
 * Player State Manager - State management, polling, and visibility filtering
 * Implements player perspective: sees only what Israel knows
 */

const PlayerState = {
    // Cached data
    agents: {},          // Agent lookup by ID
    agentCategories: {}, // Category-grouped agents
    events: [],          // All visible events
    kpis: {},            // Current KPIs
    mapState: {},        // Map entities and locations
    pmApprovals: [],     // Pending PM decisions

    // Simulation state
    simulation: {
        running: false,
        paused: false,
        gameTime: '--:--:--',
        currentTurn: 0
    },

    // UI state
    filters: {
        military: true,
        diplomatic: true,
        intelligence: true,
        media: true,
        security: true,
        economic: true,
        political: true
    },

    // Polling intervals (ms)
    POLL_INTERVALS: {
        status: 2000,      // Check sim status frequently
        events: 5000,      // Events every 5 seconds
        kpis: 10000,       // KPIs every 10 seconds
        agents: 15000,     // Agent status every 15 seconds
        map: 5000,         // Map state every 5 seconds
        pmApprovals: 3000  // Check for PM decisions frequently
    },

    // Polling timers
    _timers: {},

    // Callbacks for UI updates
    _callbacks: {
        onSimulationUpdate: null,
        onEventsUpdate: null,
        onKPIsUpdate: null,
        onAgentsUpdate: null,
        onMapUpdate: null,
        onPMApprovalRequired: null
    },

    /**
     * Initialize the state manager and start polling
     */
    async init() {
        console.log('[PlayerState] Initializing...');

        try {
            // Initial data fetch
            console.log('[PlayerState] Fetching initial data...');
            await this.refreshAll();
            console.log('[PlayerState] Initial data fetched');

            // Start polling
            console.log('[PlayerState] Starting polling...');
            this.startPolling();

            console.log('[PlayerState] Initialized');
        } catch (error) {
            console.error('[PlayerState] Init failed:', error);
            throw error;  // Re-throw so PlayApp can catch it
        }
    },

    /**
     * Register callbacks for UI updates
     */
    on(event, callback) {
        if (this._callbacks.hasOwnProperty('on' + event.charAt(0).toUpperCase() + event.slice(1))) {
            this._callbacks['on' + event.charAt(0).toUpperCase() + event.slice(1)] = callback;
        }
    },

    /**
     * Start all polling loops
     */
    startPolling() {
        // Simulation status
        this._timers.status = setInterval(() => this.pollSimulationStatus(), this.POLL_INTERVALS.status);

        // Events
        this._timers.events = setInterval(() => this.pollEvents(), this.POLL_INTERVALS.events);

        // KPIs
        this._timers.kpis = setInterval(() => this.pollKPIs(), this.POLL_INTERVALS.kpis);

        // Agents
        this._timers.agents = setInterval(() => this.pollAgents(), this.POLL_INTERVALS.agents);

        // Map
        this._timers.map = setInterval(() => this.pollMap(), this.POLL_INTERVALS.map);

        // PM Approvals
        this._timers.pmApprovals = setInterval(() => this.pollPMApprovals(), this.POLL_INTERVALS.pmApprovals);
    },

    /**
     * Stop all polling loops
     */
    stopPolling() {
        for (const timer of Object.values(this._timers)) {
            clearInterval(timer);
        }
        this._timers = {};
    },

    /**
     * Refresh all data
     */
    async refreshAll() {
        // Run all polls in parallel, catching individual failures
        const results = await Promise.allSettled([
            this.pollSimulationStatus().catch(e => console.error('[PlayerState] pollSimulationStatus failed:', e)),
            this.pollEvents().catch(e => console.error('[PlayerState] pollEvents failed:', e)),
            this.pollKPIs().catch(e => console.error('[PlayerState] pollKPIs failed:', e)),
            this.pollAgents().catch(e => console.error('[PlayerState] pollAgents failed:', e)),
            this.pollMap().catch(e => console.error('[PlayerState] pollMap failed:', e)),
            this.pollPMApprovals().catch(e => console.error('[PlayerState] pollPMApprovals failed:', e))
        ]);

        // Log any failures but don't throw
        const failures = results.filter(r => r.status === 'rejected');
        if (failures.length > 0) {
            console.warn('[PlayerState] Some polls failed:', failures);
        }
    },

    /**
     * Poll simulation status
     */
    async pollSimulationStatus() {
        const status = await ApiAdapter.getSimulationStatus();
        console.log('[PlayerState] Simulation status:', status);
        this.simulation = {
            running: status.running,
            paused: status.paused,
            gameTime: status.game_time,
            currentTurn: status.current_turn
        };

        if (this._callbacks.onSimulationUpdate) {
            this._callbacks.onSimulationUpdate(this.simulation);
        }
    },

    /**
     * Poll events and filter for player visibility
     */
    async pollEvents() {
        const allEvents = await ApiAdapter.getEvents();
        console.log('[PlayerState] Events received:', allEvents.length, 'events');

        // Filter for player visibility
        this.events = allEvents.filter(event => this.isEventVisibleToPlayer(event));
        console.log('[PlayerState] Visible events:', this.events.length);

        // Apply type filters
        const filteredEvents = this.events.filter(event => this.filters[event.type] !== false);

        if (this._callbacks.onEventsUpdate) {
            this._callbacks.onEventsUpdate(filteredEvents);
        }
    },

    /**
     * Determine if an event is visible to the player (Israel's perspective)
     */
    isEventVisibleToPlayer(event) {
        // Hide events from System agents (internal simulation events)
        if (this.isSystemAgent(event.agentId)) return false;

        // Public events are always visible
        if (event.isPublic) return true;

        // Private events only visible if from friendly agent
        const agent = this.agents[event.agentId];
        if (!agent) {
            // Unknown agent - assume not visible
            return false;
        }

        // Friendly agents' private events are visible (intel reports, etc.)
        return agent.raw && agent.raw.is_enemy !== true;
    },

    /**
     * Check if an agent is a System agent (not player-facing)
     */
    isSystemAgent(agentId) {
        // Known System agent IDs
        const systemAgents = ['System', 'GameMaster', 'Narrator', 'system', 'gamemaster', 'narrator'];
        if (systemAgents.includes(agentId)) return true;

        // Check if we have agent data and it's marked as System
        if (this._allAgents && this._allAgents[agentId]) {
            const entityType = (this._allAgents[agentId].entity_type || '').toLowerCase();
            return entityType === 'system';
        }

        return false;
    },

    /**
     * Poll KPIs
     */
    async pollKPIs() {
        this.kpis = await ApiAdapter.getKPIs();
        console.log('[PlayerState] KPIs loaded:', Object.keys(this.kpis).length, 'categories');

        if (this._callbacks.onKPIsUpdate) {
            this._callbacks.onKPIsUpdate(this.kpis);
        }
    },

    /**
     * Poll agents
     */
    async pollAgents() {
        // Fetch all agents raw data for system agent detection
        try {
            const response = await fetch('/agents');
            if (response.ok) {
                const data = await response.json();
                let allAgents = data.agents || data || [];
                if (!Array.isArray(allAgents)) {
                    allAgents = Object.values(allAgents);
                }
                // Store all agents for entity_type checking
                this._allAgents = {};
                for (const agent of allAgents) {
                    this._allAgents[agent.agent_id || agent.id] = agent;
                }
            }
        } catch (e) {
            console.warn('[PlayerState] Could not fetch all agents for system check');
        }

        this.agentCategories = await ApiAdapter.getAgents();

        // Build agent lookup map (only friendly, non-system agents)
        this.agents = {};
        let agentCount = 0;
        for (const category of Object.values(this.agentCategories)) {
            for (const agent of category.agents) {
                this.agents[agent.id] = agent;
                agentCount++;
            }
        }
        console.log('[PlayerState] Agents loaded:', agentCount, 'friendly agents');

        if (this._callbacks.onAgentsUpdate) {
            this._callbacks.onAgentsUpdate(this.agentCategories);
        }
    },

    /**
     * Poll map state
     */
    async pollMap() {
        this.mapState = await ApiAdapter.getMapState();

        if (this._callbacks.onMapUpdate) {
            this._callbacks.onMapUpdate(this.mapState);
        }
    },

    /**
     * Poll PM approvals - triggers auto-pause if any pending
     */
    async pollPMApprovals() {
        const approvals = await ApiAdapter.getPMApprovals();

        // Check if new approvals arrived
        const hadApprovals = this.pmApprovals.length > 0;
        this.pmApprovals = approvals;

        // If there are pending approvals, notify UI
        if (approvals.length > 0 && this._callbacks.onPMApprovalRequired) {
            this._callbacks.onPMApprovalRequired(approvals[0]); // Show first pending
        }
    },

    /**
     * Submit PM decision
     */
    async submitPMDecision(approvalId, decision) {
        const success = await ApiAdapter.submitPMDecision(approvalId, decision);
        if (success) {
            // Remove from local list
            this.pmApprovals = this.pmApprovals.filter(a => a.id !== approvalId);

            // Check for more pending
            if (this.pmApprovals.length > 0 && this._callbacks.onPMApprovalRequired) {
                this._callbacks.onPMApprovalRequired(this.pmApprovals[0]);
            }
        }
        return success;
    },

    /**
     * Set event type filter
     */
    setFilter(type, enabled) {
        this.filters[type] = enabled;
        // Trigger events update with new filter
        if (this._callbacks.onEventsUpdate) {
            const filteredEvents = this.events.filter(event => this.filters[event.type] !== false);
            this._callbacks.onEventsUpdate(filteredEvents);
        }
    },

    /**
     * Get agent by ID
     */
    getAgent(agentId) {
        return this.agents[agentId] || null;
    },

    /**
     * Check if entity is friendly (belongs to Israel)
     */
    isFriendlyEntity(entity) {
        return entity.owner === 'Israel' || entity.isFriendly === true;
    },

    /**
     * Get entity visibility for map (fog of war)
     */
    getEntityVisibility(entity) {
        if (this.isFriendlyEntity(entity)) {
            // Full visibility for friendly entities
            return { visible: true, uncertainty: 0 };
        } else {
            // Enemy entities have uncertainty (fog of war)
            return {
                visible: true,
                uncertainty: entity.uncertainty || 10  // Default 10km uncertainty
            };
        }
    }
};

// Export for use in other modules
window.PlayerState = PlayerState;
