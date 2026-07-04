// user-profile.js - Handles loading user profile data and updating UI across authenticated pages.

const PERSON_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:60%;height:60%;color:rgba(255,255,255,0.7);"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`;

document.addEventListener('DOMContentLoaded', async () => {
    const token = localStorage.getItem('token');
    if (!token) return;

    try {
        const res = await fetch(`${API_BASE}/api/auth/me`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const data = await res.json();
        if (res.ok && data) {

            /**
             * Apply avatar to an element:
             * - If profile picture exists → show as background image
             * - Otherwise → show a person SVG icon (consistent, professional)
             */
            function applyAvatar(el, pic) {
                if (!el) return;
                if (pic) {
                    el.style.backgroundImage = `url(${pic})`;
                    el.style.backgroundSize = 'cover';
                    el.style.backgroundPosition = 'center';
                    el.innerHTML = '';
                } else {
                    el.style.backgroundImage = '';
                    el.style.display = 'flex';
                    el.style.alignItems = 'center';
                    el.style.justifyContent = 'center';
                    el.innerHTML = PERSON_SVG;
                }
            }

            // ── Sidebar avatar + greeting ──────────────────────────────
            applyAvatar(document.getElementById('sidebar-avatar'), data.profile_picture);

            const greetingEl = document.getElementById('sidebar-greeting');
            if (greetingEl) {
                greetingEl.innerText = `Hello, ${data.first_name || 'there'}`;
            }

            // ── Profile page ───────────────────────────────────────────
            if (window.location.pathname.endsWith('profile.html')) {
                const fnInput = document.getElementById('firstName');
                const lnInput = document.getElementById('lastName');
                const emInput = document.getElementById('email');
                if (fnInput) fnInput.value = data.first_name || '';
                if (lnInput) lnInput.value = data.last_name || '';
                if (emInput) emInput.value = data.email || '';

                // Both avatar elements on profile page
                applyAvatar(document.getElementById('profile-page-avatar'), data.profile_picture);
                applyAvatar(document.getElementById('profile-page-avatar-large'), data.profile_picture);

                // Auth provider badge
                const providerBadge = document.getElementById('authProviderBadge');
                if (providerBadge && data.auth_provider) {
                    const map = { google: '🔵 Google Account', local: '🔐 Email & Password', both: '🔗 Google + Password' };
                    providerBadge.textContent = map[data.auth_provider] || data.auth_provider;
                }
            }
        }
    } catch (err) {
        console.error("Failed to load user profile:", err);
    }
});
