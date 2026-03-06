import { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import * as turf from '@turf/turf';

// Using Carto Dark Matter as our dark canvas, stripping out extra labels where possible
const MAP_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-nolabels-gl-style/style.json';
const TRAIL_LENGTH = 30; // Longer trail to really show off the gradient

// Opacity levels for zone pulse animation (active vs inactive)
const ZONE_OPACITY_INACTIVE = 0.05;
const ZONE_OPACITY_ACTIVE = 0.25;

// Module-level color fn
function stringToColorStatic(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) hash = str.charCodeAt(i) + ((hash << 5) - hash);
    const c = (hash & 0x00FFFFFF).toString(16).toUpperCase();
    return '#' + '00000'.substring(0, 6 - c.length) + c;
}

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
    const multiMarkersRef = useRef({});
    const trailRef = useRef([]);
    const animationRef = useRef({}); // map of animation frames by deviceId
    const currentPosRef = useRef({});
    const mapReadyRef = useRef(false);
    const tiltRef = useRef(false);
    const [mapReady, setMapReady] = useState(false);
    const liveDevicesRef = useRef(liveDevices);

    useEffect(() => { liveDevicesRef.current = liveDevices; }, [liveDevices]);

    // ── Initialize Map once ───────────────────────────────────────────────
    useEffect(() => {
        if (mapRef.current) return;

        const map = new maplibregl.Map({
            container: mapContainer.current,
            style: MAP_STYLE,
            center: [-87.6230, 41.8827],
            zoom: 14,
            pitch: 50,
            bearing: -15, // slight angle for depth
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
                    'fill-outline-color': 'transparent'
                }
            }, 'watername_ocean'); // Add below labels ideally
            // Zone border ring (dashed for calm containment)
            map.addLayer({
                id: 'zones-border',
                type: 'line',
                source: 'zones-source',
                paint: {
                    'line-color': ['get', 'color'],
                    'line-width': 2,
                    'line-opacity': 0.6,
                    'line-dasharray': [2, 4]
                }
            });

            // ── Breadcrumb trail (live mode) ─────────────────────────────────
            map.addSource('trail-source', {
                type: 'geojson',
                lineMetrics: true, // Critical for line-gradient
                data: { type: 'Feature', geometry: { type: 'LineString', coordinates: [] } }
            });

            map.addLayer({
                id: 'trail-layer',
                type: 'line',
                source: 'trail-source',
                layout: { 'line-join': 'round', 'line-cap': 'round' },
                paint: {
                    'line-width': 4,
                    'line-gradient': [
                        'interpolate',
                        ['linear'],
                        ['line-progress'],
                        0, 'rgba(0, 230, 184, 0.0)', // Transparent start
                        0.5, 'rgba(0, 230, 184, 0.5)',
                        1, 'rgba(0, 230, 184, 1.0)'  // Solid active color
                    ]
                }
            });

            // ── Full-day history route ───────────────────────────────────────
            map.addSource('history-route-source', {
                type: 'geojson',
                lineMetrics: true,
                data: { type: 'FeatureCollection', features: [] }
            });

            map.addLayer({
                id: 'history-route-layer',
                type: 'line',
                source: 'history-route-source',
                layout: { 'line-join': 'round', 'line-cap': 'round' },
                paint: {
                    'line-color': 'rgba(255, 255, 255, 0.8)',
                    'line-width': 3,
                    'line-opacity': 0.8
                }
            });

            mapReadyRef.current = true;
            setMapReady(true);

            // Fast-sync devices that arrived early
            Object.entries(liveDevicesRef.current).forEach(([id, deviceState]) => {
                const loc = deviceState.lastLocation;
                if (!loc || !loc.lat || !loc.lon) return;
                const pos = [loc.lon, loc.lat];
                if (!multiMarkersRef.current[id]) {
                    const el = createMarkerElement(id, deviceState.status, false);
                    multiMarkersRef.current[id] = new maplibregl.Marker({ element: el }).setLngLat(pos).addTo(map);
                    currentPosRef.current[id] = pos;
                }
            });

            if (onMapReady) onMapReady(map);
        });

        return () => {
            Object.values(animationRef.current).forEach(cancelAnimationFrame);
            map.remove();
            mapRef.current = null;
            mapReadyRef.current = false;
        };
    }, []);

    // ── Fly to selected device ───────────────────────────────────────────
    useEffect(() => {
        if (!mapReadyRef.current || !mapRef.current || !activeDeviceId) return;
        const deviceState = liveDevices[activeDeviceId];
        const loc = deviceState?.lastLocation;
        if (loc?.lat && loc?.lon) {
            mapRef.current.flyTo({
                center: [loc.lon, loc.lat],
                zoom: 16,
                duration: 1200,
                essential: true,
                easing: (t) => t * (2 - t) // Ease-out curve
            });
        }
    }, [activeDeviceId]);

    // ── Update zone polygons ─────────────────────────────────────────────
    useEffect(() => {
        if (!mapReadyRef.current || !mapRef.current) return;
        const src = mapRef.current.getSource('zones-source');
        if (src) src.setData({ type: 'FeatureCollection', features: zonePolygons });
    }, [zonePolygons]);

    // ── Pulse active zones ───────────────────────────────────────────────
    useEffect(() => {
        if (!mapReadyRef.current || !mapRef.current) return;
        const map = mapRef.current;
        if (!map.getLayer('zones-fill')) return;

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

        // Slightly bold the border of active zones
        map.setPaintProperty('zones-border', 'line-width', [
            'case', ['==', ['get', '_active'], 1], 3, 1
        ]);
    }, [activeZoneIds, zonePolygons]);

    // ── History route layer ──────────────────────────────────────────────
    useEffect(() => {
        if (!mapReadyRef.current || !mapRef.current) return;
        const src = mapRef.current.getSource('history-route-source');
        if (src) src.setData({ type: 'FeatureCollection', features: historyFeatures });

        if (historyFeatures.length > 0) {
            const allCoords = historyFeatures.flatMap(f => f.geometry?.coordinates || []);
            if (allCoords.length > 1) {
                const lons = allCoords.map(c => c[0]), lats = allCoords.map(c => c[1]);
                mapRef.current.fitBounds(
                    [[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]],
                    { padding: 120, duration: 1200, easing: (t) => t * (2 - t) }
                );
            }
        }
    }, [historyFeatures]);

    // Helper to generate marker DOM element based on status
    function createMarkerElement(id, status, isActiveTarget) {
        const el = document.createElement('div');
        el.className = `child-marker status-${status || 'STALE'} ${isActiveTarget ? 'active-target' : ''}`;

        const color = isActiveTarget ? 'var(--color-signal-active)' : stringToColorStatic(id);
        el.style.setProperty('--marker-color', color);

        const inner = document.createElement('div');
        inner.className = 'marker-inner';
        el.appendChild(inner);

        if (status !== 'OFFLINE') {
            const pulse = document.createElement('div');
            pulse.className = 'marker-pulse';
            el.appendChild(pulse);
        }

        return el;
    }

    // ── Location updates (live animation OR history snap) ────────────────
    useEffect(() => {
        if (!isHistory || !targetLocation || !mapReadyRef.current) return;
        const newTarget = [targetLocation.lon, targetLocation.lat];

        if (!multiMarkersRef.current['__history']) {
            const el = createMarkerElement('history', 'ONLINE', true);
            el.style.setProperty('--marker-color', 'var(--color-text-primary)');
            multiMarkersRef.current['__history'] = new maplibregl.Marker({ element: el }).setLngLat(newTarget).addTo(mapRef.current);
        } else {
            multiMarkersRef.current['__history'].setLngLat(newTarget);
        }
        currentPosRef.current['__history'] = newTarget;
    }, [targetLocation, isHistory]);

    // Handle live multi-device locations
    useEffect(() => {
        if (isHistory || !mapReadyRef.current) {
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

        if (multiMarkersRef.current['__history']) {
            multiMarkersRef.current['__history'].remove();
            delete multiMarkersRef.current['__history'];
        }

        Object.entries(liveDevices).forEach(([id, deviceState]) => {
            const loc = deviceState.lastLocation;
            if (!loc) return;
            const pos = [loc.lon, loc.lat];
            const isActive = id === activeDeviceId;
            const status = deviceState.status;

            if (!multiMarkersRef.current[id]) {
                const el = createMarkerElement(id, status, isActive);
                multiMarkersRef.current[id] = new maplibregl.Marker({ element: el }).setLngLat(pos).addTo(mapRef.current);
                currentPosRef.current[id] = pos;
            } else {
                const marker = multiMarkersRef.current[id];
                const el = marker.getElement();

                // Update class list for status
                el.className = `child-marker status-${status || 'STALE'} ${isActive ? 'active-target' : ''}`;
                const color = isActive ? 'var(--color-signal-active)' : stringToColorStatic(id);
                el.style.setProperty('--marker-color', color);

                // Re-render inner DOM if pulse needs to change 
                el.innerHTML = '';
                const inner = document.createElement('div');
                inner.className = 'marker-inner';
                el.appendChild(inner);

                if (status !== 'OFFLINE') {
                    const pulse = document.createElement('div');
                    pulse.className = 'marker-pulse';
                    el.appendChild(pulse);
                }

                if (isActive) animateActiveMarker(id, marker, pos);
                else {
                    marker.setLngLat(pos);
                    currentPosRef.current[id] = pos;
                }
            }
        });

        // Cleanup disconnected devices
        Object.keys(multiMarkersRef.current).forEach(id => {
            if (id !== '__history' && !liveDevices[id]) {
                if (animationRef.current[id]) cancelAnimationFrame(animationRef.current[id]);
                multiMarkersRef.current[id].remove();
                delete multiMarkersRef.current[id];
                delete currentPosRef.current[id];
            }
        });

    }, [liveDevices, activeDeviceId, isHistory, mapReady]);

    function animateActiveMarker(id, marker, newTarget) {
        if (!currentPosRef.current[id]) {
            currentPosRef.current[id] = newTarget;
            marker.setLngLat(newTarget);
            trailRef.current = [newTarget];
            return;
        }

        const startP = turf.point(currentPosRef.current[id]);
        const endP = turf.point(newTarget);
        const dist = turf.distance(startP, endP);

        // Don't interpolate if movement is negligible to save CPU
        if (dist < 0.001) {
            currentPosRef.current[id] = newTarget;
            marker.setLngLat(newTarget);
            return;
        }

        trailRef.current.push(newTarget);
        if (trailRef.current.length > TRAIL_LENGTH) trailRef.current.shift();

        // We only draw trail if we have more than 1 point to avoid line-gradient error on single point
        if (trailRef.current.length > 1) {
            const trailSrc = mapRef.current.getSource('trail-source');
            if (trailSrc) {
                trailSrc.setData({
                    type: 'Feature',
                    geometry: { type: 'LineString', coordinates: trailRef.current }
                });
            }
        }

        const bearing = turf.bearing(startP, endP);
        const duration = 1500; // Slower, smoother interpolation 1.5s
        const startTime = performance.now();

        if (animationRef.current[id]) cancelAnimationFrame(animationRef.current[id]);

        function animate(time) {
            const progress = Math.min((time - startTime) / duration, 1);
            // using easeOut effect
            const easeProgress = progress * (2 - progress);
            const pos = turf.destination(startP, dist * easeProgress, bearing).geometry.coordinates;

            marker.setLngLat(pos);
            currentPosRef.current[id] = pos;

            // Pan nicely to track
            if (mapRef.current.isMoving()) {
                // If user is panning manually, don't battle them
            } else {
                mapRef.current.panTo(pos, { duration: 0 });
            }

            if (progress < 1) {
                animationRef.current[id] = requestAnimationFrame(animate);
            }
        }

        animationRef.current[id] = requestAnimationFrame(animate);
    }

    // ── Expose tilt control ──────────────────────────────────────────────
    function handleTilt() {
        if (!mapRef.current) return;
        tiltRef.current = !tiltRef.current;
        mapRef.current.easeTo({ pitch: tiltRef.current ? 65 : 10, duration: 800 });
    }

    return (
        <div style={{ width: '100vw', height: '100vh', position: 'absolute', inset: 0, overflow: 'hidden' }}>
            <div ref={mapContainer} style={{ width: '100%', height: '100%' }} />

            <div className="map-controls">
                <button className="map-control-btn" title="Zoom In" onClick={() => mapRef.current?.zoomIn()}>＋</button>
                <button className="map-control-btn" title="Zoom Out" onClick={() => mapRef.current?.zoomOut()}>－</button>
                <div className="map-control-divider" />
                <button className="map-control-btn" title="Reset North" onClick={() => mapRef.current?.resetNorth({ duration: 800 })}>⊕</button>
                <button className="map-control-btn" title="Toggle 3D Tilt" onClick={handleTilt}>◈</button>
            </div>
        </div>
    );
}
