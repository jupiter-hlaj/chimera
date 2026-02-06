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
    closeDataModal: document.getElementById('close-data-modal'),
    // Alignment
    triggerAlignmentBtn: document.getElementById('trigger-alignment-btn'),
    alignmentCard: document.getElementById('alignment-card'),
    alignmentFile: document.getElementById('alignment-file'),
    alignmentTime: document.getElementById('alignment-time'),
    alignmentSize: document.getElementById('alignment-size'),
    // AI Analysis
    triggerAnalysisBtn: document.getElementById('trigger-analysis-btn'),
    analysisCard: document.getElementById('analysis-card'),
    analysisStatus: document.getElementById('analysis-status'),
    analysisCount: document.getElementById('analysis-count'),
    analysisTime: document.getElementById('analysis-time'),
    correlationsPreview: document.getElementById('correlations-preview'),
    correlationList: document.getElementById('correlation-list')
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
async function fetchAlignmentStatus() {
    try {
        const data = await fetchAPI('/processed');

        elements.alignmentFile.textContent = data.latest_file.replace('master_aligned_', '');
        elements.alignmentTime.textContent = formatDate(data.last_modified);
        elements.alignmentSize.textContent = `${Math.round(data.size / 1024)} KB`;
        elements.alignmentCard.classList.remove('active'); // Stop pulsing if it was pulsing

    } catch (error) {
        if (error.message.includes('404')) {
            elements.alignmentFile.textContent = 'No aligned data found';
            elements.alignmentTime.textContent = '--';
            elements.alignmentSize.textContent = '--';
        } else {
            console.warn('Alignment status check failed:', error);
            elements.alignmentFile.textContent = 'Check failed';
        }
    }
}

async function triggerAlignment() {
    try {
        elements.triggerAlignmentBtn.disabled = true;
        elements.alignmentCard.classList.add('active'); // Pulse effect
        elements.alignmentFile.textContent = 'Processing...';

        const response = await fetch(`${CONFIG.apiUrl}/process`, { method: 'POST' });
        if (!response.ok) throw new Error('Failed to trigger');

        const result = await response.json();

        logActivity(`Alignment job started: ${result.function}`);

        // Poll for updates a few times
        setTimeout(fetchAlignmentStatus, 2000);
        setTimeout(fetchAlignmentStatus, 5000);
        setTimeout(fetchAlignmentStatus, 10000);

    } catch (error) {
        logActivity('Failed to trigger alignment');
        console.error(error);
        elements.alignmentCard.classList.remove('active');
    } finally {
        setTimeout(() => {
            elements.triggerAlignmentBtn.disabled = false;
        }, 1000);
    }
}

async function fetchCorrelationStatus() {
    try {
        const data = await fetchAPI('/correlations');

        if (data.message && data.message.includes('No correlations')) {
            elements.analysisStatus.textContent = 'No analysis yet';
            elements.analysisCount.textContent = '--';
            elements.analysisTime.textContent = '--';
            elements.correlationsPreview.style.display = 'none';
            return;
        }

        elements.analysisStatus.textContent = `${data.total_correlations_found} correlations found`;
        elements.analysisCount.textContent = `Shape: ${data.data_shape?.[0]}×${data.data_shape?.[1]}`;
        elements.analysisTime.textContent = formatDate(data.generated_at);

        // Show top correlations
        if (data.top_correlations && data.top_correlations.length > 0) {
            renderCorrelations(data.top_correlations.slice(0, 5));
            elements.correlationsPreview.style.display = 'block';
        }

    } catch (error) {
        if (error.message.includes('404')) {
            elements.analysisStatus.textContent = 'No analysis yet';
            elements.analysisCount.textContent = '--';
            elements.analysisTime.textContent = '--';
        } else {
            console.warn('Correlation status check failed:', error);
            elements.analysisStatus.textContent = 'Check failed';
        }
    }
}

