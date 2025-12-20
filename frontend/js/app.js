/**
 * Main Application Logic for PM1 Agent Admin Panel
 */

// Application state
const state = {
    agents: {},
    selectedAgentId: null,
    currentTab: 'simulation',  // Default to simulation tab
    currentContext: 'simulation',  // 'simulation' or 'agent'
    isEditing: false,
    simulationPollingInterval: null,
    simulationStatus: null,
    // Debug console state
    debugSubtab: 'gameflow',
    testAgentId: null,
    debugPollingInterval: null,
    // PM Approvals state
    pmApprovalsPollingInterval: null,
    // Meetings state
    meetingsPollingInterval: null,
    activeMeeting: null,
    meetingTypes: {},
    selectedMeetingType: null,
    meetingParticipants: []
};

// Simulation-level tabs (always visible)
const SIMULATION_TABS = ['simulation', 'mapstate', 'logs', 'kpis', 'pmapprovals', 'meetings', 'games'];
// Agent-level tabs (only when agent selected)
const AGENT_TABS = ['details', 'skills', 'memory', 'chat', 'debug'];

/**
 * Initialize the application
 */
async function init() {
    console.log('[PM1] Initializing app...');
    try {
        // Load agents
        await loadAgents();
        console.log('[PM1] Agents loaded');

        // Set up event listeners
        setupEventListeners();
        console.log('[PM1] Event listeners set up');

        // Show Simulation tab by default (main screen for admin)
        components.showSimulationTab('simulation');
        console.log('[PM1] Simulation tab shown');

        loadSimulationStatus().then(() => {
            if (state.simulationStatus && state.simulationStatus.is_running) {
                startSimulationPolling();
            }
        });
        loadSimulationEvents();
        console.log('[PM1] Init complete');
    } catch (error) {
        console.error('[PM1] Init error:', error);
    }
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
    state.currentContext = 'agent';

    // Stop any simulation-level polling
    stopSimulationPolling();
    stopPMApprovalsPolling();
    stopMeetingsPolling();

    // Update UI - show agent context
    components.renderAgentList(state.agents, agentId);
    components.setAgentTitle(`Agent: ${agentId}`);
    components.showAgentContext(true);
    components.showAgentTab('details');

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

            // Load prompts for display
            await loadAgentPrompts();
        }
    } catch (error) {
        console.error('Failed to load agent data:', error);
        components.showToast('Failed to load agent data', 'error');
    }
}

/**
 * Save inline edit changes
 */
async function saveInlineEdit() {
    if (!state.selectedAgentId) return;

    const agentData = {
        model: document.getElementById('detailModel').value,
        system_prompt: document.getElementById('detailSystemPrompt').value,
        entity_type: document.getElementById('detailEntityType').value,
        event_frequency: parseInt(document.getElementById('detailEventFrequency').value) || 60,
        agent_category: document.getElementById('detailAgentCategory').value,
        is_enabled: document.getElementById('detailIsEnabled').checked,
        is_enemy: document.getElementById('detailIsEnemy').checked,
        is_west: document.getElementById('detailIsWest').checked,
        is_evil_axis: document.getElementById('detailIsEvilAxis').checked,
        is_reporting_government: document.getElementById('detailIsReportingGovernment').checked,
        agenda: document.getElementById('detailAgenda').value,
        primary_objectives: document.getElementById('detailPrimaryObjectives').value,
        hard_rules: document.getElementById('detailHardRules').value
    };

    const saveBtn = document.getElementById('saveInlineEditBtn');
    const originalText = saveBtn.textContent;
    saveBtn.textContent = 'Saving...';
    saveBtn.disabled = true;

    try {
        await api.updateAgent(state.selectedAgentId, agentData);
        components.showToast('Agent updated successfully', 'success');

        // Refresh agent data and prompts
        await loadAgents();
        await loadAgentData(state.selectedAgentId);
    } catch (error) {
        console.error('Failed to update agent:', error);
        components.showToast('Failed to update agent', 'error');
    } finally {
        saveBtn.textContent = originalText;
        saveBtn.disabled = false;
    }
}

/**
 * Load and display agent prompts
 */
async function loadAgentPrompts() {
    if (!state.selectedAgentId) return;

    try {
        const result = await api.getActionPrompt(state.selectedAgentId);

        if (result.status === 'success') {
            // Update compiled system prompt
            document.getElementById('displayCompiledPrompt').textContent =
                result.prompts.compiled_system_prompt || '(Not compiled)';

            // Update full action prompt
            document.getElementById('displayActionPrompt').textContent =
                result.prompts.full_action_prompt || '(Not available)';

            // Update context info
            document.getElementById('promptGameTime').textContent = result.game_time || '--';
            document.getElementById('promptMemoryCount').textContent = result.context.memory_count || 0;

            // Location summary - truncate if too long
            const locContext = result.context.location_context || '';
            document.getElementById('promptLocationSummary').textContent =
                locContext.length > 30 ? locContext.substring(0, 30) + '...' : (locContext || '--');

            // Intel access
            const intelContext = result.context.known_locations;
            document.getElementById('promptIntelAccess').textContent =
                intelContext ? 'Yes' : 'None';
        }
    } catch (error) {
        console.error('Failed to load prompts:', error);
        // Don't show toast for prompts - it's not critical
        document.getElementById('displayCompiledPrompt').textContent = '(Failed to load)';
        document.getElementById('displayActionPrompt').textContent = '(Failed to load)';
    }
}

/**
 * Set up prompt section toggle handlers
 */
function setupPromptToggles() {
    const sections = [
        { btn: 'toggleCompiledPromptBtn', section: 'compiledPromptSection', icon: 'compiledPromptToggleIcon' },
        { btn: 'toggleActionPromptBtn', section: 'actionPromptSection', icon: 'actionPromptToggleIcon' }
    ];

    sections.forEach(({ btn, section, icon }) => {
        const btnEl = document.getElementById(btn);
        if (btnEl) {
            btnEl.addEventListener('click', () => {
                const sectionEl = document.getElementById(section);
                const iconEl = document.getElementById(icon);
                const isHidden = sectionEl.classList.contains('hidden');

                sectionEl.classList.toggle('hidden');
                iconEl.textContent = isHidden ? '- Collapse' : '+ Expand';
            });
        }
    });
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
 * Safely add event listener (null-safe)
 */
function safeAddListener(elementId, event, handler) {
    const el = document.getElementById(elementId);
    if (el) {
        el.addEventListener(event, handler);
    } else {
        console.warn(`[PM1] Element not found: ${elementId}`);
    }
}

/**
 * Set up all event listeners
 */
function setupEventListeners() {
    console.log('[PM1] Setting up event listeners...');

    // Agent list click
    const agentList = document.getElementById('agentList');
    if (agentList) {
        agentList.addEventListener('click', (e) => {
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
    }

    // Enable All button
    safeAddListener('enableAllBtn', 'click', async () => {
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
    safeAddListener('disableAllBtn', 'click', async () => {
        try {
            await api.setAllAgentsEnabled(false);
            components.showToast('All agents disabled', 'success');
            await loadAgents();
        } catch (error) {
            console.error('Failed to disable all agents:', error);
            components.showToast('Failed to disable all agents', 'error');
        }
    });

    // Simulation tab clicks (always visible)
    document.querySelectorAll('.sim-tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            state.currentTab = tab;
            state.currentContext = 'simulation';

            // Hide agent context, show simulation tab
            components.showAgentContext(false);
            components.showSimulationTab(tab);

            // Handle tab-specific data loading
            handleSimulationTabLoad(tab);
        });
    });

    // Agent tab clicks (only when agent selected)
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            if (!state.selectedAgentId) {
                components.showToast('Please select an agent first', 'warning');
                return;
            }

            const tab = btn.dataset.tab;
            state.currentTab = tab;
            state.currentContext = 'agent';
            components.showAgentTab(tab);

            // Handle tab-specific data loading
            handleAgentTabLoad(tab);
        });
    });

    // Continue with rest of event listeners
    setupEventListenersContinued();
}

/**
 * Handle simulation tab data loading
 */
function handleSimulationTabLoad(tab) {
    // Stop agent-level polling when switching to simulation context
    stopSimulationPolling();
    stopPMApprovalsPolling();
    stopMeetingsPolling();

    if (tab === 'simulation') {
        loadSimulationStatus().then(() => {
            if (state.simulationStatus && state.simulationStatus.is_running) {
                startSimulationPolling();
            }
        });
        loadSimulationEvents();
    }
    if (tab === 'logs') {
        loadLogs();
    }
    if (tab === 'mapstate') {
        loadMapState();
    }
    if (tab === 'kpis') {
        loadKPIs();
        loadKPIChangeLog();
    }
    if (tab === 'pmapprovals') {
        loadPMApprovals();
        startPMApprovalsPolling();
    }
    if (tab === 'meetings') {
        loadMeetings();
        loadMeetingRequests();
        startMeetingsPolling();
    }
    if (tab === 'games') {
        loadGamesList();
    }
}

/**
 * Handle agent tab data loading
 */
function handleAgentTabLoad(tab) {
    // Stop simulation-level polling when in agent context
    stopSimulationPolling();
    stopPMApprovalsPolling();
    stopMeetingsPolling();

    if (tab === 'debug') {
        populateDebugAgentSelects();
        loadGameFlow();
        loadDebugStats();
    }
}

