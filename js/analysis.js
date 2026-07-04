// analysis.js - Handles repository analysis data fetching and display

document.addEventListener('DOMContentLoaded', () => {
    
    // Function to animate the circular progress indicator
    function animateProgress() {
        const circle = document.getElementById('progressCircle');
        const value = document.getElementById('progressValue');
        if (!circle || !value) return;

        // The circle's stroke-dasharray is 339.292 (2 * pi * 54)
        const circumference = 339.292;
        
        // Define animation steps
        const steps = [
            { percent: 0, delay: 0 },
            { percent: 40, delay: 500 },
            { percent: 75, delay: 1500 },
            { percent: 100, delay: 2200 }
        ];

        steps.forEach(step => {
            setTimeout(() => {
                const offset = circumference - (step.percent / 100) * circumference;
                circle.style.strokeDashoffset = offset;
                
                // Animate text counter
                let currentVal = parseInt(value.innerText) || 0;
                const targetVal = step.percent;
                const diff = targetVal - currentVal;
                const stepTime = Math.max(20, 500 / (diff || 1));
                
                if (diff > 0) {
                    let counter = currentVal;
                    const timer = setInterval(() => {
                        counter += 1;
                        value.innerText = `${counter}%`;
                        if (counter >= targetVal) clearInterval(timer);
                    }, stepTime);
                }
            }, step.delay);
        });
    }

    // Function to fetch repository analysis data
    function loadAnalysisData() {
        console.log('Fetching analysis data for the current workspace...');
        
        const workspaceId = localStorage.getItem('currentWorkspaceId');
        const token = localStorage.getItem('token');
        const workspaceNameFallback = localStorage.getItem('lastWorkspaceName') || 'Workspace';

        // Set fallback immediately
        const metaRepoName = document.getElementById('metaRepoName');
        if (metaRepoName) metaRepoName.innerText = workspaceNameFallback;
        const workspaceNameHeader = document.getElementById('workspaceNameHeader');
        if (workspaceNameHeader) workspaceNameHeader.innerText = workspaceNameFallback;

        if (!workspaceId || !token) {
            console.warn("No workspace ID or token found in localStorage.");
            return;
        }

        fetch(`${API_BASE}/api/workspace/${workspaceId}`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        })
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                console.error("Error fetching workspace:", data.error);
                return;
            }

            // Update Repo Name Badges/Headers
            if (metaRepoName) metaRepoName.innerText = data.name;
            if (workspaceNameHeader) workspaceNameHeader.innerText = data.name;

            // Update Total Files
            const metricTotalFiles = document.getElementById('metricTotalFiles');
            if (metricTotalFiles) {
                metricTotalFiles.innerText = data.total_files;
            }

            // Update Summary
            const summaryText = document.getElementById('summaryText');
            if (summaryText) {
                summaryText.innerText = `This repository (${data.name}) contains ${data.total_files} files and is primarily built using ${data.technologies.join(', ')}.`;
            }

            // Update Technology Stack container (assuming it's the element after the summary)
            const techStackHeaders = Array.from(document.querySelectorAll('h2')).filter(h => h.innerText.includes('Technology Stack'));
            if (techStackHeaders.length > 0) {
                const stackContainer = techStackHeaders[0].parentElement;
                
                // Clear existing pills (if any)
                const existingPills = stackContainer.querySelectorAll('.tech-pill-container');
                existingPills.forEach(p => p.remove());

                // Create a container for the pills
                const pillContainer = document.createElement('div');
                pillContainer.className = 'tech-pill-container';
                pillContainer.style.display = 'flex';
                pillContainer.style.gap = '10px';
                pillContainer.style.flexWrap = 'wrap';

                data.technologies.forEach(tech => {
                    const span = document.createElement('span');
                    span.className = 'tech-pill';
                    span.innerText = tech;
                    span.style.padding = '8px 16px';
                    span.style.background = 'var(--alpha-10)';
                    span.style.border = '1px solid var(--alpha-20)';
                    span.style.borderRadius = '20px';
                    span.style.color = 'var(--text-main)';
                    span.style.fontSize = '0.9rem';
                    pillContainer.appendChild(span);
                });

                stackContainer.appendChild(pillContainer);
            }

            // Trigger the progress animation
            animateProgress();
        })
        .catch(err => {
            console.error("Failed to fetch workspace details:", err);
            animateProgress(); // fallback
        });
    }

    // Only run if we are on the workspace detail page
    if (document.getElementById('metaRepoName') || document.getElementById('progressCircle') || document.getElementById('summaryText')) {
        loadAnalysisData();
    }
});
