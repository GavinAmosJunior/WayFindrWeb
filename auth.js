const AUTH_STYLES = `
    .auth-overlay { position: fixed; inset: 0; display: flex; align-items: center; justify-content: center; padding: 16px; background: var(--bg-color, #f4f5f7); z-index: 1000; }
    .auth-card { width: 100%; max-width: 360px; box-sizing: border-box; padding: 28px; background: #fff; border-radius: 12px; box-shadow: 0 12px 30px rgba(15, 23, 42, 0.15); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    .auth-card h2 { margin: 0 0 18px; font-size: 20px; color: var(--dark-slate, #0F172A); }
    .auth-card input { width: 100%; box-sizing: border-box; margin-bottom: 12px; padding: 10px 12px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 14px; }
    .auth-card button, .auth-signout { border: none; border-radius: 8px; color: #fff; font-weight: 600; cursor: pointer; background: var(--primary-blue, var(--primary-red, #0F172A)); }
    .auth-card button { width: 100%; padding: 11px; font-size: 14px; }
    .auth-card button:disabled { opacity: 0.6; cursor: default; }
    .auth-error { min-height: 18px; margin: 0 0 10px; color: #dc2626; font-size: 13px; }
    .auth-signout { position: fixed; top: 12px; right: 12px; padding: 6px 12px; font-size: 12px; z-index: 999; }
`;

function addAuthStyles() {
    if (document.getElementById('authStyles')) return;
    const style = document.createElement('style');
    style.id = 'authStyles';
    style.textContent = AUTH_STYLES;
    document.head.appendChild(style);
}

function addSignOutButton(client) {
    const button = document.createElement('button');
    button.className = 'auth-signout';
    button.textContent = 'Sign out';
    button.onclick = async () => {
        await client.auth.signOut();
        location.reload();
    };
    document.body.appendChild(button);
}

function showLoginForm(client, onReady) {
    const overlay = document.createElement('div');
    overlay.className = 'auth-overlay';
    overlay.innerHTML = `
        <form class="auth-card">
            <h2>Sign in</h2>
            <input type="email" name="email" placeholder="Email" autocomplete="username" required>
            <input type="password" name="password" placeholder="Password" autocomplete="current-password" required>
            <p class="auth-error"></p>
            <button type="submit">Sign in</button>
        </form>`;
    document.body.appendChild(overlay);

    const form = overlay.querySelector('form');
    const errorText = overlay.querySelector('.auth-error');
    const submitButton = overlay.querySelector('button');
    form.onsubmit = async event => {
        event.preventDefault();
        submitButton.disabled = true;
        errorText.textContent = '';
        const { error } = await client.auth.signInWithPassword({
            email: form.email.value.trim(),
            password: form.password.value,
        });
        submitButton.disabled = false;
        if (error) {
            errorText.textContent = error.message;
            return;
        }
        overlay.remove();
        addSignOutButton(client);
        onReady();
    };
}

async function requireAuth(client, onReady) {
    addAuthStyles();
    const { data: { session } } = await client.auth.getSession();
    if (session) {
        addSignOutButton(client);
        onReady();
    } else {
        showLoginForm(client, onReady);
    }
}