/**
 * Set up all event listeners (continued)
 */
function setupEventListenersContinued() {
    // Add agent button
    const addAgentBtn = document.getElementById('addAgentBtn');
    if (addAgentBtn) {
        addAgentBtn.addEventListener('click', () => {
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
    }

    // Inline edit form submit
    const inlineEditForm = document.getElementById('inlineEditForm');
    if (inlineEditForm) {
        inlineEditForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            await saveInlineEdit();
        });
    }

    // Cancel inline edit - reset form to original values
    const cancelBtn = document.getElementById('cancelInlineEditBtn');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', () => {
            const original = components.getOriginalAgentData();
            if (original && state.selectedAgentId) {
                components.renderAgentDetails(original, state.selectedAgentId);
                components.showToast('Changes discarded', 'info');
            }
        });
    }

    // Refresh prompts button
    const refreshPromptsBtn = document.getElementById('refreshPromptsBtn');
    if (refreshPromptsBtn) {
        refreshPromptsBtn.addEventListener('click', loadAgentPrompts);
    }

    // Prompt section toggle handlers
    setupPromptToggles();

    // Delete agent button
    const deleteAgentBtn = document.getElementById('deleteAgentBtn');
    if (deleteAgentBtn) {
        deleteAgentBtn.addEventListener('click', () => {
            if (state.selectedAgentId) {
                components.showModal('deleteModal');
            }
        });
    }

    // Confirm delete
    const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');
    if (confirmDeleteBtn) {
        confirmDeleteBtn.addEventListener('click', async () => {
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
    }

    // Cancel delete
    const cancelDeleteBtn = document.getElementById('cancelDeleteBtn');
    if (cancelDeleteBtn) {
        cancelDeleteBtn.addEventListener('click', () => {
            components.hideModal('deleteModal');
        });
    }

    // Agent form submit
    const agentForm = document.getElementById('agentForm');
    if (agentForm) {
        agentForm.addEventListener('submit', async (e) => {
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
    }

    // Cancel agent modal
    const cancelModalBtn = document.getElementById('cancelModalBtn');
    if (cancelModalBtn) {
        cancelModalBtn.addEventListener('click', () => {
            components.hideModal('agentModal');
        });
    }

    // Add skill button
    const addSkillBtn = document.getElementById('addSkillBtn');
    if (addSkillBtn) {
        addSkillBtn.addEventListener('click', () => {
            document.getElementById('formSkill').value = '';
            components.showModal('skillModal');
        });
    }

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
    document.getElementById('resolveNowBtn').addEventListener('click', resolveNow);

    // KPIs tab controls
    document.getElementById('refreshKpisBtn').addEventListener('click', () => {
        loadKPIs();
        loadKPIChangeLog();
    });
    document.getElementById('kpiLogEntityFilter').addEventListener('change', loadKPIChangeLog);

    // PM Approvals controls
    setupPMApprovalsListeners();

    // Debug Console controls
    setupDebugConsoleListeners();

    // Meetings controls
    setupMeetingsListeners();
}

/**
 * Set up PM Approvals event listeners
 */
function setupPMApprovalsListeners() {
    // Refresh approvals button
    const refreshBtn = document.getElementById('refreshApprovalsBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', loadPMApprovals);
    }

    // PM Approvals container click delegation for approve/modify/reject buttons
    const approvalsContainer = document.getElementById('pmApprovalsContainer');
    if (approvalsContainer) {
        approvalsContainer.addEventListener('click', (e) => {
            const approveBtn = e.target.closest('.pm-approve-btn');
            const modifyBtn = e.target.closest('.pm-modify-btn');
            const rejectBtn = e.target.closest('.pm-reject-btn');

            if (approveBtn) {
                handlePMApprove(approveBtn.dataset.approvalId);
            } else if (modifyBtn) {
                handlePMModifyOpen(modifyBtn.dataset.approvalId, modifyBtn.dataset.summary);
            } else if (rejectBtn) {
                handlePMReject(rejectBtn.dataset.approvalId);
            }
        });
    }

    // Scheduled events container click delegation for cancel buttons
    const scheduledContainer = document.getElementById('scheduledEventsContainer');
    if (scheduledContainer) {
        scheduledContainer.addEventListener('click', (e) => {
            const cancelBtn = e.target.closest('.cancel-scheduled-btn');
            if (cancelBtn) {
                handleCancelScheduledEvent(cancelBtn.dataset.scheduleId);
            }
        });
    }

    // Modify modal handlers
    const cancelModifyBtn = document.getElementById('cancelModifyBtn');
    if (cancelModifyBtn) {
        cancelModifyBtn.addEventListener('click', () => {
            components.hideModal('pmModifyModal');
        });
    }

    const modifyForm = document.getElementById('pmModifyForm');
    if (modifyForm) {
        modifyForm.addEventListener('submit', handlePMModifySubmit);
    }

    // Close modal on outside click
    const modifyModal = document.getElementById('pmModifyModal');
    if (modifyModal) {
        modifyModal.addEventListener('click', (e) => {
            if (e.target.id === 'pmModifyModal') {
                components.hideModal('pmModifyModal');
            }
        });
    }
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

// ============================================================================
// PM APPROVALS FUNCTIONS
// ============================================================================

/**
 * Load PM approval requests and scheduled events
 */
async function loadPMApprovals() {
    try {
        const [approvalsResult, scheduledResult] = await Promise.all([
            api.getPMApprovals(),
            api.getScheduledEvents()
        ]);

        if (approvalsResult.status === 'success') {
            components.renderPMApprovals(approvalsResult.approvals || []);
        }

        if (scheduledResult.status === 'success') {
            components.renderScheduledEvents(scheduledResult.events || []);
        }
    } catch (error) {
        console.error('Failed to load PM approvals:', error);
    }
}

/**
 * Start polling for PM approvals updates
 */
function startPMApprovalsPolling() {
    if (state.pmApprovalsPollingInterval) return;

    state.pmApprovalsPollingInterval = setInterval(async () => {
        if (state.simulationStatus && state.simulationStatus.is_running) {
            await loadPMApprovals();
        }
    }, 3000);
}

/**
 * Stop polling for PM approvals
 */
function stopPMApprovalsPolling() {
    if (state.pmApprovalsPollingInterval) {
        clearInterval(state.pmApprovalsPollingInterval);
        state.pmApprovalsPollingInterval = null;
    }
}

/**
 * Handle approve button click
 */
async function handlePMApprove(approvalId) {
    try {
        const result = await api.processPMDecision(approvalId, 'approve');
        if (result.status === 'success') {
            components.showToast('Request approved', 'success');
            await loadPMApprovals();
        } else {
            components.showToast(result.message || 'Failed to approve', 'error');
        }
    } catch (error) {
        console.error('Failed to approve:', error);
        components.showToast('Failed to approve request', 'error');
    }
}

/**
 * Handle reject button click
 */
async function handlePMReject(approvalId) {
    if (!confirm('Reject this request?')) return;

    try {
        const result = await api.processPMDecision(approvalId, 'reject');
        if (result.status === 'success') {
            components.showToast('Request rejected', 'success');
            await loadPMApprovals();
        } else {
            components.showToast(result.message || 'Failed to reject', 'error');
        }
    } catch (error) {
        console.error('Failed to reject:', error);
        components.showToast('Failed to reject request', 'error');
    }
}

/**
 * Handle modify button click - opens modal
 */
function handlePMModifyOpen(approvalId, originalSummary) {
    document.getElementById('modifyApprovalId').value = approvalId;
    document.getElementById('modifyOriginalSummary').textContent = originalSummary;
    document.getElementById('modifyNewSummary').value = originalSummary;
    document.getElementById('modifyNotes').value = '';
    document.getElementById('modifyDueTime').value = '';
    components.showModal('pmModifyModal');
}

/**
 * Handle modify form submit
 */
async function handlePMModifySubmit(e) {
    e.preventDefault();

    const approvalId = document.getElementById('modifyApprovalId').value;
    const modifiedSummary = document.getElementById('modifyNewSummary').value.trim();
    const notes = document.getElementById('modifyNotes').value.trim();
    const dueTimeInput = document.getElementById('modifyDueTime').value;

    let dueGameTime = null;
    if (dueTimeInput) {
        dueGameTime = new Date(dueTimeInput).toISOString();
    }

    try {
        const result = await api.processPMDecision(
            approvalId,
            'approve',
            notes || null,
            modifiedSummary,
            dueGameTime
        );
        if (result.status === 'success') {
            components.hideModal('pmModifyModal');
            components.showToast('Modified request approved', 'success');
            await loadPMApprovals();
        } else {
            components.showToast(result.message || 'Failed to process', 'error');
        }
    } catch (error) {
        console.error('Failed to process modified approval:', error);
        components.showToast('Failed to process request', 'error');
    }
}

/**
 * Handle cancel scheduled event
 */
async function handleCancelScheduledEvent(scheduleId) {
    if (!confirm('Cancel this scheduled event?')) return;

    try {
        const result = await api.cancelScheduledEvent(scheduleId);
        if (result.status === 'success') {
            components.showToast('Scheduled event cancelled', 'success');
            await loadPMApprovals();
        } else {
            components.showToast(result.message || 'Failed to cancel', 'error');
        }
    } catch (error) {
        console.error('Failed to cancel scheduled event:', error);
        components.showToast('Failed to cancel', 'error');
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

// =============================================================================
// MEETINGS FUNCTIONS
// =============================================================================

/**
 * Set up meetings event listeners
 */
function setupMeetingsListeners() {
    // Meeting type buttons
    document.querySelectorAll('.meeting-type-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            selectMeetingType(btn.dataset.type);
        });
    });

    // Schedule meeting button
    const scheduleBtn = document.getElementById('scheduleMeetingBtn');
    if (scheduleBtn) {
        scheduleBtn.addEventListener('click', scheduleMeeting);
    }

    // Add agenda item button
    const addAgendaBtn = document.getElementById('addAgendaItemBtn');
    if (addAgendaBtn) {
        addAgendaBtn.addEventListener('click', addAgendaItem);
    }

    // Refresh meetings button
    const refreshBtn = document.getElementById('refreshMeetingsBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            loadMeetings();
            loadMeetingRequests();
        });
    }

    // Meeting requests container - approve/reject delegation
    const requestsContainer = document.getElementById('meetingRequestsList');
    if (requestsContainer) {
        requestsContainer.addEventListener('click', (e) => {
            const approveBtn = e.target.closest('.approve-meeting-request-btn');
            const rejectBtn = e.target.closest('.reject-meeting-request-btn');

            if (approveBtn) {
                approveMeetingRequest(approveBtn.dataset.requestId);
            } else if (rejectBtn) {
                rejectMeetingRequest(rejectBtn.dataset.requestId);
            }
        });
    }

    // Scheduled meetings container - start meeting delegation
    const scheduledContainer = document.getElementById('scheduledMeetingsList');
    if (scheduledContainer) {
        scheduledContainer.addEventListener('click', (e) => {
            const startBtn = e.target.closest('.start-meeting-btn');
            if (startBtn) {
                startMeeting(startBtn.dataset.meetingId);
            }
        });
    }

    // Active meeting panel - open meeting room button
    const openMeetingBtn = document.getElementById('openMeetingRoomBtn');
    if (openMeetingBtn) {
        openMeetingBtn.addEventListener('click', () => {
            if (state.activeMeeting) {
                openMeetingRoom(state.activeMeeting.meeting_id);
            }
        });
    }

    // Meeting history container - view details delegation
    const historyContainer = document.getElementById('meetingHistoryList');
    if (historyContainer) {
        historyContainer.addEventListener('click', (e) => {
            const viewBtn = e.target.closest('.view-meeting-btn');
            if (viewBtn) {
                viewMeetingOutcome(viewBtn.dataset.meetingId);
            }
        });
    }

    // Meeting Room Modal controls
    setupMeetingRoomListeners();

    // Meeting Outcome Modal close
    const closeOutcomeBtn = document.getElementById('closeMeetingOutcomeBtn');
    if (closeOutcomeBtn) {
        closeOutcomeBtn.addEventListener('click', () => {
            components.hideModal('meetingOutcomeModal');
        });
    }

    // Close modals on outside click
    const meetingRoomModal = document.getElementById('meetingRoomModal');
    if (meetingRoomModal) {
        meetingRoomModal.addEventListener('click', (e) => {
            // Don't close on content click
            if (e.target === meetingRoomModal) {
                // Prompt before closing active meeting
                if (state.activeMeeting && state.activeMeeting.status === 'active') {
                    if (confirm('Leave meeting room? The meeting will continue.')) {
                        closeMeetingRoom();
                    }
                } else {
                    closeMeetingRoom();
                }
            }
        });
    }

    const outcomeModal = document.getElementById('meetingOutcomeModal');
    if (outcomeModal) {
        outcomeModal.addEventListener('click', (e) => {
            if (e.target === outcomeModal) {
                components.hideModal('meetingOutcomeModal');
            }
        });
    }
}

