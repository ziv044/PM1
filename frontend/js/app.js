/**
 * Main Application Logic for PM1 Agent Admin Panel
 */

// Application state
const state = {
    agents: {},
    selectedAgentId: null,
    currentTab: 'details',
    isEditing: false,
    simulationPollingInterval: null,
    simulationStatus: null
};

/**
 * Initialize the application
 */
async function init() {
    // Load agents
    await loadAgents();

    // Set up event listeners
    setupEventListeners();

    // Show empty state initially
    components.showEmptyState(true);
}

/**
 * Load all agents from the API
 */
async function loadAgents() {
    try {
        const result = await api.getAgents();
        state.agents = result.agents || {};
        components.renderAgentList(state.agents, state.selectedAgentId);
    } catch (error) {
        console.error('Failed to load agents:', error);
        components.showToast('Failed to load agents', 'error');
    }
}

/**
 * Select an agent
 */
async function selectAgent(agentId) {
    state.selectedAgentId = agentId;
    state.currentTab = 'details';

    // Update UI
    components.renderAgentList(state.agents, agentId);
    components.setAgentTitle(`Agent: ${agentId}`);
    components.showEmptyState(false);
    components.showTab('details');

    // Load agent details
    await loadAgentData(agentId);
}

/**
 * Load agent data for all tabs
 */
async function loadAgentData(agentId) {
    try {
        const agent = state.agents[agentId];
        if (agent) {
            components.renderAgentDetails(agent, agentId);
            components.renderSkillsList(agent.skills);
            components.renderMemoryList(agent.memory);
            components.renderConversation(agent.conversation);
        }
    } catch (error) {
        console.error('Failed to load agent data:', error);
        components.showToast('Failed to load agent data', 'error');
    }
}

/**
 * Set up all event listeners
 */
