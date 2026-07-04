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

            // Handle Summary AI Generation
            const summaryLoader = document.getElementById('summaryLoader');
            const loaderText = document.getElementById('loaderText');
            const summaryText = document.getElementById('summaryText');

            if (summaryLoader && loaderText && summaryText) {
                if (data.summary) {
                    summaryLoader.style.display = 'none';
                    summaryText.innerText = data.summary;
                    summaryText.style.display = 'block';
                } else {
                    const messages = ["Reading repo...", "Understanding the architecture...", "Analyzing logic..."];
                    let msgIndex = 0;
                    const msgInterval = setInterval(() => {
                        msgIndex = (msgIndex + 1) % messages.length;
                        loaderText.innerText = messages[msgIndex];
                    }, 2500);

                    fetch(`${API_BASE}/api/workspace/${workspaceId}/generate_summary`, {
                        method: 'POST',
                        headers: { 'Authorization': `Bearer ${token}` }
                    })
                    .then(res => res.json())
                    .then(summaryData => {
                        clearInterval(msgInterval);
                        summaryLoader.style.display = 'none';
                        if (summaryData.summary) {
                            summaryText.innerText = summaryData.summary;
                            summaryText.style.display = 'block';
                            showNotification("Analysis Summary is ready!");
                        } else {
                            summaryText.innerText = "Failed to generate AI summary.";
                            summaryText.style.display = 'block';
                        }
                    })
                    .catch(err => {
                        clearInterval(msgInterval);
                        summaryLoader.style.display = 'none';
                        summaryText.innerText = "Error generating AI summary.";
                        summaryText.style.display = 'block';
                    });
                }
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

            // Update API Endpoints
            const metricApiEndpoints = document.getElementById('metricApiEndpoints');
            if (metricApiEndpoints) {
                metricApiEndpoints.innerText = data.api_endpoints_count || 0;
            }

            // Update Detected Modules
            const metricDetectedModules = document.getElementById('metricDetectedModules');
            if (metricDetectedModules) {
                if (data.detected_modules && data.detected_modules.length > 0) {
                    metricDetectedModules.innerText = data.detected_modules.join(', ');
                    metricDetectedModules.style.fontSize = '1.25rem'; // smaller font since it's a list
                } else {
                    metricDetectedModules.innerText = '0';
                    metricDetectedModules.style.fontSize = '2.5rem'; // reset to large font for 0
                }
                metricDetectedModules.style.wordBreak = 'break-word';
            }

            // Update Folder Structure
            const preTags = document.querySelectorAll('pre');
            const folderPre = Array.from(preTags).find(pre => pre.innerText.includes('Loading folder structure'));
            if (folderPre) {
                folderPre.innerText = data.folder_structure || 'No folder structure available.';
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

// Helper for slide-in notifications
function showNotification(message) {
    let container = document.getElementById('notification-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'notification-container';
        container.style.position = 'fixed';
        container.style.top = '20px';
        container.style.right = '20px';
        container.style.zIndex = '9999';
        container.style.display = 'flex';
        container.style.flexDirection = 'column';
        container.style.gap = '10px';
        document.body.appendChild(container);
    }
    
    const notif = document.createElement('div');
    notif.style.background = 'linear-gradient(135deg, rgba(168, 85, 247, 0.95), rgba(124, 58, 237, 0.95))';
    notif.style.color = '#fff';
    notif.style.padding = '12px 20px';
    notif.style.borderRadius = '8px';
    notif.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
    notif.style.fontWeight = '500';
    notif.style.transform = 'translateX(120%)';
    notif.style.transition = 'transform 0.3s ease-out';
    notif.innerText = message;
    
    container.appendChild(notif);
    
    // Trigger slide in
    setTimeout(() => {
        notif.style.transform = 'translateX(0)';
    }, 10);
    
    // Remove after 3 seconds
    setTimeout(() => {
        notif.style.transform = 'translateX(120%)';
        setTimeout(() => {
            if (notif.parentNode) {
                notif.parentNode.removeChild(notif);
            }
        }, 300);
    }, 3000);
}
