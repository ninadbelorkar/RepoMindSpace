// artifacts.js - Handles fetching, saving, and exporting generated artifacts

document.addEventListener('DOMContentLoaded', () => {
    console.log('Artifacts module loaded.');

    let allArtifacts = [];

    // Function to load the list of saved artifacts
    async function loadArtifacts() {
        const workspaceId = localStorage.getItem('currentWorkspaceId');
        const token = localStorage.getItem('token');
        if (!workspaceId || !token) return;

        // Check if we are on the artifacts.html page by looking for the grid container
        const gridContainer = document.getElementById('populatedGridContainer');
        const emptyStateContainer = document.getElementById('emptyStateContainer');
        
        if (gridContainer) {
            try {
                const response = await fetch(`${API_BASE}/api/artifacts/workspace/${workspaceId}`, {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                const data = await response.json();
                
                if (data.artifacts) {
                    allArtifacts = data.artifacts;
                    let total = allArtifacts.length;
                    let docs = 0;
                    let reports = 0;
                    let tests = 0;
                    
                    if (total > 0) {
                        allArtifacts.forEach(art => {
                            const t = art.type.toLowerCase();
                            if (t === 'readme' || t === 'architecture' || t === 'api' || t === 'docs') docs++;
                            else if (t === 'testcases') tests++;
                            else reports++; // BugAnalysis, CommitSummary, etc.
                        });
                        
                        if (emptyStateContainer) emptyStateContainer.style.display = 'none';
                        gridContainer.style.display = 'grid';
                        renderArtifacts(allArtifacts);
                        setupFiltersAndSearch();
                        
                        // Update DOM counters
                        const countTotal = document.getElementById('countTotal');
                        const countDocs = document.getElementById('countDocs');
                        const countReports = document.getElementById('countReports');
                        const countTests = document.getElementById('countTests');
                        
                        if (countTotal) countTotal.innerText = total;
                        if (countDocs) countDocs.innerText = docs;
                        if (countReports) countReports.innerText = reports;
                        if (countTests) countTests.innerText = tests;
                    }
                }
            } catch (err) {
                console.error("Failed to load saved artifacts", err);
            }
        }
    }

    function renderArtifacts(artifactsToRender) {
        const gridContainer = document.getElementById('populatedGridContainer');
        if (!gridContainer) return;
        
        gridContainer.innerHTML = '';
        
        if (artifactsToRender.length === 0) {
            gridContainer.innerHTML = '<div style="color: var(--text-muted); padding: 2rem; grid-column: 1 / -1; text-align: center;">No artifacts found matching your criteria.</div>';
            return;
        }
        
        artifactsToRender.forEach(art => {
            const t = art.type.toLowerCase();
            let icon = '📄';
            let category = art.type;
            if (t === 'readme') { icon = '📘'; }
            else if (t === 'architecture' || t === 'api') { icon = '🧩'; category = 'Documentation'; }
            else if (t === 'testcases') { icon = '🧪'; category = 'Tests'; }
            else if (t === 'buganalysis') { icon = '🐞'; category = 'Analysis'; }
            else if (t === 'commitsummary') { icon = '📊'; category = 'Report'; }
            
            const date = new Date(art.created_at).toLocaleDateString();
            
            const card = document.createElement('div');
            card.className = 'glass-card artifact-item-card';
            card.innerHTML = `
                <div style="display: flex; justify-content: space-between; margin-bottom: 1rem;">
                    <div style="display: flex; align-items: center; gap: 0.75rem;">
                        <span style="font-size: 1.5rem;">${icon}</span>
                        <span class="tech-pill" style="background: rgba(124, 58, 237, 0.15); color: #c4b5fd; border: none;">${category}</span>
                    </div>
                    <span style="color: var(--text-muted); font-size: 0.8rem;">${date}</span>
                </div>
                <h3 style="color: var(--text-main); font-size: 1.25rem; font-weight: 600; margin-bottom: 0.5rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${art.title}">${art.title}</h3>
                <p style="color: var(--text-muted); font-size: 0.9rem; line-height: 1.5; margin-bottom: 1.5rem; flex-grow: 1;">
                    Auto-generated ${category.toLowerCase()} document.
                </p>
                <div style="display: flex; gap: 0.5rem; border-top: 1px solid var(--alpha-5); padding-top: 1rem;">
                    <a href="edit-artifact.html?id=${art.id}" class="tech-pill" style="flex: 1; justify-content: center; background: var(--alpha-5); border-color: var(--alpha-10); color: var(--text-main); text-decoration: none; display: flex; align-items: center;">View</a>
                </div>
            `;
            gridContainer.appendChild(card);
        });
    }

    function setupFiltersAndSearch() {
        const searchInput = document.querySelector('.search-input');
        const filterTabs = document.querySelectorAll('.filter-tab');
        
        let currentFilter = 'All';
        let currentSearch = '';
        
        function applyFilters() {
            let filtered = allArtifacts;
            
            if (currentFilter !== 'All') {
                filtered = filtered.filter(art => {
                    const t = art.type.toLowerCase();
                    const f = currentFilter.toLowerCase();
                    if (f === 'readme') return t === 'readme';
                    if (f === 'docs') return t === 'architecture' || t === 'api' || t === 'docs';
                    if (f === 'tests') return t === 'testcases';
                    if (f === 'reports') return t === 'buganalysis' || t === 'commitsummary';
                    if (f === 'user stories') return t === 'userstories';
                    return t === f;
                });
            }
            
            if (currentSearch) {
                const s = currentSearch.toLowerCase();
                filtered = filtered.filter(art => 
                    art.title.toLowerCase().includes(s) || 
                    art.type.toLowerCase().includes(s)
                );
            }
            
            renderArtifacts(filtered);
        }
        
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                currentSearch = e.target.value.trim();
                applyFilters();
            });
        }
        
        filterTabs.forEach(tab => {
            tab.addEventListener('click', (e) => {
                currentFilter = e.target.innerText.trim();
                applyFilters();
            });
        });
    }

    // Function to handle saving changes to an artifact
    window.saveArtifactChanges = async (id, content) => {
        console.log(`Saving changes for artifact ${id}...`);
        // API call to PUT/PATCH the artifact
    };

    // Function to handle exporting an artifact
    window.exportArtifact = (id, format) => {
        console.log(`Exporting artifact ${id} as ${format}...`);
        // API call to download the artifact
    };

    loadArtifacts();
});