function setupEventListeners() {
    // Agent list click
    document.getElementById('agentList').addEventListener('click', (e) => {
        const card = e.target.closest('.agent-card');
        if (card) {
            selectAgent(card.dataset.agentId);
        }
    });

    // Tab clicks
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            state.currentTab = tab;
            components.showTab(tab);

            // Load logs on demand
            if (tab === 'logs') {
                loadLogs();
            }
            // Load simulation status on demand
            if (tab === 'simulation') {
                loadSimulationStatus();
                loadSimulationEvents();
            }
        });
    });

    // Add agent button
    document.getElementById('addAgentBtn').addEventListener('click', () => {
        state.isEditing = false;
        document.getElementById('modalTitle').textContent = 'Add Agent';
        document.getElementById('formAgentId').value = '';
        document.getElementById('formAgentId').disabled = false;
        document.getElementById('formModel').value = 'claude-sonnet-4-20250514';
        document.getElementById('formSystemPrompt').value = '';
        // Reset simulation fields
        document.getElementById('formEntityType').value = 'System';
        document.getElementById('formEventFrequency').value = '60';
        document.getElementById('formIsEnemy').checked = false;
        document.getElementById('formIsWest').checked = false;
        document.getElementById('formIsEvilAxis').checked = false;
        document.getElementById('formAgenda').value = '';
        document.getElementById('formPrimaryObjectives').value = '';
        document.getElementById('formHardRules').value = '';
        components.showModal('agentModal');
    });

    // Edit agent button
    document.getElementById('editAgentBtn').addEventListener('click', () => {
        if (!state.selectedAgentId) return;

        state.isEditing = true;
        const agent = state.agents[state.selectedAgentId];

        document.getElementById('modalTitle').textContent = 'Edit Agent';
        document.getElementById('formAgentId').value = state.selectedAgentId;
        document.getElementById('formAgentId').disabled = true;
        document.getElementById('formModel').value = agent.model;
        document.getElementById('formSystemPrompt').value = agent.system_prompt || '';
        // Populate simulation fields
        document.getElementById('formEntityType').value = agent.entity_type || 'System';
        document.getElementById('formEventFrequency').value = agent.event_frequency || 60;
        document.getElementById('formIsEnemy').checked = agent.is_enemy || false;
        document.getElementById('formIsWest').checked = agent.is_west || false;
        document.getElementById('formIsEvilAxis').checked = agent.is_evil_axis || false;
        document.getElementById('formAgenda').value = agent.agenda || '';
        document.getElementById('formPrimaryObjectives').value = agent.primary_objectives || '';
        document.getElementById('formHardRules').value = agent.hard_rules || '';
        components.showModal('agentModal');
    });

    // Delete agent button
    document.getElementById('deleteAgentBtn').addEventListener('click', () => {
        if (state.selectedAgentId) {
            components.showModal('deleteModal');
        }
    });

    // Confirm delete
    document.getElementById('confirmDeleteBtn').addEventListener('click', async () => {
        if (!state.selectedAgentId) return;

        try {
            await api.deleteAgent(state.selectedAgentId);
            components.hideModal('deleteModal');
            components.showToast('Agent deleted successfully', 'success');

            state.selectedAgentId = null;
            components.showEmptyState(true);
            components.setAgentTitle('Select an Agent');
            await loadAgents();
        } catch (error) {
            console.error('Failed to delete agent:', error);
            components.showToast('Failed to delete agent', 'error');
        }
    });

    // Cancel delete
    document.getElementById('cancelDeleteBtn').addEventListener('click', () => {
        components.hideModal('deleteModal');
    });

    // Agent form submit
    document.getElementById('agentForm').addEventListener('submit', async (e) => {
        e.preventDefault();

        const agentId = document.getElementById('formAgentId').value.trim();
        const agentData = {
            agent_id: agentId,
            model: document.getElementById('formModel').value,
            system_prompt: document.getElementById('formSystemPrompt').value,
            entity_type: document.getElementById('formEntityType').value,
            event_frequency: parseInt(document.getElementById('formEventFrequency').value) || 60,
            is_enemy: document.getElementById('formIsEnemy').checked,
            is_west: document.getElementById('formIsWest').checked,
            is_evil_axis: document.getElementById('formIsEvilAxis').checked,
            agenda: document.getElementById('formAgenda').value,
            primary_objectives: document.getElementById('formPrimaryObjectives').value,
            hard_rules: document.getElementById('formHardRules').value
        };

        try {
            if (state.isEditing) {
                await api.updateAgent(agentId, agentData);
                components.showToast('Agent updated successfully', 'success');
            } else {
                await api.createAgent(agentData);
                components.showToast('Agent created successfully', 'success');
            }

            components.hideModal('agentModal');
            await loadAgents();

            // Select the new/updated agent
            selectAgent(agentId);
        } catch (error) {
            console.error('Failed to save agent:', error);
            components.showToast('Failed to save agent', 'error');
        }
    });

    // Cancel agent modal
    document.getElementById('cancelModalBtn').addEventListener('click', () => {
        components.hideModal('agentModal');
    });

    // Add skill button
    document.getElementById('addSkillBtn').addEventListener('click', () => {
        document.getElementById('formSkill').value = '';
        components.showModal('skillModal');
    });

    // Skill form submit
    document.getElementById('skillForm').addEventListener('submit', async (e) => {
        e.preventDefault();

        const skill = document.getElementById('formSkill').value.trim();
        if (!skill || !state.selectedAgentId) return;

        try {
            await api.addSkills(state.selectedAgentId, [skill]);
            components.hideModal('skillModal');
            components.showToast('Skill added successfully', 'success');

            // Refresh agent data
            await loadAgents();
            await loadAgentData(state.selectedAgentId);
        } catch (error) {
            console.error('Failed to add skill:', error);
            components.showToast('Failed to add skill', 'error');
        }
    });

    // Cancel skill modal
    document.getElementById('cancelSkillBtn').addEventListener('click', () => {
        components.hideModal('skillModal');
    });

    // Add memory button
    document.getElementById('addMemoryBtn').addEventListener('click', () => {
        document.getElementById('formMemory').value = '';
        components.showModal('memoryModal');
    });

    // Memory form submit
    document.getElementById('memoryForm').addEventListener('submit', async (e) => {
        e.preventDefault();

        const memoryItem = document.getElementById('formMemory').value.trim();
        if (!memoryItem || !state.selectedAgentId) return;

        try {
            await api.addMemory(state.selectedAgentId, memoryItem);
            components.hideModal('memoryModal');
            components.showToast('Memory added successfully', 'success');

            // Refresh agent data
            await loadAgents();
            await loadAgentData(state.selectedAgentId);
        } catch (error) {
            console.error('Failed to add memory:', error);
            components.showToast('Failed to add memory', 'error');
        }
    });

    // Cancel memory modal
    document.getElementById('cancelMemoryBtn').addEventListener('click', () => {
        components.hideModal('memoryModal');
    });

    // Chat send button
    document.getElementById('sendChatBtn').addEventListener('click', sendChatMessage);

    // Chat input enter key
    document.getElementById('chatInput').addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendChatMessage();
        }
    });

    // Refresh logs button
    document.getElementById('refreshLogsBtn').addEventListener('click', loadLogs);

    // Close modals when clicking outside
    document.querySelectorAll('#agentModal, #skillModal, #memoryModal, #deleteModal').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                components.hideModal(modal.id);
            }
        });
    });

    // Simulation controls
    document.getElementById('startSimBtn').addEventListener('click', startSimulation);
    document.getElementById('stopSimBtn').addEventListener('click', stopSimulation);
    document.getElementById('updateClockSpeedBtn').addEventListener('click', updateClockSpeed);
    document.getElementById('refreshEventsBtn').addEventListener('click', loadSimulationEvents);
}

