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

        container.innerHTML = Object.entries(agents).map(([id, agent]) => `
            <div class="agent-card p-3 rounded cursor-pointer transition-colors ${id === selectedAgentId ? 'bg-blue-600' : 'bg-gray-700 hover:bg-gray-600'}"
                 data-agent-id="${this.escapeHtml(id)}">
                <div class="font-medium truncate">${this.escapeHtml(id)}</div>
                <div class="text-xs text-gray-300 truncate">${this.escapeHtml(agent.model)}</div>
            </div>
        `).join('');
    },

    /**
     * Render agent details tab
     */
    renderAgentDetails(agent, agentId) {
        document.getElementById('detailAgentId').textContent = agentId;
        document.getElementById('detailModel').textContent = agent.model;
        document.getElementById('detailSystemPrompt').textContent = agent.system_prompt || '(No system prompt set)';

        // Simulation properties
        document.getElementById('detailEntityType').textContent = agent.entity_type || 'System';
        document.getElementById('detailEventFrequency').textContent = agent.event_frequency || 60;
        document.getElementById('detailAgentCategory').textContent = agent.agent_category || '(Not set)';
        document.getElementById('detailIsEnemy').checked = agent.is_enemy || false;
        document.getElementById('detailIsWest').checked = agent.is_west || false;
        document.getElementById('detailIsEvilAxis').checked = agent.is_evil_axis || false;
        document.getElementById('detailIsReportingGovernment').checked = agent.is_reporting_government || false;
        document.getElementById('detailAgenda').textContent = agent.agenda || '(Not set)';
        document.getElementById('detailPrimaryObjectives').textContent = agent.primary_objectives || '(Not set)';
        document.getElementById('detailHardRules').textContent = agent.hard_rules || '(Not set)';
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
     * Show a specific tab
     */
    showTab(tabName) {
        // Hide all tabs
        document.querySelectorAll('.tab-content').forEach(tab => {
            tab.classList.add('hidden');
        });

        // Remove active state from all tab buttons
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.remove('border-blue-600', 'text-blue-600');
            btn.classList.add('border-transparent');
        });

        // Show selected tab
        const tabElement = document.getElementById(`${tabName}Tab`);
        if (tabElement) {
            tabElement.classList.remove('hidden');
        }

        // Activate tab button
        const tabBtn = document.querySelector(`.tab-btn[data-tab="${tabName}"]`);
        if (tabBtn) {
            tabBtn.classList.add('border-blue-600', 'text-blue-600');
            tabBtn.classList.remove('border-transparent');
        }
    },

    /**
     * Show/hide empty state
     */
    showEmptyState(show) {
        document.getElementById('emptyState').classList.toggle('hidden', !show);
        document.getElementById('tabsContainer').classList.toggle('hidden', show);
        document.getElementById('agentActions').classList.toggle('hidden', show);
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
