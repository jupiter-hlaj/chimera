/**
 * Chimera Dashboard Application
 * Frontend JavaScript for monitoring data ingestion
 */

// ============================================================================
// Configuration
// ============================================================================
const CONFIG = {
    // API URL - hardcoded for dev environment
    apiUrl: localStorage.getItem('chimera_api_url') || 'https://cflufzjv1a.execute-api.us-east-1.amazonaws.com/dev',
    refreshInterval: 30000, // 30 seconds
    maxActivityItems: 50
};

// ============================================================================
// State
// ============================================================================
let refreshTimer = null;
const activityLog = [];

// ============================================================================
// DOM Elements
// ============================================================================
const elements = {
    environment: document.getElementById('environment'),
    systemStatus: document.getElementById('system-status'),
    healthGrid: document.getElementById('health-grid'),
    sourcesGrid: document.getElementById('sources-grid'),
    lastUpdated: document.getElementById('last-updated'),
    activityLog: document.getElementById('activity-log'),
    refreshBtn: document.getElementById('refresh-btn'),
    apiUrl: document.getElementById('api-url'),
    configModal: document.getElementById('config-modal'),
    apiInput: document.getElementById('api-input'),
    saveConfig: document.getElementById('save-config'),
    cancelConfig: document.getElementById('cancel-config'),
    // Data modal
    dataModal: document.getElementById('data-modal'),
    dataModalTitle: document.getElementById('data-modal-title'),
    dataS3Key: document.getElementById('data-s3-key'),
    dataLastModified: document.getElementById('data-last-modified'),
    dataContent: document.getElementById('data-content'),
    dataViewer: document.getElementById('data-viewer'),
    closeDataModal: document.getElementById('close-data-modal')
};

// ============================================================================
// Utilities
// ============================================================================
function formatTime(date) {
    return new Date(date).toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
}

function formatDate(dateStr) {
    if (!dateStr) return '--';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function logActivity(message) {
    const time = formatTime(new Date());
    activityLog.unshift({ time, message });
    if (activityLog.length > CONFIG.maxActivityItems) {
        activityLog.pop();
    }
    renderActivityLog();
}

// ============================================================================
// API Functions
// ============================================================================
async function fetchAPI(endpoint) {
    if (!CONFIG.apiUrl) {
        throw new Error('API URL not configured');
    }

    const url = `${CONFIG.apiUrl}${endpoint}`;
    const response = await fetch(url);

    if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
    }

    return response.json();
}

async function fetchHealth() {
    try {
        const data = await fetchAPI('/health');
        renderHealth(data);
        updateSystemStatus(data.status);
        logActivity('Health check completed');
        return data;
    } catch (error) {
        console.error('Error fetching health:', error);
        updateSystemStatus('error');
        logActivity(`Health check failed: ${error.message}`);
        throw error;
    }
}

async function fetchStatus() {
    try {
        const data = await fetchAPI('/status');
        renderSources(data.sources);
        elements.environment.textContent = data.environment || 'dev';
        elements.lastUpdated.textContent = `Last updated: ${formatTime(new Date())}`;
        logActivity('Status refresh completed');
        return data;
    } catch (error) {
        console.error('Error fetching status:', error);
        logActivity(`Status fetch failed: ${error.message}`);
        throw error;
    }
}

