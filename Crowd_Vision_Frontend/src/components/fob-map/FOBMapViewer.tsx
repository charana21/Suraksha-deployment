import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { CameraAnalytics, ZoneAnalytics } from '@/types/zone';
import { cn } from '@/lib/utils';
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

const VB_W = 1600;
const VB_H = 600;

const CAMERA_BOXES = [
  { id: 'cam_pf1_fob_kzj', label: 'HYB FOB', x: 180, y: 80, w: 260, h: 140 },
  { id: 'cam_middle_fob_4_5', label: 'MIDDLE FOB', x: 670, y: 80, w: 260, h: 140 },
  { id: 'cam_kzj_pf1_fob_kzj', label: 'KZJ FOB', x: 1160, y: 80, w: 260, h: 140 },

  { id: 'cam_hyb_pf1', label: 'PF 1', x: 120, y: 280, w: 200, h: 70 },
  { id: 'cam_hyb_pf2', label: 'PF 2', x: 360, y: 280, w: 200, h: 70 },
  { id: 'cam_hyb_pf3', label: 'PF 3', x: 600, y: 280, w: 200, h: 70 },
  { id: 'cam_hyb_pf4', label: 'PF 4', x: 840, y: 280, w: 200, h: 70 },
  { id: 'cam_hyb_pf5', label: 'PF 5', x: 1080, y: 280, w: 200, h: 70 },

  { id: 'cam_hyb_pf6', label: 'PF 6', x: 120, y: 410, w: 200, h: 70 },
  { id: 'cam_middle_fob_4_5', label: 'PF 7', x: 360, y: 410, w: 200, h: 70 },
  { id: 'cam_hyb_pf8', label: 'PF 8', x: 600, y: 410, w: 200, h: 70 },
  { id: 'cam_hyb_pf9', label: 'PF 9', x: 840, y: 410, w: 200, h: 70 },
  { id: 'cam_hyb_pf10', label: 'PF 10', x: 1080, y: 410, w: 200, h: 70 },

  { id: 'cam_hyb_booking', label: 'BOOKING', x: 1160, y: 520, w: 260, h: 60 },
];

const formatCameraId = (cameraId: string) =>
  cameraId
    .replace(/^cam_hyb_/i, 'camera_hyd_')
    .replace(/^cam_/i, 'camera_');

interface SvgBounds {
  offX: number;
  offY: number;
  scaleX: number;
  scaleY: number;
}

