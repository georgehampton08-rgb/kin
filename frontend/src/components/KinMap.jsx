import { useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import * as turf from '@turf/turf';

const MAP_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';
const TRAIL_LENGTH = 10;

export default function KinMap({ targetLocation, historyFeatures = [], isHistory = false }) {
    const mapContainer = useRef(null);
    const mapRef = useRef(null);
    const markerRef = useRef(null);
    const trailRef = useRef([]);
    const animationRef = useRef(null);
    const currentPosRef = useRef(null);
    const mapReadyRef = useRef(false);

    // ── Initialize Map once ────────────────────────────────────────────────
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
            // ── Breadcrumb trail (live mode) ────
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

            // ── Full-day history route (history mode) ──────────
            map.addSource('history-route-source', {
                type: 'geojson',
                data: { type: 'FeatureCollection', features: [] }
            });
            // Glow background layer
            map.addLayer({
                id: 'history-route-glow',
                type: 'line',
                source: 'history-route-source',
                layout: { 'line-join': 'round', 'line-cap': 'round' },
                paint: {
                    'line-color': '#4488ff',
                    'line-width': 10,
                    'line-opacity': 0.25,
                    'line-blur': 6,
                }
            });
            // Main solid route line
            map.addLayer({
                id: 'history-route-layer',
                type: 'line',
                source: 'history-route-source',
                layout: { 'line-join': 'round', 'line-cap': 'round' },
                paint: {
                    'line-color': '#5599ff',
                    'line-width': 3,
                    'line-opacity': 0.9,
                }
            });

            // ── Custom Child Marker ─────────────────────────────
            const el = document.createElement('div');
            el.className = 'child-marker';
            const dot = document.createElement('div');
            dot.className = 'marker-dot';
            el.appendChild(dot);
            const pulse = document.createElement('div');
            pulse.className = 'marker-pulse';
            el.appendChild(pulse);

            markerRef.current = new maplibregl.Marker({ element: el })
                .setLngLat([-87.6230, 41.8827])
                .addTo(map);

            mapReadyRef.current = true;
        });

        return () => {
            cancelAnimationFrame(animationRef.current);
            map.remove();
            mapRef.current = null;
            mapReadyRef.current = false;
        };
    }, []);

    // ── Update history route layer when features change ────────────────────
    useEffect(() => {
        if (!mapReadyRef.current || !mapRef.current) return;
        const source = mapRef.current.getSource('history-route-source');
        if (!source) return;

        source.setData({ type: 'FeatureCollection', features: historyFeatures });

        // Fly to the extent of the history route
        if (historyFeatures.length > 0) {
            const allCoords = historyFeatures.flatMap(f => f.geometry?.coordinates || []);
            if (allCoords.length > 0) {
                const [minLon, minLat] = allCoords.reduce(
                    ([minX, minY], [x, y]) => [Math.min(minX, x), Math.min(minY, y)],
                    [Infinity, Infinity]
                );
                const [maxLon, maxLat] = allCoords.reduce(
                    ([maxX, maxY], [x, y]) => [Math.max(maxX, x), Math.max(maxY, y)],
                    [-Infinity, -Infinity]
                );
                mapRef.current.fitBounds(
                    [[minLon, minLat], [maxLon, maxLat]],
                    { padding: 80, duration: 800 }
                );
            }
        }
    }, [historyFeatures]);

    // ── Handle incoming location (live animation OR history scrub snap) ────
    useEffect(() => {
        if (!targetLocation || !mapReadyRef.current || !markerRef.current) return;

        const newTarget = [targetLocation.lon, targetLocation.lat];

        // History scrub: snap instantly, no animation
        if (isHistory) {
            markerRef.current.setLngLat(newTarget);
            currentPosRef.current = newTarget;
            return;
        }

        // ── Live mode: first point, teleport ─────────────────────────────────
        if (!currentPosRef.current) {
            currentPosRef.current = newTarget;
            markerRef.current.setLngLat(newTarget);
            mapRef.current.flyTo({ center: newTarget, zoom: 16, duration: 800 });
            trailRef.current = [newTarget];
            return;
        }

        // ── Live mode: breadcrumb trail update ────────────────────────────────
        trailRef.current.push(newTarget);
        if (trailRef.current.length > TRAIL_LENGTH) trailRef.current.shift();
        const trailSource = mapRef.current.getSource('trail-source');
        if (trailSource) {
            trailSource.setData({
                type: 'Feature',
                geometry: { type: 'LineString', coordinates: trailRef.current }
            });
        }

        // ── Live mode: smooth Turf.js animation ──────────────────────────────
        const startPoint = turf.point(currentPosRef.current);
        const endPoint = turf.point(newTarget);
        const distance = turf.distance(startPoint, endPoint);
        const bearing = turf.bearing(startPoint, endPoint);

        if (distance < 0.001) {
            currentPosRef.current = newTarget;
            markerRef.current.setLngLat(newTarget);
            return;
        }

        const duration = 800;
        const startTime = performance.now();

        function animateMarker(time) {
            const progress = Math.min((time - startTime) / duration, 1);
            const currentDistance = distance * progress;
            const intermediatePoint = turf.destination(startPoint, currentDistance, bearing);
            const newPos = intermediatePoint.geometry.coordinates;
            markerRef.current.setLngLat(newPos);
            currentPosRef.current = newPos;
            mapRef.current.panTo(newPos, { duration: 0 });
            if (progress < 1) animationRef.current = requestAnimationFrame(animateMarker);
        }

        cancelAnimationFrame(animationRef.current);
        animationRef.current = requestAnimationFrame(animateMarker);
    }, [targetLocation, isHistory]);

    return (
        <div
            ref={mapContainer}
            style={{ width: '100%', height: '100%', position: 'absolute', inset: 0 }}
        />
    );
}
