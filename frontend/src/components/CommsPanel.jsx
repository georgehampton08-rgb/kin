import React, { useState, useEffect, useCallback } from 'react';
import { fetchWithAuth } from '../utils/api';

const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const TAB_LABELS = { notifications: '🔔 Notifications', sms: '💬 SMS', calls: '📞 Calls' };
const LIMIT = 100;

function formatTs(ts) {
    if (!ts) return '—';
    const d = new Date(ts);
    return d.toLocaleString([], { month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

function fmtDuration(sec) {
    if (!sec) return '0s';
    const m = Math.floor(sec / 60), s = sec % 60;
    return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

export default function CommsPanel({ deviceId, knownDevices = [], onSelectDevice }) {
    const [activeTab, setActiveTab] = useState('notifications');
    const [data, setData] = useState({ notifications: [], sms: [], calls: [] });
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [lastRefresh, setLastRefresh] = useState(null);

    const fetchData = useCallback(async (tab, devId) => {
        if (!devId) return;
        setLoading(true);
        setError(null);
        try {
            const res = await fetchWithAuth(`${apiUrl}/api/v1/devices/${devId}/${tab}?limit=${LIMIT}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const json = await res.json();
            setData(prev => ({ ...prev, [tab]: json[tab] || [] }));
            setLastRefresh(new Date());

            // Mark as read silently
            fetchWithAuth(`${apiUrl}/api/v1/devices/${devId}/comms/mark_read`, {
                method: 'POST',
                body: JSON.stringify({ type: tab })
            }).catch(() => { });
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, []);

    // Fetch on tab or device change
    useEffect(() => {
        setData({ notifications: [], sms: [], calls: [] });
        fetchData(activeTab, deviceId);
    }, [activeTab, deviceId, fetchData]);

    const currentDevice = knownDevices.find(d => d.device_id === deviceId);

    return (
        <div className="comms-panel">
            {/* Device selector row */}
            <div className="comms-device-row">
                <span className="comms-panel-label">📱 Device:</span>
                {knownDevices.length === 0 ? (
                    <span style={{ color: '#666', fontSize: '0.8rem' }}>No devices paired</span>
                ) : (
                    <select
                        className="comms-device-select"
                        value={deviceId || ''}
                        onChange={e => onSelectDevice && onSelectDevice(e.target.value)}
                    >
                        <option value="">— Select Device —</option>
                        {knownDevices.map(d => (
                            <option key={d.device_id} value={d.device_id}>
                                {d.nickname || d.device_id.slice(-10)} {d.status === 'ONLINE' ? '🟢' : '⚫'}
                            </option>
                        ))}
                    </select>
                )}
                <button
                    className="comms-refresh-btn"
                    onClick={() => fetchData(activeTab, deviceId)}
                    disabled={!deviceId || loading}
                    title="Refresh"
                >↺</button>
                {lastRefresh && (
                    <span className="comms-refresh-time">
                        Updated {lastRefresh.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                    </span>
                )}
            </div>

            {/* Tabs */}
            <div className="comms-tabs">
                {Object.entries(TAB_LABELS).map(([key, label]) => (
                    <button
                        key={key}
                        className={`comms-tab ${activeTab === key ? 'active' : ''}`}
                        onClick={() => setActiveTab(key)}
                    >{label}</button>
                ))}
            </div>

            {/* Content */}
            <div className="comms-content">
                {!deviceId && <div className="comms-empty">Select a device above to view its communications.</div>}
                {deviceId && loading && <div className="comms-loading"><div className="comms-spinner" />Loading…</div>}
                {deviceId && error && <div className="comms-error">⚠️ {error}</div>}

                {deviceId && !loading && !error && (
                    <>
                        {/* ── Notifications Table ── */}
                        {activeTab === 'notifications' && (
                            data.notifications.length === 0
                                ? <div className="comms-empty">No notifications recorded.</div>
                                : <div className="comms-table-wrap">
                                    <table className="comms-table">
                                        <thead>
                                            <tr>
                                                <th>App</th>
                                                <th>Title</th>
                                                <th>Message</th>
                                                <th>Time</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {data.notifications.map(n => (
                                                <tr key={n.id}>
                                                    <td><span className="comms-pkg">{n.package_name?.split('.').pop()}</span></td>
                                                    <td>{n.title || '—'}</td>
                                                    <td className="comms-body-cell">{n.text || '—'}</td>
                                                    <td className="comms-ts">{formatTs(n.timestamp)}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                        )}

                        {/* ── SMS Table ── */}
                        {activeTab === 'sms' && (
                            data.sms.length === 0
                                ? <div className="comms-empty">No SMS recorded.</div>
                                : <div className="comms-table-wrap">
                                    <table className="comms-table">
                                        <thead>
                                            <tr>
                                                <th>Dir</th>
                                                <th>Contact</th>
                                                <th>Message</th>
                                                <th>Time</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {data.sms.map(s => (
                                                <tr key={s.id} className={s.is_incoming ? 'sms-in' : 'sms-out'}>
                                                    <td>{s.is_incoming ? '📥' : '📤'}</td>
                                                    <td><strong>{s.sender}</strong></td>
                                                    <td className="comms-body-cell">{s.body || '—'}</td>
                                                    <td className="comms-ts">{formatTs(s.timestamp)}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                        )}

                        {/* ── Calls Table ── */}
                        {activeTab === 'calls' && (
                            data.calls.length === 0
                                ? <div className="comms-empty">No calls recorded.</div>
                                : <div className="comms-table-wrap">
                                    <table className="comms-table">
                                        <thead>
                                            <tr>
                                                <th>Type</th>
                                                <th>Number</th>
                                                <th>Duration</th>
                                                <th>Time</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {data.calls.map(c => (
                                                <tr key={c.id} className={`call-${c.type}`}>
                                                    <td>
                                                        <span className={`call-badge type-${c.type}`}>
                                                            {c.type === 'missed' ? '❌' : c.type === 'incoming' ? '📲' : '📞'} {c.type.toUpperCase()}
                                                        </span>
                                                    </td>
                                                    <td><strong>{c.number}</strong></td>
                                                    <td>{fmtDuration(c.duration_seconds)}</td>
                                                    <td className="comms-ts">{formatTs(c.timestamp)}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                        )}
                    </>
                )}
            </div>

            <style>{`
                .comms-panel {
                    display: flex; flex-direction: column; height: 100%;
                    background: rgba(8,10,16,0.97); color: #e0e4ff;
                    font-family: 'Inter', sans-serif; font-size: 0.82rem;
                    border-radius: 12px; overflow: hidden;
                }
                .comms-device-row {
                    display: flex; align-items: center; gap: 8px;
                    padding: 10px 14px; background: rgba(255,255,255,0.04);
                    border-bottom: 1px solid rgba(255,255,255,0.08);
                    flex-wrap: wrap;
                }
                .comms-panel-label { color: #888; white-space: nowrap; }
                .comms-device-select {
                    flex: 1; background: rgba(255,255,255,0.07); color: #e0e4ff;
                    border: 1px solid rgba(255,255,255,0.15); border-radius: 6px;
                    padding: 4px 8px; font-size: 0.82rem; cursor: pointer;
                    min-width: 140px;
                }
                .comms-refresh-btn {
                    background: rgba(0,255,204,0.1); border: 1px solid rgba(0,255,204,0.25);
                    color: #00ffcc; border-radius: 6px; padding: 4px 10px;
                    cursor: pointer; font-size: 1rem; transition: background 0.2s;
                }
                .comms-refresh-btn:hover { background: rgba(0,255,204,0.2); }
                .comms-refresh-btn:disabled { opacity: 0.4; cursor: default; }
                .comms-refresh-time { color: #555; font-size: 0.72rem; }
                .comms-tabs {
                    display: flex; border-bottom: 1px solid rgba(255,255,255,0.08);
                }
                .comms-tab {
                    flex: 1; padding: 10px 6px; background: none; border: none;
                    color: #666; cursor: pointer; font-size: 0.78rem; font-weight: 600;
                    letter-spacing: 0.03em; border-bottom: 2px solid transparent;
                    transition: all 0.2s;
                }
                .comms-tab.active { color: #00ffcc; border-bottom-color: #00ffcc; background: rgba(0,255,204,0.05); }
                .comms-tab:hover:not(.active) { color: #aaa; background: rgba(255,255,255,0.03); }
                .comms-content { flex: 1; overflow: hidden; display: flex; flex-direction: column; }
                .comms-table-wrap { flex: 1; overflow-y: auto; }
                .comms-table { width: 100%; border-collapse: collapse; }
                .comms-table th {
                    position: sticky; top: 0; background: rgba(10,12,20,0.98);
                    color: #555; font-size: 0.7rem; text-transform: uppercase;
                    letter-spacing: 0.07em; padding: 8px 10px; text-align: left;
                    border-bottom: 1px solid rgba(255,255,255,0.08);
                }
                .comms-table td {
                    padding: 7px 10px; border-bottom: 1px solid rgba(255,255,255,0.04);
                    vertical-align: top; max-width: 260px;
                }
                .comms-table tr:hover td { background: rgba(255,255,255,0.03); }
                .comms-body-cell { word-break: break-word; color: #b0b8d8; }
                .comms-ts { color: #555; white-space: nowrap; font-size: 0.72rem; }
                .comms-pkg {
                    background: rgba(100,100,255,0.15); color: #8888ff;
                    padding: 1px 5px; border-radius: 4px; font-size: 0.72rem;
                    white-space: nowrap;
                }
                .sms-in td:first-child { color: #00ccff; }
                .sms-out td:first-child { color: #aa88ff; }
                .call-badge { padding: 2px 6px; border-radius: 4px; font-size: 0.72rem; white-space: nowrap; }
                .call-badge.type-missed { background: rgba(255,50,50,0.15); color: #ff5555; }
                .call-badge.type-incoming { background: rgba(0,200,100,0.15); color: #00cc66; }
                .call-badge.type-outgoing { background: rgba(100,100,255,0.15); color: #8888ff; }
                .comms-empty {
                    display: flex; align-items: center; justify-content: center;
                    height: 120px; color: #444; font-size: 0.85rem;
                }
                .comms-loading {
                    display: flex; align-items: center; justify-content: center;
                    gap: 10px; height: 80px; color: #666;
                }
                .comms-spinner {
                    width: 18px; height: 18px; border: 2px solid rgba(0,255,204,0.3);
                    border-top-color: #00ffcc; border-radius: 50%; animation: spin 0.8s linear infinite;
                }
                @keyframes spin { to { transform: rotate(360deg); } }
                .comms-error { color: #ff5555; padding: 16px; text-align: center; }
            `}</style>
        </div>
    );
}