function renderCorrelations(correlations) {
    elements.correlationList.innerHTML = correlations.map(c => {
        const insight = generateInsight(c);
        const strength = getStrengthLabel(c.correlation);
        const direction = c.correlation > 0 ? 'positive' : 'negative';
        const barWidth = Math.abs(c.correlation) * 100;
        const directionArrow = c.correlation > 0 ? '↗' : '↘';

        return `
            <div class="correlation-card">
                <div class="correlation-header">
                    <span class="strength-badge ${strength.class}">${strength.label}</span>
                    ${c.lag_hours > 0 ? `<span class="predictive-badge">🔮 Predictive</span>` : ''}
                    <span class="direction-indicator ${direction}">${directionArrow}</span>
                </div>
                
                <div class="correlation-visual">
                    <div class="strength-bar-container">
                        <div class="strength-bar ${direction}" style="width: ${barWidth}%"></div>
                    </div>
                    <span class="strength-percent ${direction}">${(c.correlation * 100).toFixed(0)}%</span>
                </div>
                
                <div class="correlation-insight">
                    <p class="insight-main">${insight.headline}</p>
                    <p class="insight-detail">${insight.explanation}</p>
                </div>
                
                <div class="correlation-footer">
                    <span class="correlation-stat">
                        <span class="stat-label">Sample Size</span>
                        <span class="stat-value">${c.sample_size} hrs</span>
                    </span>
                    ${c.lag_hours > 0 ? `
                    <span class="correlation-stat">
                        <span class="stat-label">Lead Time</span>
                        <span class="stat-value highlight">${c.lag_hours}h ahead</span>
                    </span>
                    ` : `
                    <span class="correlation-stat">
                        <span class="stat-label">Timing</span>
                        <span class="stat-value">Real-time</span>
                    </span>
                    `}
                </div>
            </div>
        `;
    }).join('');
}

function getStrengthLabel(r) {
    const abs = Math.abs(r);
    if (abs >= 0.7) return { label: 'Very Strong', class: 'very-strong' };
    if (abs >= 0.5) return { label: 'Strong', class: 'strong' };
    if (abs >= 0.4) return { label: 'Moderate', class: 'moderate' };
    return { label: 'Weak', class: 'weak' };
}

function generateInsight(c) {
    const market = formatMarketFactor(c.market_factor);
    const env = formatEnvFactor(c.environmental_factor);
    const direction = c.correlation > 0;
    const lag = c.lag_hours;

    // Generate headline
    let headline = '';
    let explanation = '';

    if (lag > 0) {
        // Predictive correlation
        headline = direction
            ? `When ${env.name} increases, ${market.name} tends to rise ${lag}h later`
            : `When ${env.name} increases, ${market.name} tends to fall ${lag}h later`;
        explanation = `${env.description} appears to ${direction ? 'positively' : 'negatively'} predict ${market.description} with a ${lag}-hour lead time. This could be useful for forecasting.`;
    } else {
        // Instant correlation
        headline = direction
            ? `${market.name} and ${env.name} move together`
            : `${market.name} and ${env.name} move in opposite directions`;
        explanation = `When ${env.description} changes, ${market.description} shows a ${direction ? 'similar' : 'contrary'} movement at the same time.`;
    }

    return { headline, explanation };
}

function formatMarketFactor(factor) {
    const map = {
        'market_vix_open': { name: 'VIX (Volatility)', description: 'market fear/volatility' },
        'market_vix_high': { name: 'VIX High', description: 'peak volatility' },
        'market_vix_low': { name: 'VIX Low', description: 'minimum volatility' },
        'market_vix_close': { name: 'VIX Close', description: 'closing volatility' },
        'market_spy_close': { name: 'S&P 500', description: 'the stock market (S&P 500)' },
        'market_spy_volume': { name: 'SPY Volume', description: 'trading volume' },
        'market_qqq_close': { name: 'Nasdaq (QQQ)', description: 'tech stocks' },
        'market_gld_close': { name: 'Gold', description: 'gold prices' },
        'market_tlt_close': { name: 'Bonds (TLT)', description: 'long-term bonds' }
    };
    return map[factor] || { name: factor.replace('market_', '').replace(/_/g, ' '), description: factor };
}

