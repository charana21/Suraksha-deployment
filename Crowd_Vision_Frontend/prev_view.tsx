import { useEffect, useRef, useState } from 'react';
import { ZoneAnalytics, RiskLevel } from '@/types/zone';
import { cn } from '@/lib/utils';
import { Clock } from 'lucide-react';
import { getDensityLevel, getMotionLevel, getRiskLevel } from '@/lib/metrics';

interface FOBMapViewerProps {
  zones?: ZoneAnalytics[];
  selectedZoneId?: string | null;
  onZoneSelect?: (zoneId: string | null) => void;
  className?: string;
  title?: string;
  fullscreen?: boolean;
  variant?: 'default' | 'dashboard';
}

// Enhanced colors for dark theme visibility matching system CSS vars
const DARK_RISK_COLORS: Record<RiskLevel | 'UNKNOWN', string> = {
  LOW: '#22c55e', // Clear Green
  MEDIUM: '#f97316', // Clear Orange
  HIGH: '#ef4444', // Clear Red
  CRITICAL: '#ef4444', // Clear Red (High & Critical same)
  UNKNOWN: '#6b7280',
};

// Zone position mapping with precise grid coordinates (Left, Top, Width)
const ZONE_POSITIONS: Record<string, { left: string; top: string; width: string }> = {
  // --- HYB ZONES (Clean Alignment) ---

  // PF-1 Group (Left Side) - Aligned Far Left (10%)
  'zone_pf1_fob_kzj': { left: '10%', top: '10%', width: '13%' },
  'zone_pf1_hyb_fob_fc_pf10': { left: '10%', top: '36%', width: '13%' },
  'zone_pf1_fob_hyb_end': { left: '10%', top: '62%', width: '13%' },

  // Middle Group (Top Side) - High clearance (Top 2%)
  'zone_middle_fob_4_5': { left: '42.5%', top: '2%', width: '13%' },
  'zone_middle_fob_6_7': { left: '57.5%', top: '2%', width: '13%' },

  // PF-10 Group (Right Side) - Aligned Far Right (90%)
  'zone_pf10_hyb_fob_fc_pf1': { left: '90%', top: '36%', width: '13%' },
  'zone_pf10_fob_steps': { left: '90%', top: '62%', width: '13%' },

  // --- KZJ VIEW ---
  'zone_pf1_kzj_fob_fc_kzj': { left: '10%', top: '5%', width: '13%' },
  'zone_new_kzj_fob_middle_fc_pf10': { left: '10%', top: '36%', width: '13%' },
  'zone_pf1_kzj_fob_fc_hyb': { left: '10%', top: '67%', width: '13%' },

  'zone_kzj_fob_middle_fc_4_5': { left: '42.5%', top: '2%', width: '13%' },
  'zone_kzj_fob_middle_fc_8_9': { left: '57.5%', top: '2%', width: '13%' },

  'zone_kzj_fob_escalator_fc_pf1': { left: '90%', top: '38%', width: '13%' },
};

const ZONE_POSITIONS_DASHBOARD: Record<string, { left: string; top: string; width: string }> = {
  // --- HYB DASHBOARD (Standard Layout) ---
  // Clone of ZONE_POSITIONS for consistent 'Previous View'
  'zone_pf1_fob_kzj': { left: '10%', top: '10%', width: '13%' },
  'zone_pf1_hyb_fob_fc_pf10': { left: '10%', top: '36%', width: '13%' },
  'zone_pf1_fob_hyb_end': { left: '10%', top: '62%', width: '13%' },

  'zone_middle_fob_4_5': { left: '42.5%', top: '2%', width: '13%' },
  'zone_middle_fob_6_7': { left: '57.5%', top: '2%', width: '13%' },

  'zone_pf10_hyb_fob_fc_pf1': { left: '90%', top: '36%', width: '13%' },
  'zone_pf10_fob_steps': { left: '90%', top: '62%', width: '13%' },
};

