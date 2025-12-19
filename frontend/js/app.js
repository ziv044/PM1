/**
 * Main Application Logic for PM1 Agent Admin Panel
 */

// Application state
const state = {
    agents: {},
    selectedAgentId: null,
    currentTab: 'details',
    isEditing: false
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
        const model = document.getElementById('formModel').value;
        const systemPrompt = document.getElementById('formSystemPrompt').value;

        try {
            if (state.isEditing) {
                await api.updateAgent(agentId, model, systemPrompt);
                components.showToast('Agent updated successfully', 'success');
            } else {
                await api.createAgent(agentId, model, systemPrompt);
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

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', init);