function formatEnvFactor(factor) {
    const parts = factor.toLowerCase();

    if (parts.includes('schumann')) {
        if (parts.includes('amplitude')) return { name: "Schumann Resonance", description: "Earth's electromagnetic resonance amplitude" };
        if (parts.includes('frequency')) return { name: "Schumann Frequency", description: "Earth's natural frequency" };
        return { name: "Schumann Resonance", description: "Earth's electromagnetic field activity" };
    }
    if (parts.includes('planetary')) {
        if (parts.includes('mars')) return { name: "Mars Position", description: "Mars angular position" };
        if (parts.includes('venus')) return { name: "Venus Position", description: "Venus angular position" };
        if (parts.includes('jupiter')) return { name: "Jupiter Position", description: "Jupiter angular position" };
        if (parts.includes('moon')) return { name: "Lunar Phase", description: "Moon phase/position" };
        if (parts.includes('sun')) return { name: "Solar Position", description: "Sun position" };
        return { name: "Planetary Factor", description: "planetary position data" };
    }
    if (parts.includes('kp') || parts.includes('geomagnetic')) {
        return { name: "Geomagnetic Activity", description: "Earth's geomagnetic field disturbance (Kp index)" };
    }
    if (parts.includes('solar') || parts.includes('flux')) {
        return { name: "Solar Activity", description: "solar radio flux/sunspot activity" };
    }
    if (parts.includes('gcp')) {
        return { name: "Global Consciousness", description: "GCP random number generator coherence" };
    }

    return { name: factor.replace(/_/g, ' '), description: factor };
}

async function triggerAnalysis() {
    try {
        elements.triggerAnalysisBtn.disabled = true;
        elements.analysisCard.classList.add('active');
        elements.analysisStatus.textContent = 'Processing...';

        const response = await fetch(`${CONFIG.apiUrl}/analyze`, { method: 'POST' });
        if (!response.ok) throw new Error('Failed to trigger');

        const result = await response.json();

        logActivity(`Correlation analysis started: ${result.function}`);

        // Poll for updates
        setTimeout(fetchCorrelationStatus, 3000);
        setTimeout(fetchCorrelationStatus, 8000);
        setTimeout(fetchCorrelationStatus, 15000);

    } catch (error) {
        logActivity('Failed to trigger analysis');
        console.error(error);
        elements.analysisCard.classList.remove('active');
    } finally {
        setTimeout(() => {
            elements.triggerAnalysisBtn.disabled = false;
        }, 1000);
    }
}

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
        await Promise.all([fetchHealth(), fetchStatus(), fetchAlignmentStatus(), fetchCorrelationStatus()]);
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

if (elements.triggerAlignmentBtn) {
    elements.triggerAlignmentBtn.addEventListener('click', triggerAlignment);
}

if (elements.triggerAnalysisBtn) {
    elements.triggerAnalysisBtn.addEventListener('click', triggerAnalysis);
}

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
    if (!data || Object.keys(data).length === 0) {
        return '<p style="color: var(--color-text-muted);">No data available</p>';
    }

    // Generate tabs for entities
    const entities = Object.keys(data).sort();
    let html = `
        <div class="entity-tabs" style="display: flex; gap: 10px; margin-bottom: 20px; overflow-x: auto; padding-bottom: 10px;">
            ${entities.map((entity, index) => `
                <button class="btn btn-secondary entity-tab ${index === 0 ? 'active' : ''}" 
                    style="${index === 0 ? 'background: var(--color-accent-primary); color: white;' : ''}"
                    onclick="switchEntityTab(this, '${entity}')">
                    ${entity}
                </button>
            `).join('')}
        </div>
    `;

    // Generate content for each entity
    entities.forEach((entity, index) => {
        html += `<div id="entity-${entity}" class="entity-content" style="${index === 0 ? 'display: block;' : 'display: none;'}">`;

        const entityData = data[entity];

        // Handle truncated data special case
        if (entityData && entityData.message && entityData.message.includes('truncated')) {
            html += `
                <div class="data-cards-grid">
                    <div class="data-card">
                        <div class="data-card-title">📊 Data Size</div>
                        <div class="data-card-value">${Math.round((entityData.size || 0) / 1024)} KB</div>
                        <div class="data-card-subtitle">Data too large to display in browser</div>
                        <div style="margin-top: 10px; font-size: 0.8em; color: var(--color-text-muted); word-break: break-all;">S3 Key: ${entityData.s3_key || 'Unknown'}</div>
                    </div>
                </div>
            `;
        } else {
            switch (source) {
                case 'market':
                    html += renderMarketData(entityData);
                    break;
                case 'planetary':
                    html += renderPlanetaryData(entityData);
                    break;
                case 'geomagnetic':
                    html += renderGeomagneticData(entityData);
                    break;
                default:
                    html += renderGenericData(entityData);
            }
        }

        html += `</div>`;
    });

    // Add tab switching script to global scope if not exists
    if (!window.switchEntityTab) {
        window.switchEntityTab = function (btn, entityId) {
            // Reset all tabs
            document.querySelectorAll('.entity-tab').forEach(t => {
                t.style.background = '';
                t.style.color = '';
                t.classList.remove('active');
            });
            // Activate clicked tab
            btn.style.background = 'var(--color-accent-primary)';
            btn.style.color = 'white';
            btn.classList.add('active');

            // Hide all content
            document.querySelectorAll('.entity-content').forEach(c => c.style.display = 'none');
            // Show selected content
            document.getElementById(`entity-${entityId}`).style.display = 'block';
        };
    }

    return html;
}

