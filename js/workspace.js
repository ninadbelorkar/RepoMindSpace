// workspace.js - Handles workspace creation and listing

document.addEventListener('DOMContentLoaded', () => {
    const ingestForm = document.getElementById('ingestForm');
    let isSubmitting = false;
    if (ingestForm) {
        ingestForm.addEventListener('submit', (e) => {
            e.preventDefault();
            if (isSubmitting) return;
            isSubmitting = true;
            
            const workspaceName = document.getElementById('workspaceName').value;
            const description = document.getElementById('workspaceDesc') ? document.getElementById('workspaceDesc').value : '';
            const repoUrl = document.getElementById('repoUrl').value;
            
            console.log(`Creating workspace: ${workspaceName} from ${repoUrl}`);
            
            // Show loading state
            const btn = ingestForm.querySelector('button[type="submit"]');
            btn.innerText = 'Fetching Repository (This may take a moment)...';
            btn.disabled = true;

            const token = localStorage.getItem('token');
            if (!token) {
                alert("You must be logged in to create a workspace.");
                window.location.href = 'login.html';
                return;
            }

            // Check which tab is active
            const isZipUpload = document.getElementById('tabZip') && document.getElementById('tabZip').classList.contains('active');
            
            let fetchOptions = {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            };

            if (isZipUpload) {
                const zipFile = document.getElementById('zipFile').files[0];
                if (!zipFile) {
                    alert('Please select a ZIP file to upload.');
                    btn.innerText = 'Create & Analyze Repository';
                    btn.disabled = false;
                    isSubmitting = false;
                    return;
                }
                const formData = new FormData();
                formData.append('name', workspaceName);
                formData.append('description', description);
                formData.append('file', zipFile);
                fetchOptions.body = formData;
            } else {
                fetchOptions.headers['Content-Type'] = 'application/json';
                fetchOptions.body = JSON.stringify({ name: workspaceName, description, repoUrl });
            }

            fetch(`${API_BASE}/api/workspace/create`, fetchOptions)
            .then(res => res.json())
            .then(data => {
                if (data.error) {
                    alert(`Error creating workspace: ${data.error}`);
                    btn.innerText = 'Create & Analyze Repository';
                    btn.disabled = false;
                    isSubmitting = false;
                } else {
                    // Mark that user has a workspace for the dashboard empty state
                    localStorage.setItem('hasWorkspace', 'true');
                    localStorage.setItem('lastWorkspaceName', workspaceName);
                    localStorage.setItem('currentWorkspaceId', data.workspace.id);
                    
                    // Redirect to workspace details
                    window.location.href = 'workspace-detail.html';
                }
            })
            .catch(err => {
                console.error(err);
                alert("Failed to connect to the server.");
                btn.innerText = 'Create & Analyze Repository';
                btn.disabled = false;
                isSubmitting = false;
            });
        });
    }

    // Function to fetch and render workspaces list
    function loadWorkspaces() {
        // Hide Getting Started section if workspace exists
        const gettingStarted = document.getElementById('gettingStartedSection');
        if (gettingStarted && localStorage.getItem('hasWorkspace') === 'true') {
            gettingStarted.style.display = 'none';
            
            const workspaceName = localStorage.getItem('lastWorkspaceName');

            // Update Metrics
            const token = localStorage.getItem('token');
            if (token) {
                fetch(`${API_BASE}/api/workspace/stats`, {
                    headers: { 'Authorization': `Bearer ${token}` }
                })
                .then(res => res.json())
                .then(stats => {
                    if (!stats.error) {
                        const metrics = document.querySelectorAll('.metric-value');
                        const trends = document.querySelectorAll('.trend-up, .trend-down');
                        if (metrics.length >= 4) {
                            metrics[0].innerText = stats.total_workspaces;
                            metrics[1].innerText = stats.repos_processed;
                            metrics[2].innerText = stats.generated_artifacts;
                            metrics[3].innerText = stats.total_chats;
                        }
                        
                        // Update Trends
                        if (stats.growth && trends.length >= 4) {
                            const setTrend = (el, val) => {
                                el.innerText = `${val >= 0 ? '+' : ''}${val}% this week`;
                                el.className = val >= 0 ? 'trend-up' : 'trend-down';
                                if (val < 0) el.style.color = '#ef4444';
                                else el.style.color = 'var(--success)';
                            };
                            setTrend(trends[0], stats.growth.workspaces);
                            setTrend(trends[1], stats.growth.repos);
                            setTrend(trends[2], stats.growth.artifacts);
                            setTrend(trends[3], stats.growth.chats);
                        }
                        
                        // Render Weekly Chart
                        if (stats.chart && document.getElementById('weeklyChart')) {
                            const chartSection = document.getElementById('weeklyChartSection');
                            if (chartSection) chartSection.style.display = 'block';
                            
                            const ctx = document.getElementById('weeklyChart').getContext('2d');
                            new Chart(ctx, {
                                type: 'line',
                                data: {
                                    labels: stats.chart.labels,
                                    datasets: [{
                                        label: 'Artifacts Generated',
                                        data: stats.chart.data,
                                        borderColor: '#a855f7',
                                        backgroundColor: 'rgba(168, 85, 247, 0.1)',
                                        borderWidth: 2,
                                        fill: true,
                                        tension: 0.4
                                    }]
                                },
                                options: {
                                    responsive: true,
                                    maintainAspectRatio: false,
                                    plugins: { legend: { display: false } },
                                    scales: {
                                        y: { beginAtZero: true, grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { stepSize: 1 } },
                                        x: { grid: { display: false } }
                                    }
                                }
                            });
                        }
                    }
                })
                .catch(err => console.error("Error fetching stats:", err));
            }

            // Update Recent Activity
            const recentActivityList = document.getElementById('recentActivityList');
            if (recentActivityList) {
                recentActivityList.innerHTML = `
                    <div style="display: flex; align-items: flex-start; gap: 1rem; margin-bottom: 1.5rem;">
                        <div style="color: var(--success); padding: 0.25rem;"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg></div>
                        <div>
                            <p class="mb-1" style="font-weight: 500;">Workspace <strong>${workspaceName}</strong> created</p>
                            <span class="text-muted" style="font-size: 0.875rem;">Just now</span>
                        </div>
                    </div>
                    <div style="display: flex; align-items: flex-start; gap: 1rem;">
                        <div style="color: var(--success); padding: 0.25rem;"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg></div>
                        <div>
                            <p class="mb-1" style="font-weight: 500;">Repository analysis completed</p>
                            <span class="text-muted" style="font-size: 0.875rem;">Just now</span>
                        </div>
                    </div>
                `;
            }

            // Update Recent Repositories
            const recentReposList = document.getElementById('recentReposList');
            if (recentReposList) {
                recentReposList.innerHTML = `
                    <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.05); padding: 1.5rem; border-radius: 0.75rem; display: flex; justify-content: space-between; align-items: center; transition: all 0.2s;">
                        <div>
                            <h4 class="mb-1" style="font-size: 1.125rem;">${workspaceName}</h4>
                            <span class="text-muted" style="font-size: 0.875rem;">JavaScript • HTML • CSS</span>
                        </div>
                        <a href="workspace-detail.html" class="btn btn-secondary" style="padding: 0.5rem 1rem; font-size: 0.875rem;">View</a>
                    </div>
                `;
            }
        }
    }

    const token = localStorage.getItem('token');
    if (token) {
        fetch(`${API_BASE}/api/workspace/recent`, {
            headers: { 'Authorization': `Bearer ${token}` }
        })
        .then(res => res.json())
        .then(data => {
            if (data.has_workspace) {
                localStorage.setItem('hasWorkspace', 'true');
                localStorage.setItem('lastWorkspaceName', data.workspace.name);
                localStorage.setItem('currentWorkspaceId', data.workspace.id);
            } else {
                localStorage.removeItem('hasWorkspace');
                localStorage.removeItem('lastWorkspaceName');
                localStorage.removeItem('currentWorkspaceId');
            }
            loadWorkspaces();
            loadWorkspacesPage();
        })
        .catch(err => {
            console.error("Error fetching recent workspace:", err);
            loadWorkspaces();
            loadWorkspacesPage();
        });
    } else {
        loadWorkspaces();
        loadWorkspacesPage();
    }

    // Logic for workspaces.html specific view - loads ALL workspaces from API
    function loadWorkspacesPage() {
        const emptyState = document.getElementById('workspacesEmptyState');
        const populatedState = document.getElementById('workspacesPopulatedState');
        if (!emptyState || !populatedState) return;

        const token = localStorage.getItem('token');
        if (!token) {
            emptyState.style.display = 'block';
            populatedState.style.display = 'none';
            return;
        }

        // Fetch real workspaces from backend
        fetch(`${API_BASE}/api/workspace/list`, {
            headers: { 'Authorization': `Bearer ${token}` }
        })
        .then(res => res.json())
        .then(data => {
            const workspaces = data.workspaces || [];

            if (workspaces.length === 0) {
                emptyState.style.display = 'block';
                populatedState.style.display = 'none';
                return;
            }

            emptyState.style.display = 'none';
            populatedState.style.display = 'block';

            // Update localStorage with most recent workspace
            localStorage.setItem('hasWorkspace', 'true');
            localStorage.setItem('lastWorkspaceName', workspaces[0].name);
            localStorage.setItem('currentWorkspaceId', workspaces[0].id);

            // Fetch and display stats
            fetch(`${API_BASE}/api/workspace/stats`, {
                headers: { 'Authorization': `Bearer ${token}` }
            })
            .then(r => r.json())
            .then(stats => {
                if (!stats.error) {
                    const setEl = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val; };
                    setEl('statTotalWorkspaces', stats.total_workspaces);
                    setEl('statRepositories', stats.repos_processed);
                    setEl('statArtifacts', stats.generated_artifacts);
                    setEl('statChats', stats.total_chats);
                }
            })
            .catch(err => console.error('Stats error:', err));

            // Render workspaces list
            const workspacesList = document.getElementById('workspacesList');
            if (workspacesList) {
                workspacesList.innerHTML = workspaces.map(ws => `
                    <div class="card glow-card" data-ws-id="${ws.id}" style="margin-bottom: 1.5rem;">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1rem;">
                            <h3 style="margin: 0; font-size: 1.25rem;">${ws.name}</h3>
                            <div style="display: flex; gap: 0.5rem; align-items: center;">
                                <span style="font-size: 0.75rem; color: var(--text-muted);">${ws.status === 'ready' ? '✅ Ready' : ws.status}</span>
                                <button onclick="deleteWorkspace('${ws.id}', this)" title="Delete workspace" style="background: transparent; border: none; color: var(--text-muted); cursor: pointer; padding: 4px; border-radius: 4px; transition: color 0.2s;" onmouseover="this.style.color='#ef4444'" onmouseout="this.style.color='var(--text-muted)'">
                                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:16px;height:16px;"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg>
                                </button>
                            </div>
                        </div>
                        ${ws.description ? `<p style="color: var(--text-muted); font-size: 0.875rem; margin-bottom: 1rem;">${ws.description}</p>` : ''}
                        <div style="margin-bottom: 1.25rem; display: flex; flex-wrap: wrap; gap: 0.5rem;">
                            ${ws.technologies.map(t => `<span class="tech-badge">${t}</span>`).join('')}
                        </div>
                        <div class="grid grid-cols-3" style="gap: 1rem; margin-bottom: 1.5rem;">
                            <div>
                                <div class="text-muted" style="font-size: 0.75rem; text-transform: uppercase; margin-bottom: 0.25rem;">Artifacts</div>
                                <div style="font-weight: 600;">${ws.artifact_count}</div>
                            </div>
                            <div>
                                <div class="text-muted" style="font-size: 0.75rem; text-transform: uppercase; margin-bottom: 0.25rem;">Chats</div>
                                <div style="font-weight: 600;">${ws.chat_count}</div>
                            </div>
                            <div>
                                <div class="text-muted" style="font-size: 0.75rem; text-transform: uppercase; margin-bottom: 0.25rem;">Repo</div>
                                <div style="font-weight: 600; font-size: 0.75rem; word-break: break-all;">${ws.repo_url ? ws.repo_url.replace('https://github.com/', '') : 'Local'}</div>
                            </div>
                        </div>
                        <a href="workspace-detail.html" onclick="localStorage.setItem('currentWorkspaceId','${ws.id}'); localStorage.setItem('lastWorkspaceName','${ws.name}');" class="btn btn-secondary text-center" style="width: 100%; display: block;">Open Workspace</a>
                    </div>
                `).join('');
            }

            // Activity log
            const activityLog = document.getElementById('activityLog');
            if (activityLog) {
                activityLog.innerHTML = workspaces.slice(0, 5).map(ws => `
                    <div class="activity-item">
                        <div class="activity-icon"></div>
                        <div class="activity-content">
                            <h4>${ws.name}</h4>
                            <p>${ws.description || 'Repository workspace'} &mdash; ${ws.artifact_count} artifact(s), ${ws.chat_count} chat(s)</p>
                        </div>
                    </div>
                `).join('');
            }
        })
        .catch(err => {
            console.error('Error loading workspaces:', err);
            emptyState.style.display = 'block';
            populatedState.style.display = 'none';
        });
    }
});

// Global delete workspace function
function deleteWorkspace(workspaceId, btn) {
    if (!confirm('Delete this workspace? This will also remove all its artifacts and chats.')) return;
    const token = localStorage.getItem('token');
    btn.disabled = true;
    fetch(`${API_BASE}/api/workspace/${workspaceId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
    })
    .then(res => res.json())
    .then(data => {
        if (data.error) {
            alert('Error: ' + data.error);
            btn.disabled = false;
        } else {
            // Remove card from DOM
            const card = document.querySelector(`[data-ws-id="${workspaceId}"]`);
            if (card) card.remove();
            // Clear localStorage if this was the current workspace
            if (localStorage.getItem('currentWorkspaceId') === workspaceId) {
                localStorage.removeItem('currentWorkspaceId');
                localStorage.removeItem('lastWorkspaceName');
                localStorage.removeItem('hasWorkspace');
            }
            // Reload page to update stats
            window.location.reload();
        }
    })
    .catch(err => { alert('Network error'); btn.disabled = false; });
}
