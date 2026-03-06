import { useState } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import { fetchWithAuth } from '../utils/api';

export default function AddDeviceModal({ onClose }) {
    const [token, setToken] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    async function generateToken() {
        setLoading(true);
        setError(null);
        try {
            const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
            const res = await fetchWithAuth(`${apiUrl}/api/v1/auth/create-pairing-token`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (!res.ok) {
                const text = await res.text();
                throw new Error(`Error: ${res.status} ${text}`);
            }

            const data = await res.json();
            setToken(data.qr_payload);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }

    return (
        <div className="modal-overlay">
            <div className="modal-content">
                <h2>Add New Device</h2>
                <button className="close-btn" onClick={onClose}>✕</button>

                {!token && !loading && (
                    <div className="modal-body">
                        <p>Generate a QR code to pair your child's device.</p>
                        <button className="primary-btn" onClick={generateToken}>Generate QR</button>
                    </div>
                )}

                {loading && <p>Generating pairing token...</p>}

                {error && (
                    <div className="modal-body">
                        <p style={{ color: '#ff5555' }}>{error}</p>
                        <button className="primary-btn" onClick={generateToken}>Retry</button>
                    </div>
                )}

                {token && (
                    <div className="qr-container">
                        <p>Scan this QR code from the Kin App:</p>
                        <div style={{ background: '#fff', padding: '16px', borderRadius: '8px', display: 'inline-block' }}>
                            <QRCodeSVG value={JSON.stringify(token)} size={256} />
                        </div>
                        <p><small>This code expires in 10 minutes.</small></p>
                    </div>
                )}
            </div>

            <style>{`
                .modal-overlay {
                    position: fixed; inset: 0; background: rgba(0,0,0,0.8);
                    display: flex; align-items: center; justify-content: center;
                    z-index: 1000; backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
                }
                .modal-content {
                    background: var(--color-surface-elevated); 
                    border: 1px solid var(--color-border-light);
                    border-radius: var(--radius-md); padding: var(--spacing-6); min-width: 320px;
                    color: var(--color-text-primary); position: relative; text-align: center;
                    box-shadow: var(--shadow-lg);
                }
                .modal-content h2 {
                    margin-bottom: var(--spacing-4);
                }
                .close-btn {
                    position: absolute; top: var(--spacing-3); right: var(--spacing-3);
                    background: none; border: none; color: var(--color-text-secondary);
                    font-size: 1.5rem; cursor: pointer; transition: var(--transition-fast);
                }
                .close-btn:hover { color: var(--color-text-primary); }
                .primary-btn {
                    background: var(--color-signal-active); color: var(--color-base); 
                    border: none; padding: var(--spacing-2) var(--spacing-4); 
                    border-radius: var(--radius-full); font-weight: var(--font-weight-bold);
                    cursor: pointer; margin-top: var(--spacing-4);
                    transition: var(--transition-fast);
                }
                .primary-btn:hover { background: #00ccaa; box-shadow: var(--shadow-glow); }
                .qr-container { margin-top: var(--spacing-5); }
                .qr-container p { color: var(--color-text-secondary); margin-bottom: var(--spacing-3); }
            `}</style>
        </div>
    );
}
