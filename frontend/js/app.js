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
    simulationStatus: null,
    // Debug console state
    debugSubtab: 'gameflow',
    testAgentId: null,
    debugPollingInterval: null
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
 * Load agent data for all tabs (fetches fresh data from API)
 */
async function loadAgentData(agentId) {
    try {
        // Fetch fresh agent data from API to get current memory/skills/conversation
        const result = await api.getAgent(agentId);
        if (result.status === 'success' && result.agent) {
            const agent = result.agent;
            // Update cache with fresh data
            state.agents[agentId] = agent;
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
 * Toggle agent enabled status
 */
async function toggleAgentEnabled(agentId) {
    try {
        const result = await api.toggleAgentEnabled(agentId);
        if (result.status === 'success') {
            const status = result.is_enabled ? 'enabled' : 'disabled';
            components.showToast(`Agent ${agentId} ${status}`, 'success');
            await loadAgents();
        }
    } catch (error) {
        console.error('Failed to toggle agent:', error);
        components.showToast('Failed to toggle agent status', 'error');
    }
}

/**
 * Set up all event listeners
 */
function setupEventListeners() {
    // Agent list click
    document.getElementById('agentList').addEventListener('click', (e) => {
        // Check if toggle button was clicked
        const toggleBtn = e.target.closest('.toggle-enabled-btn');
        if (toggleBtn) {
            e.stopPropagation();
            toggleAgentEnabled(toggleBtn.dataset.agentId);
            return;
        }

        const card = e.target.closest('.agent-card');
        if (card) {
            selectAgent(card.dataset.agentId);
        }
    });

    // Enable All button
    document.getElementById('enableAllBtn').addEventListener('click', async () => {
        try {
            await api.setAllAgentsEnabled(true);
            components.showToast('All agents enabled', 'success');
            await loadAgents();
        } catch (error) {
            console.error('Failed to enable all agents:', error);
            components.showToast('Failed to enable all agents', 'error');
        }
    });

    // Disable All button
    document.getElementById('disableAllBtn').addEventListener('click', async () => {
        try {
            await api.setAllAgentsEnabled(false);
            components.showToast('All agents disabled', 'success');
            await loadAgents();
        } catch (error) {
            console.error('Failed to disable all agents:', error);
            components.showToast('Failed to disable all agents', 'error');
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
                loadSimulationStatus().then(() => {
                    // Start polling if simulation is already running
                    if (state.simulationStatus && state.simulationStatus.is_running) {
                        startSimulationPolling();
                    }
                });
                loadSimulationEvents();
            } else {
                // Stop polling when leaving simulation tab
                stopSimulationPolling();
            }
            // Load debug console on demand
            if (tab === 'debug') {
                populateDebugAgentSelects();
                loadGameFlow();
                loadDebugStats();
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
        document.getElementById('formAgentCategory').value = '';
        document.getElementById('formIsEnabled').checked = true;
        document.getElementById('formIsEnemy').checked = false;
        document.getElementById('formIsWest').checked = false;
        document.getElementById('formIsEvilAxis').checked = false;
        document.getElementById('formIsReportingGovernment').checked = false;
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
        document.getElementById('formAgentCategory').value = agent.agent_category || '';
        document.getElementById('formIsEnabled').checked = agent.is_enabled !== false;
        document.getElementById('formIsEnemy').checked = agent.is_enemy || false;
        document.getElementById('formIsWest').checked = agent.is_west || false;
        document.getElementById('formIsEvilAxis').checked = agent.is_evil_axis || false;
        document.getElementById('formIsReportingGovernment').checked = agent.is_reporting_government || false;
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
            agent_category: document.getElementById('formAgentCategory').value,
            is_enabled: document.getElementById('formIsEnabled').checked,
            is_enemy: document.getElementById('formIsEnemy').checked,
            is_west: document.getElementById('formIsWest').checked,
            is_evil_axis: document.getElementById('formIsEvilAxis').checked,
            is_reporting_government: document.getElementById('formIsReportingGovernment').checked,
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
    document.getElementById('setGameTimeBtn').addEventListener('click', setGameTime);
    document.getElementById('saveSimStateBtn').addEventListener('click', saveSimulationState);

    // Debug Console controls
    setupDebugConsoleListeners();
}

/**
 * Set up debug console event listeners
 */
function setupDebugConsoleListeners() {
    // Debug sub-tab clicks
    document.querySelectorAll('.debug-subtab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const subtab = btn.dataset.subtab;
            state.debugSubtab = subtab;
            showDebugSubtab(subtab);
        });
    });

    // Game Flow controls
    document.getElementById('refreshGameflowBtn').addEventListener('click', loadGameFlow);
    document.getElementById('clearGameflowBtn').addEventListener('click', clearGameFlow);
    document.getElementById('gameflowAgentFilter').addEventListener('change', loadGameFlow);
    document.getElementById('gameflowTypeFilter').addEventListener('change', loadGameFlow);

    // Agents Test controls
    document.getElementById('testAgentSelect').addEventListener('change', onTestAgentChange);
    document.getElementById('injectMemoryBtn').addEventListener('click', injectTestMemory);
    document.getElementById('refreshTestMemoryBtn').addEventListener('click', loadTestAgentMemory);
    document.getElementById('clearTestConversationBtn').addEventListener('click', clearTestConversation);
    document.getElementById('sendTestChatBtn').addEventListener('click', sendTestChat);
    document.getElementById('testChatInput').addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendTestChat();
        }
    });
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
            await loadSimulationStatus();
        }
    } catch (error) {
        console.error('Failed to update clock speed:', error);
        components.showToast('Failed to update clock speed', 'error');
    }
}

