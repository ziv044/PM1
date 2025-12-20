/**
 * KPI Panel Component - Displays Israel's key performance indicators
 */

const KPIPanel = {
    container: null,
    lastHash: '',  // Track last state to avoid flicker

    /**
     * Initialize the KPI panel
     */
    init() {
        this.container = document.getElementById('kpiContent');
        console.log('[KPIPanel] Initialized');
    },

    /**
     * Render KPIs grouped by category
     * @param {Object} categories - Category-grouped KPIs from ApiAdapter
     */
    render(categories) {
        if (!this.container) return;

        if (!categories || Object.keys(categories).length === 0) {
            if (this.lastHash !== 'empty') {
                this.container.innerHTML = `
                    <div class="text-gray-500 text-sm text-center py-8">
                        No KPI data available
                    </div>
                `;
                this.lastHash = 'empty';
            }
            return;
        }

        // Create hash of current values to detect changes
        const hash = this.hashCategories(categories);
        if (hash === this.lastHash) {
            return;  // No change, skip re-render
        }
        this.lastHash = hash;

        this.container.innerHTML = Object.entries(categories)
            .map(([name, category]) => this.renderCategory(name, category))
            .join('');
    },

    /**
     * Create a simple hash of category values for change detection
     */
    hashCategories(categories) {
        const values = [];
        for (const [name, cat] of Object.entries(categories)) {
            for (const [key, metric] of Object.entries(cat.metrics)) {
                values.push(`${key}:${metric.value}`);
            }
        }
        return values.join('|');
    },

    /**
     * Render a single KPI category
     */
    renderCategory(name, category) {
        const metrics = Object.entries(category.metrics);
        if (metrics.length === 0) return '';

        return `
            <div class="kpi-category">
                <div class="flex items-center gap-2 mb-3">
                    <span class="text-xl">${category.icon}</span>
                    <h3 class="font-semibold text-gray-200">${name}</h3>
                </div>
                <div class="space-y-2">
                    ${metrics.map(([key, metric]) => this.renderMetric(metric)).join('')}
                </div>
            </div>
        `;
    },

    /**
     * Render a single metric
     */
    renderMetric(metric) {
        const trendColors = {
            good: 'text-game-success',
            warning: 'text-game-warning',
            critical: 'text-game-danger'
        };

        const trendIcons = {
            good: '&#9650;',     // up triangle
            warning: '&#9670;',  // diamond
            critical: '&#9660;'  // down triangle
        };

        // For inverse metrics, trend display is flipped
        let displayTrend = metric.trend;
        if (metric.inverse) {
            if (displayTrend === 'good') displayTrend = 'critical';
            else if (displayTrend === 'critical') displayTrend = 'good';
        }

        const trendColor = trendColors[displayTrend] || 'text-gray-400';
        const trendIcon = trendIcons[displayTrend] || '';

        // Progress bar for percentage values
        const isPercentage = metric.displayValue.includes('%');
        const progressBar = isPercentage ? this.renderProgressBar(metric.value, metric.inverse) : '';

        return `
            <div class="bg-game-card rounded-lg p-3 border border-game-border">
                <div class="flex items-center justify-between mb-1">
                    <span class="text-sm text-gray-400">${metric.label}</span>
                    <div class="flex items-center gap-1">
                        <span class="font-mono font-medium text-gray-200">${metric.displayValue}</span>
                        <span class="${trendColor}">${trendIcon}</span>
                    </div>
                </div>
                ${progressBar}
            </div>
        `;
    },

    /**
     * Render a progress bar for percentage metrics
     */
    renderProgressBar(value, inverse = false) {
        // Clamp value between 0-100
        const pct = Math.max(0, Math.min(100, value));

        // Color based on value and whether inverse
        let barColor;
        if (inverse) {
            // Lower is better
            if (pct > 50) barColor = 'bg-game-danger';
            else if (pct > 20) barColor = 'bg-game-warning';
            else barColor = 'bg-game-success';
        } else {
            // Higher is better
            if (pct < 30) barColor = 'bg-game-danger';
            else if (pct < 60) barColor = 'bg-game-warning';
            else barColor = 'bg-game-success';
        }

        return `
            <div class="w-full h-1.5 bg-game-border rounded-full overflow-hidden mt-2">
                <div class="${barColor} h-full rounded-full transition-all duration-500" style="width: ${pct}%"></div>
            </div>
        `;
    }
};

// Export
window.KPIPanel = KPIPanel;