/**
 * Set up Meeting Room modal listeners
 */
function setupMeetingRoomListeners() {
    // Close meeting room button
    const closeBtn = document.getElementById('closeMeetingRoomBtn');
    if (closeBtn) {
        closeBtn.addEventListener('click', closeMeetingRoom);
    }

    // PM interjection submit button
    const submitBtn = document.getElementById('submitPmMeetingInput');
    if (submitBtn) {
        submitBtn.addEventListener('click', submitPMInterjection);
    }

    // Enter key in PM input
    const pmInput = document.getElementById('pmMeetingInput');
    if (pmInput) {
        pmInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                submitPMInterjection();
            }
        });
    }

    // Advance round button
    const advanceBtn = document.getElementById('advanceRoundBtn');
    if (advanceBtn) {
        advanceBtn.addEventListener('click', advanceMeetingRound);
    }

    // Conclude meeting button
    const concludeBtn = document.getElementById('concludeMeetingBtn');
    if (concludeBtn) {
        concludeBtn.addEventListener('click', concludeMeeting);
    }

    // Abort meeting button
    const abortBtn = document.getElementById('abortMeetingBtn');
    if (abortBtn) {
        abortBtn.addEventListener('click', abortMeeting);
    }
}

/**
 * Start polling for meetings updates
 */
function startMeetingsPolling() {
    if (state.meetingsPollingInterval) return;

    state.meetingsPollingInterval = setInterval(async () => {
        await loadMeetings();
        await loadMeetingRequests();
        // If in meeting room, refresh the meeting state
        if (state.activeMeeting && state.activeMeeting.status === 'active') {
            await refreshMeetingRoom();
        }
    }, 3000);
}

/**
 * Stop polling for meetings
 */
function stopMeetingsPolling() {
    if (state.meetingsPollingInterval) {
        clearInterval(state.meetingsPollingInterval);
        state.meetingsPollingInterval = null;
    }
}

/**
 * Load all meetings and state
 */
async function loadMeetings() {
    try {
        const result = await api.getMeetings();

        if (result.status === 'success') {
            const meetings = result.meetings || [];
            const activeMeeting = result.active_meeting;

            // Update active meeting state
            state.activeMeeting = activeMeeting;

            // Update active meeting panel
            updateActiveMeetingPanel(activeMeeting);

            // Render scheduled meetings
            const scheduled = meetings.filter(m => m.status === 'scheduled' || m.status === 'pending');
            renderScheduledMeetings(scheduled);

            // Render meeting history
            const history = meetings.filter(m => m.status === 'concluded' || m.status === 'failed');
            renderMeetingHistory(history);
        }
    } catch (error) {
        console.error('Failed to load meetings:', error);
    }
}

/**
 * Load meeting types
 */
async function loadMeetingTypes() {
    try {
        const result = await api.getMeetingTypes();
        if (result.status === 'success') {
            state.meetingTypes = result.types || {};
        }
    } catch (error) {
        console.error('Failed to load meeting types:', error);
    }
}

/**
 * Load meeting requests
 */
async function loadMeetingRequests() {
    try {
        const result = await api.getMeetingRequests();

        if (result.status === 'success') {
            renderMeetingRequests(result.requests || []);
        }
    } catch (error) {
        console.error('Failed to load meeting requests:', error);
    }
}

/**
 * Select a meeting type for scheduling
 */
function selectMeetingType(type) {
    state.selectedMeetingType = type;
    state.meetingParticipants = [];

    // Update button styles
    document.querySelectorAll('.meeting-type-btn').forEach(btn => {
        if (btn.dataset.type === type) {
            btn.classList.add('ring-2', 'ring-blue-500');
            btn.classList.remove('opacity-50');
        } else {
            btn.classList.remove('ring-2', 'ring-blue-500');
            btn.classList.add('opacity-50');
        }
    });

    // Populate participants based on type
    populateMeetingParticipants(type);
}

/**
 * Populate participant options based on meeting type
 */
function populateMeetingParticipants(type) {
    const select = document.getElementById('meetingParticipantsSelect');
    if (!select) return;

    const agents = Object.values(state.agents);

    // Filter agents based on meeting type
    let options = [];

    switch (type) {
        case 'cabinet_war_room':
            // Israeli officials only
            options = agents.filter(a =>
                a.entity_type === 'Israel' ||
                (a.is_reporting_government && !a.is_enemy)
            );
            break;
        case 'negotiation':
            // Multi-party including enemies and mediators
            options = agents.filter(a =>
                a.entity_type !== 'System'
            );
            break;
        case 'leader_talk':
            // Leaders of other entities - foreign heads of state/government
            options = agents.filter(a =>
                a.agent_category === 'International Affairs' ||
                a.agent_id?.toLowerCase().includes('president') ||
                a.agent_id?.toLowerCase().includes('leader') ||
                a.agent_id?.toLowerCase().includes('prime-minister')
            );
            break;
        case 'agent_briefing':
            // Israeli officials for 1-on-1
            options = agents.filter(a =>
                a.is_reporting_government ||
                a.entity_type === 'Israel'
            );
            break;
        default:
            options = agents;
    }

    select.innerHTML = options.map(agent =>
        `<option value="${agent.agent_id}">${agent.agent_id} (${agent.entity_type})</option>`
    ).join('');
}

/**
 * Add an agenda item to the list
 */
function addAgendaItem() {
    const container = document.getElementById('agendaItems');
    const existingInputs = container.querySelectorAll('input.agenda-item');
    const newIndex = existingInputs.length + 1;

    const newInput = document.createElement('input');
    newInput.type = 'text';
    newInput.className = 'agenda-item w-full border border-gray-300 rounded px-3 py-2 text-sm';
    newInput.placeholder = `Topic ${newIndex}...`;

    container.appendChild(newInput);
    newInput.focus();
}

