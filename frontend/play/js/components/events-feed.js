/**
 * Events Feed Component - Displays game events in a scrollable feed
 */

const EventsFeed = {
    container: null,
    countEl: null,
    lastEventIds: '',  // Track last rendered event IDs to avoid unnecessary re-renders

    /**
     * Initialize the events feed
     */
    init() {
        this.container = document.getElementById('eventsContent');
        this.countEl = document.getElementById('eventCount');

        // Setup filter button
        const filterBtn = document.getElementById('filterEventsBtn');
        const filterModal = document.getElementById('filterModal');
        const closeFilterBtn = document.getElementById('closeFilterBtn');

        if (filterBtn && filterModal) {
            filterBtn.addEventListener('click', () => {
                filterModal.classList.remove('hidden');
            });
        }

        if (closeFilterBtn && filterModal) {
            closeFilterBtn.addEventListener('click', () => {
                filterModal.classList.add('hidden');
            });

            // Close on backdrop click
            filterModal.addEventListener('click', (e) => {
                if (e.target === filterModal) {
                    filterModal.classList.add('hidden');
                }
            });
        }

        // Setup filter checkboxes
        document.querySelectorAll('.event-filter').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const type = e.target.dataset.type;
                PlayerState.setFilter(type, e.target.checked);
            });
        });

        console.log('[EventsFeed] Initialized');
    },

    /**
     * Render events list
     * @param {Array} events - Transformed events from ApiAdapter
     */
    render(events) {
        if (!this.container) return;

        // Update count
        if (this.countEl) {
            this.countEl.textContent = `${events.length} events`;
        }

        if (events.length === 0) {
            if (this.lastEventIds !== 'empty') {
                this.container.innerHTML = `
                    <div class="text-gray-500 text-sm text-center py-8">
                        No events to display
                    </div>
                `;
                this.lastEventIds = 'empty';
            }
            return;
        }

        // Sort by timestamp (newest first)
        const sortedEvents = [...events].sort((a, b) =>
            new Date(b.timestamp) - new Date(a.timestamp)
        );

        // Check if events have changed by comparing IDs
        const currentEventIds = sortedEvents.map(e => e.id).join(',');
        if (currentEventIds === this.lastEventIds) {
            // No change, skip re-render to prevent blinking
            return;
        }
        this.lastEventIds = currentEventIds;

        // Render events
        this.container.innerHTML = sortedEvents.map(event => this.renderEvent(event)).join('');
    },

    /**
     * Render a single event card
     */
    renderEvent(event) {
        const colorClasses = {
            danger: 'border-l-game-danger bg-game-danger/5',
            warning: 'border-l-game-warning bg-game-warning/5',
            success: 'border-l-game-success bg-game-success/5',
            accent: 'border-l-game-accent bg-game-accent/5',
            purple: 'border-l-game-purple bg-game-purple/5',
            gray: 'border-l-gray-500 bg-gray-500/5'
        };

        const priorityBadges = {
            high: '<span class="px-1.5 py-0.5 text-xs rounded bg-game-danger/20 text-game-danger">HIGH</span>',
            medium: '<span class="px-1.5 py-0.5 text-xs rounded bg-game-warning/20 text-game-warning">MED</span>',
            low: ''
        };

        const typeIcons = {
            military: '&#9876;',      // crossed swords
            diplomatic: '&#127760;',   // globe
            intelligence: '&#128065;', // eye
            media: '&#128250;',        // TV
            security: '&#128737;',     // shield
            economic: '&#128176;',     // money bag
            political: '&#127963;'     // classical building
        };

        const colorClass = colorClasses[event.color] || colorClasses.gray;
        const priorityBadge = priorityBadges[event.priority] || '';
        const icon = typeIcons[event.type] || '&#128196;';
        const actualTime = this.formatActualTime(event.timestamp);

        return `
            <div class="p-4 border-l-4 ${colorClass} border-b border-game-border hover:bg-white/5 transition-colors cursor-pointer"
                 data-event-id="${event.id}">
                <div class="flex items-start gap-3 mb-2">
                    <span class="text-xs text-gray-500 font-mono whitespace-nowrap pt-0.5">${actualTime}</span>
                    <div class="flex-1">
                        <div class="flex items-center gap-2">
                            <span class="text-lg">${icon}</span>
                            <span class="font-medium text-gray-200 text-sm">${this.escapeHtml(event.title)}</span>
                            ${priorityBadge}
                        </div>
                    </div>
                </div>
                <p class="text-sm text-gray-400 line-clamp-2 ml-16">${this.escapeHtml(event.description)}</p>
                <div class="mt-2 ml-16 flex items-center gap-2 text-xs text-gray-500">
                    <span>From: ${this.escapeHtml(event.agentName)}</span>
                    ${event.isPublic ? '<span class="text-game-accent">&#128227; Public</span>' : '<span>&#128274; Intel</span>'}
                </div>
            </div>
        `;
    },

    /**
     * Format timestamp as actual time (e.g., "07 Oct 06:29")
     */
    formatActualTime(timestamp) {
        try {
            const date = new Date(timestamp);
            if (isNaN(date.getTime())) return '--:--';

            const day = date.getDate().toString().padStart(2, '0');
            const month = date.toLocaleString('en-US', { month: 'short' });
            const hours = date.getHours().toString().padStart(2, '0');
            const mins = date.getMinutes().toString().padStart(2, '0');

            return `${day} ${month} ${hours}:${mins}`;
        } catch {
            return '--:--';
        }
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
window.EventsFeed = EventsFeed;
