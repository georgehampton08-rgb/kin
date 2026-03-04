import { useState, useEffect, useRef } from 'react';

export function useKinSocket(deviceId) {
    const [lastLocation, setLastLocation] = useState(null);
    const [status, setStatus] = useState('connecting'); // connecting, connected, disconnected
    const wsRef = useRef(null);
    const reconnectTimeoutRef = useRef(null);

    useEffect(() => {
        if (!deviceId) return;

        function connect() {
            // Connect to the local FastAPI server
            const wsUrl = `ws://localhost:8000/ws/live/${deviceId}`;
            const ws = new WebSocket(wsUrl);

            ws.onopen = () => {
                setStatus('connected');
                console.log(`[WS] Connected to dashboard stream for ${deviceId}`);
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
                    }
                } catch (e) {
                    console.error('[WS] Error parsing message', e);
                }
            };

            ws.onclose = () => {
                setStatus('disconnected');
                console.warn(`[WS] Disconnected. Reconnecting in 3s...`);
                clearTimeout(reconnectTimeoutRef.current);
                reconnectTimeoutRef.current = setTimeout(connect, 3000);
            };

            ws.onerror = (err) => {
                console.error('[WS] Error', err);
                ws.close();
            };

            wsRef.current = ws;
        }

        connect();

        return () => {
            clearTimeout(reconnectTimeoutRef.current);
            if (wsRef.current) {
                wsRef.current.close();
            }
        };
    }, [deviceId]);

    return { lastLocation, status };
}
