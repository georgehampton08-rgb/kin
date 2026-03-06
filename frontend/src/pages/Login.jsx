import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Toaster } from 'react-hot-toast';

export default function Login() {
    const { login, register } = useAuth();
    const [isRegistering, setIsRegistering] = useState(false);

    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [familyName, setFamilyName] = useState('');
    const [firstName, setFirstName] = useState('');
    const [lastName, setLastName] = useState('');

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (isRegistering) {
            await register(email, password, familyName, firstName, lastName);
        } else {
            await login(email, password);
        }
    };

    return (
        <div className="login-container">
            <Toaster position="top-right" />
            <div className="login-card">
                <h1>{isRegistering ? 'Create Family Account' : 'Kin Login'}</h1>
                <p className="login-subtitle">
                    {isRegistering
                        ? 'Set up your family account to manage devices.'
                        : 'Sign in to access your dashboard.'}
                </p>

                <form onSubmit={handleSubmit} className="login-form">
                    {isRegistering && (
                        <>
                            <div className="form-group">
                                <label>Family Name</label>
                                <input
                                    type="text"
                                    value={familyName}
                                    onChange={e => setFamilyName(e.target.value)}
                                    placeholder="E.g., The Smiths"
                                    required
                                />
                            </div>
                            <div className="name-row">
                                <div className="form-group">
                                    <label>First Name</label>
                                    <input
                                        type="text"
                                        value={firstName}
                                        onChange={e => setFirstName(e.target.value)}
                                        placeholder="George"
                                    />
                                </div>
                                <div className="form-group">
                                    <label>Last Name</label>
                                    <input
                                        type="text"
                                        value={lastName}
                                        onChange={e => setLastName(e.target.value)}
                                        placeholder="Hampton"
                                    />
                                </div>
                            </div>
                        </>
                    )}

                    <div className="form-group">
                        <label>Email Address</label>
                        <input
                            type="email"
                            value={email}
                            onChange={e => setEmail(e.target.value)}
                            placeholder="parent@example.com"
                            required
                        />
                    </div>

                    <div className="form-group">
                        <label>Password</label>
                        <input
                            type="password"
                            value={password}
                            onChange={e => setPassword(e.target.value)}
                            placeholder="••••••••"
                            required
                            minLength={8}
                        />
                    </div>

                    <button type="submit" className="login-btn">
                        {isRegistering ? 'Register' : 'Sign In'}
                    </button>

                    <button
                        type="button"
                        className="toggle-mode-btn"
                        onClick={() => setIsRegistering(!isRegistering)}
                    >
                        {isRegistering
                            ? 'Already have an account? Sign In'
                            : 'Need an account? Register'}
                    </button>
                </form>
            </div>

            <style>{`
                .login-container {
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                    background: #090a0f;
                    color: #fff;
                    font-family: inherit;
                }
                .login-card {
                    background: rgba(20, 24, 32, 0.8);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    padding: 40px;
                    border-radius: 12px;
                    width: 100%;
                    max-width: 400px;
                    box-shadow: 0 16px 40px rgba(0,0,0,0.5);
                    backdrop-filter: blur(10px);
                }
                .login-card h1 {
                    margin-top: 0;
                    margin-bottom: 8px;
                    font-size: 1.8rem;
                    color: #fff;
                }
                .login-subtitle {
                    color: #8892b0;
                    margin-bottom: 24px;
                    font-size: 0.95rem;
                }
                .form-group {
                    margin-bottom: 20px;
                }
                .form-group label {
                    display: block;
                    margin-bottom: 8px;
                    font-size: 0.85rem;
                    color: #a0aec0;
                    text-transform: uppercase;
                    letter-spacing: 0.05em;
                }
                .form-group input {
                    width: 100%;
                    padding: 12px;
                    background: rgba(0, 0, 0, 0.3);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 6px;
                    color: #fff;
                    font-size: 1rem;
                    box-sizing: border-box;
                    transition: border-color 0.2s;
                }
                .form-group input:focus {
                    outline: none;
                    border-color: #00ffcc;
                }
                .login-btn {
                    width: 100%;
                    padding: 14px;
                    background: #00ffcc;
                    color: #000;
                    border: none;
                    border-radius: 6px;
                    font-size: 1rem;
                    font-weight: bold;
                    cursor: pointer;
                    margin-top: 10px;
                    transition: background 0.2s;
                }
                .login-btn:hover {
                    background: #00ccaa;
                }
                .toggle-mode-btn {
                    width: 100%;
                    background: none;
                    border: none;
                    color: #8892b0;
                    margin-top: 16px;
                    cursor: pointer;
                    font-size: 0.9rem;
                    transition: color 0.2s;
                }
                .toggle-mode-btn:hover {
                    color: #fff;
                    text-decoration: underline;
                }
                .name-row {
                    display: flex;
                    gap: 12px;
                }
                .name-row .form-group {
                    flex: 1;
                }
            `}</style>
        </div>
    );
}
