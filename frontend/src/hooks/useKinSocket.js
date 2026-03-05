import { useState, useEffect, useRef } from 'react';

/**
 * useKinSocket
 * Native WebSocket hook with auto-reconnect.
 * Handles both 'telemetry' and 'geofence_alert' message types.
 * @param {string} deviceId   - Target device to subscribe to
 * @param {function} onAlert  - Callback fired with geofence alert data
 */
export function useKinSocket(deviceId, onAlert) {
    const [lastLocation, setLastLocation] = useState(null);
    const [status, setStatus] = useState('connecting');
    const wsRef = useRef(null);
    const reconnectRef = useRef(null);
    const onAlertRef = useRef(onAlert);

    // Keep ref fresh on each render without restarting the socket
    useEffect(() => { onAlertRef.current = onAlert; }, [onAlert]);

    useEffect(() => {
        if (!deviceId) return;

        function connect() {
            const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
            // Convert http(s):// → ws(s):// for WebSocket
            const wsBase = apiUrl.replace(/^http/, 'ws');
            const ws = new WebSocket(`${wsBase}/ws/live/${deviceId}`);

            ws.onopen = () => {
                setStatus('connected');
                console.log(`[WS] Connected for ${deviceId}`);
            };

            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);

                    if (data.type === 'telemetry') {
                        setLastLocation({
                            lat: data.lat,
                            lon: data.lon,
                            speed: data.speed,
                            battery: data.battery_level,
                            timestamp: Date.now()
                        });
                    } else if (data.type === 'geofence_alert') {
                        // Fire the alert callback (non-blocking)
                        if (onAlertRef.current) onAlertRef.current(data);
                    }
                } catch (e) {
                    console.error('[WS] Parse error', e);
                }
            };

            ws.onclose = () => {
                setStatus('disconnected');
                clearTimeout(reconnectRef.current);
                reconnectRef.current = setTimeout(connect, 3000);
            };

            ws.onerror = () => ws.close();
            wsRef.current = ws;
        }

        connect();
        return () => {
            clearTimeout(reconnectRef.current);
            wsRef.current?.close();
        };
    }, [deviceId]);

    return { lastLocation, status };
}
