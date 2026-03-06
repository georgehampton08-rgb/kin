import { useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import * as turf from '@turf/turf';

const MAP_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';
const TRAIL_LENGTH = 10;

// Opacity levels for zone pulse animation (active vs inactive)
const ZONE_OPACITY_INACTIVE = 0.15;
const ZONE_OPACITY_ACTIVE = 0.45;

export default function KinMap({
    targetLocation,
    historyFeatures = [],
    isHistory = false,
    zonePolygons = [],
    activeZoneIds = new Set(),
    liveDevices = {},
    activeDeviceId = null,
    onMapReady,
}) {
    const mapContainer = useRef(null);
    const mapRef = useRef(null);
    const multiMarkersRef = useRef({}); // Stores markers by deviceId
    const trailRef = useRef([]); // Only tracks active device trail
    const animationRef = useRef(null);
    const currentPosRef = useRef(null);
    const mapReadyRef = useRef(false);
    const tiltRef = useRef(false);

    // ── Initialize Map once ───────────────────────────────────────────────
    useEffect(() => {
        if (mapRef.current) return;

        const map = new maplibregl.Map({
            container: mapContainer.current,
            style: MAP_STYLE,
            center: [-87.6230, 41.8827],
            zoom: 14,
            pitch: 40,
            attributionControl: false,
        });

        mapRef.current = map;

        map.on('load', () => {
            // ── Zone circles source ──────────────────────────────────────────
            map.addSource('zones-source', {
                type: 'geojson',
                data: { type: 'FeatureCollection', features: [] }
            });
            // Semi-transparent fill
            map.addLayer({
                id: 'zones-fill',
                type: 'fill',
                source: 'zones-source',
                paint: {
                    'fill-color': ['get', 'color'],
                    'fill-opacity': ZONE_OPACITY_INACTIVE,
                }
            });
            // Zone border ring
            map.addLayer({
                id: 'zones-border',
                type: 'line',
                source: 'zones-source',
                paint: {
                    'line-color': ['get', 'color'],
                    'line-width': 1.5,
                    'line-opacity': 0.7,
                }
            });

            // ── Breadcrumb trail (live mode) ─────────────────────────────────
            map.addSource('trail-source', {
                type: 'geojson',
                data: { type: 'Feature', geometry: { type: 'LineString', coordinates: [] } }
            });
            map.addLayer({
                id: 'trail-layer',
                type: 'line',
                source: 'trail-source',
                layout: { 'line-join': 'round', 'line-cap': 'round' },
                paint: {
                    'line-color': '#00ffcc',
                    'line-width': 3,
                    'line-opacity': 0.45,
                    'line-dasharray': [0, 2]
                }
            });

            // ── Full-day history route ───────────────────────────────────────
            map.addSource('history-route-source', {
                type: 'geojson',
                data: { type: 'FeatureCollection', features: [] }
            });
            map.addLayer({
                id: 'history-route-glow',
                type: 'line',
                source: 'history-route-source',
                layout: { 'line-join': 'round', 'line-cap': 'round' },
                paint: { 'line-color': '#4488ff', 'line-width': 10, 'line-opacity': 0.2, 'line-blur': 6 }
            });
            map.addLayer({
                id: 'history-route-layer',
                type: 'line',
                source: 'history-route-source',
                layout: { 'line-join': 'round', 'line-cap': 'round' },
                paint: { 'line-color': '#5599ff', 'line-width': 3, 'line-opacity': 0.9 }
            });

            // Removed single child marker creation from here.
            // Markers will be created dynamically as devices report location.

            mapReadyRef.current = true;
            if (onMapReady) onMapReady(map);
        });

        return () => {
            cancelAnimationFrame(animationRef.current);
            map.remove();
            mapRef.current = null;
            mapReadyRef.current = false;
        };
    }, []);

    // ── Update zone polygons ─────────────────────────────────────────────
    useEffect(() => {
        if (!mapReadyRef.current || !mapRef.current) return;
        const src = mapRef.current.getSource('zones-source');
        if (!src) return;
        src.setData({ type: 'FeatureCollection', features: zonePolygons });
    }, [zonePolygons]);

    // ── Pulse active zones ───────────────────────────────────────────────
    useEffect(() => {
        if (!mapReadyRef.current || !mapRef.current) return;
        const map = mapRef.current;
        if (!map.getLayer('zones-fill')) return;
        // Use a data-driven expression that ups opacity for active zone ids
        // We encode this as extra properties in the feature
        const updatedFeatures = zonePolygons.map(f => ({
            ...f,
            properties: {
                ...f.properties,
                _active: activeZoneIds.has(f.properties.id) ? 1 : 0,
            }
        }));
        const src = map.getSource('zones-source');
        if (src) src.setData({ type: 'FeatureCollection', features: updatedFeatures });
        map.setPaintProperty('zones-fill', 'fill-opacity', [
            'case', ['==', ['get', '_active'], 1], ZONE_OPACITY_ACTIVE, ZONE_OPACITY_INACTIVE
        ]);
    }, [activeZoneIds, zonePolygons]);

    // ── History route layer ──────────────────────────────────────────────
    useEffect(() => {
        if (!mapReadyRef.current || !mapRef.current) return;
        const src = mapRef.current.getSource('history-route-source');
        if (!src) return;
        src.setData({ type: 'FeatureCollection', features: historyFeatures });

        if (historyFeatures.length > 0) {
            const allCoords = historyFeatures.flatMap(f => f.geometry?.coordinates || []);
            if (allCoords.length > 1) {
                const lons = allCoords.map(c => c[0]), lats = allCoords.map(c => c[1]);
                mapRef.current.fitBounds(
                    [[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]],
                    { padding: 80, duration: 800 }
                );
            }
        }
    }, [historyFeatures]);

    // Helper to get a consistent color from string
    const stringToColor = (str) => {
        let hash = 0;
        for (let i = 0; i < str.length; i++) hash = str.charCodeAt(i) + ((hash << 5) - hash);
        const c = (hash & 0x00FFFFFF).toString(16).toUpperCase();
        return '#' + '00000'.substring(0, 6 - c.length) + c;
    };

    // ── Location updates (live animation OR history snap) ────────────────
    // Handle history snap for targetLocation
    useEffect(() => {
        if (!isHistory || !targetLocation || !mapReadyRef.current) return;
        const newTarget = [targetLocation.lon, targetLocation.lat];

        // Hide multi markers in history mode, or just move the active one
        if (!multiMarkersRef.current['__history']) {
            const el = document.createElement('div');
            el.className = 'child-marker active-target';
            el.style.setProperty('--marker-color', '#fff');
            const dot = document.createElement('div'); dot.className = 'marker-dot'; el.appendChild(dot);
            multiMarkersRef.current['__history'] = new maplibregl.Marker({ element: el }).setLngLat(newTarget).addTo(mapRef.current);
        } else {
            multiMarkersRef.current['__history'].setLngLat(newTarget);
        }
        currentPosRef.current = newTarget;
    }, [targetLocation, isHistory]);

    // Handle live multi-device locations
    useEffect(() => {
        if (isHistory || !mapReadyRef.current) {
            // Cleanup markers if entering history
            if (isHistory) {
                Object.keys(multiMarkersRef.current).forEach(id => {
                    if (id !== '__history') {
                        multiMarkersRef.current[id].remove();
                        delete multiMarkersRef.current[id];
                    }
                });
            }
            return;
        }

        // Remove history marker if present
        if (multiMarkersRef.current['__history']) {
            multiMarkersRef.current['__history'].remove();
            delete multiMarkersRef.current['__history'];
        }

        // Sync markers
        Object.entries(liveDevices).forEach(([id, deviceState]) => {
            const loc = deviceState.lastLocation;
            if (!loc) return;
            const pos = [loc.lon, loc.lat];

            const isActive = id === activeDeviceId;

            if (!multiMarkersRef.current[id]) {
                const el = document.createElement('div');
                el.className = `child-marker ${isActive ? 'active-target' : 'bg-target'}`;

                const color = isActive ? '#00ffcc' : stringToColor(id);
                el.style.setProperty('--marker-color', color);

                const dot = document.createElement('div'); dot.className = 'marker-dot'; el.appendChild(dot);
                if (isActive) {
                    const pulse = document.createElement('div'); pulse.className = 'marker-pulse'; el.appendChild(pulse);
                    const pulseSlow = document.createElement('div'); pulseSlow.className = 'marker-pulse-slow'; el.appendChild(pulseSlow);
                }

                multiMarkersRef.current[id] = new maplibregl.Marker({ element: el })
                    .setLngLat(pos)
                    .addTo(mapRef.current);
            } else {
                const marker = multiMarkersRef.current[id];
                const el = marker.getElement();
                const color = isActive ? '#00ffcc' : stringToColor(id);
                el.style.setProperty('--marker-color', color);

                if (isActive) {
                    if (!el.classList.contains('active-target')) {
                        el.classList.remove('bg-target');
                        el.classList.add('active-target');
                        if (!el.querySelector('.marker-pulse')) {
                            const pulse = document.createElement('div'); pulse.className = 'marker-pulse'; el.appendChild(pulse);
                            const pulseSlow = document.createElement('div'); pulseSlow.className = 'marker-pulse-slow'; el.appendChild(pulseSlow);
                        }
                    }
                } else {
                    if (el.classList.contains('active-target')) {
                        el.classList.remove('active-target');
                        el.classList.add('bg-target');
                        el.querySelectorAll('.marker-pulse, .marker-pulse-slow').forEach(n => n.remove());
                    }
                }

                // If this is the active device, animate and pan
                if (isActive) {
                    animateActiveMarker(marker, pos);
                } else {
                    marker.setLngLat(pos);
                }
            }
        });

        // Cleanup disconnected devices
        Object.keys(multiMarkersRef.current).forEach(id => {
            if (id !== '__history' && !liveDevices[id]) {
                multiMarkersRef.current[id].remove();
                delete multiMarkersRef.current[id];
            }
        });

    }, [liveDevices, activeDeviceId, isHistory]);

    function animateActiveMarker(marker, newTarget) {
        if (!currentPosRef.current) {
            currentPosRef.current = newTarget;
            marker.setLngLat(newTarget);
            mapRef.current.flyTo({ center: newTarget, zoom: 16, duration: 800 });
            trailRef.current = [newTarget];
            return;
        }

        const startP = turf.point(currentPosRef.current);
        const endP = turf.point(newTarget);
        const dist = turf.distance(startP, endP);

        // Only trigger update if moved significantly
        if (dist < 0.001) {
            currentPosRef.current = newTarget;
            marker.setLngLat(newTarget);
            return;
        }

        trailRef.current.push(newTarget);
        if (trailRef.current.length > TRAIL_LENGTH) trailRef.current.shift();
        const trailSrc = mapRef.current.getSource('trail-source');
        if (trailSrc) trailSrc.setData({ type: 'Feature', geometry: { type: 'LineString', coordinates: trailRef.current } });

        const bearing = turf.bearing(startP, endP);
        const duration = 800;
        const startTime = performance.now();

        function animate(time) {
            const progress = Math.min((time - startTime) / duration, 1);
            const pos = turf.destination(startP, dist * progress, bearing).geometry.coordinates;
            marker.setLngLat(pos);
            currentPosRef.current = pos;
            mapRef.current.panTo(pos, { duration: 0 });
            if (progress < 1) animationRef.current = requestAnimationFrame(animate);
        }
        cancelAnimationFrame(animationRef.current);
        animationRef.current = requestAnimationFrame(animate);
    }



    // ── Expose tilt control via ref ──────────────────────────────────────
    function handleTilt() {
        if (!mapRef.current) return;
        tiltRef.current = !tiltRef.current;
        mapRef.current.easeTo({ pitch: tiltRef.current ? 55 : 0, duration: 400 });
    }

    return (
        <div style={{ width: '100%', height: '100%', position: 'absolute', inset: 0 }}>
            <div ref={mapContainer} style={{ width: '100%', height: '100%' }} />

            {/* Map Control Bar */}
            <div className="map-controls">
                <button className="map-control-btn" title="Zoom In" onClick={() => mapRef.current?.zoomIn()}>＋</button>
                <button className="map-control-btn" title="Zoom Out" onClick={() => mapRef.current?.zoomOut()}>－</button>
                <div className="map-control-divider" />
                <button className="map-control-btn" title="Reset North" onClick={() => mapRef.current?.resetNorth({ duration: 400 })}>⊕</button>
                <button className="map-control-btn" title="Toggle 3D Tilt" onClick={handleTilt}>◈</button>
            </div>
        </div>
    );
}
