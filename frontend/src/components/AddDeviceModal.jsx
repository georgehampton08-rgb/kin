import { useState } from 'react';
import { QRCodeSVG } from 'qrcode.react';

export default function AddDeviceModal({ onClose }) {
    const [token, setToken] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    async function generateToken() {
        setLoading(true);
        setError(null);
        try {
            const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
            const res = await fetch(`${apiUrl}/api/v1/auth/create-pairing-token`, {
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
                    z-index: 1000; backdrop-filter: blur(4px);
                }
                .modal-content {
                    background: #141720; border: 1px solid rgba(255,255,255,0.1);
                    border-radius: 12px; padding: 24px; min-width: 320px;
                    color: white; position: relative; text-align: center;
                }
                .close-btn {
                    position: absolute; top: 12px; right: 12px;
                    background: none; border: none; color: #888;
                    font-size: 1.2rem; cursor: pointer;
                }
                .close-btn:hover { color: #fff; }
                .primary-btn {
                    background: #00ffcc; color: #000; border: none;
                    padding: 8px 16px; border-radius: 6px; font-weight: bold;
                    cursor: pointer; margin-top: 16px;
                }
                .primary-btn:hover { background: #00ccaa; }
                .qr-container { margin-top: 20px; }
            `}</style>
        </div>
    );
}
