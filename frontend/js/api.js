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
     * Enable or disable all agents
     */
    async setAllAgentsEnabled(enabled) {
        const response = await fetch(`${API_BASE}/agents/bulk-enabled`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: enabled })
        });
        return response.json();
    }
};
