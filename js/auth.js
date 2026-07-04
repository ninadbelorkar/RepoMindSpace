// auth.js - Handles authentication logic

const API_BASE_URL = `${API_BASE}/api/auth`;
const GOOGLE_CLIENT_ID = '1091939061408-1rpl2tqd6tn2iulba1oo8v1cfh94t4bs.apps.googleusercontent.com';

document.addEventListener('DOMContentLoaded', () => {

    // --- Traditional Login ---
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            const errorDiv = document.getElementById('loginError');

            if (errorDiv) errorDiv.style.display = 'none';

            try {
                const response = await fetch(${API_BASE_URL}/login, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, password })
                });

                const data = await response.json();

                if (response.ok) {
                    // 4.4 MFA required
                    if (data.mfa_required && data.pre_token) {
                        sessionStorage.setItem('mfa_pre_token', data.pre_token);
                        window.location.href = 'mfa-verify.html';
                        return;
                    }
                    localStorage.setItem('token', data.token);
                    if (data.user && data.user.onboarding_completed === false) {
                        window.location.href = 'onboarding.html';
                    } else {
                        window.location.href = 'dashboard.html';
                    }
                } else {
                    let msg = data.error || 'Login failed';
                    // 4.2 Hint for Google accounts
                    if (data.provider_hint === 'google') {
                        msg += ' Please use the Sign in with Google button below.';
                    }
                    if (errorDiv) {
                        errorDiv.textContent = msg;
                        errorDiv.style.display = 'block';
                    } else {
                        alert(msg);
                    }
                }
            } catch (error) {
                console.error('Error logging in:', error);
                if (errorDiv) {
                    errorDiv.textContent = 'An error occurred during login.';
                    errorDiv.style.display = 'block';
                } else {
                    alert('An error occurred during login.');
                }
            }
        });
    }

    // --- Traditional Registration ---
    const registerForm = document.getElementById('registerForm');
    if (registerForm) {
        registerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const firstName = document.getElementById('firstName').value;
            const lastName = document.getElementById('lastName').value;
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            const errorDiv = document.getElementById('registerError');

            if (errorDiv) errorDiv.style.display = 'none';

            try {
                const response = await fetch(${API_BASE_URL}/register, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ firstName, lastName, email, password })
                });

                const data = await response.json();
                if (response.ok) {
                    localStorage.setItem('token', data.token);
                    // 4.2 Account linked
                    if (data.account_linked) {
                        alert('Your Google account has been linked! You can now sign in with email/password or Google.');
                        window.location.href = 'dashboard.html';
                        return;
                    }
                    if (data.user && data.user.onboarding_completed === false) {
                        window.location.href = 'onboarding.html';
                    } else {
                        window.location.href = 'dashboard.html';
                    }
                } else {
                    const msg = data.error || 'Registration failed';
                    if (errorDiv) {
                        errorDiv.textContent = msg;
                        errorDiv.style.display = 'block';
                    } else {
                        alert(msg);
                    }
                }
            } catch (error) {
                console.error('Error registering:', error);
                alert('An error occurred during registration.');
            }
        });
    }

    // --- Logout ---
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', (e) => {
            e.preventDefault();
            const theme = localStorage.getItem('theme');
            localStorage.clear();
            sessionStorage.clear();
            if (theme) localStorage.setItem('theme', theme);
            window.location.href = '../index.html';
        });
    }
});
