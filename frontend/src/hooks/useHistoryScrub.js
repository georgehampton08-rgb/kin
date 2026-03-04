import { useState, useCallback } from 'react';

/**
 * useHistoryScrub
 * Fetches the MatchedRoutes GeoJSON FeatureCollection for a device+date
 * and provides an ordered flat list of coordinates for slider scrubbing.
 */
export function useHistoryScrub(deviceId) {
    const [features, setFeatures] = useState([]);   // raw GeoJSON features
    const [coordinates, setCoordinates] = useState([]); // flat [lon, lat, timestamp] array
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const fetchHistory = useCallback(async (date) => {
        if (!deviceId || !date) return;
        setLoading(true);
        setError(null);
        try {
            const resp = await fetch(
                `http://localhost:8000/api/v1/history/replay/${deviceId}/${date}`
            );
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();

            setFeatures(data.features || []);

            // Flatten all LineString coordinates into one ordered array with timestamps
            const flat = [];
            for (const feature of data.features || []) {
                const coords = feature.geometry?.coordinates || [];
                const tripStart = new Date(feature.properties.trip_start).getTime();
                const tripEnd = new Date(feature.properties.trip_end).getTime();
                const duration = tripEnd - tripStart;
                const count = coords.length;

                coords.forEach(([lon, lat], i) => {
                    // Interpolate the timestamp across the segment
                    const t = count > 1 ? tripStart + (duration * i) / (count - 1) : tripStart;
                    flat.push({ lon, lat, timestamp: t });
                });
            }

            // Sort by timestamp just in case segments arrive out of order
            flat.sort((a, b) => a.timestamp - b.timestamp);
            setCoordinates(flat);
        } catch (e) {
            setError(e.message);
            console.error('[HistoryScrub] Error fetching history:', e);
        } finally {
            setLoading(false);
        }
    }, [deviceId]);

    return { features, coordinates, loading, error, fetchHistory };
}