/**
 * Schedule a new meeting
 */
async function scheduleMeeting() {
    if (!state.selectedMeetingType) {
        components.showToast('Please select a meeting type', 'error');
        return;
    }

    const title = document.getElementById('meetingTitle')?.value.trim();
    const participantsSelect = document.getElementById('meetingParticipantsSelect');
    const selectedOptions = participantsSelect ? Array.from(participantsSelect.selectedOptions) : [];
    // Convert to participant config objects expected by backend
    const participants = selectedOptions.map(opt => ({
        agent_id: opt.value,
        role: 'principal',  // Default role
        initial_position: ''
    }));

    if (!title) {
        components.showToast('Please enter a meeting title', 'error');
        return;
    }

    if (participants.length === 0) {
        components.showToast('Please select at least one participant', 'error');
        return;
    }

    // Collect agenda items from input fields
    const agendaItems = [];
    document.querySelectorAll('#agendaItems input.agenda-item').forEach(input => {
        const value = input.value.trim();
        if (value) agendaItems.push(value);
    });

    // Get current game time for scheduling
    const gameTimeInput = document.getElementById('gameTimeInput');
    const scheduledGameTime = gameTimeInput?.value
        ? new Date(gameTimeInput.value).toISOString()
        : new Date().toISOString();

    const meetingData = {
        meeting_type: state.selectedMeetingType,
        title: title,
        participants: participants,
        agenda_items: agendaItems,
        scheduled_game_time: scheduledGameTime,
        context: ''
    };

    try {
        const btn = document.getElementById('scheduleMeetingBtn');
        btn.disabled = true;
        btn.textContent = 'Scheduling...';

        const result = await api.createMeeting(meetingData);

        if (result.status === 'success') {
            components.showToast('Meeting scheduled successfully', 'success');

            // Clear form
            document.getElementById('meetingTitle').value = '';
            // Reset agenda items to single input
            document.getElementById('agendaItems').innerHTML = `
                <input type="text" class="agenda-item w-full border border-gray-300 rounded px-3 py-2 text-sm"
                    placeholder="Topic 1...">
            `;
            state.selectedMeetingType = null;

            // Reset type buttons
            document.querySelectorAll('.meeting-type-btn').forEach(btn => {
                btn.classList.remove('ring-2', 'ring-blue-500', 'opacity-50');
            });

            // Reload meetings
            await loadMeetings();
        } else {
            components.showToast(result.message || 'Failed to schedule meeting', 'error');
        }
    } catch (error) {
        console.error('Failed to schedule meeting:', error);
        components.showToast('Failed to schedule meeting', 'error');
    } finally {
        const btn = document.getElementById('scheduleMeetingBtn');
        btn.disabled = false;
        btn.textContent = 'Schedule Meeting';
    }
}

/**
 * Approve a meeting request
 */
async function approveMeetingRequest(requestId) {
    try {
        const result = await api.approveMeetingRequest(requestId);
        if (result.status === 'success') {
            components.showToast('Meeting request approved', 'success');
            await loadMeetingRequests();
            await loadMeetings();
        } else {
            components.showToast(result.message || 'Failed to approve', 'error');
        }
    } catch (error) {
        console.error('Failed to approve meeting request:', error);
        components.showToast('Failed to approve request', 'error');
    }
}

/**
 * Reject a meeting request
 */
async function rejectMeetingRequest(requestId) {
    if (!confirm('Reject this meeting request?')) return;

    try {
        const result = await api.rejectMeetingRequest(requestId);
        if (result.status === 'success') {
            components.showToast('Meeting request rejected', 'success');
            await loadMeetingRequests();
        } else {
            components.showToast(result.message || 'Failed to reject', 'error');
        }
    } catch (error) {
        console.error('Failed to reject meeting request:', error);
        components.showToast('Failed to reject request', 'error');
    }
}

/**
 * Start a scheduled meeting
 */
async function startMeeting(meetingId) {
    try {
        const result = await api.startMeeting(meetingId);

        if (result.status === 'success') {
            components.showToast('Meeting started - Simulation paused', 'success');
            state.activeMeeting = result.meeting;

            // Open meeting room
            openMeetingRoom(meetingId);

            // Reload meetings list
            await loadMeetings();
        } else {
            components.showToast(result.message || 'Failed to start meeting', 'error');
        }
    } catch (error) {
        console.error('Failed to start meeting:', error);
        components.showToast('Failed to start meeting', 'error');
    }
}

/**
 * Open the meeting room modal
 */
async function openMeetingRoom(meetingId) {
    try {
        const result = await api.getMeeting(meetingId);

        if (result.status === 'success') {
            const meeting = result.meeting;
            state.activeMeeting = meeting;

            // Render meeting room content
            renderMeetingRoom(meeting);

            // Show modal
            components.showModal('meetingRoomModal');
        } else {
            components.showToast(result.message || 'Failed to load meeting', 'error');
        }
    } catch (error) {
        console.error('Failed to open meeting room:', error);
        components.showToast('Failed to open meeting room', 'error');
    }
}

/**
 * Close the meeting room modal
 */
function closeMeetingRoom() {
    components.hideModal('meetingRoomModal');
}

/**
 * Render meeting room content
 */
function renderMeetingRoom(meeting) {
    // Title
    document.getElementById('meetingRoomTitle').textContent = meeting.title;
    document.getElementById('meetingRoomType').textContent = formatMeetingType(meeting.meeting_type);
    document.getElementById('meetingRoomRound').textContent = meeting.current_round || 1;
    document.getElementById('meetingRoomMaxRounds').textContent = meeting.max_rounds || 10;

    // Participants list
    const participantsList = document.getElementById('meetingRoomParticipants');
    if (participantsList && meeting.participants) {
        participantsList.innerHTML = meeting.participants.map(p => {
            // Handle both object and string participant formats
            const agentId = typeof p === 'string' ? p : p.agent_id;
            const role = typeof p === 'string' ? 'principal' : (p.role || 'principal');
            const entity = typeof p === 'string' ? '' : (p.entity || '');
            const hasSpoken = typeof p === 'string' ? false : p.has_spoken_this_round;

            const speakingClass = hasSpoken ? 'bg-green-700' : 'bg-gray-700';
            const roleColor = {
                'chair': 'text-purple-400',
                'principal': 'text-blue-400',
                'mediator': 'text-orange-400',
                'advisor': 'text-gray-400',
                'observer': 'text-gray-500'
            }[role] || 'text-gray-400';

            return `
                <div class="p-2 rounded ${speakingClass}">
                    <div class="font-medium text-white">${agentId}</div>
                    <div class="text-xs ${roleColor}">${role}</div>
                    <div class="text-xs text-gray-400">${entity}</div>
                </div>
            `;
        }).join('');
    }

    // Agenda
    const agendaList = document.getElementById('meetingRoomAgenda');
    if (agendaList) {
        if (meeting.agenda && meeting.agenda.items) {
            agendaList.innerHTML = meeting.agenda.items.map((item, idx) => {
                const isCurrent = idx === (meeting.agenda.current_item_index || 0);
                const currentClass = isCurrent ? 'text-green-400 font-medium' : 'text-gray-400';
                const checkmark = isCurrent ? '▶' : (idx < (meeting.agenda.current_item_index || 0) ? '✓' : '○');
                return `<div class="p-1 ${currentClass}">${checkmark} ${item}</div>`;
            }).join('');
        } else {
            agendaList.innerHTML = '<div class="text-gray-500">No agenda items</div>';
        }
    }

    // Transcript
    renderMeetingTranscript(meeting.turns || []);

    // Update turn count
    const turnCount = document.getElementById('meetingTurnCount');
    if (turnCount) turnCount.textContent = meeting.turns?.length || 0;

    // Update current topic
    const currentTopic = document.getElementById('meetingCurrentTopic');
    if (currentTopic && meeting.agenda?.items) {
        const currentIdx = meeting.agenda.current_item_index || 0;
        currentTopic.textContent = meeting.agenda.items[currentIdx] || 'General discussion';
    }

    // Intelligence panel - update stakes and summary
    const stakesEl = document.getElementById('meetingStakes');
    if (stakesEl) stakesEl.textContent = meeting.stakes || 'Not specified';

    const summaryEl = document.getElementById('meetingStateSummary');
    if (summaryEl) {
        if (meeting.turns?.length > 0) {
            summaryEl.textContent = `Meeting in progress. ${meeting.turns.length} turns completed.`;
        } else {
            summaryEl.textContent = 'Meeting has just begun. Click Advance Round to start.';
        }
    }

    // Update control buttons state
    const advanceBtn = document.getElementById('advanceRoundBtn');
    const concludeBtn = document.getElementById('concludeMeetingBtn');

    if (meeting.status === 'active') {
        advanceBtn.disabled = false;
        concludeBtn.disabled = false;
    } else {
        advanceBtn.disabled = true;
        concludeBtn.disabled = true;
    }

    // Populate addressed-to dropdown with participants
    const addressedTo = document.getElementById('pmAddressedTo');
    if (addressedTo && meeting.participants) {
        addressedTo.innerHTML = '<option value="">To: Everyone</option>' +
            meeting.participants.map(p => {
                // Handle both object and string participant formats
                const agentId = typeof p === 'string' ? p : p.agent_id;
                return `<option value="${agentId}">${agentId}</option>`;
            }).join('');
    }
}

