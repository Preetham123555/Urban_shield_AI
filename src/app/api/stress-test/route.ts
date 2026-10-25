import { NextResponse } from "next/server";
import { logger } from "@/utils/logger";
import { ApiResponse } from "@/types";
import { weatherService } from "@/services/weatherService";
import { calculateRiskMetrics } from "@/engines/predictionEngine";

export async function POST(req: Request): Promise<NextResponse<ApiResponse>> {
    try {
        const text = await req.text();
        if (!text) {
            return NextResponse.json({
                success: false,
                error: "Empty request body",
                code: "VALIDATION_ERROR"
            }, { status: 400 });
        }

        const body = JSON.parse(text);

        // Request Validation
        if (body.lat !== undefined && typeof body.lat !== 'number') {
            return NextResponse.json({ success: false, error: "Invalid latitude", code: "VALIDATION_ERROR" }, { status: 400 });
        }
        const lonValid = typeof body.lng === 'number' || typeof body.lon === 'number' || (body.lng === undefined && body.lon === undefined);
        if (!lonValid) {
            return NextResponse.json({ success: false, error: "Invalid longitude", code: "VALIDATION_ERROR" }, { status: 400 });
        }

        let cityStr = body.city || "Bengaluru";
        const lat = body.lat;
        const lon = body.lng || body.lon;

        logger.info(`Processing stress-test for ${cityStr} (${lat}, ${lon})`);

        // Fetch real-time weather telemetry
        const weather = await weatherService.fetchWeather(Number(lat), Number(lon));

        // Forward to Python hybrid engine with real weather overrides
        const response = await fetch("http://127.0.0.1:8001/analyze-city", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                city: cityStr,
                overrides: {
                    ...(lat !== undefined && { lat: Number(lat) }),
                    ...(lon !== undefined && { lon: Number(lon) }),
                    ...(weather && {
                        temperature: weather.temperature,
                        humidity: weather.humidity,
                        rainfall: weather.rainfall,
                        windspeed: weather.windspeed
                    })
                }
            })
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Python Engine Error: ${response.status} ${errorText}`);
        }

        const data = await response.json();

        // Phase 4: Calculate standardized risk metrics for explainable categorization
        const riskMetrics = calculateRiskMetrics({
            rainfall: weather?.rainfall || 0,
            temperature: weather?.temperature || 28,
            humidity: weather?.humidity || 60,
            populationDensity: data?.urban_profile?.population_density || 0.5,
            drainageCapacity: data?.urban_profile?.drainage_efficiency || 0.5
        });

                   return NextResponse.json({
            success: true,
            data: { ...riskMetrics, ...data, zone: data?.zone ?? null },
            timestamp: new Date().toISOString(),
            source: "urban-intelligence-core"
        });
    } catch (error: any) {
        logger.error("API error in stress-test route", error.message);
        return NextResponse.json(
            { success: false, error: "Computation failed", code: "API_ERROR" },
            { status: 500 }
        );
    }
}
