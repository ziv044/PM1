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
    async createAgent(agentId, model, systemPrompt) {
        const response = await fetch(`${API_BASE}/agents`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                agent_id: agentId,
                model: model,
                system_prompt: systemPrompt
            })
        });
        return response.json();
    },

    /**
     * Update an existing agent
     */
    async updateAgent(agentId, model, systemPrompt) {
        const response = await fetch(`${API_BASE}/agents/${encodeURIComponent(agentId)}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                model: model,
                system_prompt: systemPrompt
            })
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
    }
};
