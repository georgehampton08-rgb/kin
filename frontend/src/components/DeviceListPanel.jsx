import { useState, useEffect, useRef } from 'react';
import { formatDistanceToNow } from 'date-fns';

export default function DeviceListPanel({ devices = [], activeDeviceId, onSelectDevice, forceClose, onDeleteDevice, onRefresh }) {
    // Default closed on mobile screens to save space
    const [isOpen, setIsOpen] = useState(() => {
        if (typeof window !== 'undefined') {
            return window.innerWidth > 768;
        }
        return true;
    });

    useEffect(() => {
        if (forceClose && typeof window !== 'undefined' && window.innerWidth <= 768) {
            setIsOpen(false);
        }
    }, [forceClose]);

    return (
        <div className="device-list-panel glass-panel stagger-3" data-open={isOpen}>
            <div className="dlp-header">
                <div className="dlp-title" onClick={() => setIsOpen(o => !o)} style={{ cursor: 'pointer', flex: 1, display: 'flex', alignItems: 'center' }}>
                    <span className="dlp-icon">📡</span>
                    <span>Devices</span>
                    <span className="dlp-count">{devices.length}</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <button className="dlp-refresh-btn" title="Refresh devices" onClick={e => { e.stopPropagation(); if (onRefresh) onRefresh(); }}>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <polyline points="23 4 23 10 17 10"></polyline>
                            <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
                        </svg>
                    </button>
                    <span className="dlp-chevron" onClick={() => setIsOpen(o => !o)} style={{ cursor: 'pointer', padding: '0 4px' }}>
                        {isOpen ? '▾' : '▸'}
                    </span>
                </div>
            </div>

            {isOpen && (
                <div className="dlp-body">
                    {devices.length === 0 ? (
                        <div className="dlp-empty">
                            <div className="dlp-empty-icon">📱</div>
                            <div>No devices connected</div>
                            <div className="dlp-empty-sub">Use the + button to pair a device</div>
                        </div>
                    ) : (
                        devices.map(dev => (
                            <DeviceCard
                                key={dev.device_id}
                                device={dev}
                                isActive={dev.device_id === activeDeviceId}
                                onClick={() => {
                                    onSelectDevice(dev.device_id);
                                    if (window.innerWidth <= 768) setIsOpen(false);
                                }}
                                onDelete={onDeleteDevice}
                            />
                        ))
                    )}
                </div>
            )}

            <style>{`
                .device-list-panel {
                    position: absolute;
                    top: 90px;
                    right: var(--spacing-5);
                    z-index: 20;
                    min-width: 260px;
                    max-width: 320px;
                    display: flex;
                    flex-direction: column;
                    overflow: hidden;
                    transition: box-shadow var(--transition-normal);
                }
                .device-list-panel:hover {
                    box-shadow: var(--shadow-lg), var(--shadow-glow);
                }
                @media (max-width: 768px) {
                    .device-list-panel {
                        top: 90px;
                        right: var(--spacing-3);
                        left: auto;
                        min-width: 200px;
                        max-width: 80vw;
                        z-index: 25;
                    }
                }
                .dlp-header {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    padding: var(--spacing-3) var(--spacing-4);
                    cursor: pointer;
                    border-bottom: 1px solid var(--color-border-light);
                    user-select: none;
                }
                .dlp-header:hover { background: rgba(0,255,204,0.04); }
                .dlp-title {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    font-size: 0.82rem;
                    font-weight: 600;
                    text-transform: uppercase;
                    letter-spacing: 1.5px;
                    color: #8b92a5;
                }
                .dlp-icon { font-size: 1rem; }
                .dlp-count {
                    background: rgba(0,255,204,0.15);
                    color: #00ffcc;
                    border-radius: 12px;
                    padding: 1px 7px;
                    font-size: 0.73rem;
                    font-weight: 700;
                    border: 1px solid rgba(0,255,204,0.25);
                    min-width: 20px;
                    text-align: center;
                }
                .dlp-refresh-btn {
                    background: rgba(0,255,204,0.1);
                    border: 1px solid rgba(0,255,204,0.25);
                    color: #00ffcc;
                    border-radius: 6px;
                    padding: 4px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    cursor: pointer;
                    transition: all 0.2s;
                }
                .dlp-refresh-btn:hover {
                    background: rgba(0,255,204,0.2);
                    transform: rotate(30deg);
                }
                .dlp-chevron {
                    font-size: 0.9rem;
                    color: #8b92a5;
                    transition: transform 0.2s;
                }
                .dlp-body {
                    max-height: 380px;
                    overflow-y: auto;
                    padding: 8px;
                    display: flex;
                    flex-direction: column;
                    gap: 6px;
                }
                .dlp-body::-webkit-scrollbar { width: 3px; }
                .dlp-body::-webkit-scrollbar-thumb { background: rgba(0,255,204,0.2); border-radius: 2px; }
                .dlp-empty {
                    padding: 24px 16px;
                    text-align: center;
                    color: #8b92a5;
                    font-size: 0.8rem;
                    display: flex;
                    flex-direction: column;
                    gap: 6px;
                    align-items: center;
                }
                .dlp-empty-icon { font-size: 2rem; opacity: 0.4; }
                .dlp-empty-sub { font-size: 0.72rem; opacity: 0.6; }
            `}</style>
        </div>
    );
}