/**
 * Render meeting transcript
 */
function renderMeetingTranscript(turns) {
    const transcript = document.getElementById('meetingTranscript');

    if (!turns || turns.length === 0) {
        transcript.innerHTML = `
            <div class="text-center text-gray-400 py-8">
                Meeting has started. Click "Advance Round" to have participants speak,
                or interject with your own statement below.
            </div>
        `;
        return;
    }

    transcript.innerHTML = turns.map(turn => {
        const isPM = turn.is_player_input;
        const alignClass = isPM ? 'ml-auto bg-blue-100' : 'bg-gray-100';
        const maxWidth = 'max-w-[80%]';

        const actionBadge = turn.action_type && turn.action_type !== 'statement'
            ? `<span class="text-xs px-2 py-0.5 rounded bg-gray-200 text-gray-600 ml-2">${turn.action_type}</span>`
            : '';

        const toneIcon = {
            'calm': '',
            'assertive': '💪',
            'concerned': '😟',
            'angry': '😠',
            'hopeful': '🙏',
            'frustrated': '😤'
        }[turn.emotional_tone] || '';

        return `
            <div class="flex ${isPM ? 'justify-end' : 'justify-start'} mb-4">
                <div class="${maxWidth} ${alignClass} rounded-lg p-3">
                    <div class="flex items-center gap-2 mb-1">
                        <span class="font-medium text-sm">${turn.speaker_agent_id}</span>
                        ${actionBadge}
                        <span>${toneIcon}</span>
                    </div>
                    <div class="text-gray-800">${turn.content}</div>
                </div>
            </div>
        `;
    }).join('');

    // Scroll to bottom
    transcript.scrollTop = transcript.scrollHeight;
}

/**
 * Refresh meeting room data
 */
async function refreshMeetingRoom() {
    if (!state.activeMeeting) return;

    try {
        const result = await api.getMeeting(state.activeMeeting.meeting_id);
        if (result.status === 'success') {
            state.activeMeeting = result.meeting;
            renderMeetingRoom(result.meeting);
        }
    } catch (error) {
        console.error('Failed to refresh meeting:', error);
    }
}

/**
 * Submit PM interjection
 */
async function submitPMInterjection() {
    if (!state.activeMeeting) return;

    const inputEl = document.getElementById('pmMeetingInput');
    const content = inputEl?.value.trim();
    if (!content) return;

    const actionType = document.getElementById('pmActionType')?.value || 'statement';
    const tone = document.getElementById('pmTone')?.value || 'calm';
    const addressedTo = document.getElementById('pmAddressedTo')?.value;
    const addressedToList = addressedTo ? [addressedTo] : [];

    try {
        const btn = document.getElementById('submitPmMeetingInput');
        if (btn) {
            btn.disabled = true;
            btn.textContent = 'Sending...';
        }

        const result = await api.meetingInterject(
            state.activeMeeting.meeting_id,
            content,
            actionType,
            addressedToList,
            tone
        );

        if (result.status === 'success') {
            // Clear input
            if (inputEl) inputEl.value = '';

            // Refresh meeting room
            await refreshMeetingRoom();
        } else {
            components.showToast(result.message || 'Failed to send', 'error');
        }
    } catch (error) {
        console.error('Failed to interject:', error);
        components.showToast('Failed to send interjection', 'error');
    } finally {
        const btn = document.getElementById('submitPmMeetingInput');
        if (btn) {
            btn.disabled = false;
            btn.textContent = 'Speak';
        }
    }
}

/**
 * Advance to next meeting round
 */
async function advanceMeetingRound() {
    if (!state.activeMeeting) return;

    try {
        const btn = document.getElementById('advanceRoundBtn');
        btn.disabled = true;
        btn.textContent = 'Processing...';

        const result = await api.advanceMeetingRound(state.activeMeeting.meeting_id);

        if (result.status === 'success') {
            state.activeMeeting = result.meeting;
            renderMeetingRoom(result.meeting);
            components.showToast(`Round ${result.meeting.current_round} complete`, 'success');
        } else {
            components.showToast(result.message || 'Failed to advance', 'error');
        }
    } catch (error) {
        console.error('Failed to advance round:', error);
        components.showToast('Failed to advance round', 'error');
    } finally {
        const btn = document.getElementById('advanceRoundBtn');
        btn.disabled = false;
        btn.textContent = 'Advance Round';
    }
}

/**
 * Conclude the meeting
 */
async function concludeMeeting() {
    if (!state.activeMeeting) return;

    if (!confirm('Conclude this meeting? This will generate outcomes and resume simulation.')) return;

    try {
        const btn = document.getElementById('concludeMeetingBtn');
        btn.disabled = true;
        btn.textContent = 'Concluding...';

        const result = await api.concludeMeeting(state.activeMeeting.meeting_id);

        if (result.status === 'success') {
            closeMeetingRoom();
            state.activeMeeting = null;

            // Show outcome modal
            displayMeetingOutcome(result.meeting);

            components.showToast('Meeting concluded - Simulation resumed', 'success');
            await loadMeetings();
        } else {
            components.showToast(result.message || 'Failed to conclude', 'error');
        }
    } catch (error) {
        console.error('Failed to conclude meeting:', error);
        components.showToast('Failed to conclude meeting', 'error');
    } finally {
        const btn = document.getElementById('concludeMeetingBtn');
        btn.disabled = false;
        btn.textContent = 'Conclude Meeting';
    }
}

/**
 * Abort the meeting without outcomes
 */
async function abortMeeting() {
    if (!state.activeMeeting) return;

    if (!confirm('Abort this meeting? No outcomes will be recorded and simulation will resume.')) return;

    try {
        const result = await api.abortMeeting(state.activeMeeting.meeting_id);

        if (result.status === 'success') {
            closeMeetingRoom();
            state.activeMeeting = null;
            components.showToast('Meeting aborted - Simulation resumed', 'info');
            await loadMeetings();
        } else {
            components.showToast(result.message || 'Failed to abort', 'error');
        }
    } catch (error) {
        console.error('Failed to abort meeting:', error);
        components.showToast('Failed to abort meeting', 'error');
    }
}

/**
 * View outcome of a concluded meeting
 */
async function viewMeetingOutcome(meetingId) {
    try {
        const result = await api.getMeeting(meetingId);

        if (result.status === 'success') {
            displayMeetingOutcome(result.meeting);
        } else {
            components.showToast('Failed to load meeting details', 'error');
        }
    } catch (error) {
        console.error('Failed to view meeting outcome:', error);
    }
}

/**
 * Display meeting outcome in modal
 */
function displayMeetingOutcome(meeting) {
    const outcome = meeting.outcome;

    // Title
    document.getElementById('outcomeModalTitle').textContent = meeting.title;

    // Outcome type banner
    const banner = document.getElementById('outcomeTypeBanner');
    const typeColors = {
        'full_agreement': 'bg-green-500',
        'partial_agreement': 'bg-yellow-500',
        'no_agreement': 'bg-red-500',
        'aborted': 'bg-gray-500'
    };
    banner.className = `py-2 px-4 rounded text-white text-center font-medium ${typeColors[outcome?.outcome_type] || 'bg-gray-500'}`;
    banner.textContent = formatOutcomeType(outcome?.outcome_type);

    // Summary
    document.getElementById('outcomeSummary').textContent = outcome?.summary || 'No summary available';

    // Agreements
    const agreementsList = document.getElementById('outcomeAgreements');
    if (outcome?.agreements && outcome.agreements.length > 0) {
        agreementsList.innerHTML = outcome.agreements.map(a =>
            `<li class="mb-2">
                <strong>${a.topic || 'Agreement'}:</strong> ${a.terms || a.description || a}
                <span class="text-xs text-gray-500 block">Parties: ${a.parties?.join(', ') || 'All'}</span>
            </li>`
        ).join('');
    } else {
        agreementsList.innerHTML = '<li class="text-gray-400">No agreements reached</li>';
    }

    // Commitments
    const commitmentsList = document.getElementById('outcomeCommitments');
    if (outcome?.commitments && outcome.commitments.length > 0) {
        commitmentsList.innerHTML = outcome.commitments.map(c =>
            `<li class="mb-2">
                <strong>${c.who || 'Party'}:</strong> ${c.what || c}
                ${c.when ? `<span class="text-xs text-gray-500 block">Due: ${c.when}</span>` : ''}
            </li>`
        ).join('');
    } else {
        commitmentsList.innerHTML = '<li class="text-gray-400">No commitments made</li>';
    }

    // Events generated
    const eventsList = document.getElementById('outcomeEvents');
    if (outcome?.events_generated && outcome.events_generated.length > 0) {
        eventsList.innerHTML = outcome.events_generated.map(e =>
            `<li class="text-sm text-gray-700">${e.summary || e}</li>`
        ).join('');
    } else {
        eventsList.innerHTML = '<li class="text-gray-400">No events generated</li>';
    }

    // Show modal
    components.showModal('meetingOutcomeModal');
}

/**
 * Update active meeting panel
 */