/**
 * Send a chat message
 */
async function sendChatMessage() {
    const input = document.getElementById('chatInput');
    const message = input.value.trim();

    if (!message || !state.selectedAgentId) return;

    // Clear input
    input.value = '';

    // Add user message to UI
    components.addChatMessage('user', message);

    // Disable send button
    const sendBtn = document.getElementById('sendChatBtn');
    components.setButtonLoading(sendBtn, true);

    try {
        const result = await api.sendMessage(state.selectedAgentId, message);

        if (result.status === 'success') {
            components.addChatMessage('assistant', result.response);

            // Update local state
            if (!state.agents[state.selectedAgentId].conversation) {
                state.agents[state.selectedAgentId].conversation = [];
            }
            state.agents[state.selectedAgentId].conversation.push(
                { role: 'user', content: message },
                { role: 'assistant', content: result.response }
            );
        }
    } catch (error) {
        console.error('Failed to send message:', error);
        components.showToast('Failed to send message', 'error');
    } finally {
        components.setButtonLoading(sendBtn, false);
    }
}

/**
 * Load application logs
 */
async function loadLogs() {
    try {
        const result = await api.getLogs();
        components.renderLogs(result.logs || []);
    } catch (error) {
        console.error('Failed to load logs:', error);
        components.showToast('Failed to load logs', 'error');
    }
}

// ========== Simulation Functions ==========

/**
 * Load simulation status
 */
async function loadSimulationStatus() {
    try {
        const result = await api.getSimulationStatus();
        state.simulationStatus = result;
        renderSimulationStatus(result);
    } catch (error) {
        console.error('Failed to get simulation status:', error);
    }
}

/**
 * Load simulation events
 */
async function loadSimulationEvents() {
    try {
        const result = await api.getSimulationEvents();
        renderSimulationEvents(result.events || []);
    } catch (error) {
        console.error('Failed to load events:', error);
    }
}

/**
 * Start the simulation
 */
async function startSimulation() {
    try {
        const clockSpeed = parseFloat(document.getElementById('clockSpeedInput').value) || 2.0;
        const result = await api.startSimulation(clockSpeed);

        if (result.status === 'success') {
            components.showToast('Simulation started', 'success');
            startSimulationPolling();
            await loadSimulationStatus();
        } else {
            components.showToast(result.message || 'Failed to start simulation', 'error');
        }
    } catch (error) {
        console.error('Failed to start simulation:', error);
        components.showToast('Failed to start simulation', 'error');
    }
}

/**
 * Stop the simulation
 */
