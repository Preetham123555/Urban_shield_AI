"use client";

import { useEffect, useRef, useState } from "react";
import "leaflet/dist/leaflet.css";

interface UrbanMapProps {
    center: [number, number];
    riskLevel: number; // 0 to 100
    onMapClick: (lat: number, lng: number) => void;
}

export default function UrbanMap({ center, riskLevel, onMapClick }: UrbanMapProps) {
    const mapRef = useRef<HTMLDivElement>(null);
    const mapInstance = useRef<any>(null);
    const markerRef = useRef<any>(null);
    const circleRef = useRef<any>(null);
    const LRef = useRef<any>(null);
    const [time, setTime] = useState("");
    const [isMounted, setIsMounted] = useState(false);

    // Initial safe mount check for SSR
    useEffect(() => {
        setIsMounted(true);
    }, []);

    // Setup live timestamp
    useEffect(() => {
        if (!isMounted) return;
        const updateTimer = () => setTime(new Date().toLocaleTimeString('en-US', { hour12: false }));
        updateTimer();
        const interval = setInterval(updateTimer, 1000);
        return () => clearInterval(interval);
    }, [isMounted]);

    const getRiskColor = (risk: number) => {
        if (risk > 70) return "red";
        if (risk > 40) return "orange";
        return "green";
    };

    // Initialize map purely on client
    useEffect(() => {
        if (typeof window === "undefined" || !mapRef.current || !isMounted) return;

        let active = true;

        if (!mapInstance.current) {
            import("leaflet").then((L) => {
                if (!active) return;
                const LObj = L.default || L;
                LRef.current = LObj;

                // Fix for default marker icons missing in webpack/nextjs
                const DefaultIcon = LObj.icon({
                    iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
                    iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
                    shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
                    iconSize: [25, 41],
                    iconAnchor: [12, 41],
                    popupAnchor: [1, -34],
                    tooltipAnchor: [16, -28],
                    shadowSize: [41, 41]
                });
                LObj.Marker.prototype.options.icon = DefaultIcon;

                // Initialize map centered on the provided center (India default if passed from parent)
                const map = LObj.map(mapRef.current!).setView(center, 5);
                mapInstance.current = map;

              LObj.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 19
}).addTo(map);

                // Initialize size correctly
                setTimeout(() => { map.invalidateSize(); }, 200);

                // Add click listener
                map.on('click', (e: any) => {
                    const { lat, lng } = e.latlng;
                    onMapClick(lat, lng);
                });

                // Initial marker
                markerRef.current = LObj.marker(center).addTo(map);

                if (riskLevel > 0) {
                    circleRef.current = LObj.circle(center, {
                        radius: 5000 + (riskLevel * 100), // Larger radius for India-scale view
                        color: getRiskColor(riskLevel),
                        fillColor: getRiskColor(riskLevel),
                        fillOpacity: 0.3,
                        weight: 2
                    }).addTo(map);
                }
            });
        }

        return () => {
            active = false;
        };
    }, [isMounted]);

    // Separate cleanup effect
    useEffect(() => {
        return () => {
            if (mapInstance.current) {
                mapInstance.current.off();
                mapInstance.current.remove();
                mapInstance.current = null;
            }
        };
    }, []);

    // Handle updates to center and riskLevel
    useEffect(() => {
        if (!mapInstance.current || !LRef.current) return;

        const LObj = LRef.current;
        const map = mapInstance.current;

        // Use flyTo for smoother transition when searching/clicking
        map.flyTo(center, map.getZoom() < 10 ? 12 : map.getZoom(), {
            duration: 1.5
        });

        // Update Marker
        if (markerRef.current) {
            markerRef.current.setLatLng(center);
        } else {
            markerRef.current = LObj.marker(center).addTo(map);
        }

        // Update Circle
        if (riskLevel > 0) {
            if (circleRef.current) {
                circleRef.current.setLatLng(center);
                circleRef.current.setRadius(5000 + (riskLevel * 100));
                circleRef.current.setStyle({
                    color: getRiskColor(riskLevel),
                    fillColor: getRiskColor(riskLevel)
                });
            } else {
                circleRef.current = LObj.circle(center, {
                    radius: 5000 + (riskLevel * 100),
                    color: getRiskColor(riskLevel),
                    fillColor: getRiskColor(riskLevel),
                    fillOpacity: 0.3,
                    weight: 2
                }).addTo(map);
            }
        } else if (circleRef.current) {
            circleRef.current.remove();
            circleRef.current = null;
        }

    }, [center, riskLevel]);

    if (!isMounted) return <div className="w-full h-full min-h-[500px] bg-slate-100 animate-pulse" />;

    return (
        <div className="w-full h-full min-h-[500px] relative z-0">
            <div ref={mapRef} className="w-full h-full min-h-[500px] z-0" />

            {/* Live Telemetry Timestamp */}
            <div className="absolute top-4 left-4 z-[400] bg-white/90 border-2 border-[var(--color-navy)] px-3 py-1 text-[10px] font-black uppercase tracking-widest text-[var(--color-navy)] shadow-[4px_4px_0px_rgba(0,0,0,0.1)]">
                <span className="animate-pulse text-red-600 mr-2">● Live</span>
                {time || "SYNCING..."}
            </div>

            {/* Risk Gradient Legend */}
            <div className="absolute bottom-6 right-4 z-[400] bg-white/90 border-2 border-[var(--color-navy)] p-3 text-[9px] font-black uppercase tracking-widest text-[var(--color-navy)] shadow-[6px_6px_0px_rgba(0,0,0,0.1)]">
                <div className="mb-2 border-b border-[var(--color-navy)]/20 pb-1">Impact Radius</div>
                <div className="flex flex-col gap-1.5">
                    <div className="flex items-center gap-2"><div className="w-3 h-3 bg-red-500 rounded-full border border-black/20"></div> Critical</div>
                    <div className="flex items-center gap-2"><div className="w-3 h-3 bg-orange-500 rounded-full border border-black/20"></div> Elevated</div>
                    <div className="flex items-center gap-2"><div className="w-3 h-3 bg-green-500 rounded-full border border-black/20"></div> Stable</div>
                </div>
            </div>
        </div>
    );
}
