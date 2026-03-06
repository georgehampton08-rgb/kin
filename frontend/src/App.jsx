import { useState, useEffect, useCallback } from 'react';
import { Toaster, toast } from 'react-hot-toast';
import KinMap from './components/KinMap';
import { useKinSocket } from './hooks/useKinSocket';
import { useHistoryScrub } from './hooks/useHistoryScrub';
import { useZones } from './hooks/useZones';
import * as turf from '@turf/turf';
import AddDeviceModal from './components/AddDeviceModal';
import DeviceStatusPanel from './components/DeviceStatusPanel';
import DeviceListPanel from './components/DeviceListPanel';
import CommsPanel from './components/CommsPanel';
import SettingsDrawer from './components/SettingsDrawer';
import DeviceTracker from './components/DeviceTracker';
import { useAuth } from './context/AuthContext';
import Login from './pages/Login';
import { fetchWithAuth } from './utils/api';

// Returns today's date in YYYY-MM-DD LOCAL format
function todayStr() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function fmtTime(ts) {
    if (!ts) return '--:--:--';
    return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function fmtDateTime(ts) {
    if (!ts) return '--';
    return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

const ZONE_LABELS = { safe: 'Safe Zone', caution: 'Caution', restricted: 'Restricted' };
const ZONE_COLORS = { safe: '#00cc66', caution: '#ffaa00', restricted: '#ff3333' };

export default function App() {
    const { user, loading: authLoading, logout } = useAuth();
    const [deviceId, setDeviceId] = useState('');
    const [mode, setMode] = useState('live');
    const [historyDate, setHistoryDate] = useState(todayStr());
    const [scrubIndex, setScrubIndex] = useState(0);
    const [sidebarOpen, setSidebarOpen] = useState(false);
    const [activeTripIdx, setActiveTripIdx] = useState(null);
    const [activeZoneIds, setActiveZoneIds] = useState(new Set());
    const [isAddCardOpen, setIsAddCardOpen] = useState(false);
    const [isSettingsOpen, setIsSettingsOpen] = useState(false);
    const [knownDevices, setKnownDevices] = useState([]);

    // Fetch paired devices on mount
    useEffect(() => {
        if (!user) return;
        const fetchDevices = async () => {
            try {
                const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
                const res = await fetchWithAuth(`${apiUrl}/api/v1/devices/`);
                if (res.ok) {
                    const data = await res.json();
                    setKnownDevices(data.devices.map(d => ({
                        device_id: d.device_id,
                        nickname: d.nickname,
                        app_version: d.app_version,
                        os_info: d.os_info,
                        unread_sms: d.unread_sms,
                        missed_calls: d.missed_calls,
                        unread_notifs: d.unread_notifs,
                        status: 'OFFLINE', // Initial status before WS connection
                        lastSeen: d.paired_at
                    })));
                }
            } catch (err) {
                console.error("Failed to fetch devices:", err);
            }
        };
        fetchDevices();
    }, [user]);

    const [deviceStates, setDeviceStates] = useState({});

    // Data hooks
    const { features, coordinates, loading, error, fetchHistory } = useHistoryScrub(deviceId);
    const { zones, zonePolygons } = useZones();

    const handleDeviceUpdate = useCallback((id, loc, stat, devStat) => {
        setDeviceStates(prev => {
            const existing = prev[id] || {};
            // avoid re-renders if no change
            if (existing.lastLocation === loc && existing.status === stat && existing.deviceStatus === devStat) {
                return prev;
            }
            return {
                ...prev,
                [id]: { lastLocation: loc, status: stat, deviceStatus: devStat }
            };
        });

        // Also update known devices so list panel stays fresh
        setKnownDevices(prev => {
            const existing = prev.find(d => d.device_id === id);
            if (!existing) return prev;

            const newStatus = devStat?.status || (stat === 'connected' ? 'ONLINE' : stat === 'connecting' ? 'STALE' : 'OFFLINE');
            if (existing.status === newStatus && existing.lastSeen === devStat?.lastSeen) return prev; // optimize

            const updated = {
                ...existing,
                status: newStatus,
                battery: devStat?.battery ?? loc?.battery ?? existing.battery,
                gpsAccuracy: devStat?.gpsAccuracy ?? existing.gpsAccuracy,
                lastSeen: devStat?.lastSeen ?? (loc ? new Date().toISOString() : existing.lastSeen),
            };
            return prev.map(d => d.device_id === id ? updated : d);
        });
    }, []);

    const selectedState = deviceStates[deviceId] || {};
    const lastLocation = selectedState.lastLocation;
    const status = selectedState.status || 'disconnected';
    const deviceStatus = selectedState.deviceStatus;

    // Check which zones the current live marker is inside
    useEffect(() => {
        if (!lastLocation || zonePolygons.length === 0) return;
        const pt = turf.point([lastLocation.lon, lastLocation.lat]);
        const inside = new Set();
        zonePolygons.forEach(poly => {
            if (turf.booleanPointInPolygon(pt, poly)) {
                inside.add(poly.properties.id);
            }
        });
        setActiveZoneIds(inside);
    }, [lastLocation, zonePolygons]);

    function handleAlert(alertData) {
        const emoji = alertData.event === 'ENTRY' ? '🟢' : '🔴';
        const verb = alertData.event === 'ENTRY' ? 'entered' : 'left';
        toast.custom(
            (t) => (
                <div className={`kin-toast ${t.visible ? 'enter' : 'exit'}`}>
                    <span className="toast-icon">{emoji}</span>
                    <div className="toast-body">
                        <div className="toast-title">Zone Alert</div>
                        <div className="toast-msg">Device {verb} <strong>{alertData.zone_name}</strong></div>
                    </div>
                </div>
            ),
            { duration: 5000 }
        );
    }

    function handleModeSwitch(newMode) {
        setMode(newMode);
        if (newMode === 'history') {
            setSidebarOpen(true);
            fetchHistory(historyDate);
            setScrubIndex(0);
        } else {
            setSidebarOpen(false);
        }
    }

    function handleDateChange(e) {
        setHistoryDate(e.target.value);
        fetchHistory(e.target.value);
        setScrubIndex(0);
        setActiveTripIdx(null);
    }

    // Jump slider to first point of a selected trip segment
    function jumpToTrip(featureIdx) {
        setActiveTripIdx(featureIdx);
        // find the coordinates index matching the start of this trip
        const tripStart = new Date(features[featureIdx].properties.trip_start).getTime();
        const idx = coordinates.findIndex(c => c.timestamp >= tripStart);
        if (idx >= 0) setScrubIndex(idx);
    }

    const scrubPoint = coordinates.length > 0 ? coordinates[scrubIndex] : null;

    if (authLoading) return <div style={{ background: '#090a0f', height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff' }}>Loading...</div>;
    if (!user) return <Login />;

    return (
        <div className="hud-container">
            {/* Toast container */}
            <Toaster position="top-right" />

            {/* ── Header ──────────────────────────────────────────────────── */}
            <header className="hud-header">
                <div className="hud-title">
                    <h1>Kin Dashboard</h1>
                    <span className="subtitle">
                        {mode === 'live' ? 'Real-Time Surveillance Link' : mode === 'history' ? 'History Playback' : 'Signals Intelligence'}
                    </span>
                </div>

                <div className="mode-toggle">
                    <button id="btn-live" className={`mode-btn ${mode === 'live' ? 'active' : ''}`} onClick={() => handleModeSwitch('live')}>Live</button>
                    <button id="btn-history" className={`mode-btn ${mode === 'history' ? 'active' : ''}`} onClick={() => handleModeSwitch('history')}>History</button>
                    <button id="btn-comms" className={`mode-btn ${mode === 'comms' ? 'active' : ''}`} onClick={() => handleModeSwitch('comms')}>Comms</button>
                </div>

                {mode === 'live' ? (
                    <div className="status-indicator">
                        <div className={`status-dot ${status}`}></div>
                        <span className="status-text">{status.toUpperCase()}</span>
                    </div>
                ) : (
                    <input id="history-date-picker" className="scrub-date-picker" type="date" value={historyDate} onChange={handleDateChange} />
                )}

                <div className="device-selector">
                    <button className="add-device-btn" title="Add New Device" onClick={() => setIsAddCardOpen(true)}>+</button>
                    <label>Target ID:</label>
                    <input id="device-id-input" value={deviceId} onChange={e => setDeviceId(e.target.value)} placeholder="Enter ID" />
                    <button className="mode-btn settings-btn" title="Global Settings" onClick={() => setIsSettingsOpen(true)}>☰</button>
                </div>
            </header>

            {/* ── Map Area ───────────────────────────────────────────────── */}
            <main className="map-view">

                {/* History Sidebar */}
                <aside className={`history-sidebar ${sidebarOpen ? 'open' : ''}`}>
                    <div className="sidebar-header">
                        <h2>📍 Trip Log</h2>
                        <button className="sidebar-close" onClick={() => setSidebarOpen(false)}>✕</button>
                    </div>
                    <div className="sidebar-content">
                        {loading && <p className="no-data-msg">Loading…</p>}
                        {error && <p className="no-data-msg" style={{ color: '#ff5555' }}>Error: {error}</p>}
                        {!loading && !error && features.length === 0 && (
                            <p className="no-data-msg">No trips recorded for this date.</p>
                        )}
                        {features.map((f, i) => (
                            <div
                                key={f.properties.id}
                                className={`trip-card ${activeTripIdx === i ? 'active' : ''}`}
                                onClick={() => jumpToTrip(i)}
                            >
                                <div className="trip-card-time">
                                    {fmtDateTime(f.properties.trip_start)} → {fmtDateTime(f.properties.trip_end)}
                                </div>
                                <div className="trip-card-meta">
                                    {f.properties.raw_point_count} pts · {f.properties.provider} · conf {(f.properties.confidence * 100).toFixed(0)}%
                                </div>
                            </div>
                        ))}
                    </div>
                </aside>

                {/* Map */}
                <KinMap
                    targetLocation={mode === 'live' ? lastLocation : scrubPoint}
                    historyFeatures={mode === 'history' ? features : []}
                    isHistory={mode === 'history'}
                    zonePolygons={zonePolygons}
                    activeZoneIds={activeZoneIds}
                    liveDevices={mode === 'live' ? deviceStates : {}}
                    activeDeviceId={deviceId}
                />

                {/* Comms Panel Overlay */}
                {mode === 'comms' && (
                    <div className="comms-overlay">
                        <CommsPanel deviceId={deviceId} />
                    </div>
                )}

                {/* Device List Panel */}
                <DeviceListPanel
                    devices={knownDevices}
                    activeDeviceId={deviceId}
                    onSelectDevice={id => setDeviceId(id)}
                    forceClose={sidebarOpen}
                />

                {/* Global Settings Drawer */}
                <SettingsDrawer
                    isOpen={isSettingsOpen}
                    onClose={() => setIsSettingsOpen(false)}
                />

                {/* Zone Legend */}
                <div className="zone-legend">
                    <div className="zone-legend-title">Zones</div>
                    {Object.entries(ZONE_LABELS).map(([type, label]) => (
                        <div key={type} className="legend-row">
                            <div className="legend-dot" style={{ background: ZONE_COLORS[type] }} />
                            {label}
                        </div>
                    ))}
                </div>

                {/* Live Telemetry HUD */}
                {mode === 'live' && lastLocation && (
                    <div className="telemetry-overlay">
                        <DeviceStatusPanel deviceStatus={deviceStatus} />
                        <div className="telemetry-bar">
                            <div className="stat">
                                <span className="label">SPD</span>
                                <span className="value">{(lastLocation.speed * 2.23694).toFixed(1)} <small>mph</small></span>
                            </div>
                            <div className="stat">
                                <span className="label">BAT</span>
                                <span className="value">{lastLocation.battery || '--'}%</span>
                            </div>
                        </div>
                    </div>
                )}

                {/* History Scrubber — bottom bar */}
                {mode === 'history' && !loading && coordinates.length > 0 && (
                    <div className="history-panel">
                        <div className="scrub-controls">
                            <div className="scrub-meta">
                                <div>
                                    <div className="scrub-label">Current Time</div>
                                    <div className="scrub-time">{fmtTime(scrubPoint?.timestamp)}</div>
                                </div>
                                <div className="scrub-label">{scrubIndex + 1} / {coordinates.length} pts</div>
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
                    </div>
                )}
            </main>

            {/* Toast styles injected inline */}
            <style>{`
        .kin-toast {
          display: flex; align-items: center; gap: 12px;
          background: rgba(12,14,18,0.96); backdrop-filter: blur(12px);
          border: 1px solid rgba(255,255,255,0.12); border-radius: 8px;
          padding: 12px 16px; color: #fff; font-size: 0.85rem;
          box-shadow: 0 8px 24px rgba(0,0,0,0.4);
        }
        .toast-icon { font-size: 1.4rem; line-height: 1; }
        .toast-msg strong { color: #00ffcc; }
        .add-device-btn {
            background: #00ffcc; color: #000; border: none; font-size: 1.2rem;
            width: 28px; height: 28px; border-radius: 50%; display: flex;
            align-items: center; justify-content: center; cursor: pointer;
            font-weight: bold; margin-right: 8px;
        }
        .add-device-btn:hover { background: #00ccaa; }
        .device-selector { display: flex; align-items: center; }
      `}</style>
            {isAddCardOpen && <AddDeviceModal onClose={() => setIsAddCardOpen(false)} />}

            {/* Background Device Trackers */}
            {mode === 'live' && knownDevices.map(d => (
                <DeviceTracker
                    key={d.device_id}
                    device={d}
                    onUpdate={handleDeviceUpdate}
                    onAlert={handleAlert}
                />
            ))}
        </div>
    );
}
