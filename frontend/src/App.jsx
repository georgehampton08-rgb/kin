import { useState } from 'react';
import KinMap from './components/KinMap';
import { useKinSocket } from './hooks/useKinSocket';
import { useHistoryScrub } from './hooks/useHistoryScrub';

// Returns today's date in YYYY-MM-DD local format
const todayStr = () => new Date().toISOString().slice(0, 10);

function App() {
    const [deviceId, setDeviceId] = useState('test_child_chicago');
    const [mode, setMode] = useState('live'); // 'live' | 'history'
    const [historyDate, setHistoryDate] = useState(todayStr());
    const [scrubIndex, setScrubIndex] = useState(0);

    // Live WebSocket stream
    const { lastLocation, status } = useKinSocket(deviceId);

    // History fetch + coordinate flatten
    const { features, coordinates, loading, error, fetchHistory } = useHistoryScrub(deviceId);

    function handleModeSwitch(newMode) {
        setMode(newMode);
        if (newMode === 'history') {
            fetchHistory(historyDate);
            setScrubIndex(0);
        }
    }

    function handleDateChange(e) {
        setHistoryDate(e.target.value);
        fetchHistory(e.target.value);
        setScrubIndex(0);
    }

    // The coordinate the marker should sit on
    const scrubPoint = coordinates.length > 0 ? coordinates[scrubIndex] : null;

    // Format timestamp for display
    function fmtTime(ts) {
        if (!ts) return '--:--:--';
        return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    }

    return (
        <div className="hud-container">
            <header className="hud-header">
                <div className="hud-title">
                    <h1>Kin Dashboard</h1>
                    <span className="subtitle">
                        {mode === 'live' ? 'Real-Time Surveillance Link' : 'History Playback'}
                    </span>
                </div>

                {/* LIVE / HISTORY mode toggle */}
                <div className="mode-toggle">
                    <button
                        id="btn-live"
                        className={`mode-btn ${mode === 'live' ? 'active' : ''}`}
                        onClick={() => handleModeSwitch('live')}
                    >
                        Live
                    </button>
                    <button
                        id="btn-history"
                        className={`mode-btn ${mode === 'history' ? 'active' : ''}`}
                        onClick={() => handleModeSwitch('history')}
                    >
                        History
                    </button>
                </div>

                {/* Status / Device controls */}
                {mode === 'live' ? (
                    <div className="status-indicator">
                        <div className={`status-dot ${status}`}></div>
                        <span className="status-text">{status.toUpperCase()}</span>
                    </div>
                ) : (
                    <input
                        id="history-date-picker"
                        className="scrub-date-picker"
                        type="date"
                        value={historyDate}
                        onChange={handleDateChange}
                    />
                )}

                <div className="device-selector">
                    <label>Target ID:</label>
                    <input
                        id="device-id-input"
                        value={deviceId}
                        onChange={e => setDeviceId(e.target.value)}
                        placeholder="e.g. child_idx_123"
                    />
                </div>
            </header>

            <main className="map-view">
                <KinMap
                    targetLocation={mode === 'live' ? lastLocation : scrubPoint}
                    historyFeatures={mode === 'history' ? features : []}
                    isHistory={mode === 'history'}
                />

                {/* LIVE mode telemetry HUD */}
                {mode === 'live' && lastLocation && (
                    <div className="telemetry-overlay">
                        <div className="telemetry-bar">
                            <div className="stat">
                                <span className="label">SPD</span>
                                <span className="value">
                                    {(lastLocation.speed * 2.23694).toFixed(1)} <small>mph</small>
                                </span>
                            </div>
                            <div className="stat">
                                <span className="label">BAT</span>
                                <span className="value">{lastLocation.battery || '--'}%</span>
                            </div>
                        </div>
                    </div>
                )}

                {/* HISTORY mode time scrubber */}
                {mode === 'history' && (
                    <div className="history-panel">
                        {loading && <p className="no-data-msg">Loading history...</p>}
                        {error && <p className="no-data-msg" style={{ color: '#ff5555' }}>Error: {error}</p>}
                        {!loading && !error && coordinates.length === 0 && (
                            <p className="no-data-msg">No routes found for this date.</p>
                        )}
                        {!loading && coordinates.length > 0 && (
                            <div className="scrub-controls">
                                <div className="scrub-meta">
                                    <div>
                                        <div className="scrub-label">Time</div>
                                        <div className="scrub-time">{fmtTime(scrubPoint?.timestamp)}</div>
                                    </div>
                                    <div className="scrub-label">
                                        {scrubIndex + 1} / {coordinates.length} points
                                    </div>
                                </div>
                                <input
                                    id="history-scrubber"
                                    type="range"
                                    className="scrub-slider"
                                    min={0}
                                    max={coordinates.length - 1}
                                    value={scrubIndex}
                                    onChange={e => setScrubIndex(Number(e.target.value))}
                                />
                            </div>
                        )}
                    </div>
                )}
            </main>
        </div>
    );
}

export default App;
