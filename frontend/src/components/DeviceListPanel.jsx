import { useState, useEffect, useRef } from 'react';
import { formatDistanceToNow } from 'date-fns';

export default function DeviceListPanel({ devices = [], activeDeviceId, onSelectDevice }) {
    const [isOpen, setIsOpen] = useState(true);

    return (
        <div className="device-list-panel" data-open={isOpen}>
            <div className="dlp-header" onClick={() => setIsOpen(o => !o)}>
                <div className="dlp-title">
                    <span className="dlp-icon">📡</span>
                    <span>Devices</span>
                    <span className="dlp-count">{devices.length}</span>
                </div>
                <span className="dlp-chevron">{isOpen ? '▾' : '▸'}</span>
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
                                onClick={() => onSelectDevice(dev.device_id)}
                            />
                        ))
                    )}
                </div>
            )}

            <style>{`
                .device-list-panel {
                    position: absolute;
                    top: 24px;
                    right: 72px;
                    z-index: 20;
                    background: rgba(10, 12, 18, 0.92);
                    backdrop-filter: blur(16px);
                    border: 1px solid rgba(0, 255, 204, 0.2);
                    border-radius: 12px;
                    min-width: 240px;
                    max-width: 300px;
                    box-shadow: 0 8px 32px rgba(0,0,0,0.5), 0 0 1px rgba(0,255,204,0.3);
                    overflow: hidden;
                    transition: box-shadow 0.3s ease;
                }
                .device-list-panel:hover {
                    box-shadow: 0 8px 48px rgba(0,0,0,0.6), 0 0 12px rgba(0,255,204,0.15);
                }
                .dlp-header {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    padding: 12px 16px;
                    cursor: pointer;
                    border-bottom: 1px solid rgba(255,255,255,0.07);
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

function DeviceCard({ device, isActive, onClick }) {
    const { device_id, status = 'UNKNOWN', battery, lastSeen, gpsAccuracy } = device;

    const statusColor = status === 'ONLINE' ? '#00ffcc'
        : status === 'STALE' ? '#ffaa00'
            : status === 'OFFLINE' ? '#ff3333'
                : '#666';

    const batteryColor = battery == null ? '#666'
        : battery < 20 ? '#ff3333'
            : battery < 50 ? '#ffaa00'
                : '#00ffcc';

    return (
        <div
            className={`device-card ${isActive ? 'active' : ''}`}
            onClick={onClick}
            title={`Device: ${device_id}`}
        >
            {/* Status glow dot */}
            <div className="dc-status-dot" style={{ '--status-color': statusColor }}>
                {status === 'ONLINE' && <div className="dc-status-ring" />}
            </div>

            <div className="dc-info">
                <div className="dc-name">{device_id.length > 16 ? '…' + device_id.slice(-12) : device_id}</div>
                <div className="dc-meta">
                    <span style={{ color: statusColor }}>{status}</span>
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
            `}</style>
        </div>
    );
}