function updateActiveMeetingPanel(meeting) {
    const panel = document.getElementById('activeMeetingPanel');
    const info = document.getElementById('activeMeetingInfo');

    if (meeting && meeting.status === 'active') {
        panel?.classList.remove('hidden');

        const titleEl = document.getElementById('activeMeetingTitle');
        const typeEl = document.getElementById('activeMeetingType');

        if (titleEl) titleEl.textContent = meeting.title;
        if (typeEl) typeEl.textContent = `${formatMeetingType(meeting.meeting_type)} - Round ${meeting.current_round}`;
    } else {
        panel?.classList.add('hidden');
    }
}

/**
 * Render meeting requests
 */
function renderMeetingRequests(requests) {
    const container = document.getElementById('meetingRequestsList');
    const countBadge = document.getElementById('meetingRequestsCount');
    if (countBadge) countBadge.textContent = requests?.length || 0;

    if (!requests || requests.length === 0) {
        container.innerHTML = '<p class="text-gray-400 text-center py-4">No pending requests</p>';
        return;
    }

    container.innerHTML = requests.map(req => {
        const urgencyColors = {
            'immediate': 'bg-red-100 text-red-800',
            'high': 'bg-orange-100 text-orange-800',
            'normal': 'bg-blue-100 text-blue-800'
        };
        const urgencyClass = urgencyColors[req.urgency] || 'bg-gray-100 text-gray-800';

        return `
            <div class="border rounded p-3 mb-2">
                <div class="flex justify-between items-start mb-2">
                    <div>
                        <span class="font-medium">${formatMeetingType(req.meeting_type)}</span>
                        <span class="px-2 py-0.5 text-xs rounded ${urgencyClass} ml-2">${req.urgency}</span>
                    </div>
                    <span class="text-xs text-gray-500">From: ${req.requested_by}</span>
                </div>
                <p class="text-sm text-gray-700 mb-2">${req.reason}</p>
                <div class="text-xs text-gray-500 mb-2">
                    Suggested: ${req.suggested_participants?.join(', ') || 'None'}
                </div>
                <div class="flex gap-2">
                    <button class="approve-meeting-request-btn px-3 py-1 text-sm bg-green-500 text-white rounded hover:bg-green-600"
                        data-request-id="${req.request_id}">Approve</button>
                    <button class="reject-meeting-request-btn px-3 py-1 text-sm bg-red-500 text-white rounded hover:bg-red-600"
                        data-request-id="${req.request_id}">Reject</button>
                </div>
            </div>
        `;
    }).join('');
}

/**
 * Render scheduled meetings
 */
function renderScheduledMeetings(meetings) {
    const container = document.getElementById('scheduledMeetingsList');

    if (!meetings || meetings.length === 0) {
        container.innerHTML = '<p class="text-gray-400 text-center py-4">No scheduled meetings</p>';
        return;
    }

    container.innerHTML = meetings.map(m => {
        const scheduledTime = m.scheduled_game_time
            ? new Date(m.scheduled_game_time).toLocaleString()
            : 'ASAP';

        return `
            <div class="border rounded p-3 mb-2">
                <div class="flex justify-between items-start">
                    <div>
                        <div class="font-medium">${m.title}</div>
                        <div class="text-xs text-gray-500">${formatMeetingType(m.meeting_type)}</div>
                    </div>
                    <span class="text-xs text-gray-400">${scheduledTime}</span>
                </div>
                <div class="text-sm text-gray-600 mt-1">
                    ${m.participants?.length || 0} participants
                </div>
                <button class="start-meeting-btn mt-2 px-3 py-1 text-sm bg-blue-500 text-white rounded hover:bg-blue-600"
                    data-meeting-id="${m.meeting_id}">Start Meeting</button>
            </div>
        `;
    }).join('');
}

/**
 * Render meeting history
 */
function renderMeetingHistory(meetings) {
    const container = document.getElementById('meetingHistoryList');

    if (!meetings || meetings.length === 0) {
        container.innerHTML = '<p class="text-gray-400 text-center py-4">No meeting history</p>';
        return;
    }

    container.innerHTML = meetings.map(m => {
        const endedTime = m.ended_at
            ? new Date(m.ended_at).toLocaleString()
            : '--';

        const outcomeType = m.outcome?.outcome_type || 'unknown';
        const outcomeColors = {
            'full_agreement': 'text-green-600',
            'partial_agreement': 'text-yellow-600',
            'no_agreement': 'text-red-600',
            'aborted': 'text-gray-600'
        };
        const outcomeClass = outcomeColors[outcomeType] || 'text-gray-600';

        return `
            <div class="border rounded p-3 mb-2">
                <div class="flex justify-between items-start">
                    <div>
                        <div class="font-medium">${m.title}</div>
                        <div class="text-xs text-gray-500">${formatMeetingType(m.meeting_type)}</div>
                    </div>
                    <span class="text-xs text-gray-400">${endedTime}</span>
                </div>
                <div class="text-sm ${outcomeClass} mt-1">
                    ${formatOutcomeType(outcomeType)}
                </div>
                <button class="view-meeting-btn mt-2 px-3 py-1 text-xs bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
                    data-meeting-id="${m.meeting_id}">View Details</button>
            </div>
        `;
    }).join('');
}

/**
 * Format meeting type for display
 */
function formatMeetingType(type) {
    const labels = {
        'cabinet_war_room': 'Cabinet War Room',
        'negotiation': 'Negotiation',
        'leader_talk': 'Leader Talk',
        'agent_briefing': 'Agent Briefing'
    };
    return labels[type] || type;
}

/**
 * Format outcome type for display
 */
function formatOutcomeType(type) {
    const labels = {
        'full_agreement': 'Full Agreement',
        'partial_agreement': 'Partial Agreement',
        'no_agreement': 'No Agreement',
        'aborted': 'Aborted'
    };
    return labels[type] || type || 'Unknown';
}

// =============================================================================
// MAP STATE FUNCTIONS
// =============================================================================

/**
 * Map state cache
 */
let mapStateCache = {
    zones: [],
    entities: [],
    locations: [],
    events: []
};

/**
 * Load map state data
 */
async function loadMapState() {
    try {
        // Fetch all map data in parallel
        const [stateResult, zonesResult] = await Promise.all([
            api.getMapState(),
            api.getMapZones()
        ]);

        if (stateResult.status === 'success') {
            const mapState = stateResult.map_state;

            // Update counts
            document.getElementById('mapLocationsCount').textContent = mapState.static_locations?.length || 0;
            document.getElementById('mapEntitiesCount').textContent = mapState.tracked_entities?.length || 0;
            document.getElementById('mapEventsCount').textContent = mapState.active_geo_events?.length || 0;

            // Cache data
            mapStateCache.locations = mapState.static_locations || [];
            mapStateCache.entities = mapState.tracked_entities || [];
            mapStateCache.events = mapState.active_geo_events || [];

            // Render tables
            renderMapEntities(mapStateCache.entities);
            renderMapLocations(mapStateCache.locations);
            renderMapEvents(mapStateCache.events);
        }

        if (zonesResult.status === 'success') {
            document.getElementById('mapZonesCount').textContent = zonesResult.count || 0;
            mapStateCache.zones = zonesResult.zones || [];
            populateZoneSelects();
        }

        // Show move entity section
        document.getElementById('moveEntitySection').classList.remove('hidden');

    } catch (error) {
        console.error('Failed to load map state:', error);
        components.showToast('Failed to load map state', 'error');
    }
}

/**
 * Render tracked entities table
 */
function renderMapEntities(entities) {
    const tbody = document.getElementById('mapEntitiesTable');

    if (!entities || entities.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="px-4 py-4 text-gray-400 text-center">No tracked entities</td></tr>';
        return;
    }

    tbody.innerHTML = entities.map(entity => {
        const statusBadge = entity.is_moving
            ? '<span class="px-2 py-1 text-xs rounded bg-yellow-100 text-yellow-800">Moving</span>'
            : '<span class="px-2 py-1 text-xs rounded bg-green-100 text-green-800">Stationary</span>';

        const categoryColors = {
            'hostage_group': 'text-red-600',
            'high_value_target': 'text-purple-600',
            'military_unit': 'text-blue-600',
            'leader': 'text-orange-600'
        };
        const catColor = categoryColors[entity.category] || 'text-gray-600';

        const difficulty = (entity.detection_difficulty * 100).toFixed(0);
        const difficultyColor = entity.detection_difficulty > 0.7 ? 'text-red-600' : 'text-green-600';

        const destInfo = entity.is_moving && entity.destination_zone
            ? `<span class="text-xs text-gray-500"> -> ${entity.destination_zone}</span>`
            : '';

        return `<tr class="hover:bg-gray-50">
            <td class="px-4 py-2 text-sm font-medium">${entity.name}</td>
            <td class="px-4 py-2 text-sm ${catColor}">${entity.category}</td>
            <td class="px-4 py-2 text-sm">${entity.owner_entity}</td>
            <td class="px-4 py-2 text-sm">${entity.current_zone}${destInfo}</td>
            <td class="px-4 py-2">${statusBadge}</td>
            <td class="px-4 py-2 text-sm ${difficultyColor}">${difficulty}%</td>
            <td class="px-4 py-2">
                <button class="text-xs text-blue-600 hover:text-blue-800 mr-2"
                    onclick="selectEntityForMove('${entity.entity_id}')">Move</button>
            </td>
        </tr>`;
    }).join('');
}