/**
 * Set game time
 */
async function setGameTime() {
    try {
        const gameTimeInput = document.getElementById('gameTimeInput').value;
        if (!gameTimeInput) {
            components.showToast('Please select a date and time', 'error');
            return;
        }

        // Convert to ISO format
        const gameTime = new Date(gameTimeInput).toISOString();
        const result = await api.setGameTime(gameTime);

        if (result.status === 'success') {
            components.showToast('Game time updated', 'success');
            await loadSimulationStatus();
        } else {
            components.showToast(result.message || 'Failed to set game time', 'error');
        }
    } catch (error) {
        console.error('Failed to set game time:', error);
        components.showToast('Failed to set game time', 'error');
    }
}

/**
 * Save simulation state
 */
async function saveSimulationState() {
    try {
        const result = await api.saveSimulationState();

        if (result.status === 'success') {
            components.showToast('Simulation state saved', 'success');
        } else {
            components.showToast(result.message || 'Failed to save state', 'error');
        }
    } catch (error) {
        console.error('Failed to save simulation state:', error);
        components.showToast('Failed to save state', 'error');
    }
}

/**
 * Start polling for simulation updates
 */
function startSimulationPolling() {
    // Don't start if already polling
    if (state.simulationPollingInterval) {
        return;
    }
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
    const gameTimeInput = document.getElementById('gameTimeInput');

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
        // Update datetime-local input with current game time
        const localIso = dt.toISOString().slice(0, 16);
        gameTimeInput.value = localIso;
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

        // Show resolution status badge
        let statusBadge = '';
        if (event.resolution_status === 'pending') {
            statusBadge = '<span class="text-orange-400">[PENDING]</span>';
        } else if (event.resolution_status === 'resolved') {
            statusBadge = '<span class="text-green-300">[RESOLVED]</span>';
        } else if (event.resolution_status === 'failed') {
            statusBadge = '<span class="text-red-400">[FAILED]</span>';
        }

        // Show parent link for resolution events
        let parentLink = '';
        if (event.parent_event_id) {
            parentLink = `<span class="text-gray-500 text-xs"> (resolves: ${event.parent_event_id})</span>`;
        }

        return `<div class="mb-2 pb-2 border-b border-gray-700">
            <span class="text-gray-500">[${timeStr}]</span>
            <span class="${typeColor}">[${event.action_type.toUpperCase()}]</span>
            ${visibility}
            ${statusBadge}
            <span class="text-blue-400">${event.agent_id}:</span>
            <span class="text-white">${event.summary}</span>
            ${parentLink}
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
        'resolution': 'text-cyan-300',
        'none': 'text-gray-500'
    };
    return colors[actionType] || 'text-gray-300';
}

// ========== Debug Console Functions ==========

/**
 * Show a debug sub-tab
 */
function showDebugSubtab(subtab) {
    // Update button styles
    document.querySelectorAll('.debug-subtab-btn').forEach(btn => {
        if (btn.dataset.subtab === subtab) {
            btn.classList.add('border-blue-600', 'text-blue-600');
            btn.classList.remove('border-transparent');
        } else {
            btn.classList.remove('border-blue-600', 'text-blue-600');
            btn.classList.add('border-transparent');
        }
    });

    // Show/hide content
    document.querySelectorAll('.debug-subtab-content').forEach(content => {
        content.classList.add('hidden');
    });
    document.getElementById(`${subtab}Subtab`).classList.remove('hidden');
}

/**
 * Populate agent select dropdowns in debug console
 */
function populateDebugAgentSelects() {
    const agentIds = Object.keys(state.agents);

    // Populate Game Flow filter
    const gameflowSelect = document.getElementById('gameflowAgentFilter');
    const currentGameflowValue = gameflowSelect.value;
    gameflowSelect.innerHTML = '<option value="">All Agents</option>';
    agentIds.forEach(id => {
        gameflowSelect.innerHTML += `<option value="${id}">${id}</option>`;
    });
    gameflowSelect.value = currentGameflowValue;

    // Populate Agents Test select
    const testSelect = document.getElementById('testAgentSelect');
    const currentTestValue = testSelect.value;
    testSelect.innerHTML = '<option value="">-- Select an agent --</option>';
    agentIds.forEach(id => {
        testSelect.innerHTML += `<option value="${id}">${id}</option>`;
    });
    testSelect.value = currentTestValue;
}

/**
 * Load game flow activity log
 */
async function loadGameFlow() {
    try {
        const agentFilter = document.getElementById('gameflowAgentFilter').value;
        const typeFilter = document.getElementById('gameflowTypeFilter').value;

        const result = await api.getActivityLog(agentFilter || null, typeFilter || null, 100);
        renderGameFlow(result.activities || []);
    } catch (error) {
        console.error('Failed to load game flow:', error);
    }
}

/**
 * Render game flow timeline
 */
function renderGameFlow(activities) {
    const timeline = document.getElementById('gameflowTimeline');

    if (activities.length === 0) {
        timeline.innerHTML = '<p class="text-gray-500">No activity recorded yet. Interact with agents to see the flow.</p>';
        return;
    }

    timeline.innerHTML = activities.map(activity => {
        const dt = new Date(activity.timestamp);
        const timeStr = dt.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        const dateStr = dt.toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit' });

        const typeColors = {
            'chat': 'text-blue-400',
            'simulation': 'text-green-400',
            'memory': 'text-purple-400',
            'function': 'text-yellow-400',
            'kpi': 'text-orange-400'
        };
        const typeColor = typeColors[activity.type] || 'text-gray-400';

        const statusIcon = activity.success ?
            '<span class="text-green-400">✓</span>' :
            '<span class="text-red-400">✗</span>';

        const durationStr = activity.duration_ms ?
            `<span class="text-gray-500">${activity.duration_ms}ms</span>` : '';

        return `<div class="mb-2 pb-2 border-b border-gray-700 flex items-start gap-2">
            <span class="text-gray-500 whitespace-nowrap">[${dateStr} ${timeStr}]</span>
            ${statusIcon}
            <span class="${typeColor}">[${activity.type.toUpperCase()}]</span>
            <span class="text-cyan-400">${activity.agent_id || 'system'}:</span>
            <span class="text-white flex-1">${activity.action}</span>
            ${durationStr}
            ${activity.error ? `<span class="text-red-400 text-xs">${activity.error}</span>` : ''}
        </div>
        <div class="text-gray-400 text-xs mb-3 ml-4">${activity.details || ''}</div>`;
    }).join('');
}

/**
 * Load debug statistics
 */
async function loadDebugStats() {
    try {
        const result = await api.getActivityStats();
        const stats = result.stats || {};

        document.getElementById('statsTotalCalls').textContent = stats.total_calls || 0;
        document.getElementById('statsActiveAgents').textContent = stats.active_agents || 0;
        document.getElementById('statsAvgTime').textContent = stats.avg_response_time_ms ?
            `${stats.avg_response_time_ms}ms` : '--';
        document.getElementById('statsErrors').textContent = stats.errors || 0;
    } catch (error) {
        console.error('Failed to load debug stats:', error);
    }
}

/**
 * Clear game flow activity log
 */
async function clearGameFlow() {
    try {
        await api.clearActivityLog();
        components.showToast('Activity log cleared', 'success');
        await loadGameFlow();
        await loadDebugStats();
    } catch (error) {
        console.error('Failed to clear activity log:', error);
        components.showToast('Failed to clear activity log', 'error');
    }
}

/**
 * Handle test agent selection change
 */
async function onTestAgentChange() {
    const agentId = document.getElementById('testAgentSelect').value;
    state.testAgentId = agentId;

    const infoPanel = document.getElementById('testAgentInfo');
    const chatInput = document.getElementById('testChatInput');
    const sendBtn = document.getElementById('sendTestChatBtn');
    const memoryBtn = document.getElementById('injectMemoryBtn');
    const clearBtn = document.getElementById('clearTestConversationBtn');

    if (!agentId) {
        infoPanel.classList.add('hidden');
        chatInput.disabled = true;
        sendBtn.disabled = true;
        memoryBtn.disabled = true;
        clearBtn.disabled = true;
        document.getElementById('testChatMessages').innerHTML =
            '<p class="text-gray-400 text-center">Select an agent and start testing</p>';
        document.getElementById('testMemoryList').innerHTML =
            '<p class="text-gray-400">Select an agent to view memory</p>';
        return;
    }

    // Enable controls
    chatInput.disabled = false;
    sendBtn.disabled = false;
    memoryBtn.disabled = false;
    clearBtn.disabled = false;

    // Load agent info
    const agent = state.agents[agentId];
    if (agent) {
        infoPanel.classList.remove('hidden');
        document.getElementById('testAgentModel').textContent = agent.model || '--';
        document.getElementById('testAgentEntityType').textContent = agent.entity_type || '--';
        document.getElementById('testAgentCategory').textContent = agent.agent_category || '--';
    }

    // Load memory and conversation
    await loadTestAgentMemory();
    await loadTestConversation();
}

/**
 * Load test agent memory
 */
async function loadTestAgentMemory() {
    if (!state.testAgentId) return;

    try {
        const result = await api.getMemory(state.testAgentId);
        const memoryList = document.getElementById('testMemoryList');

        if (!result.memory || result.memory.length === 0) {
            memoryList.innerHTML = '<p class="text-gray-400">No memory items</p>';
            return;
        }

        memoryList.innerHTML = result.memory.map((item, index) =>
            `<div class="p-1 bg-white rounded mb-1 border-l-2 border-purple-400">
                <span class="text-gray-500">${index + 1}.</span> ${item}
            </div>`
        ).join('');
    } catch (error) {
        console.error('Failed to load memory:', error);
    }
}

/**
 * Load test agent conversation
 */
async function loadTestConversation() {
    if (!state.testAgentId) return;

    try {
        const result = await api.getConversation(state.testAgentId);
        const chatMessages = document.getElementById('testChatMessages');

        if (!result.conversation || result.conversation.length === 0) {
            chatMessages.innerHTML = '<p class="text-gray-400 text-center">No conversation history. Start chatting!</p>';
            return;
        }

        chatMessages.innerHTML = result.conversation.map(msg => {
            const isUser = msg.role === 'user';
            return `<div class="mb-3 ${isUser ? 'text-right' : ''}">
                <span class="text-xs text-gray-500">${msg.role}</span>
                <div class="inline-block max-w-[80%] p-2 rounded ${isUser ? 'bg-blue-100' : 'bg-gray-200'} text-left">
                    ${msg.content}
                </div>
            </div>`;
        }).join('');

        chatMessages.scrollTop = chatMessages.scrollHeight;
    } catch (error) {
        console.error('Failed to load conversation:', error);
    }
}

/**
 * Inject memory into test agent
 */
async function injectTestMemory() {
    if (!state.testAgentId) return;

    const memoryInput = document.getElementById('testMemoryInput');
    const memory = memoryInput.value.trim();
    if (!memory) return;

    try {
        await api.addMemory(state.testAgentId, memory);
        memoryInput.value = '';
        components.showToast('Memory injected successfully', 'success');
        await loadTestAgentMemory();
        // Also refresh the main agent data if this is the selected agent
        if (state.testAgentId === state.selectedAgentId) {
            await loadAgents();
            await loadAgentData(state.selectedAgentId);
        }
    } catch (error) {
        console.error('Failed to inject memory:', error);
        components.showToast('Failed to inject memory', 'error');
    }
}

/**
 * Clear test agent conversation
 */
async function clearTestConversation() {
    if (!state.testAgentId) return;

    if (!confirm('Are you sure you want to clear the conversation history?')) return;

    try {
        await api.clearConversation(state.testAgentId);
        components.showToast('Conversation cleared', 'success');
        await loadTestConversation();
        // Also refresh the main agent data if this is the selected agent
        if (state.testAgentId === state.selectedAgentId) {
            await loadAgents();
            await loadAgentData(state.selectedAgentId);
        }
    } catch (error) {
        console.error('Failed to clear conversation:', error);
        components.showToast('Failed to clear conversation', 'error');
    }
}

/**
 * Send test chat message
 */
async function sendTestChat() {
    if (!state.testAgentId) return;

    const input = document.getElementById('testChatInput');
    const message = input.value.trim();
    if (!message) return;

    input.value = '';

    // Add user message to UI
    const chatMessages = document.getElementById('testChatMessages');
    // Clear placeholder if present
    if (chatMessages.querySelector('.text-gray-400')) {
        chatMessages.innerHTML = '';
    }

    chatMessages.innerHTML += `<div class="mb-3 text-right">
        <span class="text-xs text-gray-500">user</span>
        <div class="inline-block max-w-[80%] p-2 rounded bg-blue-100 text-left">${message}</div>
    </div>`;
    chatMessages.scrollTop = chatMessages.scrollHeight;

    // Disable controls
    const sendBtn = document.getElementById('sendTestChatBtn');
    sendBtn.disabled = true;
    sendBtn.textContent = 'Sending...';

    const startTime = Date.now();

    try {
        const maxTokens = parseInt(document.getElementById('testMaxTokens').value) || 1024;
        const temperature = parseFloat(document.getElementById('testTemperature').value) || 1.0;

        const result = await api.sendMessage(state.testAgentId, message, maxTokens, temperature);
        const duration = Date.now() - startTime;

        if (result.status === 'success') {
            chatMessages.innerHTML += `<div class="mb-3">
                <span class="text-xs text-gray-500">assistant</span>
                <div class="inline-block max-w-[80%] p-2 rounded bg-gray-200 text-left">${result.response}</div>
            </div>`;
            chatMessages.scrollTop = chatMessages.scrollHeight;

            // Show response info
            document.getElementById('testResponseInfo').classList.remove('hidden');
            document.getElementById('testResponseTime').textContent = result.duration_ms || duration;
            document.getElementById('testResponseTokens').textContent = '--';
        }

        // Refresh game flow to show the new activity
        await loadGameFlow();
        await loadDebugStats();

    } catch (error) {
        console.error('Failed to send test message:', error);
        components.showToast('Failed to send message', 'error');
    } finally {
        sendBtn.disabled = false;
        sendBtn.textContent = 'Send';
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', init);
