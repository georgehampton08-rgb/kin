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
    onMapReady,
}) {
    const mapContainer = useRef(null);
    const mapRef = useRef(null);
    const markerRef = useRef(null);
    const trailRef = useRef([]);
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

            // ── Child Marker ─────────────────────────────────────────────────
            const el = document.createElement('div');
            el.className = 'child-marker';
            const dot = document.createElement('div'); dot.className = 'marker-dot'; el.appendChild(dot);
            const pulse = document.createElement('div'); pulse.className = 'marker-pulse'; el.appendChild(pulse);
            const pulseSlow = document.createElement('div'); pulseSlow.className = 'marker-pulse-slow'; el.appendChild(pulseSlow);

            markerRef.current = new maplibregl.Marker({ element: el })
                .setLngLat([-87.6230, 41.8827])
                .addTo(map);

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

    // ── Location updates (live animation OR history snap) ────────────────
    useEffect(() => {
        if (!targetLocation || !mapReadyRef.current || !markerRef.current) return;
        const newTarget = [targetLocation.lon, targetLocation.lat];

        if (isHistory) {
            markerRef.current.setLngLat(newTarget);
            currentPosRef.current = newTarget;
            return;
        }

        if (!currentPosRef.current) {
            currentPosRef.current = newTarget;
            markerRef.current.setLngLat(newTarget);
            mapRef.current.flyTo({ center: newTarget, zoom: 16, duration: 800 });
            trailRef.current = [newTarget];
            return;
        }

        trailRef.current.push(newTarget);
        if (trailRef.current.length > TRAIL_LENGTH) trailRef.current.shift();
        const trailSrc = mapRef.current.getSource('trail-source');
        if (trailSrc) trailSrc.setData({ type: 'Feature', geometry: { type: 'LineString', coordinates: trailRef.current } });

        const startP = turf.point(currentPosRef.current);
        const endP = turf.point(newTarget);
        const dist = turf.distance(startP, endP);
        const bearing = turf.bearing(startP, endP);
        if (dist < 0.001) { currentPosRef.current = newTarget; markerRef.current.setLngLat(newTarget); return; }

        const duration = 800;
        const startTime = performance.now();
        function animate(time) {
            const progress = Math.min((time - startTime) / duration, 1);
            const pos = turf.destination(startP, dist * progress, bearing).geometry.coordinates;
            markerRef.current.setLngLat(pos);
            currentPosRef.current = pos;
            mapRef.current.panTo(pos, { duration: 0 });
            if (progress < 1) animationRef.current = requestAnimationFrame(animate);
        }
        cancelAnimationFrame(animationRef.current);
        animationRef.current = requestAnimationFrame(animate);
    }, [targetLocation, isHistory]);

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
