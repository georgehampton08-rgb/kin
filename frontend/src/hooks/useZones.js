import { useState, useEffect } from 'react';
import * as turf from '@turf/turf';
import { fetchWithAuth } from '../utils/api';

/**
 * useZones
 * Fetches all geofence zones from the backend and returns:
 *  - zones: raw zone feature array
 *  - zonePolygons: Turf circle GeoJSON features for each zone
 * Only fetches when `user` is authenticated.
 */
export function useZones(user) {
    const [zones, setZones] = useState([]);
    const [zonePolygons, setZonePolygons] = useState([]);

    useEffect(() => {
        if (!user) return; // Don't fetch without auth — avoids 401
        const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
        fetchWithAuth(`${apiUrl}/api/v1/zones/`)
            .then(r => r.json())
            .then(data => {
                const features = data.features || [];
                setZones(features);

                // Build turf circle polygons for each zone
                const polygons = features.map(f => {
                    const { lon, lat } = { lon: f.geometry.coordinates[0], lat: f.geometry.coordinates[1] };
                    const radiusKm = f.properties.radius_meters / 1000;
                    const circle = turf.circle([lon, lat], radiusKm, { steps: 64, units: 'kilometers' });
                    circle.properties = { ...f.properties };
                    return circle;
                });
                setZonePolygons(polygons);
            })
            .catch(e => console.error('[Zones] Failed to fetch zones:', e));
    }, [user]); // Re-run when user logs in

    return { zones, zonePolygons };
}