import { fetchWithAuth } from '../utils/api';

function DeviceCard({ device, isActive, onClick, onDelete }) {
    const { device_id, status = 'UNKNOWN', battery, lastSeen, gpsAccuracy,
        nickname, app_version, os_info, unread_sms, missed_calls, unread_notifs,
        last_lat, last_lon, last_seen_at, tripStatus, speed } = device;

    const [isEditingName, setIsEditingName] = useState(false);
    const [editNameValue, setEditNameValue] = useState(nickname || '');
    const [displayName, setDisplayName] = useState(nickname);
    const [confirmDelete, setConfirmDelete] = useState(false);

    // Derive activity state from tripStatus or speed
    const activityInfo = (() => {
        if (tripStatus === 'OPEN') {
            const spd = speed ?? 0;
            if (spd > 8.9) return { label: 'DRIVING', icon: '🚗', color: '#ff9900' };
            if (spd > 1.4) return { label: 'WALKING', icon: '🚶', color: '#00ccff' };
            return { label: 'MOVING', icon: '📍', color: '#00ffcc' };
        }
        if (status === 'ONLINE') return { label: 'IDLE', icon: '🔵', color: '#4488ff' };
        if (status === 'STALE') return { label: 'STALE', icon: '🟡', color: '#ffaa00' };
        return { label: 'OFFLINE', icon: '⚫', color: '#666' };
    })();

    const statusColor = status === 'ONLINE' ? '#00ffcc'
        : status === 'STALE' ? '#ffaa00'
            : status === 'OFFLINE' ? '#ff3333'
                : '#666';

    const batteryColor = battery == null ? '#666'
        : battery < 20 ? '#ff3333'
            : battery < 50 ? '#ffaa00'
                : '#00ffcc';

    const handleSaveName = async (e) => {
        e.stopPropagation();
        try {
            const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
            const res = await fetchWithAuth(`${apiUrl}/api/v1/devices/${device_id}`, {
                method: 'PATCH',
                body: JSON.stringify({ nickname: editNameValue })
            });
            if (res.ok) {
                setDisplayName(editNameValue);
                setIsEditingName(false);
            }
        } catch (err) {
            console.error("Failed to update nickname:", err);
        }
    };

    const handleDelete = async (e) => {
        e.stopPropagation();
        if (!confirmDelete) { setConfirmDelete(true); setTimeout(() => setConfirmDelete(false), 3000); return; }
        try {
            const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
            const res = await fetchWithAuth(`${apiUrl}/api/v1/devices/${device_id}`, { method: 'DELETE' });
            if (res.ok && onDelete) onDelete(device_id);
        } catch (err) {
            console.error('Failed to delete device:', err);
        }
    };

    return (
        <div
            className={`device-card ${isActive ? 'active' : ''}`}
            onClick={onClick}
            title={`Device: ${device_id}`}
        >
            <div className="dc-main-row">
                {/* Status glow dot */}
                <div className="dc-status-dot" style={{ '--status-color': statusColor }}>
                    {status === 'ONLINE' && <div className="dc-status-ring" />}
                </div>

                <div className="dc-info">
                    <div className="dc-name-row">
                        {isEditingName ? (
                            <div className="dc-name-edit" onClick={e => e.stopPropagation()}>
                                <input
                                    autoFocus
                                    value={editNameValue}
                                    onChange={e => setEditNameValue(e.target.value)}
                                    onKeyDown={e => { if (e.key === 'Enter') handleSaveName(e) }}
                                    placeholder="Device Name..."
                                />
                                <button onClick={handleSaveName}>✓</button>
                                <button onClick={() => setIsEditingName(false)}>✕</button>
                            </div>
                        ) : (
                            <div className="dc-name">
                                <span onClick={(e) => { e.stopPropagation(); setIsEditingName(true); }} title="Click to rename">
                                    {displayName || (device_id.length > 16 ? '…' + device_id.slice(-12) : device_id)}
                                </span>
                                {battery != null && (
                                    <span className="dc-battery-inline" style={{ color: batteryColor }} title={`Battery: ${battery.toFixed(0)}%`}>
                                        🔋{battery.toFixed(0)}%
                                    </span>
                                )}
                                <button className="dc-edit-btn" onClick={(e) => { e.stopPropagation(); setIsEditingName(true); }} title="Rename device">✎</button>
                            </div>
                        )}
                    </div>

                    <div className="dc-meta">
                        <span style={{ color: activityInfo.color }}>{activityInfo.icon} {activityInfo.label}</span>
                        {speed != null && speed > 0.5 && (
                            <span style={{ color: '#ffaa00' }}>⚡ {(speed * 2.237).toFixed(1)} mph</span>
                        )}
                        {battery != null && (
                            <span style={{ color: batteryColor }}>🔋 {battery.toFixed(0)}%</span>
                        )}
                        {gpsAccuracy != null && (
                            <span style={{ color: '#666' }}>📍 ±{gpsAccuracy.toFixed(0)}m</span>
                        )}
                    </div>
                    {lastSeen && (
                        <div className="dc-lastseen">
                            {formatDistanceToNow(new Date(lastSeen), { addSuffix: true })}
                        </div>
                    )}
                </div>

                {/* Badges + Delete */}
                <div className="dc-badges">
                    {unread_notifs > 0 && <span className="dc-badge notif" title="Unread Notifications">🔔 {unread_notifs}</span>}
                    {unread_sms > 0 && <span className="dc-badge sms" title="Unread SMS">💬 {unread_sms}</span>}
                    {missed_calls > 0 && <span className="dc-badge call" title="Missed Calls">📞 {missed_calls}</span>}
                    <button
                        className={`dc-delete-btn ${confirmDelete ? 'confirm' : ''}`}
                        onClick={handleDelete}
                        title={confirmDelete ? 'Click again to confirm delete' : 'Remove device'}
                    >{confirmDelete ? '⚠️' : '🗑'}</button>
                </div>
            </div>

            {/* Expandable Details when Active */}
            {isActive && (
                <div className="dc-details">
                    {last_lat && last_lon && (
                        <div className="dc-detail-row">
                            <span>📍 Coords:</span> {last_lat.toFixed(5)}, {last_lon.toFixed(5)}
                        </div>
                    )}
                    {last_seen_at && (
                        <div className="dc-detail-row">
                            <span>🕐 Last Update:</span> {formatDistanceToNow(new Date(last_seen_at), { addSuffix: true })}
                        </div>
                    )}
                    {os_info && <div className="dc-detail-row"><span>OS:</span> {os_info}</div>}
                    {app_version && <div className="dc-detail-row"><span>App:</span> v{app_version}</div>}
                    <div className="dc-detail-row"><span>ID:</span> {device_id}</div>
                </div>
            )}

            <style>{`
                .device-card {
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    padding: 10px 12px;
                    border-radius: 8px;
                    border: 1px solid rgba(255,255,255,0.06);
                    cursor: pointer;
                    transition: all 0.2s ease;
                    background: rgba(255,255,255,0.02);
                }
                .device-card:hover {
                    border-color: rgba(0,255,204,0.3);
                    background: rgba(0,255,204,0.04);
                }
                .device-card.active {
                    border-color: rgba(0,255,204,0.5);
                    background: rgba(0,255,204,0.06);
                    box-shadow: 0 0 12px rgba(0,255,204,0.08);
                }
                .dc-status-dot {
                    width: 10px;
                    height: 10px;
                    border-radius: 50%;
                    background: var(--status-color);
                    box-shadow: 0 0 6px var(--status-color);
                    flex-shrink: 0;
                    position: relative;
                }
                .dc-status-ring {
                    position: absolute;
                    inset: -4px;
                    border-radius: 50%;
                    border: 1.5px solid var(--status-color);
                    opacity: 0.6;
                    animation: devicePing 2s ease-out infinite;
                }
                @keyframes devicePing {
                    0% { transform: scale(1); opacity: 0.6; }
                    100% { transform: scale(2.2); opacity: 0; }
                }
                .dc-info { flex: 1; min-width: 0; }
                .dc-name {
                    font-size: 0.82rem;
                    font-weight: 600;
                    color: #e0e4ef;
                    font-family: 'JetBrains Mono', monospace;
                    white-space: nowrap;
                    overflow: hidden;
                    text-overflow: ellipsis;
                }
                .dc-meta {
                    display: flex;
                    gap: 8px;
                    font-size: 0.72rem;
                    margin-top: 3px;
                    flex-wrap: wrap;
                }
                .dc-lastseen {
                    font-size: 0.68rem;
                    color: #555;
                    margin-top: 2px;
                }
                .dc-main-row {
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    width: 100%;
                }
                .dc-name-row {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }
                .dc-edit-btn {
                    background: none;
                    border: none;
                    color: #8b92a5;
                    cursor: pointer;
                    font-size: 0.8rem;
                    opacity: 0;
                    transition: opacity 0.2s;
                }
                .device-card:hover .dc-edit-btn {
                    opacity: 1;
                }
                .dc-name-edit {
                    display: flex;
                    gap: 4px;
                    align-items: center;
                }
                .dc-name-edit input {
                    background: rgba(0,0,0,0.5);
                    border: 1px solid rgba(255,255,255,0.2);
                    color: white;
                    border-radius: 4px;
                    padding: 2px 6px;
                    font-size: 0.8rem;
                    width: 120px;
                }
                .dc-name-edit button {
                    background: rgba(255,255,255,0.1);
                    border: none;
                    color: white;
                    border-radius: 4px;
                    cursor: pointer;
                }
                .dc-badges {
                    display: flex;
                    flex-direction: column;
                    gap: 4px;
                }
                .dc-badge {
                    font-size: 0.65rem;
                    padding: 2px 6px;
                    border-radius: 12px;
                    font-weight: bold;
                    white-space: nowrap;
                }
                .dc-badge.notif { background: rgba(0,255,204,0.15); color: #00ffcc; border: 1px solid rgba(0,255,204,0.3); }
                .dc-badge.sms { background: rgba(0,150,255,0.15); color: #0096ff; border: 1px solid rgba(0,150,255,0.3); }
                .dc-badge.call { background: rgba(255,50,50,0.15); color: #ff3333; border: 1px solid rgba(255,50,50,0.3); }
                
                .dc-details {
                    margin-top: 10px;
                    padding-top: 10px;
                    border-top: 1px dashed rgba(255,255,255,0.1);
                    font-size: 0.7rem;
                    color: #a0a6cc;
                    width: 100%;
                }
                .dc-detail-row {
                    display: flex;
                    justify-content: space-between;
                    margin-bottom: 2px;
                }
                .dc-detail-row span {
                    color: #666;
                }
                .device-card {
                    flex-direction: column;
                    align-items: flex-start;
                }
                .dc-delete-btn {
                    background: none;
                    border: none;
                    cursor: pointer;
                    font-size: 0.85rem;
                    opacity: 0.4;
                    transition: all 0.2s;
                    padding: 2px 4px;
                    border-radius: 4px;
                }
                .dc-delete-btn:hover { opacity: 1; background: rgba(255,50,50,0.2); }
                .dc-delete-btn.confirm { opacity: 1; background: rgba(255,150,0,0.2); animation: pulse 0.5s infinite alternate; }
                @keyframes pulse { from { background: rgba(255,150,0,0.2); } to { background: rgba(255,150,0,0.4); } }
            `}</style>
        </div>
    );
}
