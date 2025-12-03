const API_BASE_URL = ''; // carga desde fastAPI

// --- Telegram Auth Callback (Must be global for widget) ---
window.onTelegramAuth = async function(user) {
    console.log("Datos de usuario de Telegram recibidos:", user);

    try {
        const response = await fetch(`${API_BASE_URL}/auth/telegram`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(user)
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || 'Authentication failed');
        }

        const data = await response.json();
        console.log("Respuesta del backend:", data);

        if (data.access_token) {
            localStorage.setItem('access_token', data.access_token);
            localStorage.setItem('user_id', data.user_id); // Store user_id
            // user.first_name is also useful for display
            localStorage.setItem('user_first_name', user.first_name || `Usuario ${user.id}`);
            console.log("Token de acceso almacenado y usuario logueado.");
            alert('¡Login exitoso! Bienvenido, ' + user.first_name + '.');
            window.location.reload(); // Recargar la página para actualizar la UI
        } else {
            throw new Error('No se recibió token de acceso.');
        }
    } catch (error) {
        console.error('Error al iniciar sesión con Telegram:', error);
        alert('Error al iniciar sesión: ' + error.message);
    }
};


// --- Utility Functions ---

function getAuthHeaders() {
    const token = localStorage.getItem('access_token');
    if (token) {
        return {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        };
    }
    return { 'Content-Type': 'application/json' };
}

async function fetchAuthenticated(endpoint, options = {}) {
    options.headers = { ...options.headers, ...getAuthHeaders() };
    const response = await fetch(`${API_BASE_URL}${endpoint}`, options);
    // Handle 401 Unauthorized globally
    if (response.status === 401) {
        console.warn('Unauthorized access, logging out...');
        alert('Sesión expirada o no autorizada. Por favor, inicia sesión de nuevo.');
        logout();
        throw new Error('Unauthorized');
    }
    return response;
}

// --- Data Fetching and Display ---

async function fetchGeneralStats() {
    try {
        const response = await fetchAuthenticated('/api/stats');
        const data = await response.json();
        document.getElementById('total-users').textContent = data.total_users;
        document.getElementById('total-transactions').textContent = data.total_transactions;
    } catch (error) {
        console.error('Error fetching general stats:', error);
        document.getElementById('total-users').textContent = 'Error';
        document.getElementById('total-transactions').textContent = 'Error';
    }
}

async function fetchTokensTracked() {
    try {
        const response = await fetchAuthenticated('/api/me/tokens');
        const tokens = await response.json();
        displayTrackedTokens(tokens);
    } catch (error) {
        console.error('Error fetching tracked tokens:', error);
        if(document.getElementById('tracked-tokens-list')) {
            document.getElementById('tracked-tokens-list').innerHTML = '<li>Error al cargar tokens</li>';
        }
    }
}

function displayTrackedTokens(tokens) {
    const listElement = document.getElementById('tracked-tokens-list');
    if (!listElement) return;

    if (tokens.length === 0) {
        listElement.innerHTML = '<li>No estás monitorizando ningún token.</li>';
        return;
    }

    listElement.innerHTML = tokens.map(token => {
        const symbol = String(token.token_symbol).replace(/</g, "&lt;").replace(/>/g, "&gt;");
        const address = String(token.token_address).replace(/</g, "&lt;").replace(/>/g, "&gt;");
        return `<li><strong>${symbol}</strong>: <code>${address}</code></li>`;
    }).join('');
}


// --- UI Management and Initialization ---

function checkLoginStatus() {
    const token = localStorage.getItem('access_token');
    const userId = localStorage.getItem('user_id');
    const userFirstName = localStorage.getItem('user_first_name');

    const loginView = document.getElementById('login-view');
    const authenticatedView = document.getElementById('authenticated-view');
    const loggedInUserInfoSpan = document.getElementById('logged-in-user-info');
    const logoutButton = document.getElementById('logout-button');
    const telegramLoginButtonContainer = document.getElementById('telegram-login-button-container');

    if (token && userId) {
        loginView.style.display = 'none';
        authenticatedView.style.display = 'block';
        loggedInUserInfoSpan.textContent = userFirstName || `Usuario ID: ${userId}`;
        logoutButton.addEventListener('click', logout);
        fetchGeneralStats();
        fetchTokensTracked();
    } else {
        loginView.style.display = 'block';
        authenticatedView.style.display = 'none';
        // Dynamically load Telegram widget script
        if (telegramLoginButtonContainer) {
            const script = document.createElement('script');
            script.async = true;
            script.src = "https://telegram.org/js/telegram-widget.js?22";
            script.setAttribute("data-telegram-login", "trackyourtokensbot");
            script.setAttribute("data-size", "large");
            script.setAttribute("data-radius", "20");
            script.setAttribute("data-onauth", "onTelegramAuth(user)");
            script.setAttribute("data-request-access", "write");
            telegramLoginButtonContainer.appendChild(script);
        }
    }
}

function logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_id');
    localStorage.removeItem('user_first_name');
    window.location.reload();
}

document.addEventListener('DOMContentLoaded', () => {
    checkLoginStatus();
});