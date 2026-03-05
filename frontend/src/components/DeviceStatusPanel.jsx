import { formatDistanceToNow } from 'date-fns';

export default function DeviceStatusPanel({ deviceStatus }) {
    if (!deviceStatus) return null;

    const { status, battery, gpsAccuracy, lastSeen, tripStatus } = deviceStatus;

    let statusColor = '#888';
    if (status === 'ONLINE') statusColor = '#00ffcc';
    if (status === 'STALE') statusColor = '#ffaa00';
    if (status === 'OFFLINE') statusColor = '#ff3333';

    let batteryColor = '#00ffcc';
    if (battery < 20) batteryColor = '#ff3333';
    else if (battery < 50) batteryColor = '#ffaa00';

    return (
        <div className="status-panel">
            <h3 className="panel-title">Device Health</h3>

            <div className="stat-grid">
                <div className="stat-box">
                    <span className="label">Status</span>
                    <span className="value" style={{ color: statusColor }}>
                        {status}
                    </span>
                </div>

                <div className="stat-box">
                    <span className="label">Trip</span>
                    <span className="value">{tripStatus}</span>
                </div>

                <div className="stat-box">
                    <span className="label">Battery</span>
                    <span className="value" style={{ color: batteryColor }}>
                        {battery != null ? `${battery.toFixed(0)}%` : '--'}
                    </span>
                </div>

                <div className="stat-box">
                    <span className="label">GPS Accuracy</span>
                    <span className="value">
                        {gpsAccuracy != null ? `${gpsAccuracy.toFixed(1)}m` : '--'}
                    </span>
                </div>
            </div>

            {lastSeen && (
                <div className="last-seen">
                    Last Seen: {formatDistanceToNow(new Date(lastSeen), { addSuffix: true })}
                </div>
            )}

            <style>{`
                .status-panel {
                    background: rgba(12, 14, 18, 0.85);
                    backdrop-filter: blur(8px);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 8px;
                    padding: 16px;
                    margin: 16px;
                    color: white;
                    min-width: 280px;
                }
                .panel-title {
                    margin: 0 0 16px 0;
                    font-size: 0.9rem;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                    color: #8b92a5;
                    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
                    padding-bottom: 8px;
                }
                .stat-grid {
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 16px;
                }
                .stat-box { display: flex; flex-direction: column; }
                .stat-box .label { font-size: 0.75rem; color: #8b92a5; margin-bottom: 4px; }
                .stat-box .value { font-size: 1.1rem; font-weight: 600; }
                .last-seen {
                    margin-top: 16px;
                    font-size: 0.8rem;
                    color: #666;
                    text-align: right;
                }
            `}</style>
        </div>
    );
}
