/**
 * PM Decisions Component - Modal for PM approval requests with auto-pause
 */

const PMDecisions = {
    modal: null,
    contentEl: null,
    actionsEl: null,
    currentApproval: null,

    /**
     * Initialize the PM decisions component
     */
    init() {
        this.modal = document.getElementById('pmDecisionModal');
        this.contentEl = document.getElementById('pmDecisionContent');
        this.actionsEl = document.getElementById('pmDecisionActions');

        console.log('[PMDecisions] Initialized');
    },

    /**
     * Show the PM decision modal with an approval request
     * @param {Object} approval - Approval request from ApiAdapter
     */
    show(approval) {
        if (!this.modal || !this.contentEl || !this.actionsEl) return;

        this.currentApproval = approval;

        // Update simulation status to show PAUSED
        this.updatePausedStatus(true);

        // Render content
        this.contentEl.innerHTML = this.renderApprovalContent(approval);

        // Render action buttons
        this.actionsEl.innerHTML = this.renderActionButtons(approval);

        // Bind button events
        this.bindActionButtons();

        // Show modal
        this.modal.classList.remove('hidden');

        // Play alert sound (optional)
        this.playAlertSound();
    },

    /**
     * Hide the modal
     */
    hide() {
        if (!this.modal) return;

        this.modal.classList.add('hidden');
        this.currentApproval = null;
        this.updatePausedStatus(false);
    },

    /**
     * Render the approval content
     */
    renderApprovalContent(approval) {
        const urgencyColors = {
            high: 'text-game-danger',
            medium: 'text-game-warning',
            low: 'text-gray-400'
        };

        const urgencyBadges = {
            high: '<span class="px-2 py-1 text-xs rounded bg-game-danger/20 text-game-danger">URGENT</span>',
            medium: '<span class="px-2 py-1 text-xs rounded bg-game-warning/20 text-game-warning">IMPORTANT</span>',
            low: '<span class="px-2 py-1 text-xs rounded bg-gray-500/20 text-gray-400">ROUTINE</span>'
        };

        const requestTypeIcons = {
            action: '&#9876;',      // crossed swords
            approval: '&#10003;',   // checkmark
            decision: '&#128204;',  // pushpin
            meeting: '&#128101;'    // busts in silhouette
        };

        const icon = requestTypeIcons[approval.requestType] || '&#128221;';
        const urgencyBadge = urgencyBadges[approval.urgency] || urgencyBadges.medium;

        return `
            <div class="space-y-4">
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-2">
                        <span class="text-2xl">${icon}</span>
                        <span class="font-semibold text-lg text-gray-200">
                            ${this.escapeHtml(approval.requestType.charAt(0).toUpperCase() + approval.requestType.slice(1))} Request
                        </span>
                    </div>
                    ${urgencyBadge}
                </div>

                <div class="bg-game-card rounded-lg p-4 border border-game-border">
                    <div class="flex items-center gap-2 mb-2">
                        <span class="text-gray-400">From:</span>
                        <span class="font-medium text-gray-200">${this.escapeHtml(approval.agentName)}</span>
                    </div>
                    <p class="text-gray-300 leading-relaxed">
                        ${this.escapeHtml(approval.summary)}
                    </p>
                </div>

                <div class="text-xs text-gray-500 flex items-center gap-4">
                    <span>Request ID: ${approval.id}</span>
                    <span>Received: ${this.formatTime(approval.timestamp)}</span>
                </div>
            </div>
        `;
    },

    /**
     * Render action buttons
     */
    renderActionButtons(approval) {
        const options = approval.options || ['Approve', 'Deny'];

        return options.map((option, index) => {
            const isApprove = option.toLowerCase().includes('approve') || index === 0;
            const btnClass = isApprove
                ? 'bg-game-success hover:bg-game-success/80 text-white'
                : 'bg-game-danger hover:bg-game-danger/80 text-white';

            return `
                <button class="pm-decision-btn px-6 py-2 rounded font-medium ${btnClass}"
                        data-decision="${this.escapeHtml(option)}">
                    ${this.escapeHtml(option)}
                </button>
            `;
        }).join('');
    },

    /**
     * Bind click events to action buttons
     */
    bindActionButtons() {
        const buttons = this.actionsEl.querySelectorAll('.pm-decision-btn');
        buttons.forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const decision = e.target.dataset.decision;
                await this.submitDecision(decision);
            });
        });
    },

    /**
     * Submit the PM decision
     */
    async submitDecision(decision) {
        if (!this.currentApproval) return;

        // Disable buttons while submitting
        const buttons = this.actionsEl.querySelectorAll('.pm-decision-btn');
        buttons.forEach(btn => {
            btn.disabled = true;
            btn.classList.add('opacity-50', 'cursor-not-allowed');
        });

        // Submit decision
        const success = await PlayerState.submitPMDecision(this.currentApproval.id, decision);

        if (success) {
            // Hide modal if no more pending approvals
            if (PlayerState.pmApprovals.length === 0) {
                this.hide();
            }
            // Otherwise, PlayerState will call show() again with next approval
        } else {
            // Re-enable buttons on error
            buttons.forEach(btn => {
                btn.disabled = false;
                btn.classList.remove('opacity-50', 'cursor-not-allowed');
            });
            alert('Failed to submit decision. Please try again.');
        }
    },

    /**
     * Update the header to show PAUSED status
     */
    updatePausedStatus(isPaused) {
        const statusEl = document.getElementById('simStatus');
        if (!statusEl) return;

        if (isPaused) {
            statusEl.innerHTML = `
                <span class="w-2 h-2 rounded-full bg-game-warning animate-pulse"></span>
                <span class="text-game-warning text-sm font-medium">PAUSED - Awaiting Decision</span>
            `;
        } else {
            // Will be updated by simulation status polling
        }
    },

    /**
     * Play alert sound for PM decision
     */
    playAlertSound() {
        // Create a simple beep using Web Audio API
        try {
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();

            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);

            oscillator.frequency.value = 800;
            oscillator.type = 'sine';

            gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3);

            oscillator.start(audioContext.currentTime);
            oscillator.stop(audioContext.currentTime + 0.3);
        } catch (e) {
            // Audio not available, ignore
        }
    },

    /**
     * Format timestamp for display
     */
    formatTime(timestamp) {
        try {
            return new Date(timestamp).toLocaleTimeString();
        } catch {
            return 'Unknown';
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
window.PMDecisions = PMDecisions;