export function FOBMapViewer({
  zones = [],
  selectedZoneId = null,
  onZoneSelect = () => {},
  className,
  title,
}: FOBMapViewerProps) {
  const svgContainerRef = useRef<HTMLDivElement>(null);
  const [svgBounds, setSvgBounds] = useState<SvgBounds | null>(null);
  const [hoveredCameraId, setHoveredCameraId] = useState<string | null>(null);

  const computeBounds = useCallback(() => {
    const el = svgContainerRef.current;
    if (!el) return;
    const { width: cW, height: cH } = el.getBoundingClientRect();
    if (!cW || !cH) return;
    const cAspect = cW / cH;
    const vbAspect = VB_W / VB_H;
    let renderW: number;
    let renderH: number;
    if (cAspect > vbAspect) {
      renderH = cH;
      renderW = cH * vbAspect;
    } else {
      renderW = cW;
      renderH = cW / vbAspect;
    }
    setSvgBounds({
      offX: (cW - renderW) / 2,
      offY: (cH - renderH) / 2,
      scaleX: renderW / VB_W,
      scaleY: renderH / VB_H,
    });
  }, []);

  useEffect(() => {
    const t = setTimeout(computeBounds, 50);
    const ro = new ResizeObserver(computeBounds);
    if (svgContainerRef.current) ro.observe(svgContainerRef.current);
    return () => {
      clearTimeout(t);
      ro.disconnect();
    };
  }, [computeBounds]);

  const cameraById = useMemo(() => {
    const map = new Map<string, CameraAnalytics>();
    zones.forEach((zone) => {
      if (!Array.isArray(zone.cameras)) return;
      zone.cameras.forEach((cam) => {
        if (cam && typeof cam === 'object' && 'camera_id' in cam) {
          map.set(cam.camera_id, cam as CameraAnalytics);
          map.set(cam.svg_region_id, cam as CameraAnalytics);
        }
      });
    });
    return map;
  }, [zones]);

  const hoveredCamera = hoveredCameraId ? cameraById.get(hoveredCameraId) : undefined;

  const svgPx = useCallback(
    (svgX: number, svgY: number) => {
      if (!svgBounds) return { x: 0, y: 0 };
      return {
        x: svgBounds.offX + svgX * svgBounds.scaleX,
        y: svgBounds.offY + svgY * svgBounds.scaleY,
      };
    },
    [svgBounds],
  );

  const tooltipPos = useMemo(() => {
    if (!hoveredCameraId || !svgBounds) return null;
    const box = CAMERA_BOXES.find((b) => b.id === hoveredCameraId);
    if (!box) return null;
    const { x, y } = svgPx(box.x + box.w + 12, box.y);
    return { left: x, top: y };
  }, [hoveredCameraId, svgBounds, svgPx]);

  return (
    <div
      className={cn(
        'relative w-full bg-[#0B0F1A] p-3 sm:p-4 md:p-6 rounded-2xl md:rounded-3xl border border-white/[0.03] flex flex-col items-center',
        className,
      )}
    >
      <div className="flex flex-col sm:flex-row justify-center items-center mb-4 sm:mb-6 md:mb-8 relative w-full max-w-[1600px] gap-3 sm:gap-0">
        <h2
          className="text-sm sm:text-base md:text-lg font-black text-center text-foreground/40 tracking-[0.15em] sm:tracking-[0.2em] md:tracking-[0.25em] uppercase"
          style={{ fontFamily: "'Outfit', sans-serif" }}
        >
          {title || 'FOB LIVE VIEW'}
        </h2>
      </div>

      <div className="w-full flex-1 overflow-hidden">
        <div className="w-full max-w-[1600px] mx-auto">
          <div
            ref={svgContainerRef}
            className="relative w-full"
            style={{ aspectRatio: `${VB_W} / ${VB_H}` }}
          >
            <svg
              viewBox={`0 0 ${VB_W} ${VB_H}`}
              xmlns="http://www.w3.org/2000/svg"
              preserveAspectRatio="xMidYMid meet"
              className="absolute inset-0 w-full h-full pointer-events-none"
            >
              <rect x="0" y="0" width={VB_W} height={VB_H} fill="#0B0F1A" />
              {CAMERA_BOXES.map((box) => (
                <rect
                  key={box.id}
                  x={box.x}
                  y={box.y}
                  width={box.w}
                  height={box.h}
                  fill="transparent"
                  stroke="#6b7280"
                  strokeWidth="2"
                  rx="8"
                />
              ))}
            </svg>

            {svgBounds &&
              CAMERA_BOXES.map((box) => {
                const pos = svgPx(box.x, box.y);
                const w = box.w * svgBounds.scaleX;
                const h = box.h * svgBounds.scaleY;
                const isSelected = selectedZoneId === box.id;

                return (
                  <div
                    key={box.id}
                    className={cn(
                      'absolute rounded-md border-2 border-gray-500/70 bg-transparent transition-all duration-200 z-20 pointer-events-auto',
                      isSelected && 'border-white/80',
                    )}
                    style={{ left: pos.x, top: pos.y, width: w, height: h }}
                    onMouseEnter={() => setHoveredCameraId(box.id)}
                    onMouseLeave={() => setHoveredCameraId(null)}
                    onClick={() =>
                      onZoneSelect?.(box.id === selectedZoneId ? null : box.id)
                    }
                  />
                );
              })}

            {hoveredCamera && tooltipPos && (
              <div
                className="absolute z-30 w-56 rounded-xl border border-border/70 bg-[#121620]/95 text-foreground shadow-2xl p-3 pointer-events-none"
                style={{ left: tooltipPos.left, top: tooltipPos.top }}
              >
                <p className="text-xs font-semibold tracking-wide">
                  {formatCameraId(hoveredCamera.camera_id)}
                </p>
                <div className="mt-2 space-y-1.5 text-[11px]">
                  <div className="flex items-center justify-between">
                    <span className="text-foreground/70">Count</span>
                    <span className="font-semibold">{hoveredCamera.people_count ?? 0}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-foreground/70">Density</span>
                    <span className="font-semibold">
                      {getDensityLevel(hoveredCamera.density_avg || 0)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-foreground/70">Motion</span>
                    <span className="font-semibold">
                      {getMotionLevel(hoveredCamera.motion_intensity || 0)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-foreground/70">Risk</span>
                    <span className="font-semibold">
                      {getRiskLevel(hoveredCamera.risk_score || 0)}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