function renderMarketData(data) {
    if (!data || !Array.isArray(data)) {
        return '<p style="color: var(--color-text-muted);">No market data available</p>';
    }

    // Sort by date descending
    const sortedData = [...data].sort((a, b) => new Date(b.Date || b.date) - new Date(a.Date || a.date));

    return `
        <div class="stats-summary">
            <div class="stat-item">
                <div class="stat-value">${data.length}</div>
                <div class="stat-label">Days</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">${sortedData[0]?.Close?.toFixed(2) || sortedData[0]?.close?.toFixed(2) || '--'}</div>
                <div class="stat-label">Last Close</div>
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
                ${sortedData.slice(0, 100).map(row => `
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
    if (!data) return '<p>No data</p>';

    // Check if it's new aggregated format or legacy
    const result = data.result || '';
    if (!result) return '<p>Invalid planetary data format</p>';

    const targetBody = result.match(/Target body name: ([^\n]+)/)?.[1] || 'Unknown';

    return `
        <div class="data-cards-grid">
            <div class="data-card">
                <div class="data-card-title">🎯 Target</div>
                <div class="data-card-subtitle">${targetBody}</div>
            </div>
        </div>
        <div style="margin-top: var(--spacing-xl);">
            <pre style="background: var(--color-bg-secondary); padding: var(--spacing-lg); border-radius: var(--radius-md); overflow-x: auto; font-size: var(--font-size-xs); max-height: 500px; overflow-y: auto;"><code>${escapeHtml(result)}</code></pre>
        </div>
    `;
}

function renderGeomagneticData(data) {
    if (!data || !Array.isArray(data)) {
        return '<p style="color: var(--color-text-muted);">No geomagnetic records available</p>';
    }

    const latestItems = data.slice(0, 50);

    return `
        <div class="stats-summary">
            <div class="stat-item">
                <div class="stat-value">${data.length}</div>
                <div class="stat-label">Records</div>
            </div>
        </div>
        <div style="overflow-x: auto;">
            <table class="data-table">
                <thead>
                    <tr>
                        ${Object.keys(latestItems[0] || {}).map(key => `<th>${key}</th>`).join('')}
                    </tr>
                </thead>
                <tbody>
                    ${latestItems.map(row => `
                        <tr>
                            ${Object.values(row).map(val => `<td>${val}</td>`).join('')}
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;
}

function renderGenericData(data) {
    const jsonStr = JSON.stringify(data, null, 2);
    return `
        <pre style="background: var(--color-bg-secondary); padding: var(--spacing-lg); border-radius: var(--radius-md); overflow-x: auto; font-size: var(--font-size-sm); max-height: 500px; overflow-y: auto;"><code>${escapeHtml(jsonStr.substring(0, 20000))}</code></pre>
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
