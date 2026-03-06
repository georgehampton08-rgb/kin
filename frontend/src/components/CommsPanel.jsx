import React, { useState, useEffect } from 'react';
import { fetchWithAuth } from '../utils/api';

const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function CommsPanel({ deviceId }) {
    const [activeTab, setActiveTab] = useState('notifications');
    const [data, setData] = useState({
        notifications: [],
        sms: [],
        calls: []
    });
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    useEffect(() => {
        if (!deviceId) return;

        let isMounted = true;
        const fetchData = async () => {
            setLoading(true);
            setError(null);
            try {
                const res = await fetchWithAuth(`${apiUrl}/api/v1/devices/${deviceId}/${activeTab}`);
                if (!res.ok) throw new Error(`Failed to fetch ${activeTab}`);
                const json = await res.json();
                if (isMounted) {
                    setData(prev => ({ ...prev, [activeTab]: json[activeTab] || [] }));

                    // Mark as read in the background
                    fetchWithAuth(`${apiUrl}/api/v1/devices/${deviceId}/comms/mark_read`, {
                        method: 'POST',
                        body: JSON.stringify({ type: activeTab })
                    }).catch(err => console.error(`Failed to mark ${activeTab} as read:`, err));
                }
            } catch (err) {
                if (isMounted) setError(err.message);
            } finally {
                if (isMounted) setLoading(false);
            }
        };

        fetchData();
        return () => { isMounted = false; };
    }, [deviceId, activeTab]);

    if (!deviceId) return <div className="comms-panel-empty">Select a device to view communications.</div>;

    return (
        <div className="comms-panel">
            <div className="comms-header">
                <h2>Communications</h2>
            </div>

            <div className="comms-tabs">
                <button
                    className={`comms-tab ${activeTab === 'notifications' ? 'active' : ''}`}
                    onClick={() => setActiveTab('notifications')}
                >
                    Notifications
                </button>
                <button
                    className={`comms-tab ${activeTab === 'sms' ? 'active' : ''}`}
                    onClick={() => setActiveTab('sms')}
                >
                    SMS
                </button>
                <button
                    className={`comms-tab ${activeTab === 'calls' ? 'active' : ''}`}
                    onClick={() => setActiveTab('calls')}
                >
                    Calls
                </button>
            </div>

            <div className="comms-content">
                {loading && <div className="comms-loading">Loading...</div>}
                {error && <div className="comms-error">{error}</div>}
                {!loading && !error && data[activeTab].length === 0 && (
                    <div className="comms-empty">No {activeTab} recorded.</div>
                )}

                {!loading && !error && activeTab === 'notifications' && (
                    <div className="comms-list">
                        {data.notifications.map(n => (
                            <div key={n.id} className="comms-card">
                                <div className="comms-card-header">
                                    <span className="comms-pkg">{n.package_name}</span>
                                    <span className="comms-time">{new Date(n.timestamp).toLocaleString()}</span>
                                </div>
                                <div className="comms-title">{n.title}</div>
                                <div className="comms-text">{n.text}</div>
                            </div>
                        ))}
                    </div>
                )}

                {!loading && !error && activeTab === 'sms' && (
                    <div className="comms-list">
                        {data.sms.map(s => (
                            <div key={s.id} className={`comms-card sms-card ${s.is_incoming ? 'incoming' : 'outgoing'}`}>
                                <div className="comms-card-header">
                                    <span className="comms-sender">{s.is_incoming ? 'From: ' : 'To: '} {s.sender}</span>
                                    <span className="comms-time">{new Date(s.timestamp).toLocaleString()}</span>
                                </div>
                                <div className="comms-text">{s.body}</div>
                            </div>
                        ))}
                    </div>
                )}

                {!loading && !error && activeTab === 'calls' && (
                    <div className="comms-list">
                        {data.calls.map(c => (
                            <div key={c.id} className={`comms-card call-card type-${c.type}`}>
                                <div className="comms-card-header">
                                    <span className="comms-number">{c.number}</span>
                                    <span className="comms-time">{new Date(c.timestamp).toLocaleString()}</span>
                                </div>
                                <div className="comms-meta">
                                    <span className="comms-type">{c.type.toUpperCase()}</span>
                                    <span className="comms-duration">{c.duration_seconds}s</span>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