async function stopSimulation() {
    try {
        const result = await api.stopSimulation();

        if (result.status === 'success') {
            components.showToast('Simulation stopped', 'success');
            stopSimulationPolling();
            await loadSimulationStatus();
        } else {
            components.showToast(result.message || 'Failed to stop simulation', 'error');
        }
    } catch (error) {
        console.error('Failed to stop simulation:', error);
        components.showToast('Failed to stop simulation', 'error');
    }
}

/**
 * Update clock speed
 */
async function updateClockSpeed() {
    try {
        const speed = parseFloat(document.getElementById('clockSpeedInput').value);
        if (speed <= 0) {
            components.showToast('Speed must be positive', 'error');
            return;
        }

        const result = await api.setClockSpeed(speed);
        if (result.status === 'success') {
            components.showToast(`Clock speed set to ${speed} sec/min`, 'success');
        }
    } catch (error) {
        console.error('Failed to update clock speed:', error);
        components.showToast('Failed to update clock speed', 'error');
    }
}

/**
 * Start polling for simulation updates
 */
function startSimulationPolling() {
    // Poll every 2 seconds for status updates
    state.simulationPollingInterval = setInterval(async () => {
        await loadSimulationStatus();
        await loadSimulationEvents();
    }, 2000);
}

/**
 * Stop polling for simulation updates
 */
function stopSimulationPolling() {
    if (state.simulationPollingInterval) {
        clearInterval(state.simulationPollingInterval);
        state.simulationPollingInterval = null;
    }
}

/**
 * Render simulation status in the UI
 */
function renderSimulationStatus(status) {
    const statusEl = document.getElementById('simStatus');
    const clockEl = document.getElementById('simClock');
    const entityCountEl = document.getElementById('simEntityCount');
    const startBtn = document.getElementById('startSimBtn');
    const stopBtn = document.getElementById('stopSimBtn');
    const clockSpeedInput = document.getElementById('clockSpeedInput');

    if (status.is_running) {
        statusEl.textContent = 'Running';
        statusEl.className = 'font-medium text-green-600';
        startBtn.disabled = true;
        stopBtn.disabled = false;
    } else {
        statusEl.textContent = 'Stopped';
        statusEl.className = 'font-medium text-red-600';
        startBtn.disabled = false;
        stopBtn.disabled = true;
    }

    // Format game time
    if (status.game_time) {
        const dt = new Date(status.game_time);
        clockEl.textContent = dt.toLocaleString('en-GB', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    } else {
        clockEl.textContent = '--';
    }

    entityCountEl.textContent = status.entity_count || 0;
    clockSpeedInput.value = status.clock_speed || 2.0;
}

/**
 * Render simulation events in the event log
 */
function renderSimulationEvents(events) {
    const eventLog = document.getElementById('eventLog');
    const eventCount = document.getElementById('eventCount');

    eventCount.textContent = `${events.length} events`;

    if (events.length === 0) {
        eventLog.innerHTML = '<p class="text-gray-500">No events yet. Start the simulation to generate events.</p>';
        return;
    }

    // Reverse to show newest first
    const reversedEvents = [...events].reverse();

    eventLog.innerHTML = reversedEvents.map(event => {
        const visibility = event.is_public ?
            '<span class="text-green-400">[PUBLIC]</span>' :
            '<span class="text-yellow-400">[PRIVATE]</span>';
        const dt = new Date(event.timestamp);
        const timeStr = dt.toLocaleString('en-GB', {
            day: '2-digit',
            month: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
        const typeColor = getActionTypeColor(event.action_type);

        return `<div class="mb-2 pb-2 border-b border-gray-700">
            <span class="text-gray-500">[${timeStr}]</span>
            <span class="${typeColor}">[${event.action_type.toUpperCase()}]</span>
            ${visibility}
            <span class="text-blue-400">${event.agent_id}:</span>
            <span class="text-white">${event.summary}</span>
        </div>`;
    }).join('');
}

/**
 * Get color class for action type
 */
function getActionTypeColor(actionType) {
    const colors = {
        'diplomatic': 'text-blue-300',
        'military': 'text-red-300',
        'economic': 'text-yellow-300',
        'intelligence': 'text-purple-300',
        'internal': 'text-gray-300',
        'none': 'text-gray-500'
    };
    return colors[actionType] || 'text-gray-300';
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', init);
