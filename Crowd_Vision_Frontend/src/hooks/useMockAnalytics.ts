import { useState, useEffect, useCallback } from 'react';
import { CameraStats, ZoneStats, HeatmapData } from '@/types/camera';

const ZONE_NAMES = ['Zone A', 'Zone B', 'Zone C', 'Zone D'];

function randomBetween(min: number, max: number) {
  return Math.random() * (max - min) + min;
}

function getDensityLevel(density: number): 'LOW' | 'MODERATE' | 'HIGH' | 'VERY HIGH' {
  if (density < 0.3) return 'LOW';
  if (density < 0.5) return 'MODERATE';
  if (density < 0.7) return 'HIGH';
  return 'VERY HIGH';
}

function getRiskLevel(score: number): 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' {
  if (score < 25) return 'LOW';
  if (score < 50) return 'MEDIUM';
  if (score < 75) return 'HIGH';
  return 'CRITICAL';
}

function generateZoneStats(): ZoneStats[] {
  return ZONE_NAMES.map((name, idx) => {
    const peopleCount = Math.floor(randomBetween(10, 150));
    const density = randomBetween(0.1, 0.9);
    const motionIntensity = randomBetween(0.1, 0.8);
    const riskScore = density * 50 + motionIntensity * 30 + (peopleCount > 100 ? 20 : 0);
    
    return {
      id: `zone-${idx + 1}`,
      name,
      peopleCount,
      density,
      densityLevel: getDensityLevel(density),
      motionIntensity,
      riskLevel: getRiskLevel(riskScore),
      riskScore: Math.min(100, riskScore),
    };
  });
}

function generateHeatmapData(type: 'density' | 'motion' | 'risk', zones: ZoneStats[]): HeatmapData {
  const gridSize = 10;
  const data: number[][] = [];
  
  for (let i = 0; i < gridSize; i++) {
    const row: number[] = [];
    for (let j = 0; j < gridSize; j++) {
      row.push(randomBetween(0, 1));
    }
    data.push(row);
  }

  const zoneRects = zones.map((zone, idx) => ({
    id: zone.id,
    name: zone.name,
    x: (idx % 2) * 50,
    y: Math.floor(idx / 2) * 50,
    width: 45,
    height: 45,
    value: type === 'density' ? zone.density : type === 'motion' ? zone.motionIntensity : zone.riskScore / 100,
  }));

  return {
    type,
    data,
    maxValue: 1,
    zones: zoneRects,
  };
}

export function useMockAnalytics(cameraId: string | null) {
  const [stats, setStats] = useState<CameraStats | null>(null);
  const [heatmap, setHeatmap] = useState<HeatmapData | null>(null);
  const [heatmapType, setHeatmapType] = useState<'density' | 'motion' | 'risk'>('density');
  const [isLive, setIsLive] = useState(true);

  const generateStats = useCallback(() => {
    if (!cameraId) return null;

    const zones = generateZoneStats();
    const totalPeople = zones.reduce((sum, z) => sum + z.peopleCount, 0);
    const avgDensity = zones.reduce((sum, z) => sum + z.density, 0) / zones.length;
    const avgMotion = zones.reduce((sum, z) => sum + z.motionIntensity, 0) / zones.length;
    const maxRiskScore = Math.max(...zones.map((z) => z.riskScore));

    const newStats: CameraStats = {
      cameraId,
      timestamp: new Date(),
      peopleCount: totalPeople,
      density: avgDensity,
      densityLevel: getDensityLevel(avgDensity),
      motionIntensity: avgMotion,
      riskLevel: getRiskLevel(maxRiskScore),
      riskScore: maxRiskScore,
      fps: Math.floor(randomBetween(20, 30)),
      frameCount: Math.floor(randomBetween(1000, 50000)),
      zones,
    };

    return newStats;
  }, [cameraId]);

  // Update stats periodically when live
  useEffect(() => {
    if (!cameraId || !isLive) return;

    const updateStats = () => {
      const newStats = generateStats();
      if (newStats) {
        setStats(newStats);
        setHeatmap(generateHeatmapData(heatmapType, newStats.zones));
      }
    };

    updateStats();
    const interval = setInterval(updateStats, 2000);

    return () => clearInterval(interval);
  }, [cameraId, isLive, heatmapType, generateStats]);

  // Update heatmap when type changes
  useEffect(() => {
    if (stats) {
      setHeatmap(generateHeatmapData(heatmapType, stats.zones));
    }
  }, [heatmapType, stats]);

  return {
    stats,
    heatmap,
    heatmapType,
    setHeatmapType,
    isLive,
    setIsLive,
  };
}
