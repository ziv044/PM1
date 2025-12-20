/**
 * UI Component Renderers for PM1 Agent Admin Panel
 */

const components = {
    /**
     * Render the agent list in the sidebar
     */
    renderAgentList(agents, selectedAgentId) {
        const container = document.getElementById('agentList');

        if (Object.keys(agents).length === 0) {
            container.innerHTML = '<p class="text-gray-400 text-sm">No agents yet</p>';
            return;
        }

        container.innerHTML = Object.entries(agents).map(([id, agent]) => {
            const isEnabled = agent.is_enabled !== false; // default to true if not set
            const statusColor = isEnabled ? 'bg-green-500' : 'bg-gray-500';
            const statusText = isEnabled ? 'ON' : 'OFF';
            const opacityClass = isEnabled ? '' : 'opacity-60';

            return `
            <div class="agent-card p-3 rounded cursor-pointer transition-colors ${id === selectedAgentId ? 'bg-blue-600' : 'bg-gray-700 hover:bg-gray-600'} ${opacityClass}"
                 data-agent-id="${this.escapeHtml(id)}">
                <div class="flex items-center justify-between">
                    <div class="font-medium truncate flex-1">${this.escapeHtml(id)}</div>
                    <button class="toggle-enabled-btn ml-2 px-2 py-0.5 text-xs rounded ${statusColor} text-white hover:opacity-80"
                            data-agent-id="${this.escapeHtml(id)}"
                            title="${isEnabled ? 'Click to disable' : 'Click to enable'}">
                        ${statusText}
                    </button>
                </div>
                <div class="text-xs text-gray-300 truncate">${this.escapeHtml(agent.model)}</div>
            </div>
        `}).join('');
    },

    /**
     * Render agent details tab - now with editable form fields
     */
    renderAgentDetails(agent, agentId) {
        // Agent ID remains read-only text
        document.getElementById('detailAgentId').textContent = agentId;

        // Form fields - use .value for inputs/selects/textareas
        document.getElementById('detailModel').value = agent.model || 'claude-sonnet-4-20250514';
        document.getElementById('detailSystemPrompt').value = agent.system_prompt || '';

        // Simulation properties
        document.getElementById('detailEntityType').value = agent.entity_type || 'System';
        document.getElementById('detailEventFrequency').value = agent.event_frequency || 60;
        document.getElementById('detailAgentCategory').value = agent.agent_category || '';

        // Checkboxes
        document.getElementById('detailIsEnabled').checked = agent.is_enabled !== false;
        document.getElementById('detailIsEnemy').checked = agent.is_enemy || false;
        document.getElementById('detailIsWest').checked = agent.is_west || false;
        document.getElementById('detailIsEvilAxis').checked = agent.is_evil_axis || false;
        document.getElementById('detailIsReportingGovernment').checked = agent.is_reporting_government || false;

        // Textareas
        document.getElementById('detailAgenda').value = agent.agenda || '';
        document.getElementById('detailPrimaryObjectives').value = agent.primary_objectives || '';
        document.getElementById('detailHardRules').value = agent.hard_rules || '';

        // Store original values for cancel functionality
        this._originalAgentData = { ...agent, agent_id: agentId };
    },

    /**
     * Get original agent data for cancel functionality
     */
    getOriginalAgentData() {
        return this._originalAgentData;
    },

    /**
     * Render skills list
     */
    renderSkillsList(skills) {
        const container = document.getElementById('skillsList');

        if (!skills || skills.length === 0) {
            container.innerHTML = '<p class="text-gray-400 text-sm">No skills added yet</p>';
            return;
        }

        container.innerHTML = skills.map(skill => `
            <div class="flex items-center justify-between bg-gray-100 p-2 rounded">
                <span class="font-mono text-sm">${this.escapeHtml(skill)}</span>
            </div>
        `).join('');
    },

    /**
     * Render memory list
     */
    renderMemoryList(memory) {
        const container = document.getElementById('memoryList');

        if (!memory || memory.length === 0) {
            container.innerHTML = '<p class="text-gray-400 text-sm">No memory items added yet</p>';
            return;
        }

        container.innerHTML = memory.map((item, index) => `
            <div class="bg-gray-100 p-3 rounded">
                <div class="text-xs text-gray-500 mb-1">Memory #${index + 1}</div>
                <div class="text-sm">${this.escapeHtml(item)}</div>
            </div>
        `).join('');
    },

    /**
     * Render chat conversation
     */
    renderConversation(conversation) {
        const container = document.getElementById('chatMessages');

        if (!conversation || conversation.length === 0) {
            container.innerHTML = '<p class="text-gray-400 text-sm text-center">No messages yet. Start a conversation!</p>';
            return;
        }

        container.innerHTML = conversation.map(msg => {
            const isUser = msg.role === 'user';
            return `
                <div class="flex ${isUser ? 'justify-end' : 'justify-start'}">
                    <div class="max-w-[80%] rounded-lg p-3 ${isUser ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-800'}">
                        <div class="text-xs ${isUser ? 'text-blue-200' : 'text-gray-500'} mb-1">${isUser ? 'You' : 'Agent'}</div>
                        <div class="whitespace-pre-wrap">${this.escapeHtml(msg.content)}</div>
                    </div>
                </div>
            `;
        }).join('');

        // Scroll to bottom
        container.scrollTop = container.scrollHeight;
    },

    /**
     * Add a single message to the chat
     */
    addChatMessage(role, content) {
        const container = document.getElementById('chatMessages');
        const isUser = role === 'user';

        // Remove empty state message if present
        const emptyMsg = container.querySelector('p.text-gray-400');
        if (emptyMsg) emptyMsg.remove();

        const msgHtml = `
            <div class="flex ${isUser ? 'justify-end' : 'justify-start'}">
                <div class="max-w-[80%] rounded-lg p-3 ${isUser ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-800'}">
                    <div class="text-xs ${isUser ? 'text-blue-200' : 'text-gray-500'} mb-1">${isUser ? 'You' : 'Agent'}</div>
                    <div class="whitespace-pre-wrap">${this.escapeHtml(content)}</div>
                </div>
            </div>
        `;

        container.insertAdjacentHTML('beforeend', msgHtml);
        container.scrollTop = container.scrollHeight;
    },

    /**
     * Render logs
     */
    renderLogs(logs) {
        const container = document.getElementById('logsContent');

        if (!logs || logs.length === 0) {
            container.textContent = 'No logs available';
            return;
        }

        container.textContent = logs.join('');
    },

    /**
     * Show a specific tab (legacy - for backwards compatibility)
     */
    showTab(tabName) {
        // Hide all tabs
        document.querySelectorAll('.tab-content').forEach(tab => {
            tab.classList.add('hidden');
        });

        // Remove active state from all tab buttons
        document.querySelectorAll('.tab-btn, .sim-tab-btn').forEach(btn => {
            btn.classList.remove('border-blue-600', 'text-blue-600');
            btn.classList.add('border-transparent');
        });

        // Show selected tab
        const tabElement = document.getElementById(`${tabName}Tab`);
        if (tabElement) {
            tabElement.classList.remove('hidden');
        }

        // Activate tab button (check both types)
        const tabBtn = document.querySelector(`.tab-btn[data-tab="${tabName}"], .sim-tab-btn[data-tab="${tabName}"]`);
        if (tabBtn) {
            tabBtn.classList.add('border-blue-600', 'text-blue-600');
            tabBtn.classList.remove('border-transparent');
        }
    },

    /**
     * Show a simulation-level tab (always accessible)
     */
    showSimulationTab(tabName) {
        // Hide all tab content
        document.querySelectorAll('.tab-content').forEach(tab => {
            tab.classList.add('hidden');
        });

        // Hide empty state
        const emptyState = document.getElementById('emptyState');
        if (emptyState) emptyState.classList.add('hidden');

        // Remove active state from ALL tab buttons (both groups)
        document.querySelectorAll('.tab-btn, .sim-tab-btn').forEach(btn => {
            btn.classList.remove('border-blue-600', 'text-blue-600');
            btn.classList.add('border-transparent');
        });

        // Show selected simulation tab
        const tabElement = document.getElementById(`${tabName}Tab`);
        if (tabElement) {
            tabElement.classList.remove('hidden');
        }

        // Activate simulation tab button
        const tabBtn = document.querySelector(`.sim-tab-btn[data-tab="${tabName}"]`);
        if (tabBtn) {
            tabBtn.classList.add('border-blue-600', 'text-blue-600');
            tabBtn.classList.remove('border-transparent');
        }
    },

    /**
     * Show an agent-level tab (requires agent selection)
     */
    showAgentTab(tabName) {
        // Hide all tab content
        document.querySelectorAll('.tab-content').forEach(tab => {
            tab.classList.add('hidden');
        });

        // Hide empty state
        const emptyState = document.getElementById('emptyState');
        if (emptyState) emptyState.classList.add('hidden');

        // Remove active state from ALL tab buttons (both groups)
        document.querySelectorAll('.tab-btn, .sim-tab-btn').forEach(btn => {
            btn.classList.remove('border-blue-600', 'text-blue-600');
            btn.classList.add('border-transparent');
        });

        // Show selected agent tab
        const tabElement = document.getElementById(`${tabName}Tab`);
        if (tabElement) {
            tabElement.classList.remove('hidden');
        }

        // Activate agent tab button
        const tabBtn = document.querySelector(`.tab-btn[data-tab="${tabName}"]`);
        if (tabBtn) {
            tabBtn.classList.add('border-blue-600', 'text-blue-600');
            tabBtn.classList.remove('border-transparent');
        }
    },

    /**
     * Show/hide agent context (header + tabs)
     */
    showAgentContext(show) {
        const agentHeader = document.getElementById('agentHeader');
        const agentTabs = document.getElementById('tabsContainer');
        const agentActions = document.getElementById('agentActions');

        if (agentHeader) agentHeader.classList.toggle('hidden', !show);
        if (agentTabs) agentTabs.classList.toggle('hidden', !show);
        if (agentActions) agentActions.classList.toggle('hidden', !show);
    },

    /**
     * Show/hide empty state
     */
    showEmptyState(show) {
        const emptyState = document.getElementById('emptyState');
        const tabsContainer = document.getElementById('tabsContainer');
        const agentActions = document.getElementById('agentActions');

        if (emptyState) emptyState.classList.toggle('hidden', !show);
        if (tabsContainer) tabsContainer.classList.toggle('hidden', show);
        if (agentActions) agentActions.classList.toggle('hidden', show);
    },

    /**
     * Update page title
     */
    setAgentTitle(title) {
        document.getElementById('agentTitle').textContent = title;
    },

    /**
     * Show modal
     */
    showModal(modalId) {
        document.getElementById(modalId).classList.remove('hidden');
    },

    /**
     * Hide modal
     */
    hideModal(modalId) {
        document.getElementById(modalId).classList.add('hidden');
    },

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    /**
     * Show loading indicator on a button
     */
    setButtonLoading(button, loading) {
        if (loading) {
            button.disabled = true;
            button.dataset.originalText = button.textContent;
            button.textContent = 'Loading...';
        } else {
            button.disabled = false;
            button.textContent = button.dataset.originalText || button.textContent;
        }
    },

    /**
     * Render PM approval cards
     */
    renderPMApprovals(approvals) {
        const container = document.getElementById('pmApprovalsContainer');
        const countEl = document.getElementById('pendingApprovalsCount');

        if (countEl) {
            countEl.textContent = `${approvals.length} pending`;
        }

        if (!approvals || approvals.length === 0) {
            container.innerHTML = '<p class="text-gray-400 text-center py-8">No pending approval requests</p>';
            return;
        }

        container.innerHTML = approvals.map(approval => {
            const urgencyColors = {
                'immediate': 'border-l-4 border-red-500 bg-red-50',
                'high': 'border-l-4 border-orange-500 bg-orange-50',
                'normal': 'border-l-4 border-blue-500 bg-blue-50',
                'low': 'border-l-4 border-gray-400 bg-gray-50'
            };
            const urgencyClass = urgencyColors[approval.urgency] || urgencyColors.normal;

            const urgencyBadgeColors = {
                'immediate': 'bg-red-200 text-red-800',
                'high': 'bg-orange-200 text-orange-800',
                'normal': 'bg-blue-200 text-blue-800',
                'low': 'bg-gray-200 text-gray-800'
            };
            const urgencyBadgeClass = urgencyBadgeColors[approval.urgency] || urgencyBadgeColors.normal;

            let timeStr = '';
            try {
                const timestamp = new Date(approval.timestamp);
                timeStr = timestamp.toLocaleString('en-GB', {
                    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'
                });
            } catch (e) {
                timeStr = approval.timestamp || '';
            }

            return `
            <div class="p-4 rounded shadow-sm ${urgencyClass}" data-approval-id="${this.escapeHtml(approval.approval_id)}">
                <div class="flex justify-between items-start mb-2">
                    <div>
                        <span class="text-xs uppercase font-medium text-gray-500">${this.escapeHtml(approval.request_type)}</span>
                        <span class="text-xs text-gray-400 ml-2">${timeStr}</span>
                    </div>
                    <span class="text-xs font-medium uppercase px-2 py-1 rounded ${urgencyBadgeClass}">${this.escapeHtml(approval.urgency)}</span>
                </div>

                <h4 class="font-medium text-gray-800 mb-2">${this.escapeHtml(approval.summary)}</h4>

                <p class="text-sm text-gray-600 mb-3">${this.escapeHtml(approval.context || '')}</p>

                <div class="flex items-center justify-between">
                    <div class="text-xs text-gray-500">
                        From: <span class="font-medium">${this.escapeHtml(approval.requesting_agent)}</span>
                        ${approval.recommendation ? ` | Recommends: <span class="text-blue-600">${this.escapeHtml(approval.recommendation)}</span>` : ''}
                    </div>

                    <div class="flex gap-2">
                        <button class="pm-approve-btn bg-green-600 hover:bg-green-700 text-white px-3 py-1 rounded text-sm"
                                data-approval-id="${this.escapeHtml(approval.approval_id)}">
                            Approve
                        </button>
                        <button class="pm-modify-btn bg-yellow-500 hover:bg-yellow-600 text-white px-3 py-1 rounded text-sm"
                                data-approval-id="${this.escapeHtml(approval.approval_id)}"
                                data-summary="${this.escapeHtml(approval.summary)}">
                            Modify
                        </button>
                        <button class="pm-reject-btn bg-red-600 hover:bg-red-700 text-white px-3 py-1 rounded text-sm"
                                data-approval-id="${this.escapeHtml(approval.approval_id)}">
                            Reject
                        </button>
                    </div>
                </div>
            </div>`;
        }).join('');
    },

    /**
     * Render scheduled events
     */
    renderScheduledEvents(events) {
        const container = document.getElementById('scheduledEventsContainer');

        if (!events || events.length === 0) {
            container.innerHTML = '<p class="text-gray-400 text-sm">No scheduled events</p>';
            return;
        }

        container.innerHTML = events.map(event => {
            let dueStr = '';
            try {
                const dueTime = new Date(event.due_game_time);
                dueStr = dueTime.toLocaleString('en-GB', {
                    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'
                });
            } catch (e) {
                dueStr = event.due_game_time || '';
            }

            return `
            <div class="flex items-center justify-between p-3 bg-gray-50 rounded border">
                <div>
                    <span class="text-sm font-medium">${this.escapeHtml(event.event_type)}</span>
                    <span class="text-xs text-gray-500 ml-2">${this.escapeHtml(event.agent_id)}</span>
                </div>
                <div class="flex items-center gap-3">
                    <span class="text-xs text-gray-500">Due: ${dueStr}</span>
                    <button class="cancel-scheduled-btn text-xs text-red-600 hover:text-red-800"
                            data-schedule-id="${this.escapeHtml(event.schedule_id)}">
                        Cancel
                    </button>
                </div>
            </div>`;
        }).join('');
    },

    /**
     * Show toast notification
     */
    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        const bgColor = type === 'error' ? 'bg-red-600' : type === 'success' ? 'bg-green-600' : 'bg-blue-600';

        toast.className = `fixed bottom-4 right-4 ${bgColor} text-white px-6 py-3 rounded-lg shadow-lg z-50 transition-opacity duration-300`;
        toast.textContent = message;

        document.body.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
};
