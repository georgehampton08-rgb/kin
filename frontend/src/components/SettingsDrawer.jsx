import { useState } from 'react';
import { toast } from 'react-hot-toast';
import { fetchWithAuth } from '../utils/api';
import { useAuth } from '../context/AuthContext';

export default function SettingsDrawer({ isOpen, onClose }) {
    const { logout, user, updateUserInfo } = useAuth();
    const [currentPassword, setCurrentPassword] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [loading, setLoading] = useState(false);
    const [editFirst, setEditFirst] = useState('');
    const [editLast, setEditLast] = useState('');
    const [nameLoading, setNameLoading] = useState(false);
    const [editingName, setEditingName] = useState(false);

    const handleChangePassword = async (e) => {
        e.preventDefault();

        if (newPassword !== confirmPassword) {
            toast.error("New passwords do not match");
            return;
        }

        if (newPassword.length < 8) {
            toast.error("New password must be at least 8 characters");
            return;
        }

        setLoading(true);
        try {
            const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
            const res = await fetchWithAuth(`${apiUrl}/api/v1/auth/change-password`, {
                method: 'POST',
                body: JSON.stringify({
                    current_password: currentPassword,
                    new_password: newPassword
                })
            });

            if (res.ok) {
                toast.success("Password updated successfully");
                setCurrentPassword('');
                setNewPassword('');
                setConfirmPassword('');
                // The backend revokes existing refresh tokens.
                // We could force a logout here, but it's not strictly necessary 
                // since the current access token is still valid. 
                // But for pure security, let's force them to log back in.
                toast("Please log in again with your new password.", { icon: '🔒' });
                setTimeout(logout, 2000);
            } else {
                const data = await res.json();
                toast.error(data.detail || "Failed to change password");
            }
        } catch (err) {
            console.error("Change password error:", err);
            toast.error("An error occurred");
        } finally {
            setLoading(false);
        }
    };

    const handleSaveName = async (e) => {
        e.preventDefault();
        setNameLoading(true);
        try {
            const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
            const res = await fetchWithAuth(`${apiUrl}/api/v1/auth/profile`, {
                method: 'PUT',
                body: JSON.stringify({ first_name: editFirst, last_name: editLast }),
            });
            if (res.ok) {
                toast.success('Name updated');
                if (updateUserInfo) updateUserInfo({ first_name: editFirst, last_name: editLast });
                setEditingName(false);
            } else {
                const data = await res.json();
                toast.error(data.detail || 'Failed to update name');
            }
        } catch (err) {
            toast.error('An error occurred');
        } finally {
            setNameLoading(false);
        }
    };

    const startEditing = () => {
        setEditFirst(user?.first_name || '');
        setEditLast(user?.last_name || '');
        setEditingName(true);
    };

    return (
        <aside className={`settings-drawer ${isOpen ? 'open' : ''}`}>
            <div className="sd-header">
                <h2>⚙️ Global Settings</h2>
                <button className="sd-close" onClick={onClose}>✕</button>
            </div>

            <div className="sd-content">
                <section className="sd-section sd-profile">
                    <div className="sd-avatar">
                        {user?.first_name ? user.first_name.charAt(0).toUpperCase() : '?'}
                        {user?.last_name ? user.last_name.charAt(0).toUpperCase() : ''}
                    </div>
                    <div className="sd-profile-info">
                        <span className="sd-name">
                            {user?.first_name || user?.last_name
                                ? `${user.first_name || ''} ${user.last_name || ''}`.trim()
                                : 'No Name Set'}
                        </span>
                        <span className="sd-email">{user?.email || 'Unknown'}</span>
                        <span className="sd-role">{user?.role === 'admin' ? '🛡️ Admin' : '👤 Parent'}</span>
                    </div>
                    <button className="sd-edit-btn" onClick={startEditing} title="Edit Name">✏️</button>
                </section>

                {editingName && (
                    <section className="sd-section">
                        <h3>Edit Name</h3>
                        <form className="sd-form" onSubmit={handleSaveName}>
                            <label>First Name</label>
                            <input value={editFirst} onChange={e => setEditFirst(e.target.value)} placeholder="First" />
                            <label>Last Name</label>
                            <input value={editLast} onChange={e => setEditLast(e.target.value)} placeholder="Last" />
                            <button type="submit" disabled={nameLoading}>{nameLoading ? 'Saving...' : 'Save Name'}</button>
                        </form>
                    </section>
                )}

                <section className="sd-section">
                    <h3>Account Security</h3>
                    <form className="sd-form" onSubmit={handleChangePassword}>
                        <label>Current Password</label>
                        <input
                            type="password"
                            required
                            value={currentPassword}
                            onChange={e => setCurrentPassword(e.target.value)}
                        />

                        <label>New Password</label>
                        <input
                            type="password"
                            required
                            value={newPassword}
                            onChange={e => setNewPassword(e.target.value)}
                        />

                        <label>Confirm New Password</label>
                        <input
                            type="password"
                            required
                            value={confirmPassword}
                            onChange={e => setConfirmPassword(e.target.value)}
                        />

                        <button type="submit" disabled={loading}>
                            {loading ? 'Updating...' : 'Change Password'}
                        </button>
                    </form>
                </section>

                <section className="sd-section">
                    <h3>Session Management</h3>
                    <button className="btn-logout" onClick={logout}>Sign Out</button>
                </section>
            </div>

            <style>{`
                .settings-drawer {
                    position: absolute;
                    top: 0;
                    right: -320px;
                    width: 300px;
                    height: 100%;
                    background: rgba(10, 15, 30, 0.95);
                    backdrop-filter: blur(10px);
                    border-left: 1px solid rgba(0, 255, 204, 0.2);
                    box-shadow: -4px 0 15px rgba(0,0,0,0.5);
                    transition: right 0.3s ease;
                    z-index: 1000;
                    display: flex;
                    flex-direction: column;
                }
                .settings-drawer.open {
                    right: 0;
                }
                .sd-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 16px 20px;
                    border-bottom: 1px solid rgba(255,255,255,0.05);
                }
                .sd-header h2 {
                    margin: 0;
                    font-size: 1.1rem;
                    color: #fff;
                    letter-spacing: 1px;
                }
                .sd-close {
                    background: none;
                    border: none;
                    color: #8b92a5;
                    font-size: 1.2rem;
                    cursor: pointer;
                }
                .sd-close:hover { color: #fff; }
                
                .sd-content {
                    padding: 20px;
                    overflow-y: auto;
                    flex: 1;
                }
                
                .sd-section {
                    margin-bottom: 30px;
                }
                .sd-section h3 {
                    margin-top: 0;
                    margin-bottom: 15px;
                    font-size: 0.85rem;
                    text-transform: uppercase;
                    color: #00ffcc;
                    letter-spacing: 1.5px;
                    border-bottom: 1px dashed rgba(0,255,204,0.3);
                    padding-bottom: 5px;
                }
                
                .sd-form {
                    display: flex;
                    flex-direction: column;
                    gap: 10px;
                }
                .sd-form label {
                    font-size: 0.75rem;
                    color: #a0a6cc;
                    margin-bottom: -5px;
                }
                .sd-form input {
                    background: rgba(0,0,0,0.4);
                    border: 1px solid rgba(255,255,255,0.1);
                    color: white;
                    padding: 8px 10px;
                    border-radius: 4px;
                    font-family: inherit;
                }
                .sd-form input:focus {
                    outline: none;
                    border-color: rgba(0,255,204,0.5);
                    box-shadow: 0 0 5px rgba(0,255,204,0.2);
                }
                .sd-form button {
                    margin-top: 10px;
                    background: rgba(0, 255, 204, 0.1);
                    color: #00ffcc;
                    border: 1px solid rgba(0, 255, 204, 0.3);
                    padding: 10px;
                    border-radius: 4px;
                    cursor: pointer;
                    font-weight: 600;
                    transition: all 0.2s;
                }
                .sd-form button:hover:not(:disabled) {
                    background: rgba(0, 255, 204, 0.2);
                    box-shadow: 0 0 10px rgba(0,255,204,0.2);
                }
                .sd-form button:disabled {
                    opacity: 0.5;
                    cursor: not-allowed;
                }
                
                .btn-logout {
                    width: 100%;
                    background: rgba(255, 51, 51, 0.1);
                    color: #ff3333;
                    border: 1px solid rgba(255, 51, 51, 0.3);
                    padding: 10px;
                    border-radius: 4px;
                    cursor: pointer;
                    font-weight: 600;
                    transition: all 0.2s;
                }
                .btn-logout:hover {
                    background: rgba(255, 51, 51, 0.2);
                    box-shadow: 0 0 10px rgba(255,51,51,0.2);
                }

                .sd-profile {
                    display: flex;
                    align-items: center;
                    gap: 14px;
                    padding-bottom: 16px;
                    border-bottom: 1px solid rgba(255,255,255,0.08);
                }
                .sd-avatar {
                    width: 48px;
                    height: 48px;
                    border-radius: 50%;
                    background: linear-gradient(135deg, #00ffcc, #0088ff);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 1.1rem;
                    font-weight: 700;
                    color: #000;
                    flex-shrink: 0;
                }
                .sd-profile-info {
                    display: flex;
                    flex-direction: column;
                    gap: 2px;
                }
                .sd-name {
                    font-size: 1rem;
                    font-weight: 600;
                    color: #fff;
                }
                .sd-email {
                    font-size: 0.8rem;
                    color: #8892b0;
                }
                .sd-role {
                    font-size: 0.75rem;
                    color: #00ffcc;
                    text-transform: uppercase;
                    letter-spacing: 0.05em;
                }
                .sd-edit-btn {
                    background: none;
                    border: none;
                    cursor: pointer;
                    font-size: 1.1rem;
                    margin-left: auto;
                    opacity: 0.6;
                    transition: opacity 0.2s;
                }
                .sd-edit-btn:hover {
                    opacity: 1;
                }
            `}</style>
        </aside>
    );
}