// Helper to format lag time
function formatLag(ms: number): string {
  const seconds = Math.floor(ms / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ago`;
}

export function FOBMapViewer({ zones = [], selectedZoneId = null, onZoneSelect = () => { }, className, title, fullscreen = false, variant = 'default' }: FOBMapViewerProps) {
  const sectionRefs = useRef<(HTMLDivElement | null)[]>([]);

  // Restore SVG zone coloring logic
  useEffect(() => {
    sectionRefs.current.forEach((container) => {
      if (!container) return;
      zones.forEach((zone) => {
        const element = container.querySelector(`#${zone.svg_region_id}`);
        if (element) {
          const score = zone.risk_score || 0;
          const derivedLevel = getRiskLevel(score);

          const hasPeople = (zone.people_count || 0) > 0;
          const color = hasPeople ? (DARK_RISK_COLORS[derivedLevel as RiskLevel] || DARK_RISK_COLORS.UNKNOWN) : DARK_RISK_COLORS.UNKNOWN;

          (element as SVGElement).style.fill = color;
          // Higher opacity for higher risk to draw attention
          const opacityMap: Record<string, string> = {
            'LOW': '0.2',
            'MEDIUM': '0.5',
            'HIGH': '0.9',
            'CRITICAL': '1.0'
          };
          (element as SVGElement).style.fillOpacity = hasPeople ? (opacityMap[derivedLevel] || '0.2') : '0.1';

          if (derivedLevel === 'HIGH' || derivedLevel === 'CRITICAL') {
            (element as SVGElement).style.stroke = color;
            (element as SVGElement).style.strokeWidth = '2px';
          } else {
            (element as SVGElement).style.stroke = 'rgba(255,255,255,0.2)';
            (element as SVGElement).style.strokeWidth = '1px';
          }
        }

        // Remove legacy stats text update if present
        const textElement = container.querySelector(`#stats_${zone.svg_region_id}`);
        if (textElement) textElement.textContent = '';
      });
    });
  }, [zones, selectedZoneId]);

  const hybContent = `
    <!-- HYB DESIGN - ORIGINAL SIZE (220x140) -->
    
    <!-- SVG Connector Lines for Data Boxes -->
    <!-- PF-1 Connectors (Left to Right) -->
    <line x1="160" y1="125" x2="320" y2="125" stroke="rgba(255,255,255,0.5)" stroke-width="2" stroke-dasharray="4 4" />
    <line x1="160" y1="275" x2="320" y2="275" stroke="rgba(255,255,255,0.5)" stroke-width="2" stroke-dasharray="4 4" />
    <line x1="160" y1="425" x2="320" y2="425" stroke="rgba(255,255,255,0.5)" stroke-width="2" stroke-dasharray="4 4" />

    <!-- Middle Connectors (Top to Bottom) - Aligned to new Centers 680, 920 -->
    <line x1="680" y1="100" x2="680" y2="200" stroke="rgba(255,255,255,0.5)" stroke-width="2" stroke-dasharray="4 4" />
    <line x1="920" y1="100" x2="920" y2="200" stroke="rgba(255,255,255,0.5)" stroke-width="2" stroke-dasharray="4 4" />

    <!-- PF-10 Connectors (Right to Left) -->
    <line x1="1280" y1="275" x2="1440" y2="275" stroke="rgba(255,255,255,0.5)" stroke-width="2" stroke-dasharray="4 4" />
    <line x1="1280" y1="425" x2="1440" y2="425" stroke="rgba(255,255,255,0.5)" stroke-width="2" stroke-dasharray="4 4" />

    <!-- PF-1 SECTION (Left Stack) - CONTIGUOUS X=320 -->
    <!-- Box 1 (Top) Y=50 -->
    <rect id="zone_pf1_fob_kzj" x="320" y="50" width="240" height="150" class="fob-zone" />
    <text x="440" y="135" class="zone-label" font-size="16">
      <tspan x="440" dy="-15">PF 1 HYB</tspan>
      <tspan x="440" dy="20">FOB FC KZJ</tspan>
      <tspan x="440" dy="20">Steps</tspan>
    </text>

    <!-- Box 2 (Middle) Y=200 -->
    <rect id="zone_pf1_hyb_fob_fc_pf10" x="320" y="200" width="240" height="150" class="fob-zone" />
    <text x="440" y="285" class="zone-label" font-size="16">
      <tspan x="440" dy="-10">PF 1 HYB</tspan>
      <tspan x="440" dy="20">FOB FC PF 10</tspan>
    </text>
    
    <!-- Box 3 (Bottom) Y=350 -->
    <rect id="zone_pf1_fob_hyb_end" x="320" y="350" width="240" height="150" class="fob-zone" />
    <text x="440" y="435" class="zone-label" font-size="16">
      <tspan x="440" dy="-15">PF 1 HYB</tspan>
      <tspan x="440" dy="20">FOB FC HYB END</tspan>
      <tspan x="440" dy="20">Steps</tspan>
    </text>

    <!-- PF-1 Title -->
    <text x="440" y="540" class="platform-label" font-size="24">PF-1</text>
    <line x1="440" y1="500" x2="440" y2="540" class="platform-line" />
    
    <!-- MIDDLE SECTION (Horizontal) - CONTIGUOUS X=560/800 -->
    <!-- Box 4 (X=560) -->
    <rect id="zone_middle_fob_4_5" x="560" y="200" width="240" height="150" class="fob-zone" />
    <text x="680" y="285" class="zone-label" font-size="16">
      <tspan x="680" dy="-10">HYB FOB</tspan>
      <tspan x="680" dy="20">MIDD FC 4&5</tspan>
    </text>
    
    <!-- Box 5 (X=800) -->
    <rect id="zone_middle_fob_6_7" x="800" y="200" width="240" height="150" class="fob-zone" />
    <text x="920" y="285" class="zone-label" font-size="16">
      <tspan x="920" dy="-10">HYB FOB</tspan>
      <tspan x="920" dy="20">MIDD FC 6&7</tspan>
    </text>

    <!-- Platform Indicators Middle -->
    <!-- First box: PF-2/3 and PF-4/5 -->
    <line x1="620" y1="350" x2="620" y2="410" class="platform-line" />
    <text x="620" y="440" class="platform-label" font-size="24">PF-2/3</text>
    
    <line x1="740" y1="350" x2="740" y2="410" class="platform-line" />
    <text x="740" y="440" class="platform-label" font-size="24">PF-4/5</text>
    
    <!-- Second box: PF-6/7 and PF-8/9 -->
    <line x1="860" y1="350" x2="860" y2="410" class="platform-line" />
    <text x="860" y="440" class="platform-label" font-size="24">PF-6/7</text>
    
    <line x1="980" y1="350" x2="980" y2="410" class="platform-line" />
    <text x="980" y="440" class="platform-label" font-size="24">PF-8/9</text>

    <!-- PF-10 SECTION (Right Stack) - CONTIGUOUS X=1040 -->
    <!-- Box 6 (Top) Y=200 -->
    <rect id="zone_pf10_hyb_fob_fc_pf1" x="1040" y="200" width="240" height="150" class="fob-zone" />
    <text x="1160" y="285" class="zone-label" font-size="16">
      <tspan x="1160" dy="-10">PF 10 HYB</tspan>
      <tspan x="1160" dy="20">FOB FC PF1</tspan>
    </text>
    
    <!-- Box 7 (Bottom) Y=350 -->
    <rect id="zone_pf10_fob_steps" x="1040" y="350" width="240" height="150" class="fob-zone" />
    <text x="1160" y="435" class="zone-label" font-size="16">
      <tspan x="1160" dy="-15">PF 10 HYB</tspan>
      <tspan x="1160" dy="20">FOB FC HYB</tspan>
      <tspan x="1160" dy="20">STEPS</tspan>
    </text>

    <!-- PF-10 Title -->
    <text x="1160" y="540" class="platform-label" font-size="24">PF-10</text>
    <line x1="1160" y1="500" x2="1160" y2="540" class="platform-line" />
  `;

  const kzjContent = `
    <!-- KZJ FOB VIEW - MATCHING HYB COMPACT (240x150) -->
    
    <!-- SVG Connector Lines for Data Boxes -->
    <!-- PF-1 Connectors (Left to Right) -->
    <line x1="160" y1="125" x2="320" y2="125" stroke="rgba(255,255,255,0.5)" stroke-width="2" stroke-dasharray="4 4" />
    <line x1="160" y1="275" x2="320" y2="275" stroke="rgba(255,255,255,0.5)" stroke-width="2" stroke-dasharray="4 4" />
    <line x1="160" y1="425" x2="320" y2="425" stroke="rgba(255,255,255,0.5)" stroke-width="2" stroke-dasharray="4 4" />

    <!-- Middle Connectors (Top to Bottom) - Aligned to new Centers 680, 920 -->
    <line x1="680" y1="100" x2="680" y2="200" stroke="rgba(255,255,255,0.5)" stroke-width="2" stroke-dasharray="4 4" />
    <line x1="920" y1="100" x2="920" y2="200" stroke="rgba(255,255,255,0.5)" stroke-width="2" stroke-dasharray="4 4" />

    <!-- PF-10 Connectors (Right to Left) -->
    <line x1="1280" y1="275" x2="1440" y2="275" stroke="rgba(255,255,255,0.5)" stroke-width="2" stroke-dasharray="4 4" />

    <!-- PF-1 SECTION (Left Stack) - CONTIGUOUS X=320 -->
    <!-- Box 1 (Top) Y=50 -->
    <rect id="zone_pf1_kzj_fob_fc_kzj" x="320" y="50" width="240" height="150" class="fob-zone" />
    <text x="440" y="130" class="zone-label" font-size="16">
      <tspan x="440" dy="-15">PF 1 KZJ</tspan>
      <tspan x="440" dy="20">FOB FC KZJ</tspan>
      <tspan x="440" dy="20">Steps</tspan>
    </text>

    <!-- Box 2 (Middle) Y=200 -->
    <rect id="zone_new_kzj_fob_middle_fc_pf10" x="320" y="200" width="240" height="150" class="fob-zone" />
    <text x="440" y="280" class="zone-label" font-size="16">
      <tspan x="440" dy="-10">PF 1 KZJ</tspan>
      <tspan x="440" dy="20">FOB FC PF 10</tspan>
    </text>
    
    <!-- Box 3 (Bottom) Y=350 -->
    <rect id="zone_pf1_kzj_fob_fc_hyb" x="320" y="350" width="240" height="150" class="fob-zone" />
    <text x="440" y="430" class="zone-label" font-size="16">
      <tspan x="440" dy="-15">PF 1 KZJ</tspan>
      <tspan x="440" dy="20">FOB FC HYB END</tspan>
      <tspan x="440" dy="20">Steps</tspan>
    </text>

    <!-- PF-1 Title -->
    <text x="440" y="540" class="platform-label" font-size="24">PF-1</text>
    <line x1="440" y1="500" x2="440" y2="540" class="platform-line" />
    
    <!-- MIDDLE SECTION (Horizontal) - CONTIGUOUS X=560/800 -->
    <!-- Box 4 (X=560) -->
    <rect id="zone_kzj_fob_middle_fc_4_5" x="560" y="200" width="240" height="150" class="fob-zone" />
    <text x="680" y="280" class="zone-label" font-size="16">
      <tspan x="680" dy="-10">KZJ FOB</tspan>
      <tspan x="680" dy="20">MIDD FC 4&5</tspan>
    </text>
    
    <!-- Box 5 (X=800) -->
    <rect id="zone_kzj_fob_middle_fc_8_9" x="800" y="200" width="240" height="150" class="fob-zone" />
    <text x="920" y="280" class="zone-label" font-size="16">
      <tspan x="920" dy="-10">KZJ FOB</tspan>
      <tspan x="920" dy="20">MIDD FC 8&9</tspan>
    </text>

    <!-- Platform Indicators Middle -->
    <!-- First box: PF-2/3 and PF-4/5 -->
    <line x1="620" y1="350" x2="620" y2="410" class="platform-line" />
    <text x="620" y="440" class="platform-label" font-size="24">PF-2/3</text>
    
    <line x1="740" y1="350" x2="740" y2="410" class="platform-line" />
    <text x="740" y="440" class="platform-label" font-size="24">PF-4/5</text>
    
    <!-- Second box: PF-6/7 and PF-8/9 -->
    <line x1="860" y1="350" x2="860" y2="410" class="platform-line" />
    <text x="860" y="440" class="platform-label" font-size="24">PF-6/7</text>
    
    <line x1="980" y1="350" x2="980" y2="410" class="platform-line" />
    <text x="980" y="440" class="platform-label" font-size="24">PF-8/9</text>

    <!-- PF-10 SECTION (Right Stack) - CONTIGUOUS X=1040 -->
    <!-- Box 6 (Top) Y=200 -->
    <rect id="zone_kzj_fob_escalator_fc_pf1" x="1040" y="200" width="240" height="150" class="fob-zone" />
    <text x="1160" y="280" class="zone-label" font-size="16">
      <tspan x="1160" dy="-10">PF 10 KZJ</tspan>
      <tspan x="1160" dy="20">FOB ESCL FC PF1</tspan>
    </text>
    
    <!-- Box 7 (Bottom) - Removed -->
    
    <!-- PF-10 Title -->
    <text x="1160" y="440" class="platform-label" font-size="24">PF-10</text>
    <line x1="1160" y1="350" x2="1160" y2="410" class="platform-line" />
  `;



  const isHyb = (title || '').includes('HYD') || (title || '').includes('HYB');
  const isKzj = (title || '').includes('KAZI') || (title || '').includes('KZJ');

  // Restore Zone Cards (Summary)
  const zoneCards = isKzj ? [] : [
    { id: 'zone_pf1_fob_lift', label: 'PF 1 HYB FOB LIFT' },
    { id: 'zone_pf10_fob_vip', label: 'PF 10 HYB FOB FC VIP ENTRANCE' },
  ];

  // Revert to Standard Content for Dashboard "Previous View"
  const hybContentDashboard = hybContent;

  // Define Sections based on Variant
  const sections = isKzj
    ? [{ id: 'kzj_bridge', title: '', content: kzjContent, viewBox: '0 0 1600 600' }]
    : [
      {
        id: 'hyb_main',
        title: '',
        content: variant === 'dashboard' ? hybContentDashboard : hybContent,
        viewBox: variant === 'dashboard' ? '0 0 1600 750' : '0 0 1600 750'
      }
    ];

  // Use correct positions
  const currentPositions = (variant === 'dashboard' && isHyb) ? ZONE_POSITIONS_DASHBOARD : ZONE_POSITIONS;

  return (
    <div className={cn('relative w-full bg-[#0B0F1A] p-3 sm:p-4 md:p-6 rounded-2xl md:rounded-3xl border border-white/[0.03] flex flex-col items-center', className)}>
      <div className="flex flex-col sm:flex-row justify-center items-center mb-4 sm:mb-6 md:mb-8 relative w-full max-w-[1600px] gap-3 sm:gap-0">
        <h2 className="text-sm sm:text-base md:text-lg font-black text-center text-foreground/40 tracking-[0.15em] sm:tracking-[0.2em] md:tracking-[0.25em] uppercase" style={{ fontFamily: "'Outfit', sans-serif" }}>
          {isKzj ? 'KAZIPET FOB VIEW' : (title || 'HYDERABAD FOB VIEW')}
        </h2>
      </div>


      <div className="w-full flex-1 overflow-auto">
        {/* Render Sections with Side Cards for HYB */}
        {sections.map((section, idx) => (
          <div
            key={section.id}
            className={cn(
              "relative w-full flex flex-row justify-center items-center gap-4 lg:gap-5 max-w-[1600px] mx-auto",
              "px-2 sm:px-3 md:px-4 py-2 sm:py-3 md:py-4",
              "min-w-[1200px] md:min-w-[1850px] xl:min-w-0"
            )}
          >
            {/* Left Cards Stack - Always Visible (Scrollable with map) */}
            {zoneCards.length > 0 && (
              <div className="flex flex-col gap-3 lg:gap-4 flex-shrink-0 w-[220px] self-center">
                {zoneCards.map((card) => {
                  const zone = zones.find(z => z.svg_region_id === card.id);

                  let derivedLevel = 'LOW';
                  if (zone) {
                    derivedLevel = getRiskLevel(zone.risk_score || 0);
                  }

                  const hasPeople = (zone?.people_count || 0) > 0;

                  // Calculate Lag
                  const now = new Date().getTime();
                  // const dataTime = zone?.timestamp ? new Date(zone.timestamp).getTime() : now;
                  // const lagMs = now - dataTime;
                  const lagMs = 0;
                  const isLagging = false;
                  const isOffline = false;

                  const riskColor = zone ? (DARK_RISK_COLORS[derivedLevel as RiskLevel] || DARK_RISK_COLORS.LOW) : DARK_RISK_COLORS.UNKNOWN;
                  let color = hasPeople ? (derivedLevel === 'LOW' ? DARK_RISK_COLORS.LOW : riskColor) : DARK_RISK_COLORS.UNKNOWN;
                  const densityLevel = zone?.density_avg ? getDensityLevel(zone.density_avg) : 'LOW';

                  // Override colors if offline/lagging
                  if (isOffline) color = '#6b7280'; // Grey

                  const getDensityColor = (lvl: string) => {
                    if (lvl === 'VERY HIGH') return 'hsl(var(--risk-critical))';
                    if (lvl === 'HIGH') return 'hsl(var(--risk-high))';
                    if (lvl === 'MODERATE') return 'hsl(var(--risk-medium))';
                    return 'hsl(var(--risk-low))';
                  };
                  const densityColor = getDensityColor(densityLevel);
                  const motionLevel = zone?.motion_intensity ? getMotionLevel(zone.motion_intensity) : 'STATIC';

                  return (
                    <div
                      key={card.id}
                      onClick={() => zone && onZoneSelect(zone.zone_id === selectedZoneId ? null : zone.zone_id)}
                      className={cn(
                        "bg-[#0F141E] border-2 rounded-lg p-4 cursor-pointer transition-all duration-300 relative overflow-hidden",
                        (!zone || (zone.people_count || 0) === 0 || isOffline) && "border-gray-500",
                        !isOffline && zone && (zone.people_count || 0) > 0 && derivedLevel === 'LOW' && "border-green-500",
                        !isOffline && zone && (zone.people_count || 0) > 0 && derivedLevel === 'MEDIUM' && "border-yellow-400",
                        !isOffline && zone && (zone.people_count || 0) > 0 && (derivedLevel === 'HIGH' || derivedLevel === 'CRITICAL') && "border-red-500",
                        isLagging && !isOffline && "border-orange-400/50" // Dim warning for lag
                      )}
                    >
                      {/* Lag Indicator Overlay */}
                      {isLagging && (
                        <div className="absolute top-0 right-0 bg-orange-500/20 px-2 py-0.5 rounded-bl-lg border-l border-b border-orange-500/30">
                          <span className="text-[9px] font-bold text-orange-200 flex items-center gap-1">
                            ΓÜá∩╕Å {isOffline ? 'OFFLINE' : formatLag(lagMs)}
                          </span>
                        </div>
                      )}

                      <p className="text-center text-[9px] font-bold text-foreground uppercase tracking-wider mb-3" style={{ fontFamily: "'Outfit', sans-serif" }}>
                        {card.label}
                      </p>
                      <div className={cn("grid grid-cols-2 gap-y-3 gap-x-2 items-center", isOffline && "opacity-50 grayscale")}>
                        <div className="text-center">
                          <p className="text-[9px] text-foreground/30 uppercase font-bold mb-0.5" style={{ fontFamily: "'Outfit', sans-serif" }}>Count</p>
                          <p className="text-xl font-black text-foreground" style={{ fontFamily: "'Outfit', sans-serif" }}>{zone?.people_count || 0}</p>
                        </div>
                        <div className="text-center">
                          <p className="text-[9px] text-foreground/30 uppercase font-bold mb-0.5" style={{ fontFamily: "'Outfit', sans-serif" }}>Risk</p>
                          <p className="text-xl font-black" style={{ color, fontFamily: "'Outfit', sans-serif" }}>{zone?.risk_score ? `${Math.round(zone.risk_score)}% ` : '0%'}</p>
                        </div>
                        <div className="text-center border-t border-white/5 pt-1.5">
                          <p className="text-[9px] text-foreground/30 uppercase font-bold mb-0.5" style={{ fontFamily: "'Outfit', sans-serif" }}>Density</p>
                          <p className="text-xs font-black uppercase tracking-wider" style={{ color: densityColor, fontFamily: "'Outfit', sans-serif" }}>{densityLevel}</p>
                        </div>
                        <div className="text-center border-t border-white/5 pt-1.5">
                          <p className="text-[9px] text-foreground/30 uppercase font-bold mb-0.5" style={{ fontFamily: "'Outfit', sans-serif" }}>Motion</p>
                          <p className="text-xs font-black uppercase tracking-wider text-blue-400" style={{ fontFamily: "'Outfit', sans-serif" }}>{motionLevel}</p>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Center SVG - Responsive view filling available space */}
            <div className="w-full h-full overflow-hidden flex items-center justify-center">
              <div
                className={cn(
                  "relative flex items-center justify-center mx-auto transition-all duration-300",
                )}
                style={{
                  aspectRatio: section.viewBox ? (() => {
                    const parts = section.viewBox.split(' ');
                    return `${parts[2]} / ${parts[3]}`;
                  })() : '1600 / 750',
                  width: '100%',
                  height: 'auto',
                  maxWidth: '100%',
                  maxHeight: '100%',
                }}
              >
                {/* Floating Data Boxes */}
                <div className="absolute inset-0 z-20 pointer-events-none">
                  {Object.entries(currentPositions).map(([zoneId, config]) => {
                    // Check if this zone belongs to this section's content
                    // For side cards (added as dummy rects), includes() works
                    if (!section.content.includes(zoneId)) return null;

                    const zone = zones.find(z => z.svg_region_id === zoneId);

                    let derivedLevel = 'LOW';
                    if (zone) {
                      derivedLevel = getRiskLevel(zone.risk_score || 0);
                    }

                    const hasPeople = (zone?.people_count || 0) > 0;

                    // Calculate Lag
                    const now = new Date().getTime();
                    // const dataTime = zone?.timestamp ? new Date(zone.timestamp).getTime() : now;
                    // const lagMs = now - dataTime;
                    const lagMs = 0;
                    const isLagging = false;
                    const isOffline = false;

                    const riskColor = zone ? (DARK_RISK_COLORS[derivedLevel as RiskLevel] || DARK_RISK_COLORS.LOW) : DARK_RISK_COLORS.UNKNOWN;
                    let color = hasPeople ? (derivedLevel === 'LOW' ? DARK_RISK_COLORS.LOW : riskColor) : DARK_RISK_COLORS.UNKNOWN;
                    const densityLevel = zone?.density_avg ? getDensityLevel(zone.density_avg) : 'LOW';

                    // Override colors if offline/lagging
                    if (isOffline) color = '#6b7280'; // Grey

                    const getDensityColor = (lvl: string) => {
                      if (lvl === 'VERY HIGH') return '#ef4444';
                      if (lvl === 'HIGH') return '#ef4444';
                      if (lvl === 'MODERATE') return '#f97316';
                      return '#22c55e';
                    };
                    const densityColor = getDensityColor(densityLevel);
                    const motionLevel = zone?.motion_intensity ? getMotionLevel(zone.motion_intensity) : 'STATIC';

                    return (
                      <div
                        key={zoneId}
                        className="absolute -translate-x-1/2 flex flex-col items-center transition-all duration-300 pointer-events-auto"
                        style={{ left: config.left, top: config.top, width: config.width }}
                      >
                        <div
                          className={cn(
                            "w-full bg-[#0B0F1A] border-2 rounded-lg sm:rounded-xl shadow-2xl backdrop-blur-sm relative overflow-hidden",
                            // Optimized padding: Standard vs Dashboard Compact
                            variant === 'dashboard'
                              ? "px-2 sm:px-3 md:px-3 lg:px-2 xl:px-2 py-1.5 sm:py-2.5 md:py-2 lg:py-1.5 xl:py-1.5"
                              : "px-2 sm:px-3 md:px-3 lg:px-2 xl:px-4 py-1.5 sm:py-2.5 md:py-2 lg:py-1.5 xl:py-3",

                            (!zone || (zone.people_count || 0) === 0 || isOffline) && "border-gray-500",
                            !isOffline && zone && (zone.people_count || 0) > 0 && derivedLevel === 'LOW' && "border-green-500",
                            !isOffline && zone && (zone.people_count || 0) > 0 && derivedLevel === 'MEDIUM' && "border-yellow-400",
                            !isOffline && zone && (zone.people_count || 0) > 0 && (derivedLevel === 'HIGH' || derivedLevel === 'CRITICAL') && "border-red-500",
                            isLagging && !isOffline && "border-orange-400/50" // Dim warning for lag
                          )}
                        >
                          {/* Lag Indicator Overlay */}
                          {isLagging && (
                            <div className="absolute top-0 right-0 bg-orange-500/20 px-1.5 py-0.5 rounded-bl-md border-l border-b border-orange-500/30">
                              <span className="text-[8px] font-bold text-orange-200 flex items-center gap-0.5">
                                ΓÜá∩╕Å {isOffline ? 'OFFLINE' : formatLag(lagMs)}
                              </span>
                            </div>
                          )}

                          <div className={cn("grid grid-cols-2 gap-x-1 sm:gap-x-2 md:gap-x-3 gap-y-1 sm:gap-y-1.5 md:gap-y-2", isOffline && "opacity-50 grayscale")}>
                            {/* Row 1: Count & Risk */}
                            <div className="flex flex-col items-center justify-center">
                              <span className="text-[10px] sm:text-[10px] md:text-[10px] font-bold text-foreground/50 uppercase leading-none mb-0.5 sm:mb-1" style={{ fontFamily: "'Outfit', sans-serif" }}>Count</span>
                              <span className="text-lg sm:text-lg md:text-xl lg:text-lg xl:text-xl 2xl:text-2xl font-black text-foreground leading-none" style={{ fontFamily: "'Outfit', sans-serif" }}>{zone?.people_count || 0}</span>
                            </div>
                            <div className="flex flex-col items-center justify-center border-l border-white/10">
                              <span className="text-[10px] sm:text-[10px] md:text-[10px] font-bold text-foreground/50 uppercase leading-none mb-0.5 sm:mb-1" style={{ fontFamily: "'Outfit', sans-serif" }}>Est. Risk</span>
                              <span className="text-lg sm:text-lg md:text-xl lg:text-lg xl:text-xl 2xl:text-2xl font-black leading-none" style={{ color, fontFamily: "'Outfit', sans-serif" }}>{zone?.risk_score ? `${Math.round(zone.risk_score)}% ` : '0%'}</span>
                            </div>

                            {/* Row 2: Density & Motion */}
                            <div className="flex flex-col items-center justify-center border-t border-white/10 pt-0.5 sm:pt-1">
                              <span className="text-[8px] sm:text-[9px] md:text-[10px] font-bold text-foreground/50 uppercase leading-none mb-0.5 sm:mb-1" style={{ fontFamily: "'Outfit', sans-serif" }}>Density</span>
                              <span className="text-[9px] sm:text-[10px] md:text-xs font-black leading-none uppercase whitespace-nowrap" style={{ color: densityColor, fontFamily: "'Outfit', sans-serif" }}>
                                {densityLevel}
                              </span>
                            </div>
                            <div className="flex flex-col items-center justify-center border-t border-l border-white/10 pt-0.5 sm:pt-1">
                              <span className="text-[8px] sm:text-[9px] md:text-[10px] font-bold text-foreground/50 uppercase leading-none mb-0.5 sm:mb-1" style={{ fontFamily: "'Outfit', sans-serif" }}>Motion</span>
                              <span className="text-[9px] sm:text-[10px] md:text-xs font-black leading-none uppercase whitespace-nowrap text-blue-400" style={{ fontFamily: "'Outfit', sans-serif" }}>
                                {motionLevel}
                              </span>
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* SVG Container */}
                <div
                  ref={(el) => (sectionRefs.current[idx] = el)}
                  className="w-full h-full"
                  dangerouslySetInnerHTML={{
                    __html: `
                    <style>
                      .fob-zone { 
                        fill: rgba(13, 17, 26, 0.95); 
                        stroke: rgba(255,255,255,0.2); 
                        stroke-width: 1.5;
                        transition: all 0.3s ease;
                        filter: drop-shadow(0 4px 6px rgba(0,0,0,0.3));
                      }
                      .fob-zone:hover {
                        fill: #252D3D;
                        stroke: rgba(255,255,255,0.8);
                      }
                      .zone-label {
                        font-family: 'Outfit', sans-serif;
                        font-size: 16px; 
                        fill: white; 
                        font-weight: 700; 
                        text-anchor: middle; 
                        pointer-events: none;
                      }
                      .platform-label {
                         font-family: 'Outfit', sans-serif;
                         font-size: 24px;
                         fill: rgba(255,255,255,0.8);
                         font-weight: 700;
                         text-anchor: middle;
                      }
                      .platform-line {
                         stroke: rgba(255,255,255,0.4);
                         stroke-width: 3;
                         fill: none;
                      }
                      .no-camera-zone {
                        fill: #151921;
                        stroke: rgba(255,255,255,0.6);
                        stroke-width: 2;
                        cursor: not-allowed;
                      }
                      .no-camera-label {
                        font-family: 'Outfit', sans-serif;
                        font-size: 14px;
                        fill: rgba(255,255,255,0.4);
                        font-weight: 600;
                        text-anchor: middle;
                        writing-mode: vertical-rl;
                      }
                      /* Responsive adjustments */
                      @media (max-width: 768px) {
                        .zone-label { font-size: 12px; }
                        .platform-label { font-size: 14px; }
                        .no-camera-label { font-size: 10px; }
                      }
                    </style>
                    <svg viewBox="0 0 1600 600" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet" style="width:100%; height:100%;">
                      <defs>
                        <filter id="glow-bv" x="-20%" y="-20%" width="140%" height="140%">
                          <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
                          <feMerge>
                            <feMergeNode in="coloredBlur"/>
                            <feMergeNode in="SourceGraphic"/>
                          </feMerge>
                        </filter>
                      </defs>
                      <g>
                        ${(!isKzj && section.title) ? `<text x="50" y="50" font-family="'Outfit', sans-serif" font-size="28" fill="rgba(255,255,255,0.5)" font-weight="800" letter-spacing="0.1em" style="text-transform: uppercase;">
                          ${section.title}
                        </text>
                        <path d="M50 70 L250 70" stroke="rgba(255,255,255,0.2)" stroke-width="2" />` : ''}
                        
                        ${section.content}
                      </g>
                    </svg>
                  `,
                  }}
                />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