async function triggerIngestion(source) {
    try {
        const response = await fetch(`${CONFIG.apiUrl}/ingest/${source}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });

        if (!response.ok) {
            throw new Error(`Trigger failed: ${response.status}`);
        }

        const data = await response.json();
        logActivity(`Triggered ingestion for ${source}`);
        return data;
    } catch (error) {
        console.error('Error triggering ingestion:', error);
        logActivity(`Failed to trigger ${source}: ${error.message}`);
        throw error;
    }
}

// ============================================================================
// Render Functions
// ============================================================================
function updateSystemStatus(status) {
    elements.systemStatus.className = `status-indicator ${status}`;
    elements.systemStatus.innerHTML = `
        <span class="status-dot"></span>
        ${status === 'healthy' ? 'All Systems Operational' :
            status === 'degraded' ? 'Degraded Performance' :
                'System Error'}
    `;
}

function renderHealth(data) {
    const checks = data.checks || {};

    elements.healthGrid.innerHTML = `
        <div class="health-card">
            <div class="health-card-header">
                <span class="health-card-title">S3 Raw Bucket</span>
                <span class="health-card-status ${checks.s3_raw_bucket?.status || 'error'}">
                    ${checks.s3_raw_bucket?.status || 'unknown'}
                </span>
            </div>
            <div class="health-card-value">
                ${checks.s3_raw_bucket?.bucket ? '✓' : '✗'}
            </div>
        </div>
        
        <div class="health-card">
            <div class="health-card-header">
                <span class="health-card-title">DynamoDB</span>
                <span class="health-card-status ${checks.dynamodb_metadata?.status || 'error'}">
                    ${checks.dynamodb_metadata?.status || 'unknown'}
                </span>
            </div>
            <div class="health-card-value">
                ${checks.dynamodb_metadata?.table ? '✓' : '✗'}
            </div>
        </div>
        
        <div class="health-card">
            <div class="health-card-header">
                <span class="health-card-title">Lambda Functions</span>
                <span class="health-card-status ${checks.lambda_functions?.status || 'error'}">
                    ${checks.lambda_functions?.status || 'unknown'}
                </span>
            </div>
            <div class="health-card-value">
                ${checks.lambda_functions?.count || 0}
            </div>
        </div>
        
        <div class="health-card">
            <div class="health-card-header">
                <span class="health-card-title">Last Check</span>
                <span class="health-card-status ok">ok</span>
            </div>
            <div class="health-card-value" style="font-size: 1rem;">
                ${formatTime(data.timestamp)}
            </div>
        </div>
    `;
}

function renderSources(sources) {
    if (!sources || sources.length === 0) {
        elements.sourcesGrid.innerHTML = `
            <div class="source-card loading">
                <span>No data sources configured</span>
            </div>
        `;
        return;
    }

    elements.sourcesGrid.innerHTML = sources.map(source => `
        <div class="source-card" data-source="${source.id}">
            <div class="source-header">
                <div class="source-icon">${source.icon}</div>
                <div class="source-info">
                    <h3>${source.name}</h3>
                    <p>${source.description}</p>
                </div>
            </div>
            
            <div class="source-status">
                <span class="source-status-dot ${source.status}"></span>
                <span class="source-status-text">
                    ${source.status === 'success' ? 'Data Available' :
            source.status === 'no_data' ? 'No Data Yet' :
                source.status === 'failed' ? 'Last Ingestion Failed' :
                    'Unknown Status'}
                </span>
            </div>
            
            <div class="source-meta">
                <div class="source-meta-item">
                    <span class="source-meta-label">Last Ingestion</span>
                    <span class="source-meta-value">${formatDate(source.last_ingestion)}</span>
                </div>
                <div class="source-meta-item">
                    <span class="source-meta-label">Records</span>
                    <span class="source-meta-value">${source.record_count || '--'}</span>
                </div>
            </div>
            
            <div class="source-actions">
                <button class="btn btn-primary trigger-btn" data-source="${source.id}">
                    <span class="btn-icon">▶</span>
                    Trigger
                </button>
                <button class="btn btn-secondary view-btn" data-source="${source.id}">
                    View Data
                </button>
            </div>
        </div>
    `).join('');

    // Attach event listeners
    document.querySelectorAll('.trigger-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const source = btn.dataset.source;
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner" style="width:16px;height:16px;"></span>';
            try {
                await triggerIngestion(source);
                btn.innerHTML = '<span class="btn-icon">✓</span> Triggered';
                setTimeout(() => {
                    btn.innerHTML = '<span class="btn-icon">▶</span> Trigger';
                    btn.disabled = false;
                }, 2000);
            } catch (error) {
                btn.innerHTML = '<span class="btn-icon">✗</span> Failed';
                setTimeout(() => {
                    btn.innerHTML = '<span class="btn-icon">▶</span> Trigger';
                    btn.disabled = false;
                }, 2000);
            }
        });
    });

    // View Data button listeners
    document.querySelectorAll('.view-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const source = btn.dataset.source;
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner" style="width:16px;height:16px;"></span>';
            try {
                const response = await fetch(`${CONFIG.apiUrl}/data/${source}`);
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                const result = await response.json();

                logActivity(`Fetched ${source} data: ${result.s3_key}`);
                showDataModal(source, result);

                btn.innerHTML = 'View Data';
                btn.disabled = false;
            } catch (error) {
                logActivity(`Failed to fetch ${source} data: ${error.message}`);
                btn.innerHTML = '✗ No Data';
                setTimeout(() => {
                    btn.innerHTML = 'View Data';
                    btn.disabled = false;
                }, 2000);
            }
        });
    });
}

function renderActivityLog() {
    if (activityLog.length === 0) {
        elements.activityLog.innerHTML = `
            <div class="activity-item">
                <span class="activity-time">--:--</span>
                <span class="activity-message">Waiting for activity...</span>
            </div>
        `;
        return;
    }

    elements.activityLog.innerHTML = activityLog.map(item => `
        <div class="activity-item">
            <span class="activity-time">${item.time}</span>
            <span class="activity-message">${item.message}</span>
        </div>
    `).join('');
}

// ============================================================================
// Configuration Modal
// ============================================================================
function showConfigModal() {
    elements.apiInput.value = CONFIG.apiUrl;
    elements.configModal.classList.add('active');
}

function hideConfigModal() {
    elements.configModal.classList.remove('active');
}

function saveApiConfig() {
    const url = elements.apiInput.value.trim();
    if (url) {
        CONFIG.apiUrl = url.replace(/\/$/, ''); // Remove trailing slash
        localStorage.setItem('chimera_api_url', CONFIG.apiUrl);
        elements.apiUrl.textContent = `API: ${CONFIG.apiUrl}`;
        hideConfigModal();
        refreshAll();
        logActivity('API URL configured');
    }
}

// ============================================================================
// Refresh Logic
// ============================================================================
async function refreshAll() {
    if (!CONFIG.apiUrl) {
        elements.healthGrid.innerHTML = `
            <div class="health-card loading">
                <span>Click "API" in footer to configure API URL</span>
            </div>
        `;
        elements.sourcesGrid.innerHTML = `
            <div class="source-card loading">
                <span>API URL not configured</span>
            </div>
        `;
        return;
    }

    try {
        await Promise.all([fetchHealth(), fetchStatus()]);
    } catch (error) {
        console.error('Refresh failed:', error);
    }
}

function startAutoRefresh() {
    if (refreshTimer) clearInterval(refreshTimer);
    refreshTimer = setInterval(refreshAll, CONFIG.refreshInterval);
}

// ============================================================================
// Event Listeners
// ============================================================================
elements.refreshBtn.addEventListener('click', () => {
    elements.refreshBtn.querySelector('.btn-icon').style.animation = 'spin 0.5s linear';
    refreshAll().finally(() => {
        setTimeout(() => {
            elements.refreshBtn.querySelector('.btn-icon').style.animation = '';
        }, 500);
    });
});

elements.apiUrl.addEventListener('click', showConfigModal);
elements.saveConfig.addEventListener('click', saveApiConfig);
elements.cancelConfig.addEventListener('click', hideConfigModal);

elements.apiInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') saveApiConfig();
});

// Close modal on outside click
elements.configModal.addEventListener('click', (e) => {
    if (e.target === elements.configModal) hideConfigModal();
});

// Data modal event listeners
elements.closeDataModal?.addEventListener('click', hideDataModal);
elements.dataModal?.addEventListener('click', (e) => {
    if (e.target === elements.dataModal) hideDataModal();
});

// ============================================================================
// Data Modal Functions
// ============================================================================
function showDataModal(source, result) {
    const icons = {
        planetary: '🪐',
        geomagnetic: '🧲',
        schumann: '🌍',
        gcp: '🧠',
        market: '📈'
    };

    elements.dataModalTitle.innerHTML = `${icons[source] || '📊'} ${source.charAt(0).toUpperCase() + source.slice(1)} Data`;
    elements.dataS3Key.textContent = result.s3_key || '--';
    elements.dataLastModified.textContent = result.last_modified ? new Date(result.last_modified).toLocaleString() : '--';

    // Render data based on source type
    elements.dataViewer.innerHTML = renderDataVisualization(source, result.data);
    elements.dataModal.classList.add('active');
}

function hideDataModal() {
    elements.dataModal.classList.remove('active');
}

function renderDataVisualization(source, data) {
    switch (source) {
        case 'market':
            return renderMarketData(data);
        case 'planetary':
            return renderPlanetaryData(data);
        case 'geomagnetic':
            return renderGeomagneticData(data);
        default:
            return renderGenericData(data);
    }
}

function renderMarketData(data) {
    if (!data || !Array.isArray(data)) {
        return '<p style="color: var(--color-text-muted);">No market data available</p>';
    }

    return `
        <div class="stats-summary">
            <div class="stat-item">
                <div class="stat-value">${data.length}</div>
                <div class="stat-label">Records</div>
            </div>
        </div>
        <table class="data-table">
            <thead>
                <tr>
                    <th>Date</th>
                    <th>Open</th>
                    <th>High</th>
                    <th>Low</th>
                    <th>Close</th>
                    <th>Volume</th>
                </tr>
            </thead>
            <tbody>
                ${data.slice(0, 50).map(row => `
                    <tr>
                        <td>${row.Date || row.date || '--'}</td>
                        <td>$${Number(row.Open || row.open || 0).toFixed(2)}</td>
                        <td>$${Number(row.High || row.high || 0).toFixed(2)}</td>
                        <td>$${Number(row.Low || row.low || 0).toFixed(2)}</td>
                        <td><strong>$${Number(row.Close || row.close || 0).toFixed(2)}</strong></td>
                        <td>${Number(row.Volume || row.volume || 0).toLocaleString()}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

function renderPlanetaryData(data) {
    // NASA JPL Horizons returns ephemeris data in a specific format
    if (!data) {
        return '<p style="color: var(--color-text-muted);">No planetary data available</p>';
    }

    // Extract key info from Horizons response
    const result = data.result || '';
    const targetBody = result.match(/Target body name: ([^\n]+)/)?.[1] || 'Unknown';
    const centerBody = result.match(/Center body name: ([^\n]+)/)?.[1] || 'Unknown';

    return `
        <div class="data-cards-grid">
            <div class="data-card">
                <div class="data-card-title">🎯 Target Body</div>
                <div class="data-card-subtitle">${targetBody}</div>
            </div>
            <div class="data-card">
                <div class="data-card-title">🌐 Reference</div>
                <div class="data-card-subtitle">${centerBody}</div>
            </div>
            <div class="data-card">
                <div class="data-card-title">📡 API Version</div>
                <div class="data-card-subtitle">${data.signature?.version || 'v1.0'}</div>
            </div>
            <div class="data-card">
                <div class="data-card-title">📅 Source</div>
                <div class="data-card-subtitle">${data.signature?.source || 'NASA JPL Horizons'}</div>
            </div>
        </div>
        <div style="margin-top: var(--spacing-xl);">
            <h4 style="margin-bottom: var(--spacing-md); color: var(--color-text-secondary);">Ephemeris Data Preview</h4>
            <pre style="background: var(--color-bg-secondary); padding: var(--spacing-lg); border-radius: var(--radius-md); overflow-x: auto; font-size: var(--font-size-xs); max-height: 300px; overflow-y: auto;"><code>${escapeHtml(result.substring(0, 3000))}</code></pre>
        </div>
    `;
}

function renderGeomagneticData(data) {
    // Handle truncated data response
    if (data && data.message && data.message.includes('truncated')) {
        return `
            <div class="data-cards-grid">
                <div class="data-card">
                    <div class="data-card-title">📊 Data Size</div>
                    <div class="data-card-value">${Math.round(data.size / 1024)} KB</div>
                    <div class="data-card-subtitle">Data too large to display in browser</div>
                </div>
            </div>
            <p style="margin-top: var(--spacing-lg); color: var(--color-text-secondary);">
                ✅ Data successfully ingested and stored in S3. View raw files in AWS Console.
            </p>
        `;
    }

    if (!data || !Array.isArray(data)) {
        return '<p style="color: var(--color-text-muted);">No geomagnetic data available</p>';
    }

    const latestItems = data.slice(0, 20);

    return `
        <div class="stats-summary">
            <div class="stat-item">
                <div class="stat-value">${data.length}</div>
                <div class="stat-label">Records</div>
            </div>
        </div>
        <table class="data-table">
            <thead>
                <tr>
                    ${Object.keys(latestItems[0] || {}).slice(0, 6).map(key => `<th>${key}</th>`).join('')}
                </tr>
            </thead>
            <tbody>
                ${latestItems.map(row => `
                    <tr>
                        ${Object.values(row).slice(0, 6).map(val => `<td>${val}</td>`).join('')}
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

function renderGenericData(data) {
    if (!data) {
        return '<p style="color: var(--color-text-muted);">No data available</p>';
    }

    const jsonStr = JSON.stringify(data, null, 2);
    return `
        <pre style="background: var(--color-bg-secondary); padding: var(--spacing-lg); border-radius: var(--radius-md); overflow-x: auto; font-size: var(--font-size-sm); max-height: 500px; overflow-y: auto;"><code>${escapeHtml(jsonStr.substring(0, 10000))}</code></pre>
    `;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================================================
// Initialization
// ============================================================================
function init() {
    // Update API display
    if (CONFIG.apiUrl) {
        elements.apiUrl.textContent = `API: ${CONFIG.apiUrl}`;
    }

    logActivity('Dashboard initialized');
    refreshAll();
    startAutoRefresh();
}

// Start the app
document.addEventListener('DOMContentLoaded', init);
