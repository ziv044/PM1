/**
 * Entity Panel Component - Displays friendly agents grouped by category
 * Includes PM Instructions flow for giving directives to agents
 */

const EntityPanel = {
    container: null,
    tabsContainer: null,
    currentCategory: 'security',
    lastAgentIds: '',  // Track to avoid flicker

    // PM Instructions modal state
    selectedAgent: null,
    pendingSummary: null,

    /**
     * Initialize the entity panel
     */
    init() {
        this.container = document.getElementById('entityCards');
        this.tabsContainer = document.getElementById('entityPanel');

        // Setup tab click handlers
        document.querySelectorAll('.entity-tab').forEach(tab => {
            tab.addEventListener('click', (e) => {
                this.switchCategory(e.target.dataset.category);
            });
        });

        // Setup agent card click delegation
        if (this.container) {
            this.container.addEventListener('click', (e) => {
                const card = e.target.closest('.agent-card');
                if (card) {
                    const agentId = card.dataset.agentId;
                    this.openPMInstructions(agentId);
                }
            });
        }

        // Setup PM Instructions modal handlers
        this.initPMInstructionsModal();

        console.log('[EntityPanel] Initialized with PM Instructions support');
    },

    /**
     * Initialize PM Instructions modal event handlers
     */
    initPMInstructionsModal() {
        // Close button
        document.getElementById('closePMInstructionsBtn')?.addEventListener('click', () => this.closePMInstructions());
        document.getElementById('cancelPMInstructionsBtn')?.addEventListener('click', () => this.closePMInstructions());

        // Backdrop click to close
        document.getElementById('pmInstructionsModal')?.addEventListener('click', (e) => {
            if (e.target.id === 'pmInstructionsModal') this.closePMInstructions();
        });

        // Summarize button
        document.getElementById('summarizePMInstructionsBtn')?.addEventListener('click', () => this.summarizeInstructions());

        // Apply button
        document.getElementById('applyPMInstructionsBtn')?.addEventListener('click', () => this.applyInstructions());
    },

    /**
     * Switch to a different category tab
     */
    switchCategory(category) {
        this.currentCategory = category;

        // Update tab styles
        document.querySelectorAll('.entity-tab').forEach(tab => {
            if (tab.dataset.category === category) {
                tab.classList.add('active', 'bg-game-dark', 'text-game-accent', 'border-t', 'border-x', 'border-game-border');
                tab.classList.remove('text-gray-400');
            } else {
                tab.classList.remove('active', 'bg-game-dark', 'text-game-accent', 'border-t', 'border-x', 'border-game-border');
                tab.classList.add('text-gray-400');
            }
        });

        // Re-render with new category (force render since tab changed)
        this.render(PlayerState.agentCategories, true);
    },

    /**
     * Render agent cards for current category
     * @param {Object} categories - Category-grouped agents from ApiAdapter
     */
    render(categories, forceRender = false) {
        if (!this.container) return;

        const category = categories[this.currentCategory];
        if (!category || category.agents.length === 0) {
            const emptyKey = `empty:${this.currentCategory}`;
            if (this.lastAgentIds !== emptyKey) {
                this.container.innerHTML = `
                    <div class="text-gray-500 text-sm py-4">
                        No agents in this category
                    </div>
                `;
                this.lastAgentIds = emptyKey;
            }
            return;
        }

        // Check if agents changed
        const agentIds = `${this.currentCategory}:${category.agents.map(a => a.id).join(',')}`;
        if (!forceRender && agentIds === this.lastAgentIds) {
            return;  // No change, skip re-render
        }
        this.lastAgentIds = agentIds;

        this.container.innerHTML = category.agents
            .map(agent => this.renderAgentCard(agent))
            .join('');
    },

    /**
     * Render a single agent card
     */
    renderAgentCard(agent) {
        const statusColors = {
            active: 'bg-game-success',
            busy: 'bg-game-warning',
            offline: 'bg-gray-500',
            alert: 'bg-game-danger'
        };

        const statusColor = statusColors[agent.status] || statusColors.active;

        return `
            <div class="agent-card flex-shrink-0 w-48 bg-game-card rounded-lg border border-game-border p-4 hover:border-game-accent/50 transition-colors cursor-pointer"
                 data-agent-id="${agent.id}">
                <div class="flex items-start gap-3 mb-3">
                    <div class="w-10 h-10 rounded-full bg-game-border flex items-center justify-center text-xl">
                        ${agent.avatar}
                    </div>
                    <div class="flex-1 min-w-0">
                        <div class="flex items-center gap-1.5">
                            <span class="w-2 h-2 rounded-full ${statusColor}"></span>
                            <span class="text-xs text-gray-500 capitalize">${agent.status}</span>
                        </div>
                        <h4 class="font-medium text-gray-200 text-sm truncate" title="${this.escapeHtml(agent.name)}">
                            ${this.escapeHtml(agent.name)}
                        </h4>
                    </div>
                </div>
                <p class="text-xs text-gray-400 truncate">${this.escapeHtml(agent.role)}</p>
                ${agent.isReporting ? '<span class="inline-block mt-2 text-xs text-game-accent">&#128269; Reporting</span>' : ''}
            </div>
        `;
    },

    /**
     * Update tab badges with agent counts
     */
    updateTabBadges(categories) {
        document.querySelectorAll('.entity-tab').forEach(tab => {
            const category = categories[tab.dataset.category];
            const count = category ? category.agents.length : 0;
            // Could add badge here if desired
        });
    },

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    // ========== PM Instructions Flow ==========

    /**
     * Open PM Instructions modal for an agent
     */
    async openPMInstructions(agentId) {
        console.log('[EntityPanel] Opening PM Instructions for:', agentId);

        // Find the agent in our cached data
        const categories = PlayerState.agentCategories;
        let agent = null;
        for (const cat of Object.values(categories)) {
            agent = cat.agents.find(a => a.id === agentId);
            if (agent) break;
        }

        if (!agent) {
            console.error('[EntityPanel] Agent not found:', agentId);
            return;
        }

        // Check if this agent reports to government (PM can only instruct these)
        if (!agent.isReporting) {
            PlayApp.showToast('PM can only give directives to agents that report to government', 'error');
            return;
        }

        this.selectedAgent = agent;
        this.pendingSummary = null;

        // Fetch full agent details to get current instructions
        const result = await ApiAdapter.getAgentDetails(agentId);
        const currentInstructions = result.success ? (result.agent.pm_instructions || '') : '';

        // Populate modal
        document.getElementById('pmInstructionsAgentAvatar').innerHTML = agent.avatar;
        document.getElementById('pmInstructionsAgentName').textContent = agent.name;

        // Show current instructions if any
        const currentSection = document.getElementById('currentInstructionsSection');
        const currentDisplay = document.getElementById('currentInstructionsDisplay');
        if (currentInstructions) {
            currentDisplay.textContent = currentInstructions;
            currentSection.classList.remove('hidden');
        } else {
            currentSection.classList.add('hidden');
        }

        // Reset input and preview
        document.getElementById('pmInstructionsInput').value = '';
        document.getElementById('pmInstructionsPreview').classList.add('hidden');
        document.getElementById('summarizePMInstructionsBtn').classList.remove('hidden');
        document.getElementById('applyPMInstructionsBtn').classList.add('hidden');

        // Show modal
        document.getElementById('pmInstructionsModal').classList.remove('hidden');
        document.getElementById('pmInstructionsInput').focus();
    },

    /**
     * Close PM Instructions modal
     */
    closePMInstructions() {
        document.getElementById('pmInstructionsModal').classList.add('hidden');
        this.selectedAgent = null;
        this.pendingSummary = null;
    },

    /**
     * Summarize the raw instructions using Haiku
     */
    async summarizeInstructions() {
        if (!this.selectedAgent) return;

        const input = document.getElementById('pmInstructionsInput');
        const rawText = input.value.trim();

        if (!rawText) {
            PlayApp.showToast('Please enter your instructions', 'error');
            return;
        }

        const btn = document.getElementById('summarizePMInstructionsBtn');
        const originalText = btn.textContent;
        btn.disabled = true;
        btn.textContent = 'Summarizing...';

        try {
            const result = await ApiAdapter.summarizePMInstructions(this.selectedAgent.id, rawText);

            if (result.success && result.summary) {
                this.pendingSummary = result.summary;

                // Show preview
                document.getElementById('pmInstructionsSummary').textContent = result.summary;
                document.getElementById('pmInstructionsPreview').classList.remove('hidden');

                // Switch buttons
                btn.classList.add('hidden');
                document.getElementById('applyPMInstructionsBtn').classList.remove('hidden');
            } else {
                PlayApp.showToast(result.error || 'Failed to summarize instructions', 'error');
            }
        } catch (error) {
            console.error('[EntityPanel] Summarize error:', error);
            PlayApp.showToast('Failed to summarize instructions', 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = originalText;
        }
    },

    /**
     * Apply the summarized instructions to the agent
     */
    async applyInstructions() {
        if (!this.selectedAgent || !this.pendingSummary) return;

        const btn = document.getElementById('applyPMInstructionsBtn');
        const originalText = btn.textContent;
        btn.disabled = true;
        btn.textContent = 'Applying...';

        try {
            const result = await ApiAdapter.applyPMInstructions(this.selectedAgent.id, this.pendingSummary);

            if (result.success) {
                PlayApp.showToast(`Directive applied to ${this.selectedAgent.name}`, 'success');
                this.closePMInstructions();
            } else {
                PlayApp.showToast(result.error || 'Failed to apply directive', 'error');
            }
        } catch (error) {
            console.error('[EntityPanel] Apply error:', error);
            PlayApp.showToast('Failed to apply directive', 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = originalText;
        }
    }
};

// Export
window.EntityPanel = EntityPanel;
