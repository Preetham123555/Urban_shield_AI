"use client";

import { useState, useMemo } from 'react';
import dynamic from 'next/dynamic';
import { motion, AnimatePresence } from "framer-motion";
import { Globe } from "lucide-react";
import { apiClient } from '@/services/apiClient';
import { translationService, SupportedLanguage } from '@/services/translationService';

import Header from '@/components/ui/Header';
import RiskPanel from '@/components/ui/RiskPanel';
import RiskAlert from '@/components/ui/RiskAlert';
import LocationSearch from '@/components/map/LocationSearch';

// SSR-Safe dynamic import for the Map
const UrbanMap = dynamic(() => import('@/components/map/UrbanMap'), {
    ssr: false,
    loading: () => <div className="w-full h-full min-h-[500px] bg-slate-100 animate-pulse flex items-center justify-center text-[10px] font-black uppercase tracking-widest text-slate-400">Loading Geospatial Engine...</div>
});

export default function Home() {
    const [isLaunched, setIsLaunched] = useState(false);
    const [loading, setLoading] = useState(false);
    const [language, setLanguage] = useState<SupportedLanguage>('en');

    // Default to India center coordinates
    const [selectedCity, setSelectedCity] = useState("India (National Core)");
    const [selectedCoords, setSelectedCoords] = useState<[number, number]>([20.5937, 78.9629]);

    const [metrics, setMetrics] = useState<any>(null);
    const [error, setError] = useState<string | null>(null);

    const t = useMemo(() => translationService.getTranslations(language), [language]);

    const CITY_COORDS: Record<string, [number, number]> = {
        "Bengaluru": [12.9716, 77.5946],
        "Delhi": [28.6139, 77.2090],
        "Mumbai": [19.0760, 72.8777],
        "Chennai": [13.0827, 80.2707],
        "Hyderabad": [17.3850, 78.4867],
        "India": [20.5937, 78.9629]
    };

    const fetchMetrics = async (city: string, lat?: number, lng?: number) => {
        setLoading(true);
        setError(null);
        try {
            const latitude = lat ?? selectedCoords[0];
            const longitude = lng ?? selectedCoords[1];

            const payload = {
                city,
                lat: latitude,
                lng: longitude
            };

            const res = await apiClient.fetch<any>("/api/stress-test", {
                method: "POST",
                body: JSON.stringify(payload)
            });

            if (res.success && res.data) {
                setMetrics(res.data);
            } else {
                throw new Error(res.error || "API returned an error");
            }
        } catch (err: any) {
            console.error("Prediction failed", err);
            setError(err.message || "SYSTEM ERROR: Backend API failed.");
        } finally {
            setLoading(false);
        }
    };

    const executeStressTest = async () => {
        fetchMetrics(selectedCity, selectedCoords[0], selectedCoords[1]);
    };

    const handleCityChange = (city: string) => {
        setSelectedCity(city);
        const coords = CITY_COORDS[city] || [20.5937, 78.9629];
        setSelectedCoords(coords);
    };

    const handleMapClick = (lat: number, lng: number) => {
        setSelectedCoords([lat, lng]);
        setSelectedCity(`Point: ${lat.toFixed(4)}, ${lng.toFixed(4)}`);
        fetchMetrics("Custom Point", lat, lng);
    };

    const handleLocationSelect = (lat: number, lng: number, displayName: string) => {
        const parts = displayName.split(",");
        const derivedCity = parts.length > 0 ? parts[0].trim() : selectedCity;
        setSelectedCity(derivedCity);
        setSelectedCoords([lat, lng]);
        fetchMetrics(derivedCity, lat, lng);
    };

    return (
        <main className="min-h-screen bg-[var(--color-bg)] flex flex-col font-sans">
            <AnimatePresence mode="wait">
                {!isLaunched ? (
                    <motion.div
                        key="entry"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0, scale: 1.02 }}
                        className="flex-1 flex flex-col items-center justify-center p-8 text-center"
                    >
                        <div className="civic-card max-w-2xl p-12 border-2 border-[var(--color-navy)] flex flex-col items-center gap-8 shadow-[12px_12px_0px_var(--color-navy)]">
                            <div className="flex flex-col items-center">
                                <h1 className="text-6xl font-black m-0 leading-[0.85] text-[var(--color-navy)] tracking-tighter uppercase">
                                    URBAN<br /><span className="text-[var(--color-accent)]">SHIELD</span>
                                </h1>
                            </div>
                            <button
                                onClick={() => setIsLaunched(true)}
                                className="civic-button px-16 py-5 text-lg"
                            >
                                INITIALIZE CONSOLE
                            </button>
                        </div>
                    </motion.div>
                ) : (
                    <motion.div
                        key="console"
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="flex flex-col flex-1"
                    >
                        <div className="page-wrapper relative">
                            <div className="w-full bg-[var(--color-navy)] text-white text-[10px] font-black tracking-widest uppercase p-1 flex justify-between items-center px-4">
                                <span className={!error && metrics ? "text-green-400" : "text-slate-400"}>
                                    ● {t.ui_telemetry} ACTIVE
                                </span>
                                <div className="flex items-center gap-4">
                                    <Globe className="w-3 h-3 text-[var(--color-accent)]" />
                                    <select
                                        value={language}
                                        onChange={(e) => setLanguage(e.target.value as SupportedLanguage)}
                                        className="bg-transparent border-none text-white focus:outline-none cursor-pointer hover:text-[var(--color-accent)] transition-colors"
                                    >
                                        <option value="en" className="bg-slate-900">ENGLISH</option>
                                        <option value="hi" className="bg-slate-900">हिन्दी (HINDI)</option>
                                        <option value="bn" className="bg-slate-900">বাংলা (BENGALI)</option>
                                        <option value="ta" className="bg-slate-900">தமிழ் (TAMIL)</option>
                                        <option value="mr" className="bg-slate-900">मराठी (MARATHI)</option>
                                    </select>
                                </div>
                            </div>

                            <Header
                                selectedCity={selectedCity}
                                onCityChange={handleCityChange}
                                overallRisk={metrics?.compound_risk_index || 0}
                            />

                            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 p-8 flex-1">
                                <div className="lg:col-span-3">
                                    <button
                                        onClick={executeStressTest}
                                        disabled={loading}
                                        className="w-full bg-amber-500 text-white font-black py-4 uppercase mb-4 shadow-[4px_4px_0px_#b45309] hover:translate-x-1 hover:translate-y-1 hover:shadow-none transition-all disabled:opacity-50 flex items-center justify-center"
                                    >
                                        {loading ? "INITIALIZING SIMULATION..." : t.ui_execute}
                                    </button>

                                    {loading && (
                                        <div className="text-[10px] uppercase font-black tracking-widest text-[var(--color-navy)] animate-pulse flex items-center gap-2 mb-4">
                                            <div className="w-2 h-2 bg-[var(--color-accent)] rounded-full animate-bounce"></div>
                                            Downloading Telemetry & Modeling Prediction...
                                        </div>
                                    )}

                                   {metrics && (
    <div className="bg-white/50 border border-[var(--color-navy)]/10 p-4 flex flex-col gap-2">
        <span className="text-[9px] font-black uppercase text-slate-500">Zone</span>
        <span className="text-sm font-black text-[var(--color-navy)]">
            {metrics.zone?.name ?? "No zone data"}
        </span>
        {metrics.zone && (
            <>
                <div className="flex justify-between text-xs font-bold">
                    <span>Score: {metrics.zone.score}/100</span>
                    <span>{metrics.zone.level}</span>
                </div>
                <div className="text-[10px] text-slate-500">
                    Drain load: {metrics.zone.drain_load_pct}% · Rain used: {metrics.zone.rainfall_mm_used} mm
                </div>
            </>
        )}
        <div className="text-[9px] text-slate-400 uppercase">
            Prototype estimate, not measured data
        </div>
    </div>
)}
                                </div>

                                <div className="lg:col-span-6 flex flex-col gap-4">
                                    <LocationSearch onSelectLocation={handleLocationSelect} />

                                    <div className="flex justify-between items-center bg-white/40 p-2 border border-[var(--color-navy)]/5 rounded-sm">
                                        <span className="text-[10px] font-black uppercase text-[var(--color-navy)] tracking-widest">
                                            Spatial Threat Mapping | India Core
                                        </span>
                                    </div>

                                    <div className="flex-1 min-h-[500px] relative border-2 border-[var(--color-navy)]">
                                        <UrbanMap
                                            center={selectedCoords}
                                            riskLevel={metrics?.compound_risk_index || 0}
                                            onMapClick={handleMapClick}
                                        />

                                        {error && (
                                            <div className="absolute inset-0 z-[1000] flex items-center justify-center bg-red-500/10 backdrop-blur-sm pointer-events-none">
                                                <div className="text-center p-6 bg-white border-2 border-red-500 pointer-events-auto">
                                                    <h3 className="text-red-600 font-black uppercase tracking-widest mb-2 flex items-center gap-2 justify-center">
                                                        Connection Error
                                                    </h3>
                                                    <p className="text-xs font-bold text-slate-800 uppercase tracking-wide">{error}</p>
                                                </div>
                                            </div>
                                        )}
                                    </div>

                                    {metrics && (
                                        <RiskAlert
                                            score={metrics.compound_risk_index}
                                            language={language}
                                        />
                                    )}
                                </div>

                                <div className="lg:col-span-3 flex flex-col gap-6">
                                    {metrics ? (
                                        <RiskPanel data={{
                                            flood_risk_index: metrics.flood_risk_index,
                                            heat_risk_index: metrics.heat_risk_index,
                                            compound_risk_index: metrics.compound_risk_index,
                                        }} />
                                    ) : (
                                        <div className="text-center font-bold text-slate-400 uppercase tracking-widest text-[10px] p-12 border-2 border-dashed border-slate-200">
                                            Run Stress Test to View Urban Telemetry
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </main>
    );
}