/**
 * Render static locations grid
 */
function renderMapLocations(locations) {
    const grid = document.getElementById('mapLocationsGrid');

    if (!locations || locations.length === 0) {
        grid.innerHTML = '<p class="text-gray-400">No static locations</p>';
        return;
    }

    const typeIcons = {
        'military_base': '🏰',
        'nuclear_plant': '☢️',
        'border_crossing': '🚧',
        'government_hq': '🏛️',
        'tunnel_entrance': '🕳️',
        'airport': '✈️',
        'port': '⚓',
        'hospital': '🏥',
        'refugee_camp': '🏕️'
    };

    grid.innerHTML = locations.map(loc => {
        const icon = typeIcons[loc.location_type] || '📍';
        const coords = loc.coordinates;
        return `<div class="p-3 border rounded bg-gray-50 text-sm">
            <div class="font-medium">${icon} ${loc.name}</div>
            <div class="text-xs text-gray-500">${loc.location_type}</div>
            <div class="text-xs text-gray-400">${loc.owner_entity}</div>
            <div class="text-xs text-gray-400">${coords.lat.toFixed(4)}, ${coords.lon.toFixed(4)}</div>
        </div>`;
    }).join('');
}

/**
 * Render active geo events
 */
function renderMapEvents(events) {
    const container = document.getElementById('mapEventsContainer');

    if (!events || events.length === 0) {
        container.innerHTML = '<p class="text-gray-400 text-sm">No active events</p>';
        return;
    }

    const typeColors = {
        'missile_launch': 'bg-red-100 text-red-800',
        'air_strike': 'bg-orange-100 text-orange-800',
        'interceptor': 'bg-blue-100 text-blue-800',
        'force_movement': 'bg-green-100 text-green-800',
        'battle_zone': 'bg-purple-100 text-purple-800',
        'intel_operation': 'bg-yellow-100 text-yellow-800',
        'force_deployment': 'bg-indigo-100 text-indigo-800',
        'hostage_transfer': 'bg-pink-100 text-pink-800'
    };

    container.innerHTML = events.map(evt => {
        const typeClass = typeColors[evt.event_type] || 'bg-gray-100 text-gray-800';
        const origin = evt.origin_zone || '--';
        const dest = evt.destination_zone || evt.center_zone || '--';

        return `<div class="p-3 border rounded flex items-center gap-4">
            <span class="px-2 py-1 text-xs rounded ${typeClass}">${evt.event_type}</span>
            <span class="text-sm">${origin} → ${dest}</span>
            <span class="text-xs text-gray-500">${evt.description || ''}</span>
            <span class="text-xs text-gray-400 ml-auto">${evt.duration_seconds}s</span>
        </div>`;
    }).join('');
}

/**
 * Populate zone select dropdowns
 */
function populateZoneSelects() {
    const destSelect = document.getElementById('moveDestZoneSelect');
    const entitySelect = document.getElementById('moveEntitySelect');

    // Populate zones
    destSelect.innerHTML = mapStateCache.zones.map(zone =>
        `<option value="${zone}">${zone}</option>`
    ).join('');

    // Populate entities
    entitySelect.innerHTML = mapStateCache.entities.map(e =>
        `<option value="${e.entity_id}">${e.name} (${e.current_zone})</option>`
    ).join('');
}

/**
 * Select an entity for movement
 */
function selectEntityForMove(entityId) {
    document.getElementById('moveEntitySelect').value = entityId;
    document.getElementById('moveEntitySection').scrollIntoView({ behavior: 'smooth' });
}

/**
 * Move entity to destination
 */
async function moveEntity() {
    const entityId = document.getElementById('moveEntitySelect').value;
    const destZone = document.getElementById('moveDestZoneSelect').value;
    const travelTime = parseInt(document.getElementById('moveTravelTime').value) || 30;

    if (!entityId || !destZone) {
        components.showToast('Please select entity and destination', 'error');
        return;
    }

    try {
        const result = await api.moveEntity(entityId, destZone, travelTime);
        if (result.status === 'success') {
            components.showToast(`Entity moving to ${destZone} (ETA: ${travelTime} min)`, 'success');
            await loadMapState();
        } else {
            components.showToast(result.message || 'Failed to move entity', 'error');
        }
    } catch (error) {
        console.error('Failed to move entity:', error);
        components.showToast('Failed to move entity', 'error');
    }
}

/**
 * Teleport entity to destination (instant)
 */
async function teleportEntity() {
    const entityId = document.getElementById('moveEntitySelect').value;
    const destZone = document.getElementById('moveDestZoneSelect').value;

    if (!entityId || !destZone) {
        components.showToast('Please select entity and destination', 'error');
        return;
    }

    try {
        const result = await api.teleportEntity(entityId, destZone);
        if (result.status === 'success') {
            components.showToast(`Entity teleported to ${destZone}`, 'success');
            await loadMapState();
        } else {
            components.showToast(result.message || 'Failed to teleport entity', 'error');
        }
    } catch (error) {
        console.error('Failed to teleport entity:', error);
        components.showToast('Failed to teleport entity', 'error');
    }
}

/**
 * Set up Map State event listeners
 */
function setupMapStateListeners() {
    document.getElementById('refreshMapStateBtn')?.addEventListener('click', loadMapState);
    document.getElementById('moveEntityBtn')?.addEventListener('click', moveEntity);
    document.getElementById('teleportEntityBtn')?.addEventListener('click', teleportEntity);
}

// =============================================================================
// KPI FUNCTIONS
// =============================================================================

/**
 * Load all entity KPIs
 */
async function loadKPIs() {
    try {
        const result = await api.getKPIs();
        if (result.status === 'success') {
            renderKPIEntities(result.kpis);
            document.getElementById('kpiLastUpdated').textContent = `Last updated: ${new Date().toLocaleTimeString()}`;
        } else {
            console.error('Failed to load KPIs:', result.message);
        }
    } catch (error) {
        console.error('Failed to load KPIs:', error);
        document.getElementById('kpiEntitiesContainer').innerHTML = '<p class="text-red-500">Failed to load KPIs</p>';
    }
}

/**
 * Render KPI entities as collapsible cards
 */
function renderKPIEntities(kpis) {
    const container = document.getElementById('kpiEntitiesContainer');
    const entities = Object.keys(kpis);

    if (entities.length === 0) {
        container.innerHTML = '<p class="text-gray-400 text-center py-8">No KPI data available</p>';
        return;
    }

    container.innerHTML = entities.map(entityId => {
        const data = kpis[entityId];
        const lastUpdated = data.last_updated ? new Date(data.last_updated).toLocaleString() : 'Never';

        return `
        <div class="border rounded-lg overflow-hidden">
            <button class="kpi-toggle-btn w-full flex justify-between items-center bg-gray-100 hover:bg-gray-200 p-4 text-left" data-entity="${entityId}">
                <div class="flex items-center gap-3">
                    <span class="font-medium text-gray-800">${entityId}</span>
                    <span class="text-xs text-gray-500">Updated: ${lastUpdated}</span>
                </div>
                <svg class="kpi-chevron w-5 h-5 text-gray-500 transform transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
                </svg>
            </button>
            <div class="kpi-content hidden p-4 bg-white">
                <div class="grid grid-cols-2 gap-6">
                    <!-- Const Metrics -->
                    <div>
                        <h5 class="text-sm font-medium text-gray-600 mb-3 uppercase">Constant Metrics</h5>
                        <table class="w-full text-sm">
                            <tbody>
                                ${renderMetricsTable(data.const_metrics || {})}
                            </tbody>
                        </table>
                    </div>
                    <!-- Dynamic Metrics -->
                    <div>
                        <h5 class="text-sm font-medium text-gray-600 mb-3 uppercase">Dynamic Metrics</h5>
                        <table class="w-full text-sm">
                            <tbody>
                                ${renderMetricsTable(data.dynamic_metrics || {})}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
        `;
    }).join('');

    // Add toggle listeners
    container.querySelectorAll('.kpi-toggle-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const content = btn.nextElementSibling;
            const chevron = btn.querySelector('.kpi-chevron');
            content.classList.toggle('hidden');
            chevron.classList.toggle('rotate-180');
        });
    });
}

/**
 * Render metrics as table rows
 */
function renderMetricsTable(metrics) {
    return Object.entries(metrics).map(([key, value]) => {
        let displayValue = value;
        if (typeof value === 'boolean') {
            displayValue = value ? '<span class="text-green-600">Yes</span>' : '<span class="text-red-600">No</span>';
        } else if (typeof value === 'number') {
            displayValue = value.toLocaleString();
        }
        const formattedKey = key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
        return `
        <tr class="border-b border-gray-100">
            <td class="py-2 text-gray-600">${formattedKey}</td>
            <td class="py-2 text-right font-mono">${displayValue}</td>
        </tr>
        `;
    }).join('');
}

/**
 * Load KPI change log (filtered activity log)
 */
async function loadKPIChangeLog() {
    try {
        const entityFilter = document.getElementById('kpiLogEntityFilter').value;
        const result = await api.getActivityLog(entityFilter || null, 'kpi', 50);
        renderKPIChangeLog(result.activities || []);
    } catch (error) {
        console.error('Failed to load KPI change log:', error);
    }
}

/**
 * Render KPI change log
 */
