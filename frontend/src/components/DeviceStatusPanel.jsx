import { useEffect, useState } from 'react';
import { formatDistanceToNow } from 'date-fns';

function BatteryIndicator({ level }) {
    if (level == null) return <span style={{ color: 'var(--color-text-muted)' }}>--</span>;

    // Segmented battery bar
    return (
        <div style={{ display: 'flex', gap: '3px', alignItems: 'center' }}>
            {[...Array(5)].map((_, i) => {
                const threshold = i * 20;
                const isFilled = level > threshold;
                let color = 'var(--color-signal-active)';
                if (level <= 20) color = 'var(--color-signal-offline)';
                else if (level <= 50) color = 'var(--color-signal-warning)';

                return (
                    <div
                        key={i}
                        style={{
                            width: '6px',
                            height: i === 0 || i === 4 ? '12px' : '16px', // Slight curve effect
                            borderRadius: '2px',
                            background: isFilled ? color : 'var(--color-border-light)',
                            boxShadow: isFilled ? `0 0 4px ${color}` : 'none',
                            transition: 'var(--transition-normal)',
                            opacity: isFilled ? 1 : 0.5
                        }}
                    />
                );
            })}
            <span style={{
                marginLeft: '8px',
                fontSize: 'var(--text-size-sm)',
                fontFamily: 'var(--font-family-mono)',
                fontWeight: '600',
                color: level <= 20 ? 'var(--color-signal-offline)' : 'var(--color-text-primary)'
            }}>
                {level.toFixed(0)}%
            </span>
        </div>
    );
}

export default function DeviceStatusPanel({ deviceStatus }) {
    const [now, setNow] = useState(Date.now());

    // Update relative time every minute smoothly
    useEffect(() => {
        const interval = setInterval(() => setNow(Date.now()), 60000);
        return () => clearInterval(interval);
    }, []);

    if (!deviceStatus) return null;

    const { status, battery, gpsAccuracy, lastSeen, tripStatus } = deviceStatus;

    let statusColor = 'var(--color-text-muted)';
    let PulseComponent = null;

    if (status === 'ONLINE') {
        statusColor = 'var(--color-signal-active)';
        PulseComponent = () => <div className="status-dot ONLINE" />;
    } else if (status === 'STALE') {
        statusColor = 'var(--color-signal-warning)';
        PulseComponent = () => <div className="status-dot STALE" />;
    } else if (status === 'OFFLINE') {
        statusColor = 'var(--color-signal-offline)';
        PulseComponent = () => <div className="status-dot OFFLINE" />;
    }

    return (
        <div className="status-panel glass-panel">
            <h3 className="panel-title">Device Health</h3>

            <div className="stat-grid">
                <div className="stat-box">
                    <span className="label">Status</span>
                    <div className="value-container">
                        {PulseComponent && <PulseComponent />}
                        <span className="value" style={{ color: statusColor, textShadow: `0 0 10px ${statusColor}` }}>
                            {status}
                        </span>
                    </div>
                </div>

                <div className="stat-box">
                    <span className="label">Trip</span>
                    <span className="value" style={{ color: tripStatus === 'active' ? 'var(--color-signal-active)' : 'var(--color-text-primary)' }}>
                        {tripStatus || '--'}
                    </span>
                </div>

                <div className="stat-box battery">
                    <span className="label">Battery Phase</span>
                    <BatteryIndicator level={battery} />
                </div>

                <div className="stat-box">
                    <span className="label">GPS Accuracy</span>
                    <span className="value mono">
                        {gpsAccuracy != null ? `${gpsAccuracy.toFixed(1)}m` : '--'}
                    </span>
                </div>
            </div>

            {lastSeen && (
                <div className="last-seen">
                    <span style={{ color: 'var(--color-text-secondary)' }}>Last Ping: </span>
                    <span className="time-text">
                        {formatDistanceToNow(new Date(lastSeen), { addSuffix: true })}
                    </span>
                </div>
            )}

            <style>{`
                .status-panel {
                    padding: var(--spacing-5);
                    color: var(--color-text-primary);
                    min-width: 320px;
                }
                .panel-title {
                    margin: 0 0 var(--spacing-4) 0;
                    font-size: var(--text-size-xs);
                    text-transform: uppercase;
                    letter-spacing: 2px;
                    color: var(--color-text-secondary);
                    border-bottom: 1px solid var(--color-border-light);
                    padding-bottom: var(--spacing-3);
                }
                .stat-grid {
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: var(--spacing-5);
                }
                .stat-box { display: flex; flex-direction: column; }
                .stat-box.battery { grid-column: span 2; }
                .stat-box .label { 
                    font-size: var(--text-size-xs); 
                    color: var(--color-text-secondary); 
                    margin-bottom: var(--spacing-1); 
                    text-transform: uppercase;
                    letter-spacing: 1px;
                }
                .value-container {
                    display: flex;
                    align-items: center;
                    gap: var(--spacing-2);
                }
                .stat-box .value { 
                    font-size: var(--text-size-lg); 
                    font-weight: var(--font-weight-bold);
                    transition: color var(--transition-normal), text-shadow var(--transition-normal);
                }
                .last-seen {
                    margin-top: var(--spacing-5);
                    font-size: var(--text-size-xs);
                    text-align: right;
                    font-family: var(--font-family-mono);
                    letter-spacing: 0.5px;
                }
                .time-text {
                    color: var(--color-text-primary);
                    opacity: 0.8;
                }
            `}</style>
        </div>
    );
}
