import { createContext, useContext, useState, useEffect } from 'react';
import { toast } from 'react-hot-toast';

const AuthContext = createContext();

export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }) {
    const [user, setUser] = useState(null);
    const [token, setToken] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const storedToken = localStorage.getItem('access_token');
        const storedUser = localStorage.getItem('user_info');

        if (storedToken && storedUser) {
            try {
                setToken(storedToken);
                setUser(JSON.parse(storedUser));
            } catch (err) {
                localStorage.removeItem('access_token');
                localStorage.removeItem('user_info');
            }
        }
        setLoading(false);
    }, []);

    const login = async (email, password) => {
        try {
            const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
            const res = await fetch(`${apiUrl}/api/v1/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password }),
            });

            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.detail || 'Login failed');
            }

            const data = await res.json();
            setToken(data.access_token);

            // Extract info from token roughly or fetch user details.
            // Since we don't have a /me endpoint, we can parse JWT payload.
            const payloadStr = atob(data.access_token.split('.')[1]);
            const payload = JSON.parse(payloadStr);

            const userInfo = {
                id: payload.sub,
                email: data.user_info?.email || email,
                familyId: payload.family_id,
                role: payload.role,
                first_name: data.user_info?.first_name || null,
                last_name: data.user_info?.last_name || null,
            };

            setUser(userInfo);
            localStorage.setItem('access_token', data.access_token);
            localStorage.setItem('refresh_token', data.refresh_token);
            localStorage.setItem('user_info', JSON.stringify(userInfo));

            toast.success('Logged in successfully');
            return true;
        } catch (err) {
            toast.error(err.message);
            return false;
        }
    };

    const register = async (email, password, familyName, firstName, lastName) => {
        try {
            const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
            const res = await fetch(`${apiUrl}/api/v1/auth/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    email, password,
                    family_name: familyName,
                    first_name: firstName || null,
                    last_name: lastName || null,
                }),
            });

            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.detail || 'Registration failed');
            }

            const data = await res.json();
            setToken(data.access_token);

            const payloadStr = atob(data.access_token.split('.')[1]);
            const payload = JSON.parse(payloadStr);

            const userInfo = {
                id: payload.sub,
                email: data.user_info?.email || email,
                familyId: payload.family_id,
                role: payload.role,
                first_name: data.user_info?.first_name || null,
                last_name: data.user_info?.last_name || null,
            };

            setUser(userInfo);
            localStorage.setItem('access_token', data.access_token);
            localStorage.setItem('refresh_token', data.refresh_token);
            localStorage.setItem('user_info', JSON.stringify(userInfo));

            toast.success('Registration successful');
            return true;
        } catch (err) {
            toast.error(err.message);
            return false;
        }
    };

    const logout = () => {
        setUser(null);
        setToken(null);
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('user_info');
    };

    const updateUserInfo = (updates) => {
        setUser(prev => {
            const updated = { ...prev, ...updates };
            localStorage.setItem('user_info', JSON.stringify(updated));
            return updated;
        });
    };

    return (
        <AuthContext.Provider value={{ user, token, loading, login, register, logout, updateUserInfo }}>
            {children}
        </AuthContext.Provider>
    );
}
