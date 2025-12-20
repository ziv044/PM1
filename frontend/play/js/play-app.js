/**
 * PM1 Player Mode - Main Application
 * Initializes all components and wires them together
 */

const PlayApp = {
    /**
     * Initialize the player application
     */
    async init() {
        console.log('[PlayApp] Initializing PM1 Player Mode...');
        console.log('[PlayApp] Checking API availability...');

        try {
            // Quick API health check first
            const healthCheck = await fetch('/api/health');
            if (healthCheck.ok) {
                const health = await healthCheck.json();
                console.log('[PlayApp] API connected:', health);
            } else {
                console.warn('[PlayApp] API health check failed:', healthCheck.status);
            }
        } catch (e) {
            console.error('[PlayApp] Cannot reach API:', e);
            this.showError('Cannot connect to backend. Make sure the server is running.');
            return;
        }

        try {
            // Initialize UI components
            console.log('[PlayApp] Step 1: Initializing components...');
            this.initComponents();

            // Register state callbacks
            console.log('[PlayApp] Step 2: Registering callbacks...');
            this.registerCallbacks();

            // Initialize state manager (starts polling)
            console.log('[PlayApp] Step 3: Initializing PlayerState...');
            await PlayerState.init();

            // Initial render
            console.log('[PlayApp] Step 4: Updating simulation status...');
            this.updateSimulationStatus(PlayerState.simulation);

            console.log('[PlayApp] Initialization complete');
        } catch (error) {
            console.error('[PlayApp] Initialization failed:', error);
            console.error('[PlayApp] Error stack:', error.stack);
            this.showError('Failed to initialize. Please refresh the page.');
        }
    },

    /**
     * Initialize all UI components
     */
    initComponents() {
        try {
            EventsFeed.init();
            console.log('[PlayApp] EventsFeed initialized');
        } catch (e) {
            console.error('[PlayApp] EventsFeed.init() failed:', e);
        }

        try {
            KPIPanel.init();
            console.log('[PlayApp] KPIPanel initialized');
        } catch (e) {
            console.error('[PlayApp] KPIPanel.init() failed:', e);
        }

        try {
            EntityPanel.init();
            console.log('[PlayApp] EntityPanel initialized');
        } catch (e) {
            console.error('[PlayApp] EntityPanel.init() failed:', e);
        }

        try {
            TacticalMap.init();
            console.log('[PlayApp] TacticalMap initialized');
        } catch (e) {
            console.error('[PlayApp] TacticalMap.init() failed:', e);
        }

        try {
            PMDecisions.init();
            console.log('[PlayApp] PMDecisions initialized');
        } catch (e) {
            console.error('[PlayApp] PMDecisions.init() failed:', e);
        }

        // Setup Play/Pause button
        const playPauseBtn = document.getElementById('playPauseBtn');
        if (playPauseBtn) {
            playPauseBtn.addEventListener('click', () => this.toggleSimulation());
        }

        console.log('[PlayApp] Components initialized');
    },

    /**
     * Toggle simulation start/stop
     */
    async toggleSimulation() {
        const btn = document.getElementById('playPauseBtn');
        if (btn) {
            btn.disabled = true;
            btn.classList.add('opacity-50');
        }

        try {
            if (PlayerState.simulation.running) {
                console.log('[PlayApp] Stopping simulation...');
                const success = await ApiAdapter.stopSimulation();
                if (success) {
                    console.log('[PlayApp] Simulation stopped');
                }
            } else {
                console.log('[PlayApp] Starting simulation...');
                const success = await ApiAdapter.startSimulation(2.0);
                if (success) {
                    console.log('[PlayApp] Simulation started');
                }
            }
            // Refresh status immediately
            await PlayerState.pollSimulationStatus();
        } catch (error) {
            console.error('[PlayApp] Toggle simulation error:', error);
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.classList.remove('opacity-50');
            }
        }
    },

    /**
     * Register callbacks for state updates
     */
    registerCallbacks() {
        // Simulation status updates
        PlayerState.on('SimulationUpdate', (status) => {
            this.updateSimulationStatus(status);
        });

        // Events updates
        PlayerState.on('EventsUpdate', (events) => {
            EventsFeed.render(events);
        });

        // KPIs updates
        PlayerState.on('KPIsUpdate', (kpis) => {
            KPIPanel.render(kpis);
        });

        // Agents updates
        PlayerState.on('AgentsUpdate', (categories) => {
            EntityPanel.render(categories);
        });

        // Map updates
        PlayerState.on('MapUpdate', (mapState) => {
            TacticalMap.render(mapState);
        });

        // PM Approval required
        PlayerState.on('PMApprovalRequired', (approval) => {
            PMDecisions.show(approval);
        });

        console.log('[PlayApp] Callbacks registered');
    },

    /**
     * Update simulation status in header
     */
    updateSimulationStatus(status) {
        // Update game time - format nicely
        const gameTimeEl = document.getElementById('gameTime');
        if (gameTimeEl) {
            const gameTime = status.gameTime || '--:--:--';
            // Format ISO datetime to readable time
            try {
                const date = new Date(gameTime);
                if (!isNaN(date.getTime())) {
                    gameTimeEl.textContent = date.toLocaleString('en-GB', {
                        day: '2-digit',
                        month: 'short',
                        hour: '2-digit',
                        minute: '2-digit'
                    });
                } else {
                    gameTimeEl.textContent = gameTime;
                }
            } catch {
                gameTimeEl.textContent = gameTime;
            }
        }

        // Update Play/Pause button
        const playPauseBtn = document.getElementById('playPauseBtn');
        const playPauseIcon = document.getElementById('playPauseIcon');
        const playPauseText = document.getElementById('playPauseText');
        if (playPauseBtn && playPauseIcon && playPauseText) {
            if (status.running) {
                // Show Stop button
                playPauseIcon.innerHTML = '&#9632;';  // Stop square
                playPauseText.textContent = 'Stop';
                playPauseBtn.classList.remove('bg-game-success', 'hover:bg-game-success/80');
                playPauseBtn.classList.add('bg-game-danger', 'hover:bg-game-danger/80');
            } else {
                // Show Start button
                playPauseIcon.innerHTML = '&#9654;';  // Play triangle
                playPauseText.textContent = 'Start';
                playPauseBtn.classList.remove('bg-game-danger', 'hover:bg-game-danger/80');
                playPauseBtn.classList.add('bg-game-success', 'hover:bg-game-success/80');
            }
        }

        // Update status indicator
        const simStatusEl = document.getElementById('simStatus');
        if (simStatusEl) {
            if (status.paused || PlayerState.pmApprovals.length > 0) {
                simStatusEl.innerHTML = `
                    <span class="w-2 h-2 rounded-full bg-game-warning animate-pulse"></span>
                    <span class="text-game-warning text-sm">Paused</span>
                `;
            } else if (status.running) {
                simStatusEl.innerHTML = `
                    <span class="w-2 h-2 rounded-full bg-game-success animate-pulse"></span>
                    <span class="text-game-success text-sm">Running</span>
                `;
            } else {
                simStatusEl.innerHTML = `
                    <span class="w-2 h-2 rounded-full bg-gray-500"></span>
                    <span class="text-gray-400 text-sm">Stopped</span>
                `;
            }
        }

        // Update alert level (based on some condition)
        const alertEl = document.getElementById('alertLevel');
        if (alertEl) {
            // Check if there are high priority events or critical KPIs
            const hasAlert = this.checkForAlerts();
            if (hasAlert) {
                alertEl.classList.remove('hidden');
            } else {
                alertEl.classList.add('hidden');
            }
        }
    },

    /**
     * Check if there are any alerts to display
     */
    checkForAlerts() {
        // Check for PM approvals
        if (PlayerState.pmApprovals.length > 0) return true;

        // Check for critical events in last 5 minutes
        const fiveMinutesAgo = Date.now() - 5 * 60 * 1000;
        const recentCritical = PlayerState.events.some(event =>
            event.priority === 'high' &&
            new Date(event.timestamp).getTime() > fiveMinutesAgo
        );

        return recentCritical;
    },

    /**
     * Show error message to user
     */
    showError(message) {
        const container = document.getElementById('eventsContent');
        if (container) {
            container.innerHTML = `
                <div class="p-4 bg-game-danger/20 text-game-danger rounded-lg m-4">
                    <p class="font-medium">Error</p>
                    <p class="text-sm">${message}</p>
                </div>
            `;
        }
    },

    /**
     * Refresh all data manually
     */
    async refresh() {
        console.log('[PlayApp] Manual refresh triggered');
        await PlayerState.refreshAll();
    },

    /**
     * Cleanup when leaving page
     */
    destroy() {
        PlayerState.stopPolling();
        console.log('[PlayApp] Destroyed');
    }
};

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    PlayApp.init();
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    PlayApp.destroy();
});

// Export for debugging
window.PlayApp = PlayApp;
