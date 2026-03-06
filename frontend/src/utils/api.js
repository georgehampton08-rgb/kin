export async function fetchWithAuth(url, options = {}) {
    const token = localStorage.getItem('access_token');

    const headers = new Headers(options.headers || {});
    if (token) {
        headers.set('Authorization', `Bearer ${token}`);
    }

    // Default to application/json if not set and body is present
    if (options.body && !headers.has('Content-Type')) {
        headers.set('Content-Type', 'application/json');
    }

    const config = {
        ...options,
        headers,
    };

    let response = await fetch(url, config);

    // Quick and dirty token refresh logic if 401
    if (response.status === 401) {
        const refreshToken = localStorage.getItem('refresh_token');
        if (refreshToken) {
            try {
                const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
                const refreshRes = await fetch(`${apiUrl}/api/v1/auth/refresh`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ refresh_token: refreshToken })
                });

                if (refreshRes.ok) {
                    const data = await refreshRes.json();
                    localStorage.setItem('access_token', data.access_token);
                    localStorage.setItem('refresh_token', data.refresh_token);

                    // Retry original request with new token
                    headers.set('Authorization', `Bearer ${data.access_token}`);
                    response = await fetch(url, { ...options, headers });
                } else {
                    // Refresh failed, clear tokens
                    localStorage.removeItem('access_token');
                    localStorage.removeItem('refresh_token');
                    localStorage.removeItem('user_info');
                    window.location.reload();
                }
            } catch (err) {
                console.error('Token refresh failed', err);
            }
        } else {
            // No refresh token available, force logout
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            localStorage.removeItem('user_info');
            window.location.reload();
        }
    }

    return response;
}
