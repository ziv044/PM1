/**
 * Entity Panel Component - Displays friendly agents grouped by category
 */

const EntityPanel = {
    container: null,
    tabsContainer: null,
    currentCategory: 'security',
    lastAgentIds: '',  // Track to avoid flicker

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

        console.log('[EntityPanel] Initialized');
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
    }
};

// Export
window.EntityPanel = EntityPanel;
