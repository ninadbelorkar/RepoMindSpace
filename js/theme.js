// js/theme.js
function applyTheme(theme) {
    if (theme === 'system') {
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
            document.documentElement.setAttribute('data-theme', 'light');
        } else {
            document.documentElement.setAttribute('data-theme', 'dark');
        }
    } else {
        document.documentElement.setAttribute('data-theme', theme);
    }
}

function updateButtonUI(theme) {
    const themeToggleText = document.getElementById('themeToggleText');
    const themeToggleIcon = document.getElementById('themeToggleIcon');
    if (!themeToggleIcon) return; // Sometimes not present (e.g. index.html)

    if (theme === 'light') {
        if(themeToggleText) themeToggleText.innerText = 'Light Mode';
        themeToggleIcon.innerHTML = '<circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>';
    } else if (theme === 'dark') {
        if(themeToggleText) themeToggleText.innerText = 'Dark Mode';
        themeToggleIcon.innerHTML = '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>';
    } else {
        if(themeToggleText) themeToggleText.innerText = 'System Mode';
        themeToggleIcon.innerHTML = '<rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect><line x1="8" y1="21" x2="16" y2="21"></line><line x1="12" y1="17" x2="12" y2="21"></line>';
    }
}

// Initial load
(function() {
    const savedTheme = localStorage.getItem('theme') || 'system';
    applyTheme(savedTheme);
})();

// Listen for OS theme changes if system is selected
window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', e => {
    if (localStorage.getItem('theme') === 'system' || !localStorage.getItem('theme')) {
        applyTheme('system');
    }
});

document.addEventListener('DOMContentLoaded', () => {
    const savedTheme = localStorage.getItem('theme') || 'system';
    updateButtonUI(savedTheme);

    const themeToggleBtn = document.getElementById('themeToggleBtn');
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', (e) => {
            e.preventDefault();
            let current = localStorage.getItem('theme') || 'system';
            let next = 'system';
            if (current === 'system') next = 'dark';
            else if (current === 'dark') next = 'light';
            else next = 'system';
            
            localStorage.setItem('theme', next);
            applyTheme(next);
            updateButtonUI(next);
        });
    }
});

window.setThemeMode = function(theme) {
    localStorage.setItem('theme', theme);
    applyTheme(theme);
    updateButtonUI(theme);
    
    // Update active styles on the buttons
    document.querySelectorAll('.theme-btn').forEach(btn => {
        btn.style.background = 'transparent';
        btn.style.color = 'var(--text-muted)';
        if(btn.getAttribute('data-theme-btn') === theme) {
            btn.style.background = 'var(--glass-hover-bg)';
            btn.style.color = 'var(--text-main)';
        }
    });
};
