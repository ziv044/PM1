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

        // Setup game menu
        this.initGameMenu();

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
    },

    // ========== Game Menu ==========

    currentGame: null,

    /**
     * Initialize game menu event listeners
     */
    initGameMenu() {
        // Game menu button
        const menuBtn = document.getElementById('gameMenuBtn');
        console.log('[PlayApp] Game menu button found:', !!menuBtn);
        if (menuBtn) {
            menuBtn.addEventListener('click', () => {
                console.log('[PlayApp] Game menu button clicked');
                this.showGameMenu();
            });
        }

        // Close buttons
        document.getElementById('closeGameMenuBtn')?.addEventListener('click', () => this.hideGameMenu());
        document.getElementById('closeNewGameBtn')?.addEventListener('click', () => this.hideNewGameModal());
        document.getElementById('closeLoadGameBtn')?.addEventListener('click', () => this.hideLoadGameModal());
        document.getElementById('cancelNewGameBtn')?.addEventListener('click', () => this.hideNewGameModal());

        // Action buttons
        document.getElementById('newGameBtn')?.addEventListener('click', () => this.showNewGameModal());
        document.getElementById('loadGameBtn')?.addEventListener('click', () => this.showLoadGameModal());
        document.getElementById('createGameBtn')?.addEventListener('click', () => this.createNewGame());

        // Close on backdrop click
        document.getElementById('gameMenuModal')?.addEventListener('click', (e) => {
            if (e.target.id === 'gameMenuModal') this.hideGameMenu();
        });
        document.getElementById('newGameModal')?.addEventListener('click', (e) => {
            if (e.target.id === 'newGameModal') this.hideNewGameModal();
        });
        document.getElementById('loadGameModal')?.addEventListener('click', (e) => {
            if (e.target.id === 'loadGameModal') this.hideLoadGameModal();
        });

        // Enter key in new game input
        document.getElementById('newGameNameInput')?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') this.createNewGame();
        });

        console.log('[PlayApp] Game menu initialized');
    },

    /**
     * Show game menu modal
     */
    async showGameMenu() {
        console.log('[PlayApp] showGameMenu called');
        const modal = document.getElementById('gameMenuModal');
        console.log('[PlayApp] Game menu modal found:', !!modal);
        if (!modal) return;

        // Fetch current game info
        const result = await ApiAdapter.getCurrentGame();
        if (result.success && result.game) {
            this.currentGame = result.game;
            document.getElementById('currentGameDisplay').textContent = result.game.display_name || result.game.game_id || 'Unknown';
            // Format game time
            const gameTime = result.game.game_clock || '--';
            try {
                const date = new Date(gameTime);
                if (!isNaN(date.getTime())) {
                    document.getElementById('currentGameTime').textContent = date.toLocaleString('en-GB', {
                        day: '2-digit',
                        month: 'short',
                        year: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit'
                    });
                } else {
                    document.getElementById('currentGameTime').textContent = gameTime;
                }
            } catch {
                document.getElementById('currentGameTime').textContent = gameTime;
            }
        } else {
            document.getElementById('currentGameDisplay').textContent = 'No game loaded';
            document.getElementById('currentGameTime').textContent = '--';
        }

        modal.classList.remove('hidden');
    },

    /**
     * Hide game menu modal
     */
    hideGameMenu() {
        document.getElementById('gameMenuModal')?.classList.add('hidden');
    },

    /**
     * Show new game modal
     */
    showNewGameModal() {
        this.hideGameMenu();
        const modal = document.getElementById('newGameModal');
        if (modal) {
            modal.classList.remove('hidden');
            document.getElementById('newGameNameInput')?.focus();
        }
    },

    /**
     * Hide new game modal
     */
    hideNewGameModal() {
        const modal = document.getElementById('newGameModal');
        if (modal) {
            modal.classList.add('hidden');
            const input = document.getElementById('newGameNameInput');
            if (input) input.value = '';
        }
    },

    /**
     * Create a new game
     */
    async createNewGame() {
        const nameInput = document.getElementById('newGameNameInput');
        const displayName = nameInput?.value.trim();

        if (!displayName) {
            this.showToast('Please enter a save name', 'error');
            return;
        }

        // Generate game_id from display name
        const gameId = displayName.toLowerCase()
            .replace(/[^a-z0-9]+/g, '-')
            .replace(/^-|-$/g, '')
            + '-' + Date.now().toString(36);

        const btn = document.getElementById('createGameBtn');
        const originalText = btn?.textContent;
        if (btn) {
            btn.disabled = true;
            btn.textContent = 'Creating...';
        }

        try {
            const createResult = await ApiAdapter.createGame(gameId, displayName);
            if (!createResult.success) {
                this.showToast(createResult.message, 'error');
                return;
            }

            // Auto-load the new game
            const loadResult = await ApiAdapter.loadGame(gameId);
            if (loadResult.success) {
                this.showToast(`New game "${displayName}" created!`, 'success');
                this.hideNewGameModal();
                // Refresh all state
                await PlayerState.refreshAll();
            } else {
                this.showToast(loadResult.message, 'error');
            }
        } catch (error) {
            console.error('[PlayApp] Create game error:', error);
            this.showToast('Failed to create game', 'error');
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.textContent = originalText || 'Create & Start';
            }
        }
    },

    /**
     * Show load game modal with games list
     */
    async showLoadGameModal() {
        this.hideGameMenu();
        const modal = document.getElementById('loadGameModal');
        const listContainer = document.getElementById('gamesListContainer');

        if (!modal || !listContainer) return;

        listContainer.innerHTML = '<p class="text-gray-400 text-center py-4">Loading...</p>';
        modal.classList.remove('hidden');

        const result = await ApiAdapter.listGames();

        if (!result.success || result.games.length === 0) {
            listContainer.innerHTML = '<p class="text-gray-400 text-center py-4">No saved games found</p>';
            return;
        }

        listContainer.innerHTML = result.games.map(game => {
            const isActive = game.game_id === result.currentGame;
            // Format game time
            let timeDisplay = 'No time data';
            try {
                const date = new Date(game.game_clock);
                if (!isNaN(date.getTime())) {
                    timeDisplay = date.toLocaleString('en-GB', {
                        day: '2-digit',
                        month: 'short',
                        hour: '2-digit',
                        minute: '2-digit'
                    });
                }
            } catch {}

            return `
                <div class="p-3 rounded-lg border ${isActive ? 'border-game-accent bg-game-accent/10' : 'border-game-border'} flex items-center justify-between">
                    <div>
                        <p class="font-medium ${isActive ? 'text-game-accent' : 'text-gray-200'}">${this.escapeHtml(game.display_name || game.game_id)}</p>
                        <p class="text-xs text-gray-400">${timeDisplay}</p>
                    </div>
                    ${isActive
                        ? '<span class="text-xs px-2 py-1 rounded bg-game-accent/20 text-game-accent">Active</span>'
                        : `<button class="load-game-item px-3 py-1 rounded bg-game-success hover:bg-game-success/80 text-white text-sm" data-game-id="${this.escapeHtml(game.game_id)}">Load</button>`
                    }
                </div>
            `;
        }).join('');

        // Add click handlers for load buttons
        listContainer.querySelectorAll('.load-game-item').forEach(btn => {
            btn.addEventListener('click', (e) => this.loadGame(e.target.dataset.gameId));
        });
    },

    /**
     * Hide load game modal
     */
    hideLoadGameModal() {
        document.getElementById('loadGameModal')?.classList.add('hidden');
    },

    /**
     * Load a specific game
     */
    async loadGame(gameId) {
        // Check simulation is stopped
        if (PlayerState.simulation.running) {
            this.showToast('Stop simulation before loading a different game', 'error');
            return;
        }

        const btn = document.querySelector(`[data-game-id="${gameId}"]`);
        const originalText = btn?.textContent;
        if (btn) {
            btn.disabled = true;
            btn.textContent = 'Loading...';
        }

        try {
            const result = await ApiAdapter.loadGame(gameId);
            if (result.success) {
                this.showToast('Game loaded!', 'success');
                this.hideLoadGameModal();
                // Refresh all state
                await PlayerState.refreshAll();
            } else {
                this.showToast(result.message, 'error');
            }
        } catch (error) {
            console.error('[PlayApp] Load game error:', error);
            this.showToast('Failed to load game', 'error');
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.textContent = originalText || 'Load';
            }
        }
    },

    /**
     * Show toast notification
     */
    showToast(message, type = 'info') {
        const colors = {
            success: 'bg-game-success',
            error: 'bg-game-danger',
            info: 'bg-game-accent'
        };
        const toast = document.createElement('div');
        toast.className = `fixed bottom-4 right-4 ${colors[type] || colors.info} text-white px-4 py-2 rounded-lg shadow-lg z-50 animate-toast`;
        toast.textContent = message;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 3000);
    },

    /**
     * Escape HTML for safe display
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
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
