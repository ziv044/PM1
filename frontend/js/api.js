/**
 * API Client for PM1 Agent Admin Panel
 */

const API_BASE = 'http://localhost:8000';

const api = {
    /**
     * Get all agents
     */
    async getAgents() {
        const response = await fetch(`${API_BASE}/agents`);
        return response.json();
    },

    /**
     * Get a single agent by ID
     */
    async getAgent(agentId) {
        const response = await fetch(`${API_BASE}/agents/${encodeURIComponent(agentId)}`);
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to get agent');
        }
        return response.json();
    },

    /**
     * Create a new agent
     */
    async createAgent(agentData) {
        const response = await fetch(`${API_BASE}/agents`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(agentData)
        });
        return response.json();
    },

    /**
     * Update an existing agent
     */
    async updateAgent(agentId, agentData) {
        const response = await fetch(`${API_BASE}/agents/${encodeURIComponent(agentId)}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(agentData)
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to update agent');
        }
        return response.json();
    },

    /**
     * Delete an agent
     */
    async deleteAgent(agentId) {
        const response = await fetch(`${API_BASE}/agents/${encodeURIComponent(agentId)}`, {
            method: 'DELETE'
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to delete agent');
        }
        return response.json();
    },

    /**
     * Get agent skills
     */
    async getSkills(agentId) {
        const response = await fetch(`${API_BASE}/agents/${encodeURIComponent(agentId)}/skills`);
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to get skills');
        }
        return response.json();
    },

    /**
     * Add skills to an agent
     */
    async addSkills(agentId, skills) {
        const response = await fetch(`${API_BASE}/agents/${encodeURIComponent(agentId)}/skills`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ skills: skills })
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to add skills');
        }
        return response.json();
    },

    /**
     * Get agent memory
     */
    async getMemory(agentId) {
        const response = await fetch(`${API_BASE}/agents/${encodeURIComponent(agentId)}/memory`);
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to get memory');
        }
        return response.json();
    },

    /**
     * Add memory to an agent
     */
    async addMemory(agentId, memoryItem) {
        const response = await fetch(`${API_BASE}/agents/${encodeURIComponent(agentId)}/memory`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ memory_item: memoryItem })
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to add memory');
        }
        return response.json();
    },

    /**
     * Get conversation history
     */
    async getConversation(agentId) {
        const response = await fetch(`${API_BASE}/agents/${encodeURIComponent(agentId)}/conversation`);
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to get conversation');
        }
        return response.json();
    },

    /**
     * Send a chat message to an agent
     */
    async sendMessage(agentId, message, maxTokens = 1024, temperature = 1.0) {
        const response = await fetch(`${API_BASE}/agents/${encodeURIComponent(agentId)}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: message,
                max_tokens: maxTokens,
                temperature: temperature,
                stream: false
            })
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to send message');
        }
        return response.json();
    },

    /**
     * Get application logs
     */
    async getLogs() {
        const response = await fetch(`${API_BASE}/logs`);
        return response.json();
    },

    // Simulation API methods

    /**
     * Start the simulation
     */
    async startSimulation(clockSpeed = 2.0) {
        const response = await fetch(`${API_BASE}/simulation/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ clock_speed: clockSpeed })
        });
        return response.json();
    },

    /**
     * Stop the simulation
     */
    async stopSimulation() {
        const response = await fetch(`${API_BASE}/simulation/stop`, {
            method: 'POST'
        });
        return response.json();
    },

    /**
     * Get simulation status
     */
    async getSimulationStatus() {
        const response = await fetch(`${API_BASE}/simulation/status`);
        return response.json();
    },

    /**
     * Get simulation events
     */
    async getSimulationEvents(since = null, agentId = null, limit = 100) {
        let url = `${API_BASE}/simulation/events?limit=${limit}`;
        if (since) url += `&since=${encodeURIComponent(since)}`;
        if (agentId) url += `&agent_id=${encodeURIComponent(agentId)}`;
        const response = await fetch(url);
        return response.json();
    },

    /**
     * Update clock speed
     */
    async setClockSpeed(speed) {
        const response = await fetch(`${API_BASE}/simulation/clock-speed`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ clock_speed: speed })
        });
        return response.json();
    },

    /**
     * Set game clock time
     */
    async setGameTime(gameTime) {
        const response = await fetch(`${API_BASE}/simulation/game-time`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ game_time: gameTime })
        });
        return response.json();
    },

    /**
     * Save simulation state
     */
    async saveSimulationState() {
        const response = await fetch(`${API_BASE}/simulation/save`, {
            method: 'POST'
        });
        return response.json();
    },

    // Debug Console API methods

    /**
     * Get activity log for debug console
     */
    async getActivityLog(agentId = null, activityType = null, limit = 100) {
        let url = `${API_BASE}/debug/activity?limit=${limit}`;
        if (agentId) url += `&agent_id=${encodeURIComponent(agentId)}`;
        if (activityType) url += `&activity_type=${encodeURIComponent(activityType)}`;
        const response = await fetch(url);
        return response.json();
    },

    /**
     * Get activity statistics
     */
    async getActivityStats() {
        const response = await fetch(`${API_BASE}/debug/stats`);
        return response.json();
    },

    /**
     * Clear activity log
     */
    async clearActivityLog() {
        const response = await fetch(`${API_BASE}/debug/activity`, {
            method: 'DELETE'
        });
        return response.json();
    },

    /**
     * Clear agent conversation history
     */
    async clearConversation(agentId) {
        const response = await fetch(`${API_BASE}/agents/${encodeURIComponent(agentId)}/conversation`, {
            method: 'DELETE'
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to clear conversation');
        }
        return response.json();
    },

    /**
     * Toggle an agent's enabled status
     */
    async toggleAgentEnabled(agentId) {
        const response = await fetch(`${API_BASE}/agents/${encodeURIComponent(agentId)}/toggle-enabled`, {
            method: 'POST'
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to toggle agent enabled status');
        }
        return response.json();
    },

    /**
     * Get the full action prompt for an agent
     */
    async getActionPrompt(agentId) {
        const response = await fetch(`${API_BASE}/agents/${encodeURIComponent(agentId)}/action-prompt`);
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to get action prompt');
        }
        return response.json();
    },

    /**
     * Enable or disable all agents
     */
    async setAllAgentsEnabled(enabled) {
        const response = await fetch(`${API_BASE}/agents/bulk-enabled`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: enabled })
        });
        return response.json();
    },

    // PM Approvals API methods

    /**
     * Get pending PM approval requests
     */
    async getPMApprovals() {
        const response = await fetch(`${API_BASE}/simulation/pm-approvals`);
        return response.json();
    },

    /**
     * Process PM decision on an approval request
     */
    async processPMDecision(approvalId, decision, notes = null, modifiedSummary = null, dueGameTime = null) {
        const response = await fetch(`${API_BASE}/simulation/pm-approve/${encodeURIComponent(approvalId)}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                decision: decision,
                notes: notes,
                modified_summary: modifiedSummary,
                due_game_time: dueGameTime
            })
        });
        return response.json();
    },

    /**
     * Get pending scheduled events
     */
    async getScheduledEvents() {
        const response = await fetch(`${API_BASE}/simulation/scheduled-events`);
        return response.json();
    },

    /**
     * Cancel a scheduled event
     */
    async cancelScheduledEvent(scheduleId) {
        const response = await fetch(`${API_BASE}/simulation/scheduled-events/${encodeURIComponent(scheduleId)}`, {
            method: 'DELETE'
        });
        return response.json();
    },

    // Map State API methods

    /**
     * Get complete map state
     */
    async getMapState() {
        const response = await fetch(`${API_BASE}/map/state`);
        return response.json();
    },

    /**
     * Get static locations
     */
    async getMapLocations(ownerEntity = null, locationType = null) {
        let url = `${API_BASE}/map/locations`;
        const params = [];
        if (ownerEntity) params.push(`owner_entity=${encodeURIComponent(ownerEntity)}`);
        if (locationType) params.push(`location_type=${encodeURIComponent(locationType)}`);
        if (params.length) url += '?' + params.join('&');
        const response = await fetch(url);
        return response.json();
    },

    /**
     * Get tracked entities
     */
    async getMapEntities(ownerEntity = null, category = null, zone = null) {
        let url = `${API_BASE}/map/entities`;
        const params = [];
        if (ownerEntity) params.push(`owner_entity=${encodeURIComponent(ownerEntity)}`);
        if (category) params.push(`category=${encodeURIComponent(category)}`);
        if (zone) params.push(`zone=${encodeURIComponent(zone)}`);
        if (params.length) url += '?' + params.join('&');
        const response = await fetch(url);
        return response.json();
    },

    /**
     * Get geo events for animations
     */
    async getMapEvents(activeOnly = true) {
        const response = await fetch(`${API_BASE}/map/events?active_only=${activeOnly}`);
        return response.json();
    },

    /**
     * Get valid zones
     */
    async getMapZones() {
        const response = await fetch(`${API_BASE}/map/zones`);
        return response.json();
    },

    /**
     * Move an entity to a destination zone
     */
    async moveEntity(entityId, destinationZone, travelTimeMinutes = 30) {
        const response = await fetch(`${API_BASE}/map/entities/${encodeURIComponent(entityId)}/move`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                destination_zone: destinationZone,
                travel_time_minutes: travelTimeMinutes
            })
        });
        return response.json();
    },

    /**
     * Teleport an entity to a zone (instant)
     */
    async teleportEntity(entityId, destinationZone) {
        const response = await fetch(`${API_BASE}/map/entities/${encodeURIComponent(entityId)}/teleport`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ destination_zone: destinationZone })
        });
        return response.json();
    },

    // KPI API methods

    /**
     * Get all entity KPIs
     */
    async getKPIs() {
        const response = await fetch(`${API_BASE}/kpis`);
        return response.json();
    },

    /**
     * Get KPIs for a specific entity
     */
    async getEntityKPIs(entityId) {
        const response = await fetch(`${API_BASE}/kpis/${encodeURIComponent(entityId)}`);
        return response.json();
    },

    /**
     * Manually trigger event resolution (works even when simulation is stopped)
     */
    async resolveNow() {
        const response = await fetch(`${API_BASE}/simulation/resolve-now`, {
            method: 'POST'
        });
        return response.json();
    },

    // =========================================================================
    // MEETINGS API
    // =========================================================================

    /**
     * Get all meetings and meeting system state
     */
    async getMeetings() {
        const response = await fetch(`${API_BASE}/meetings`);
        return response.json();
    },

    /**
     * Get meeting types and configurations
     */
    async getMeetingTypes() {
        const response = await fetch(`${API_BASE}/meetings/types`);
        return response.json();
    },

    /**
     * Get a specific meeting
     */
    async getMeeting(meetingId) {
        const response = await fetch(`${API_BASE}/meetings/${encodeURIComponent(meetingId)}`);
        return response.json();
    },

    /**
     * Create/schedule a new meeting
     */
    async createMeeting(meetingData) {
        const response = await fetch(`${API_BASE}/meetings`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(meetingData)
        });
        return response.json();
    },

    /**
     * Get pending meeting requests from AI/system
     */
    async getMeetingRequests() {
        const response = await fetch(`${API_BASE}/meetings/requests`);
        return response.json();
    },

    /**
     * Approve a meeting request
     */
    async approveMeetingRequest(requestId) {
        const response = await fetch(`${API_BASE}/meetings/requests/${encodeURIComponent(requestId)}/approve`, {
            method: 'POST'
        });
        return response.json();
    },

    /**
     * Reject a meeting request
     */
    async rejectMeetingRequest(requestId) {
        const response = await fetch(`${API_BASE}/meetings/requests/${encodeURIComponent(requestId)}/reject`, {
            method: 'POST'
        });
        return response.json();
    },

    /**
     * Start a scheduled meeting (pauses simulation)
     */
    async startMeeting(meetingId) {
        const response = await fetch(`${API_BASE}/meetings/${encodeURIComponent(meetingId)}/start`, {
            method: 'POST'
        });
        return response.json();
    },

    /**
     * PM interjects with a statement during meeting
     */
    async meetingInterject(meetingId, content, actionType = 'statement', addressedTo = [], emotionalTone = 'calm') {
        const response = await fetch(`${API_BASE}/meetings/${encodeURIComponent(meetingId)}/turn`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                content: content,
                action_type: actionType,
                addressed_to: addressedTo,
                emotional_tone: emotionalTone
            })
        });
        return response.json();
    },

    /**
     * Advance to next round (execute AI turns)
     */
    async advanceMeetingRound(meetingId) {
        const response = await fetch(`${API_BASE}/meetings/${encodeURIComponent(meetingId)}/advance`, {
            method: 'POST'
        });
        return response.json();
    },

    /**
     * Conclude meeting and generate outcomes
     */
    async concludeMeeting(meetingId) {
        const response = await fetch(`${API_BASE}/meetings/${encodeURIComponent(meetingId)}/conclude`, {
            method: 'POST'
        });
        return response.json();
    },

    /**
     * Abort meeting without outcomes
     */
    async abortMeeting(meetingId) {
        const response = await fetch(`${API_BASE}/meetings/${encodeURIComponent(meetingId)}/abort`, {
            method: 'POST'
        });
        return response.json();
    },

    // =========================================================================
    // GAME MANAGEMENT
    // =========================================================================

    /**
     * List all saved games
     */
    async listGames() {
        const response = await fetch(`${API_BASE}/games`);
        return response.json();
    },

    /**
     * Get current active game
     */
    async getCurrentGame() {
        const response = await fetch(`${API_BASE}/games/current`);
        return response.json();
    },

    /**
     * Get available templates
     */
    async getTemplates() {
        const response = await fetch(`${API_BASE}/games/templates`);
        return response.json();
    },

    /**
     * Create a new game from template
     */
    async createGame(gameId, displayName, template = 'october7', description = '') {
        const response = await fetch(`${API_BASE}/games`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                game_id: gameId,
                display_name: displayName,
                template: template,
                description: description
            })
        });
        return response.json();
    },

    /**
     * Load/switch to a different game
     */
    async loadGame(gameId) {
        const response = await fetch(`${API_BASE}/games/${encodeURIComponent(gameId)}/load`, {
            method: 'POST'
        });
        return response.json();
    },

    /**
     * Delete a saved game
     */
    async deleteGame(gameId) {
        const response = await fetch(`${API_BASE}/games/${encodeURIComponent(gameId)}`, {
            method: 'DELETE'
        });
        return response.json();
    },

    /**
     * Run data migration to multi-game system
     */
    async migrateData() {
        const response = await fetch(`${API_BASE}/admin/migrate`, {
            method: 'POST'
        });
        return response.json();
    }
};