function renderKPIChangeLog(activities) {
    const container = document.getElementById('kpiChangeLog');

    if (activities.length === 0) {
        container.innerHTML = '<p class="text-gray-500">No KPI changes recorded yet.</p>';
        return;
    }

    container.innerHTML = activities.map(activity => {
        const dt = new Date(activity.timestamp);
        const timeStr = dt.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        const dateStr = dt.toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit' });

        return `<div class="mb-1 flex gap-2">
            <span class="text-gray-500">[${dateStr} ${timeStr}]</span>
            <span class="text-cyan-400">${activity.agent_id}:</span>
            <span class="text-orange-400">${activity.details || activity.action}</span>
        </div>`;
    }).join('');
}

/**
 * Manually trigger event resolution
 */
async function resolveNow() {
    try {
        const btn = document.getElementById('resolveNowBtn');
        btn.disabled = true;
        btn.textContent = 'Resolving...';

        const result = await api.resolveNow();

        if (result.status === 'success') {
            const resolved = result.events_resolved || 0;
            const kpiChanges = result.kpi_changes || 0;
            components.showToast(`Resolved ${resolved} events, ${kpiChanges} KPI changes`, 'success');
            // Refresh events and KPIs
            await loadSimulationEvents();
            if (state.currentTab === 'kpis') {
                await loadKPIs();
                await loadKPIChangeLog();
            }
        } else {
            components.showToast(result.message || 'Resolution failed', 'error');
        }
    } catch (error) {
        console.error('Failed to resolve events:', error);
        components.showToast('Failed to resolve events', 'error');
    } finally {
        const btn = document.getElementById('resolveNowBtn');
        btn.disabled = false;
        btn.textContent = 'Resolve Pending';
    }
}

// =============================================================================
// GAME MANAGEMENT FUNCTIONS
// =============================================================================

/**
 * Load and display the list of saved games
 */
async function loadGamesList() {
    try {
        const result = await api.listGames();
        if (result.status === 'success') {
            renderGamesList(result.games, result.current_game);

            // Update current game banner
            const currentGame = result.games.find(g => g.game_id === result.current_game);
            updateCurrentGameBanner(currentGame);

            // Show migration section if no games exist
            const migrationSection = document.getElementById('migrationSection');
            if (migrationSection) {
                if (!result.current_game && result.games.length === 0) {
                    migrationSection.classList.remove('hidden');
                } else {
                    migrationSection.classList.add('hidden');
                }
            }
        }
    } catch (error) {
        console.error('Failed to load games:', error);
        components.showToast('Failed to load games list', 'error');
    }
}

/**
 * Render the games list
 */
function renderGamesList(games, currentGameId) {
    const container = document.getElementById('gamesList');
    if (!container) return;

    if (!games || games.length === 0) {
        container.innerHTML = '<p class="text-gray-400">No saved games found. Run migration or create a new game.</p>';
        return;
    }

    container.innerHTML = games.map(game => {
        const isActive = game.game_id === currentGameId;
        const borderClass = isActive ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-300';

        return `
            <div class="p-4 border rounded-lg ${borderClass} transition-colors">
                <div class="flex items-center justify-between">
                    <div>
                        <h4 class="font-semibold text-gray-800">${escapeHtml(game.display_name)}</h4>
                        <p class="text-sm text-gray-500">ID: ${escapeHtml(game.game_id)}</p>
                        <p class="text-xs text-gray-400">
                            Created: ${new Date(game.created_at).toLocaleDateString()}
                            | Last played: ${new Date(game.last_played).toLocaleDateString()}
                        </p>
                        ${game.game_clock ? `<p class="text-xs text-gray-400">Game time: ${game.game_clock}</p>` : ''}
                    </div>
                    <div class="flex gap-2">
                        ${isActive ?
                            '<span class="px-3 py-1 bg-blue-600 text-white rounded text-sm">Active</span>' :
                            `<button class="load-game-btn px-3 py-1 bg-green-600 hover:bg-green-700 text-white rounded text-sm transition-colors"
                                     data-game-id="${escapeHtml(game.game_id)}">
                                Load
                            </button>
                            <button class="delete-game-btn px-3 py-1 bg-red-500 hover:bg-red-600 text-white rounded text-sm transition-colors"
                                     data-game-id="${escapeHtml(game.game_id)}">
                                Delete
                            </button>`
                        }
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

/**
 * Update the current game banner
 */
function updateCurrentGameBanner(game) {
    const nameEl = document.getElementById('currentGameName');
    const clockEl = document.getElementById('currentGameClock');

    if (nameEl) {
        if (game) {
            nameEl.textContent = game.display_name || game.game_id;
        } else {
            nameEl.textContent = 'No game active (run migration first)';
        }
    }
    if (clockEl) {
        clockEl.textContent = game && game.game_clock ? `Game Time: ${game.game_clock}` : '';
    }
}

/**
 * Create a new game
 */
async function createNewGame() {
    const gameIdInput = document.getElementById('newGameId');
    const displayNameInput = document.getElementById('newGameName');
    const templateSelect = document.getElementById('newGameTemplate');

    const gameId = gameIdInput?.value.trim();
    const displayName = displayNameInput?.value.trim();
    const template = templateSelect?.value || 'october7';

    if (!gameId || !displayName) {
        components.showToast('Please fill in Game ID and Display Name', 'error');
        return;
    }

    // Validate game ID format
    if (!/^[a-zA-Z0-9_-]+$/.test(gameId)) {
        components.showToast('Game ID can only contain letters, numbers, hyphens, and underscores', 'error');
        return;
    }

    const btn = document.getElementById('createGameBtn');
    try {
        btn.disabled = true;
        btn.textContent = 'Creating...';

        const result = await api.createGame(gameId, displayName, template);
        if (result.status === 'success') {
            components.showToast(`Game '${displayName}' created!`, 'success');
            gameIdInput.value = '';
            displayNameInput.value = '';
            await loadGamesList();
        } else {
            components.showToast(result.message || result.detail || 'Failed to create game', 'error');
        }
    } catch (error) {
        console.error('Failed to create game:', error);
        components.showToast('Failed to create game', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Create New Game';
    }
}

/**
 * Handle game action clicks (load/delete)
 */
async function handleGameAction(event) {
    const loadBtn = event.target.closest('.load-game-btn');
    const deleteBtn = event.target.closest('.delete-game-btn');

    if (loadBtn) {
        const gameId = loadBtn.dataset.gameId;

        // Check if simulation is running
        if (state.simulationStatus?.is_running) {
            components.showToast('Stop simulation before switching games', 'error');
            return;
        }

        try {
            loadBtn.disabled = true;
            loadBtn.textContent = 'Loading...';

            const result = await api.loadGame(gameId);
            if (result.status === 'success') {
                components.showToast(`Loaded game: ${gameId}`, 'success');
                // Refresh everything
                await loadGamesList();
                await loadAgents();
                await loadSimulationStatus();
            } else {
                components.showToast(result.message || result.detail || 'Failed to load game', 'error');
            }
        } catch (error) {
            console.error('Failed to load game:', error);
            components.showToast('Failed to load game', 'error');
        } finally {
            loadBtn.disabled = false;
            loadBtn.textContent = 'Load';
        }
    }

    if (deleteBtn) {
        const gameId = deleteBtn.dataset.gameId;

        if (!confirm(`Delete game '${gameId}'? This cannot be undone.`)) {
            return;
        }

        try {
            deleteBtn.disabled = true;
            deleteBtn.textContent = 'Deleting...';

            const result = await api.deleteGame(gameId);
            if (result.status === 'success') {
                components.showToast(`Deleted game: ${gameId}`, 'success');
                await loadGamesList();
            } else {
                components.showToast(result.message || result.detail || 'Failed to delete game', 'error');
            }
        } catch (error) {
            console.error('Failed to delete game:', error);
            components.showToast('Failed to delete game', 'error');
        } finally {
            deleteBtn.disabled = false;
            deleteBtn.textContent = 'Delete';
        }
    }
}

/**
 * Run the data migration
 */
async function runMigration() {
    if (!confirm('This will backup your current data and migrate to the new game system. Continue?')) {
        return;
    }

    const btn = document.getElementById('migrateBtn');
    try {
        btn.disabled = true;
        btn.textContent = 'Migrating...';

        const result = await api.migrateData();
        if (result.status === 'success') {
            components.showToast('Migration successful!', 'success');
            document.getElementById('migrationSection')?.classList.add('hidden');
            await loadGamesList();
            await loadAgents();
            await loadSimulationStatus();
        } else {
            components.showToast(result.message || result.detail || 'Migration failed', 'error');
        }
    } catch (error) {
        console.error('Migration failed:', error);
        components.showToast('Migration failed', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Migrate Data';
    }
}

/**
 * Escape HTML for safe display
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Set up game management event listeners
 */
function setupGameManagementListeners() {
    // Create game button
    safeAddListener('createGameBtn', 'click', createNewGame);

    // Migrate button
    safeAddListener('migrateBtn', 'click', runMigration);

    // Refresh games button
    safeAddListener('refreshGamesBtn', 'click', loadGamesList);

    // Games list delegation for load/delete buttons
    const gamesList = document.getElementById('gamesList');
    if (gamesList) {
        gamesList.addEventListener('click', handleGameAction);
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    init();
    setupMapStateListeners();
    setupGameManagementListeners();
});
