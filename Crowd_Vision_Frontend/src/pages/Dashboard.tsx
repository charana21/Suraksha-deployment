import { useState, useMemo, useEffect, useLayoutEffect, useRef, useCallback } from "react";
import { PageLayout } from "@/components/layout/PageLayout";
import { FOBPeopleCountChart } from "@/components/dashboard/FOBPeopleCountChart";
import { StatsOverview, RiskCounts } from "@/components/dashboard/StatsOverview";
import { ActiveRiskPanel } from "@/components/dashboard/ActiveRiskPanel";
import { useZoneAnalytics } from "@/hooks/useZoneAnalytics";
import { useAlerts } from "@/hooks/useAlerts";
import { useCameras } from "@/hooks/useCameras";
import { useLocation } from "react-router-dom";
import { rtspApi } from "@/services/rtspApi";
import { trackingUserApi, TrackingUserRecord } from "@/services/trackingUserApi";
//import { IoPersonSharp } from "react-icons/io5";
import {
  WifiOff,
  RefreshCw,
  Building2,
  ChevronDown,
  Settings2,
  CalendarClock,
  ArrowLeft,
  X,
  Maximize2,
  Minimize2,
} from "lucide-react";
import { ActionIcon } from "@mantine/core";
import { IconMaximize } from "@tabler/icons-react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogTrigger,
} from "@/components/ui/dialog";
import { UpcomingTrains } from "@/components/dashboard/UpcomingTrains";
import { TrainUpload } from "@/components/admin/TrainUpload";
import { StationGoogleMap } from "@/components/dashboard/StationGoogleMap";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getDensityLevel, getMotionLevel, getRiskLevel } from "@/lib/metrics";
import { RiskLevel } from "@/types/zone";
import SecLayoutSvg from "@/assets/sec-layout-1-2.svg";
import SecLayoutLayoutSvg from "@/assets/sec-layout-1-3-layout.svg";
import SecLayoutNoFobSvg from "@/assets/sec-layout-1-2-layout-no-fobs.svg";
import SecLayoutLiveCleanSvg from "@/assets/sec-layout-1-2-layout.svg";
import SecLayoutLiveSvgRaw from "@/assets/sec-layout-1-2-layout.svg?raw";
import MicSvg from "@/assets/mic.svg";
import {
  LIVE_VIEWBOX_HEIGHT,
  VIEWBOX_WIDTH,
} from "@/data/secLayoutLiveBoxes";
import { CameraAnalytics, ZoneAnalytics } from "@/types/zone";


const LAYOUT_VIEWBOX_HEIGHT = 1556;

const PF1_STATUS_CARD_GROUP_ID = "pf1_hour_card_group";
const PF1_STATUS_CARD_BG_ID = "pf1_hour_card_bg";
const PF1_STATUS_CARD_CENTER_X = 980;
const PF1_STATUS_CARD_WIDTH = 230;
const PF1_STATUS_CARD_HEIGHT = 84;
const PF1_STATUS_CARD_Y = 388;
const PF1_STATUS_CARD_LINE_HEIGHT = 18;
const PF1_STATUS_INDICATOR_CENTER_X = 915;
const PF1_STATUS_INDICATOR_CENTER_Y = 383;
const PF1_STATUS_INDICATOR_RADIUS = 10;
const PF1_MIC_ICON_SIZE = 90;
const PF1_INDICATOR_ICON_SPACING = 0;





// ─── SVG coordinate constants ─────────────────────────────────────────────────
// ????????? SVG coordinate constants ???????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????
const FLOW_VB_W = 2100;
const FLOW_VB_H = 1856;

// FOB centre-X positions
const FOB_HYB_CX = 380;
const FOB_MID_CX = 1498;
const FOB_KZJ_CX = 1833;

// Flow path Y levels
const SPINE_Y = 330;   // horizontal spine in the white gap above PF-1
const ENTRY_TOP_Y = 260;   // Gate 4 booking office drop-in Y (below count)
const FOB_BOTTOM_Y = 470;  // stop above the person icon
// FOB box edges (SVG rect y=330..1310 + 28px group translate); round caps add ~5px, so the lines just touch the FOB
const FOB_TOP_EDGE_Y = 352;
const FOB_BOTTOM_EDGE_Y = 1344;
const ENTRY_SOURCE_X = 485;  // Gate 4 booking office X
const ENTRY_2A_SOURCE_X = 1510; // Gate 2A booking counter X (centre of cam_hyb_booking, x=1360..1660)

const SPINE_BOTTOM_Y = 1360; // bottom spine above PF10
const ENTRY_BOTTOM_Y = 1430; // drop-up Y for Gate 6 and 8
const ENTRY_6_SOURCE_X = 836; // Gate 6 X
const ENTRY_8_SOURCE_X = 1576; // Gate 8 X

// CORRECTED: Threshold value for detecting high crowd density in FOBs (120 people)
const FOB_THRESHOLD = 120;

const CAMERA_DATA_SOURCE_BY_REGION: Record<string, string> = {
  cam_hyd_booking_gate2a: 'cam_hyb_booking_gate2a',
  cam_gate2a_fc_parking: 'cam_north_parking',
  cam_new_kzj_fob_near_pf1: 'cam_mid_fob_pf1',
  cam_new_kzj_fob_fc_pf1: 'cam_mid_fob_center',
  cam_pf1_fob_kzj: 'cam_pf1_fob_pf10',
};

const HYD_CAMERA_IDS = [
  "cam_middle_fob_4_5",
  "cam_pf1_fob_pf10",
  "cam_hyb_pf1_a",
];
const KZJ_NEW_CAMERA_ID = "cam_mid_fob_pf1";
const KZJ_CAMERA_IDS = ["cam_kzj_pf1_fob_pf10", "cam_kzj_pf1_fob_kzj"];

type SvgPoint = { x: number; y: number };
type GeoPoint = { lat: number; lon: number };

type MappedUserMarker = {
  phoneKey: string;
  record: TrackingUserRecord;
  rawPoint: SvgPoint;
  markerPoint: SvgPoint;
};

const PLATFORM_DISPLAY_ANCHORS: Record<string, SvgPoint> = {
  pf1: { x: 1050, y: 393 },
  pf2: { x: 1050, y: 500 },
  pf3: { x: 1050, y: 610 },
  pf4: { x: 1050, y: 720 },
  pf5: { x: 1050, y: 830 },
  pf6: { x: 1050, y: 940 },
  pf7: { x: 1050, y: 1040 },
  pf8: { x: 1050, y: 1135 },
  pf9: { x: 1050, y: 1220 },
  pf10: { x: 1050, y: 1273 },
};

const FOB_ICON_EXCLUSION_HALF_WIDTH = 85;
const MARKER_MIN_X = 100;
const MARKER_MAX_X = 2000;

const clampMarkerAwayFromFobs = (x: number): number => {
  const fobXs = [FOB_HYB_CX, FOB_MID_CX, FOB_KZJ_CX];
  let adjusted = x;

  for (const fobX of fobXs) {
    const left = fobX - FOB_ICON_EXCLUSION_HALF_WIDTH;
    const right = fobX + FOB_ICON_EXCLUSION_HALF_WIDTH;
    if (adjusted >= left && adjusted <= right) {
      adjusted = adjusted < fobX ? left - 8 : right + 8;
    }
  }

  return Math.max(MARKER_MIN_X, Math.min(MARKER_MAX_X, adjusted));
};

// ─── Lat/lon → SVG mapping ─────────────────────────────────────────────────
// The base layout SVG (sec-layout-1-2-layout.svg) has viewBox "0 0 2100 1856"
// and draws every platform/track shape inside a top-level
// <g transform="translate(0,28)">, while the marker-overlay <svg> that renders
// these mapped points shares the same viewBox but has NO such offset — so any
// y-coordinate read off an element inside that group needs +28 added before
// it lines up with the overlay. With that offset applied:
//   PF1  rect: <rect x="140" y="320"  width="1900" height="90" .../> -> x:[140,2040] y:[348,438]
//   PF10 rect: <rect x="140" y="1220" width="1900" height="90" .../> -> x:[140,2040] y:[1248,1338]
// These rectangles are the SVG ground-control targets below.
const PF1_SVG_RECT = { left: 140, right: 2040, top: 348, bottom: 438 };
const PF10_SVG_RECT = { left: 140, right: 2040, top: 1248, bottom: 1338 };
// The entrance/booking-hall area north of PF1 has no single labelled shape in
// the SVG, so its top edge is approximated just above the
// "ENTRANCE & BOOKING OFFICES AREA" bar.
const STATION_TOP_SVG_Y = 90;

// Platform 1 boundary (HYD end = "left", KZJ end = "right").
const PF1_GEO = {
  leftUpper: { lat: 17.432936, lon: 78.499125 },
  leftBottom: { lat: 17.432834, lon: 78.499123 },
  rightUpper: { lat: 17.433767, lon: 78.503199 },
  rightBottom: { lat: 17.4339786, lon: 78.5032991 },
};

// Platform 10 boundary.
const PF10_GEO = {
  leftUpper: { lat: 17.432222, lon: 78.499669 },
  leftBottom: { lat: 17.432208, lon: 78.499205 },
  rightUpper: { lat: 17.43328, lon: 78.504644 },
  rightBottom: { lat: 17.433266, lon: 78.504645 },
};

// SEC station outer boundary (bottomLeft/bottomRight coincide exactly with
// PF10's leftBottom/rightBottom).
const STATION_GEO = {
  topLeft: { lat: 17.433748, lon: 78.499739 },
  topRight: { lat: 17.434623, lon: 78.504426 },
};

const clamp01 = (n: number) => Math.min(1, Math.max(0, n));

type LocalFitPoint = SvgPoint & { u: number; v: number };
type SvgRect = { left: number; right: number; top: number; bottom: number };

/**
 * Builds a local (u, v) coordinate fit from 3 geo corners - origin(u=0,v=0),
 * uCorner(u=1,v=0), vCorner(u=0,v=1) - then maps (u, v) into an SVG rectangle.
 * This is exact at those 3 corners. A platform is ~40x longer than it is
 * wide, so a full 4-corner quad fit (bilinear or least-squares) is nearly
 * singular and blows up numerically; anchoring on 3 corners via a direct 2x2
 * solve avoids that entirely, at the cost of the 4th (unused) corner only
 * being approximated.
 */
const makeLocalFit = (origin: GeoPoint, uCorner: GeoPoint, vCorner: GeoPoint, rect: SvgRect) => {
  const uAxis = { lon: uCorner.lon - origin.lon, lat: uCorner.lat - origin.lat };
  const vAxis = { lon: vCorner.lon - origin.lon, lat: vCorner.lat - origin.lat };
  const det = uAxis.lon * vAxis.lat - uAxis.lat * vAxis.lon;

  return (latitude: number, longitude: number): LocalFitPoint => {
    const dLon = longitude - origin.lon;
    const dLat = latitude - origin.lat;
    const u = (dLon * vAxis.lat - dLat * vAxis.lon) / det;
    const v = (uAxis.lon * dLat - uAxis.lat * dLon) / det;
    return {
      x: rect.left + clamp01(u) * (rect.right - rect.left),
      y: rect.top + clamp01(v) * (rect.bottom - rect.top),
      u,
      v,
    };
  };
};

// Four bands, north to south, each an exact fit at its own 3 named corners.
const entranceFit = makeLocalFit(STATION_GEO.topLeft, STATION_GEO.topRight, PF1_GEO.leftUpper,
  { left: PF1_SVG_RECT.left, right: PF1_SVG_RECT.right, top: STATION_TOP_SVG_Y, bottom: PF1_SVG_RECT.top });
const pf1Fit = makeLocalFit(PF1_GEO.leftUpper, PF1_GEO.rightUpper, PF1_GEO.leftBottom,
  { left: PF1_SVG_RECT.left, right: PF1_SVG_RECT.right, top: PF1_SVG_RECT.top, bottom: PF1_SVG_RECT.bottom });
const middleFit = makeLocalFit(PF1_GEO.leftBottom, PF1_GEO.rightBottom, PF10_GEO.leftUpper,
  { left: PF1_SVG_RECT.left, right: PF1_SVG_RECT.right, top: PF1_SVG_RECT.bottom, bottom: PF10_SVG_RECT.top });
const pf10Fit = makeLocalFit(PF10_GEO.leftUpper, PF10_GEO.rightUpper, PF10_GEO.leftBottom,
  { left: PF10_SVG_RECT.left, right: PF10_SVG_RECT.right, top: PF10_SVG_RECT.top, bottom: PF10_SVG_RECT.bottom });

// How far outside its own [0, 1] x [0, 1] a band's fit is allowed to be while
// still being accepted as "this point's band".
const BAND_TOLERANCE = 0.12;
const isWithinBandTolerance = (p: LocalFitPoint) =>
  p.u >= -BAND_TOLERANCE && p.u <= 1 + BAND_TOLERANCE && p.v >= -BAND_TOLERANCE && p.v <= 1 + BAND_TOLERANCE;
const bandViolation = (p: LocalFitPoint) =>
  Math.max(0, -p.u) + Math.max(0, p.u - 1) + Math.max(0, -p.v) + Math.max(0, p.v - 1);

const toSvgPointFromLatLon = (latitude: number, longitude: number): SvgPoint => {
  // Platform-calibrated bands first (all 4 of their named corners are known
  // exactly), then the connector bands that only have 2 known corners each.
  const candidates = [
    pf1Fit(latitude, longitude),
    pf10Fit(latitude, longitude),
    middleFit(latitude, longitude),
    entranceFit(latitude, longitude),
  ];

  const confidentMatch = candidates.find(isWithinBandTolerance);
  if (confidentMatch) return confidentMatch;

  // Point isn't confidently inside any band (e.g. GPS noise far outside the
  // station) - fall back to whichever band's fit is least out-of-range.
  return candidates.reduce((best, candidate) =>
    bandViolation(candidate) < bandViolation(best) ? candidate : best
  );
};

const HYB_GEO_BOUNDS = {
  minLat: 17.42,
  maxLat: 17.45,
  minLon: 78.49,
  maxLon: 78.51,
};

const isWithinHybBounds = (lat: number, lon: number) =>
  lat >= HYB_GEO_BOUNDS.minLat
  && lat <= HYB_GEO_BOUNDS.maxLat
  && lon >= HYB_GEO_BOUNDS.minLon
  && lon <= HYB_GEO_BOUNDS.maxLon;

const normalizeLatLon = (lat: number, lon: number) => {
  if (isWithinHybBounds(lat, lon)) {
    return { lat, lon };
  }
  if (isWithinHybBounds(lon, lat)) {
    return { lat: lon, lon: lat };
  }
  return { lat, lon };
};

const getUserIdentityKey = (rec: { phoneNumber?: string }) => {
  const raw = (rec.phoneNumber || "").trim();
  return raw || null;
};

// ─── Spread overlapping user markers apart ─────────────────────────────────
// Multiple tracked phones can resolve to (nearly) the same SVG point, which
// stacks their pin icons on top of each other and hides how many users are
// actually there. Cluster markers that are within MARKER_CLUSTER_RADIUS of
// each other and fan them out around their shared centroid so every pin
// stays visible and clickable.
const MARKER_CLUSTER_RADIUS = 34;
const MARKER_SPREAD_SPACING = 40;

const spreadOverlappingMarkers = (markers: MappedUserMarker[]): MappedUserMarker[] => {
  const used = new Array(markers.length).fill(false);
  const result: MappedUserMarker[] = new Array(markers.length);

  for (let i = 0; i < markers.length; i++) {
    if (used[i]) continue;
    const clusterIdx = [i];
    used[i] = true;
    for (let j = i + 1; j < markers.length; j++) {
      if (used[j]) continue;
      const dx = markers[j].markerPoint.x - markers[i].markerPoint.x;
      const dy = markers[j].markerPoint.y - markers[i].markerPoint.y;
      if (Math.sqrt(dx * dx + dy * dy) <= MARKER_CLUSTER_RADIUS) {
        clusterIdx.push(j);
        used[j] = true;
      }
    }

    if (clusterIdx.length === 1) {
      result[i] = markers[i];
      continue;
    }

    const cx = clusterIdx.reduce((sum, idx) => sum + markers[idx].markerPoint.x, 0) / clusterIdx.length;
    const cy = clusterIdx.reduce((sum, idx) => sum + markers[idx].markerPoint.y, 0) / clusterIdx.length;
    const radius = Math.max(MARKER_SPREAD_SPACING, (clusterIdx.length * MARKER_SPREAD_SPACING) / (2 * Math.PI));

    clusterIdx.forEach((idx, k) => {
      const angle = (2 * Math.PI * k) / clusterIdx.length;
      result[idx] = {
        ...markers[idx],
        markerPoint: {
          x: cx + Math.cos(angle) * radius,
          y: cy + Math.sin(angle) * radius,
        },
      };
    });
  }

  return result;
};

// ─── CrowdFlowOverlay ─────────────────────────────────────────────────────────
/**
 * CrowdFlowOverlay Component
 *
 * PURPOSE:
 * Displays animated crowd flow paths from Gate 4 Booking Office to each FOB.
 * Routes turn red when the FOB crowd count exceeds the FOB_THRESHOLD (120).
 *
 * LOGIC:
 * 1. Receives people counts from three FOBs (HYB, MID, KZJ)
 * 2. Compares each count against FOB_THRESHOLD (120)
 * 3. If count >= 120: Route to that FOB is colored RED (congested)
 * 4. If count < 120: Route is colored GREEN (normal)
 * 5. Shows "CONGESTED" badge on routes that exceed threshold
 * 6. Shows "ALTERNATE ROUTE" badge on non-congested FOBs when others are congested
 *
 * COLOR SCHEME:
 * - GREEN (#50C878): Normal crowd flow (< 120 people)
 * - RED (#e2584f): Congested route (>= 120 people)
 *
 * ANIMATED ELEMENTS:
 * - Vertical line from Gate 4 Booking Office down to main spine
 * - Horizontal spine connecting to all three FOBs
 * - Vertical lines dropping down to each FOB
 * - Dynamic badges showing congestion status
 */
interface FlowOverlayProps {
  hybFobCount: number;
  midFobCount: number;
  kzjFobCount: number;
  preserveAspectRatio?: string;
}

function CrowdFlowOverlay({ hybFobCount, midFobCount, kzjFobCount, preserveAspectRatio = "xMidYMid meet" }: FlowOverlayProps) {
  // Memoize FOB data to prevent unnecessary re-renders
  const fobs = useMemo(() => [
    { id: "HYB", fobX: FOB_HYB_CX, count: hybFobCount },
    { id: "MID", fobX: FOB_MID_CX, count: midFobCount },
    { id: "KZJ", fobX: FOB_KZJ_CX, count: kzjFobCount },
  ], [hybFobCount, midFobCount, kzjFobCount]);

  // ═════════════════════════════════════════════════════════════════════════════
  // THRESHOLD LOGIC: Determine if any FOB is congested
  // ═════════════════════════════════════════════════════════════════════════════
  const anyCongest = useMemo(() => {
    return fobs.some(f => f.count > FOB_THRESHOLD);
  }, [fobs]);

  const spineColor = "#50C878";
  const spineGlow = "url(#flo-glow-g)";
  const entryColor = anyCongest ? "#e2584f" : spineColor;
  const entryGlow = anyCongest ? "url(#flo-glow-r)" : spineGlow;

  return (
    <svg
      className="absolute top-0 left-0 w-full h-full pointer-events-none"
      viewBox={`0 0 ${FLOW_VB_W} ${FLOW_VB_H}`}
      preserveAspectRatio={preserveAspectRatio}
      style={{ zIndex: 20 }}
    >
      <defs>
        <style>{`
          @keyframes flow-dash {
            from { stroke-dashoffset: 48; }
            to   { stroke-dashoffset: 0; }
          }
          @keyframes badge-pulse {
            0%, 100% { opacity: 1; }
            50%       { opacity: 0.55; }
          }
          .fda  { animation: flow-dash 0.8s linear infinite; }
          .fdas { animation: flow-dash 1.6s linear infinite; }
          .bp   { animation: badge-pulse 1.3s ease-in-out infinite; }
        `}</style>

        <filter id="flo-glow-g" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="6" result="b" />
          <feMerge><feMergeNode in="b" /><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
        <filter id="flo-glow-r" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="6" result="b" />
          <feMerge><feMergeNode in="b" /><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
        <filter id="flo-shadow" x="-20%" y="-40%" width="140%" height="200%">
          <feDropShadow dx="0" dy="2" stdDeviation="4" floodColor="#000" floodOpacity="0.6" />
        </filter>

        <marker id="flo-arrow-green" viewBox="0 0 12 12" refX="9" refY="6"
          markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M1 1 L11 6 L1 11 Z" fill="#50C878" />
        </marker>
        <marker id="flo-arrow-red" viewBox="0 0 12 12" refX="9" refY="6"
          markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M1 1 L11 6 L1 11 Z" fill="#e2584f" />
        </marker>
        <marker id="flo-arrow-w" viewBox="0 0 12 12" refX="9" refY="6"
          markerWidth="4" markerHeight="4" orient="auto-start-reverse">
          <path d="M1 1 L11 6 L1 11 Z" fill="rgba(255,255,255,0.9)" />
        </marker>
      </defs>

      {/* ═══════════════════════════════════════════════════════════════════════ */}
      {/* SECTION 1: Vertical entry drop from Gate 4A booking office down to spine */}
      {/* ═══════════════════════════════════════════════════════════════════════ */}
      <g>
        {/* Glow layer - soft green aura */}
        <line x1={ENTRY_SOURCE_X} y1={ENTRY_TOP_Y} x2={ENTRY_SOURCE_X} y2={SPINE_Y}
          stroke={entryColor} strokeOpacity="0.20" strokeWidth="26"
          strokeLinecap="round" filter={entryGlow} />
        {/* Dark border - dark outline for contrast */}
        <line x1={ENTRY_SOURCE_X} y1={ENTRY_TOP_Y} x2={ENTRY_SOURCE_X} y2={SPINE_Y}
          stroke="#0b3b1b" strokeOpacity="0.9" strokeWidth="14"
          strokeLinecap="round" />
        {/* Solid - main path */}
        <line x1={ENTRY_SOURCE_X} y1={ENTRY_TOP_Y} x2={ENTRY_SOURCE_X} y2={SPINE_Y}
          stroke={entryColor} strokeWidth="10" strokeLinecap="round" />
        {/* Dotted inner path - animated dashed line */}
        <line x1={ENTRY_SOURCE_X} y1={ENTRY_TOP_Y} x2={ENTRY_SOURCE_X} y2={SPINE_Y}
          stroke="rgba(255,255,255,0.9)" strokeWidth="4"
          strokeDasharray="2 14" strokeLinecap="round"
          className={anyCongest ? "fdas" : "fda"} />
      </g>

      {/* ═══════════════════════════════════════════════════════════════════════ */}
      {/* SECTION 1.5: Vertical entry drop from Gate 2A booking counter down to spine */}
      {/* ═══════════════════════════════════════════════════════════════════════ */}
      <g>
        {/* Glow layer - soft green aura */}
        <line x1={ENTRY_2A_SOURCE_X} y1={ENTRY_TOP_Y} x2={ENTRY_2A_SOURCE_X} y2={SPINE_Y}
          stroke={entryColor} strokeOpacity="0.20" strokeWidth="26"
          strokeLinecap="round" filter={entryGlow} />
        {/* Dark border - dark outline for contrast */}
        <line x1={ENTRY_2A_SOURCE_X} y1={ENTRY_TOP_Y} x2={ENTRY_2A_SOURCE_X} y2={SPINE_Y}
          stroke="#0b3b1b" strokeOpacity="0.9" strokeWidth="14"
          strokeLinecap="round" />
        {/* Solid - main path */}
        <line x1={ENTRY_2A_SOURCE_X} y1={ENTRY_TOP_Y} x2={ENTRY_2A_SOURCE_X} y2={SPINE_Y}
          stroke={entryColor} strokeWidth="10" strokeLinecap="round" />
        {/* Dotted inner path - animated dashed line */}
        <line x1={ENTRY_2A_SOURCE_X} y1={ENTRY_TOP_Y} x2={ENTRY_2A_SOURCE_X} y2={SPINE_Y}
          stroke="rgba(255,255,255,0.9)" strokeWidth="4"
          strokeDasharray="2 14" strokeLinecap="round"
          className={anyCongest ? "fdas" : "fda"} />
      </g>

      {/* ═══════════════════════════════════════════════════════════════════════ */}
      {/* SECTION 1.6: Vertical entry drop from Gate 6 up to bottom spine */}
      {/* ═══════════════════════════════════════════════════════════════════════ */}
      <g>
        <line x1={ENTRY_6_SOURCE_X} y1={ENTRY_BOTTOM_Y} x2={ENTRY_6_SOURCE_X} y2={SPINE_BOTTOM_Y}
          stroke={entryColor} strokeOpacity="0.20" strokeWidth="26" strokeLinecap="round" filter={entryGlow} />
        <line x1={ENTRY_6_SOURCE_X} y1={ENTRY_BOTTOM_Y} x2={ENTRY_6_SOURCE_X} y2={SPINE_BOTTOM_Y}
          stroke="#0b3b1b" strokeOpacity="0.9" strokeWidth="14" strokeLinecap="round" />
        <line x1={ENTRY_6_SOURCE_X} y1={ENTRY_BOTTOM_Y} x2={ENTRY_6_SOURCE_X} y2={SPINE_BOTTOM_Y}
          stroke={entryColor} strokeWidth="10" strokeLinecap="round" />
        <line x1={ENTRY_6_SOURCE_X} y1={ENTRY_BOTTOM_Y} x2={ENTRY_6_SOURCE_X} y2={SPINE_BOTTOM_Y}
          stroke="rgba(255,255,255,0.9)" strokeWidth="4" strokeDasharray="2 14" strokeLinecap="round"
          className={anyCongest ? "fdas" : "fda"} />
      </g>

      {/* ═══════════════════════════════════════════════════════════════════════ */}
      {/* SECTION 1.7: Vertical entry drop from Gate 8 up to bottom spine */}
      {/* ═══════════════════════════════════════════════════════════════════════ */}
      <g>
        <line x1={ENTRY_8_SOURCE_X} y1={ENTRY_BOTTOM_Y} x2={ENTRY_8_SOURCE_X} y2={SPINE_BOTTOM_Y}
          stroke={entryColor} strokeOpacity="0.20" strokeWidth="26" strokeLinecap="round" filter={entryGlow} />
        <line x1={ENTRY_8_SOURCE_X} y1={ENTRY_BOTTOM_Y} x2={ENTRY_8_SOURCE_X} y2={SPINE_BOTTOM_Y}
          stroke="#0b3b1b" strokeOpacity="0.9" strokeWidth="14" strokeLinecap="round" />
        <line x1={ENTRY_8_SOURCE_X} y1={ENTRY_BOTTOM_Y} x2={ENTRY_8_SOURCE_X} y2={SPINE_BOTTOM_Y}
          stroke={entryColor} strokeWidth="10" strokeLinecap="round" />
        <line x1={ENTRY_8_SOURCE_X} y1={ENTRY_BOTTOM_Y} x2={ENTRY_8_SOURCE_X} y2={SPINE_BOTTOM_Y}
          stroke="rgba(255,255,255,0.9)" strokeWidth="4" strokeDasharray="2 14" strokeLinecap="round"
          className={anyCongest ? "fdas" : "fda"} />
      </g>

      {/* ═══════════════════════════════════════════════════════════════════════ */}
      {/* SECTION 2: Horizontal spine along PF-1 top connecting entry to all FOBs */}
      {/* ═══════════════════════════════════════════════════════════════════════ */}
      <g>
        {/* Base spine from leftmost FOB to rightmost FOB */}
        <line x1={FOB_HYB_CX} y1={SPINE_Y} x2={FOB_KZJ_CX} y2={SPINE_Y}
          stroke={spineColor} strokeOpacity="0.20" strokeWidth="26"
          strokeLinecap="round" filter={spineGlow} />
        {/* Dark border */}
        <line x1={FOB_HYB_CX} y1={SPINE_Y} x2={FOB_KZJ_CX} y2={SPINE_Y}
          stroke="#0b3b1b" strokeOpacity="0.9" strokeWidth="14"
          strokeLinecap="round" />
        {/* Solid */}
        <line x1={FOB_HYB_CX} y1={SPINE_Y} x2={FOB_KZJ_CX} y2={SPINE_Y}
          stroke={spineColor} strokeWidth="10" strokeLinecap="round" />
        {/* Dotted inner path */}
        <line x1={FOB_HYB_CX} y1={SPINE_Y} x2={FOB_KZJ_CX} y2={SPINE_Y}
          stroke="rgba(255,255,255,0.9)" strokeWidth="4"
          strokeDasharray="2 14" strokeLinecap="round"
          className="fda"
        />

        {/* Draw congested route overlays LAST so they are never hidden by green base */}
        {fobs.map(({ id, fobX, count }) => {
          if (count <= FOB_THRESHOLD) return null;
          // Route from whichever PF-1 entry (Gate 4 or Gate 2A) is nearest to this FOB
          const entryX = Math.abs(ENTRY_SOURCE_X - fobX) <= Math.abs(ENTRY_2A_SOURCE_X - fobX)
            ? ENTRY_SOURCE_X
            : ENTRY_2A_SOURCE_X;
          const x1 = Math.min(entryX, fobX);
          const x2 = Math.max(entryX, fobX);
          return (
            <g key={`spine-congested-${id}`}>
              <line x1={x1} y1={SPINE_Y} x2={x2} y2={SPINE_Y}
                stroke="#e2584f" strokeOpacity="0.20" strokeWidth="26"
                strokeLinecap="round" filter="url(#flo-glow-r)" />
              <line x1={x1} y1={SPINE_Y} x2={x2} y2={SPINE_Y}
                stroke="#0b3b1b" strokeOpacity="0.9" strokeWidth="14"
                strokeLinecap="round" />
              <line x1={x1} y1={SPINE_Y} x2={x2} y2={SPINE_Y}
                stroke="#e2584f" strokeWidth="10" strokeLinecap="round" />
              <line x1={x1} y1={SPINE_Y} x2={x2} y2={SPINE_Y}
                stroke="rgba(255,255,255,0.9)" strokeWidth="4"
                strokeDasharray="2 14" strokeLinecap="round"
                className="fdas" />
            </g>
          );
        })}
      </g>

      {/* ═══════════════════════════════════════════════════════════════════════ */}
      {/* SECTION 2.5: Horizontal bottom spine connecting bottom entries to all FOBs */}
      {/* ═══════════════════════════════════════════════════════════════════════ */}
      <g>
        {/* Base spine from leftmost FOB to rightmost FOB */}
        <line x1={FOB_HYB_CX} y1={SPINE_BOTTOM_Y} x2={FOB_KZJ_CX} y2={SPINE_BOTTOM_Y}
          stroke={spineColor} strokeOpacity="0.20" strokeWidth="26" strokeLinecap="round" filter={spineGlow} />
        <line x1={FOB_HYB_CX} y1={SPINE_BOTTOM_Y} x2={FOB_KZJ_CX} y2={SPINE_BOTTOM_Y}
          stroke="#0b3b1b" strokeOpacity="0.9" strokeWidth="14" strokeLinecap="round" />
        <line x1={FOB_HYB_CX} y1={SPINE_BOTTOM_Y} x2={FOB_KZJ_CX} y2={SPINE_BOTTOM_Y}
          stroke={spineColor} strokeWidth="10" strokeLinecap="round" />
        <line x1={FOB_HYB_CX} y1={SPINE_BOTTOM_Y} x2={FOB_KZJ_CX} y2={SPINE_BOTTOM_Y}
          stroke="rgba(255,255,255,0.9)" strokeWidth="4" strokeDasharray="2 14" strokeLinecap="round"
          className="fda" />

        {/* Congested overlays for bottom spine */}
        {fobs.map(({ id, fobX, count }) => {
          if (count <= FOB_THRESHOLD) return null;
          const x1_g6 = Math.min(ENTRY_6_SOURCE_X, fobX);
          const x2_g6 = Math.max(ENTRY_6_SOURCE_X, fobX);
          const x1_g8 = Math.min(ENTRY_8_SOURCE_X, fobX);
          const x2_g8 = Math.max(ENTRY_8_SOURCE_X, fobX);

          return (
            <g key={`bottom-spine-congested-${id}`}>
              {/* Overlay for Gate 6 */}
              <line x1={x1_g6} y1={SPINE_BOTTOM_Y} x2={x2_g6} y2={SPINE_BOTTOM_Y} stroke="#e2584f" strokeOpacity="0.20" strokeWidth="26" strokeLinecap="round" filter="url(#flo-glow-r)" />
              <line x1={x1_g6} y1={SPINE_BOTTOM_Y} x2={x2_g6} y2={SPINE_BOTTOM_Y} stroke="#0b3b1b" strokeOpacity="0.9" strokeWidth="14" strokeLinecap="round" />
              <line x1={x1_g6} y1={SPINE_BOTTOM_Y} x2={x2_g6} y2={SPINE_BOTTOM_Y} stroke="#e2584f" strokeWidth="10" strokeLinecap="round" />
              <line x1={x1_g6} y1={SPINE_BOTTOM_Y} x2={x2_g6} y2={SPINE_BOTTOM_Y} stroke="rgba(255,255,255,0.9)" strokeWidth="4" strokeDasharray="2 14" strokeLinecap="round" className="fdas" />

              {/* Overlay for Gate 8 */}
              <line x1={x1_g8} y1={SPINE_BOTTOM_Y} x2={x2_g8} y2={SPINE_BOTTOM_Y} stroke="#e2584f" strokeOpacity="0.20" strokeWidth="26" strokeLinecap="round" filter="url(#flo-glow-r)" />
              <line x1={x1_g8} y1={SPINE_BOTTOM_Y} x2={x2_g8} y2={SPINE_BOTTOM_Y} stroke="#0b3b1b" strokeOpacity="0.9" strokeWidth="14" strokeLinecap="round" />
              <line x1={x1_g8} y1={SPINE_BOTTOM_Y} x2={x2_g8} y2={SPINE_BOTTOM_Y} stroke="#e2584f" strokeWidth="10" strokeLinecap="round" />
              <line x1={x1_g8} y1={SPINE_BOTTOM_Y} x2={x2_g8} y2={SPINE_BOTTOM_Y} stroke="rgba(255,255,255,0.9)" strokeWidth="4" strokeDasharray="2 14" strokeLinecap="round" className="fdas" />
            </g>
          );
        })}
      </g>

      {/* SECTION 3: Per-FOB vertical drops down the column */}
      {/* Color logic: RED if count > FOB_THRESHOLD, else GREEN */}
      {/* ═══════════════════════════════════════════════════════════════════════ */}
      {fobs.map(({ id, fobX, count }) => {
        // ─────────────────────────────────────────────────────────────────────
        // CRITICAL LOGIC: Determine route color based on count vs threshold
        // ─────────────────────────────────────────────────────────────────────
        const congested = count > FOB_THRESHOLD;
        const isAlt = anyCongest && !congested;
        const color = congested ? "#e2584f" : "#50C878";  // RED if congested, GREEN otherwise
        const glowFilter = congested ? "url(#flo-glow-r)" : "url(#flo-glow-g)";
        const animCls = congested ? "fdas" : "fda";

        const vertPath = `M ${fobX} ${SPINE_Y} L ${fobX} ${FOB_TOP_EDGE_Y}`;
        const badgeX = fobX;
        const badgeY = SPINE_Y + (FOB_BOTTOM_Y - SPINE_Y) * 0.38;

        return (
          <g key={id}>
            {/* Glow layer */}
            <path d={vertPath} fill="none" stroke={color} strokeOpacity="0.20"
              strokeWidth="26" strokeLinecap="round" filter={glowFilter} />
            {/* Dark border */}
            <path d={vertPath} fill="none" stroke="#0b3b1b" strokeOpacity="0.9"
              strokeWidth="14" strokeLinecap="round" />
            {/* Solid line */}
            <path d={vertPath} fill="none" stroke={color} strokeWidth="10"
              strokeLinecap="round" />
            {/* Dotted inner path - animated dashed line */}
            <path d={vertPath} fill="none" stroke="rgba(255,255,255,0.9)"
              strokeWidth="4" strokeDasharray="2 14" strokeLinecap="round"
              className={animCls} />

            {/* Short vertical drop into the FOB from the bottom spine */}
            <path d={`M ${fobX} ${FOB_BOTTOM_EDGE_Y} L ${fobX} ${SPINE_BOTTOM_Y}`} fill="none" stroke={color} strokeOpacity="0.20"
              strokeWidth="26" strokeLinecap="round" filter={glowFilter} />
            <path d={`M ${fobX} ${FOB_BOTTOM_EDGE_Y} L ${fobX} ${SPINE_BOTTOM_Y}`} fill="none" stroke="#0b3b1b" strokeOpacity="0.9"
              strokeWidth="14" strokeLinecap="round" />
            <path d={`M ${fobX} ${FOB_BOTTOM_EDGE_Y} L ${fobX} ${SPINE_BOTTOM_Y}`} fill="none" stroke={color} strokeWidth="10"
              strokeLinecap="round" />
            <path d={`M ${fobX} ${FOB_BOTTOM_EDGE_Y} L ${fobX} ${SPINE_BOTTOM_Y}`} fill="none" stroke="rgba(255,255,255,0.9)"
              strokeWidth="4" strokeDasharray="2 14" strokeLinecap="round"
              className={animCls} />

            {/* ═══════════════════════════════════════════════════════════════ */}
            {/* BADGE 1: CONGESTED badge (shown when count > FOB_THRESHOLD) */}
            {/* ═══════════════════════════════════════════════════════════════ */}
            {congested && (
              <g className="bp" filter="url(#flo-shadow)">
                <rect x={badgeX - 84} y={badgeY - 20} width={168} height={34}
                  rx={17} fill="#18181b" stroke="#e2584f" strokeWidth={2} />
                <text x={badgeX} y={badgeY + 3}
                  fontFamily="Arial, sans-serif" fontWeight="bold" fontSize={15}
                  fill="#e2584f" textAnchor="middle" letterSpacing={1}>
                  CONGESTED
                </text>
              </g>
            )}

            {/* ═══════════════════════════════════════════════════════════════ */}
            {/* BADGE 2: ALTERNATE ROUTE badge */}
            {/* Shown when this FOB is NOT congested, but at least one other is */}
            {/* ═══════════════════════════════════════════════════════════════ */}
            {isAlt && (
              <g filter="url(#flo-shadow)">
                <rect x={badgeX - 102} y={badgeY - 20} width={204} height={34}
                  rx={17} fill="#052e16" stroke="#50C878" strokeWidth={2} />
                <text x={badgeX} y={badgeY + 3}
                  fontFamily="Arial, sans-serif" fontWeight="bold" fontSize={15}
                  fill="#50C878" textAnchor="middle">
                  ALTERNATE ROUTE
                </text>
              </g>
            )}

          </g>
        );
      })}
    </svg>
  );
}

// ─── LiveClock ────────────────────────────────────────────────────────────────
const LiveClock = () => {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <span className="text-xs font-mono font-medium text-foreground">
      {time.toLocaleTimeString("en-IN", {
        timeZone: "Asia/Kolkata",
        hour12: true,
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })}
    </span>
  );
};

const FOB_OPTIONS = [
  { id: "HYB", name: "Hyderabad FOB", shortName: "HYD" },
  { id: "KZJ", name: "Kazipet FOB", shortName: "KZJ" },
];

export default function Dashboard() {
  const [fobId, setFobId] = useState<string>("HYB");
  const [viewMode, setViewMode] = useState<'cameraLayout' | 'layout' | 'live' | 'withoutFobs'>('live');
  const [showTrainSchedule, setShowTrainSchedule] = useState(true);
  const [isSvgFullscreen, setIsSvgFullscreen] = useState(false);
  const [digitalTwin, setDigitalTwin] = useState(true);
  const [hoveredCameraId, setHoveredCameraId] = useState<string | null>(null);
  const [tooltipPos, setTooltipPos] = useState<{ left: number; top: number } | null>(null);
  const [liveStreamCameraId, setLiveStreamCameraId] = useState<string | null>(null);
  const [liveStreamStatus, setLiveStreamStatus] = useState<'connecting' | 'ready' | 'error'>('connecting');
  const [liveStreamAttempt, setLiveStreamAttempt] = useState(0);
  const [isLiveStreamMaximized, setIsLiveStreamMaximized] = useState(false);
  const [trackingUsers, setTrackingUsers] = useState<TrackingUserRecord[]>([]);
  const [hoveredUserPhone, setHoveredUserPhone] = useState<string | null>(null);
  const [dashboardTab, setDashboardTab] = useState<'layout' | 'map'>('layout');
  const location = useLocation();
  const prevPathRef = useRef(location.pathname);

  const liveSvgRef = useRef<HTMLDivElement>(null);
  const svgScrollRef = useRef<HTMLDivElement>(null);

  const openLiveStream = useCallback(async (id: string) => {
    setLiveStreamCameraId(id);
    setLiveStreamStatus('connecting');
    setLiveStreamAttempt((n) => n + 1);

    try {
      const status = await rtspApi.getCameraRuntimeStatus(id);
      if (status.runtime_status !== 'running') {
        await rtspApi.startCamera(id);
      }
      setLiveStreamStatus('ready');
    } catch (err) {
      console.error(`Failed to start live stream for ${id}:`, err);
      setLiveStreamStatus('error');
    }
  }, []);

  const closeLiveStream = () => {
    setLiveStreamCameraId(null);
    setLiveStreamStatus('connecting');
    setIsLiveStreamMaximized(false);
  };

  const resetMapScroll = () => {
    const scroller = svgScrollRef.current;
    if (!scroller) return;
    scroller.scrollTop = 0;
    scroller.scrollLeft = 0;
  };

  const handleViewModeChange = (mode: 'cameraLayout' | 'layout' | 'live' | 'withoutFobs') => {
    setViewMode(mode);
    requestAnimationFrame(() => {
      resetMapScroll();
      requestAnimationFrame(resetMapScroll);
    });
  };

  const toggleSvgFullscreen = async () => {
    const target = document.getElementById('dashboard-svg-stage');
    if (!target) return;

    if (!document.fullscreenElement) {
      try {
        await target.requestFullscreen();
      } catch {
        setIsSvgFullscreen(true);
      }
      return;
    }

    try {
      await document.exitFullscreen();
    } catch {
      setIsSvgFullscreen(false);
    }
  };

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsSvgFullscreen(Boolean(document.fullscreenElement?.id === 'dashboard-svg-stage'));
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  // In full screen, stretch the base SVG to fill the entire viewport (no letterbox gaps, no scroll).
  // Reverts to its normal aspect-preserving fit as soon as full screen is exited.
  useEffect(() => {
    const svgEl = liveSvgRef.current?.querySelector('svg');
    if (!svgEl) return;
    if (isSvgFullscreen) {
      svgEl.setAttribute('preserveAspectRatio', 'none');
    } else {
      svgEl.removeAttribute('preserveAspectRatio');
    }
  }, [isSvgFullscreen, viewMode, fobId]);

  const { zones: rawZones, isLoading, isConnected, refresh, lastUpdate, dataTimestamp } =
    useZoneAnalytics({ stationId: fobId, enableWebSocket: true });

  useEffect(() => {
    if (location.pathname === "/" && prevPathRef.current !== "/") {
      refresh();
    }
    prevPathRef.current = location.pathname;
  }, [location.pathname, refresh]);

  const { alerts, acknowledgeAlert, checkForAlerts } = useAlerts();
  const { cameras } = useCameras();

  const selectedFOB = FOB_OPTIONS.find((f) => f.id === fobId) || FOB_OPTIONS[0];
  const zones = useMemo(() => rawZones, [rawZones]);

  // ── Global Risk ──────────────────────────────────────────────────────────────
  const globalRisk = useMemo(() => {
    if (!zones.length) return "LOW";
    if (zones.some((z) => z.risk_level === "CRITICAL")) return "CRITICAL";
    if (zones.some((z) => z.risk_level === "HIGH")) return "HIGH";
    if (zones.some((z) => z.risk_level === "MEDIUM")) return "MEDIUM";
    return "LOW";
  }, [zones]);

  const highRiskZones = zones.filter(
    (z) => z.risk_level === "MEDIUM" || z.risk_level === "HIGH" || z.risk_level === "CRITICAL"
  );

  const riskCounts: RiskCounts = useMemo(() => ({
    LOW: zones.filter((z) => z.risk_level === "LOW").length,
    MEDIUM: zones.filter((z) => z.risk_level === "MEDIUM").length,
    HIGH: zones.filter((z) => z.risk_level === "HIGH").length,
    CRITICAL: zones.filter((z) => z.risk_level === "CRITICAL").length,
  }), [zones]);

  // ── Aggregates ───────────────────────────────────────────────────────────────
  const totalPeople = zones.reduce((acc, z) => acc + (z.people_count || 0), 0);
  const hybFobCount = zones.find(z => z.zone_id === 'zone_hyb_fob')?.people_count || 0;
  const kzjFobCount = zones.find(z => z.zone_id === 'zone_kzj_fob')?.people_count || 0;
  const midFobCount = zones.find(z => z.zone_id === 'zone_mid_fob')?.people_count || 0;
  const avgDensity = zones.length > 0
    ? zones.reduce((a, z) => a + (z.density_avg || 0), 0) / zones.length
    : 0;

  const dashboardStats = useMemo(() => {
    const avgMotionIntensity = zones.length > 0
      ? zones.reduce((a, z) => a + (z.motion_intensity || 0), 0) / zones.length
      : 0;
    const avgRiskScore = zones.length > 0
      ? zones.reduce((a, z) => a + (z.risk_score || 0), 0) / zones.length
      : 0;
    return {
      peopleCount: totalPeople,
      density: avgDensity,
      motionIntensity: avgMotionIntensity,
      motionLevel: getMotionLevel(avgMotionIntensity),
      riskLevel: globalRisk,
      riskScore: avgRiskScore,
      densityLevel: globalRisk,
    };
  }, [zones, totalPeople, avgDensity, globalRisk]);

  // Generate alerts from zone data
  useEffect(() => {
    if (zones.length > 0) {
      const stats = {
        cameraId: fobId,
        riskLevel: dashboardStats.riskLevel,
        riskScore: dashboardStats.riskScore,
        density: dashboardStats.density,
        motionIntensity: dashboardStats.motionIntensity,
        zones: zones.map(z => ({
          id: z.zone_id,
          name: z.zone_name,
          riskLevel: z.risk_level,
          peopleCount: z.people_count,
          density: z.density_avg,
          motionIntensity: z.motion_intensity,
        })),
      };
      checkForAlerts(stats as any, `${selectedFOB.name} System`);
    }
  }, [zones, dashboardStats, checkForAlerts, fobId, selectedFOB.name]);

  const isLive = useMemo(() => {
    if (isConnected) return true;
    if (lastUpdate && !isLoading) {
      return new Date().getTime() - lastUpdate.getTime() < 10000;
    }
    return false;
  }, [isConnected, lastUpdate, isLoading]);

  const activeSvg = viewMode === 'withoutFobs'
    ? SecLayoutNoFobSvg
    : viewMode === 'live'
      ? SecLayoutLiveCleanSvg
      : viewMode === 'layout'
        ? SecLayoutLayoutSvg
        : SecLayoutSvg;

  const activeSvgHeight = (viewMode === 'layout' || viewMode === 'withoutFobs')
    ? LAYOUT_VIEWBOX_HEIGHT
    : LIVE_VIEWBOX_HEIGHT;

  useLayoutEffect(() => {
    const scroller = svgScrollRef.current;
    if (!scroller) return;
    resetMapScroll();
    requestAnimationFrame(resetMapScroll);
    setTimeout(resetMapScroll, 60);
  }, [viewMode, activeSvgHeight, fobId]);

  const LIVE_CAMERA_IDS = useMemo(() => ([
    'cam_hyb_pf1',
    'cam_hyb_pf2',
    'cam_hyb_pf4',
    //'cam_hyb_pf6',
    'cam_mid_fob_center',
    'cam_middle_fob_4_5',
    'cam_pf8_mid_fc_kzj',
    'cam_hyb_pf10',
    'cam_pf1_fob_pf10',
    'cam_hyb_pf1_a',
    'cam_mid_fob_pf1',
    'cam_pf1_fob_hyb_end',
    'cam_kzj_pf1_fob_kzj',
    'cam_kzj_pf1_fob_pf10',
    'cam_kzj_fob_mid_8_9',
    'cam_kzj_fob_mid_4_5',
    'cam_pf2_fc_hyd_side',
    'cam_pf10_vip_saloon',
    'cam_new_kzj_fob_near_pf1',
    'cam_new_kzj_fob_fc_pf1',
    'cam_rethifile_entr',
    'cam_rethifile_bo',
    'cam_gate2a_fc_parking',
    'cam_hyb_booking',
    'cam_hyb_booking_gate6',
    'cam_hyb_booking_gate8',
    'cam_pf10_bme_counter',
    'cam_hyb_booking_gate4a',
    'cam_gate2_wh',
    'cam_gate2_fc_ac_wh',
    'cam_near_gate_2a_fc_swathi_ent',
    'cam_hyd_booking_gate2a',
  ]), []);

  const CAMERA_TITLES: Record<string, string> = {
    cam_hyb_pf1: 'PF 1 NEAR KZJ END FACING GATE 2',
    cam_hyb_pf2: 'PF 2 KZJ FOB FACING RRI',
    cam_hyb_pf4: 'PF 4&5 NEAR KZJ FOB FACING HYB',
    //cam_hyb_pf6: 'PF 6 NEAR NEAR MID FOB',
    cam_mid_fob_center: 'NEW KZJ FOB MIDDLE FACING PF 10',
    cam_middle_fob_4_5: 'HYB FOB MIDDLE FACING PF 4&5',
    cam_pf8_mid_fc_kzj: 'PF 8 MID FACING KZJ',
    cam_hyb_pf10: 'PF 10 OPPOSITE TO GATE 8 FACING KZJ END',
    cam_pf1_fob_pf10: 'HYB FOB FACING PF 10',
    cam_hyb_pf1_a: 'PF 1 NEAR GATE 4 FACING HYB',
    cam_mid_fob_pf1: 'NEW KZJ FOB FACING PF 10',
    cam_pf1_fob_hyb_end: 'PF 10 HYB FOB PATHWAY FACING PF 1',
    cam_kzj_pf1_fob_kzj: 'PF 1 KZJ FOB FACING PF 10',
    cam_kzj_pf1_fob_pf10: 'KZJ FOB ESCALATOR FACING PF 1',
    cam_kzj_fob_mid_8_9: 'KZJ FOB MID FACING 8&9',
    cam_kzj_fob_mid_4_5: 'KZJ FOB MID FACING 4&5',
    cam_pf2_fc_hyd_side: 'PF 2 FACING HYD SIDE',
    cam_pf10_vip_saloon: 'PF10 VIP SALOON SIDING',
    cam_new_kzj_fob_near_pf1: 'NEW KZJ FOB NEAR PF 4&5',
    cam_new_kzj_fob_fc_pf1: 'NEW KZJ FOB FACING PF 1',
    cam_rethifile_entr: 'RETHIFILE ENTRANCE',
    cam_rethifile_bo: 'RETHIFILE BO/BUS STOP',
    cam_gate2a_fc_parking: 'GATE 2A FACING CAR PARKING',
    cam_hyb_booking: 'GATE 2A BOOKING COUNTER',
    cam_hyb_booking_gate6: 'GATE 6 BOOKING OFFICE',
    cam_hyb_booking_gate8: 'GATE 8 OUTSIDE',
    cam_pf10_bme_counter: 'PF-10 WAITING HALL AREA',
    cam_hyb_booking_gate4a: 'GATE 4 GENERAL WAITING HALL',
    cam_gate2_wh: 'GATE 2 WAITING HALL',
    cam_gate2_fc_ac_wh: 'GATE 2 FACING AC WAITING HALL',
    cam_near_gate_2a_fc_swathi_ent: 'NEAR GATE 2A FACING SWATHI ENT',
    cam_hyd_booking_gate2a: 'GATE 2A ENTRANCE',
  };

  const cameraById = useMemo(() => {
    const map = new Map<string, CameraAnalytics>();
    zones.forEach((zone: ZoneAnalytics) => {
      if (!Array.isArray(zone.cameras)) return;
      zone.cameras.forEach((cam: any) => {
        if (cam && typeof cam === 'object' && 'camera_id' in cam) {
          const rawId = String(cam.camera_id || '');
          const trimmedId = rawId.trim();
          const rawSvg = String(cam.svg_region_id || '');
          const trimmedSvg = rawSvg.trim();

          if (rawId) map.set(rawId, cam as CameraAnalytics);
          if (trimmedId) map.set(trimmedId, cam as CameraAnalytics);
          if (rawSvg) map.set(rawSvg, cam as CameraAnalytics);
          if (trimmedSvg) map.set(trimmedSvg, cam as CameraAnalytics);
        }
      });
    });
    return map;
  }, [zones]);

  const hybRouteCongested = useMemo(() => hybFobCount > FOB_THRESHOLD, [hybFobCount]);
  const midRouteCongested = useMemo(() => midFobCount > FOB_THRESHOLD, [midFobCount]);
  const kzjRouteCongested = useMemo(() => kzjFobCount > FOB_THRESHOLD, [kzjFobCount]);

  const routeStatus = useMemo(() => ({
    HYB: hybRouteCongested,
    MID: midRouteCongested,
    KZJ: kzjRouteCongested,
  }), [hybRouteCongested, midRouteCongested, kzjRouteCongested]);

  const hoveredCamera = useMemo(() => {
    if (!hoveredCameraId) return undefined;
    const trimmedHoverId = hoveredCameraId.trim();
    const sourceCameraId = (CAMERA_DATA_SOURCE_BY_REGION[hoveredCameraId] || CAMERA_DATA_SOURCE_BY_REGION[trimmedHoverId] || hoveredCameraId).trim();
    return (
      cameraById.get(hoveredCameraId) ||
      cameraById.get(trimmedHoverId) ||
      cameraById.get(sourceCameraId) || ({
        camera_id: sourceCameraId,
        people_count: 0,
        density_avg: 0,
        motion_intensity: 0,
        risk_score: 0,
      } as CameraAnalytics)
    );
  }, [hoveredCameraId, cameraById]);

  useEffect(() => {
    let mounted = true;

    const fetchTrackingUsers = async () => {
      try {
        const users = await trackingUserApi.getTrackingUsers();

        if (!mounted) return;
        setTrackingUsers(users);
      } catch {
        if (!mounted) return;
      }
    };

    fetchTrackingUsers();
    const timer = setInterval(fetchTrackingUsers, 10000);
    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, []);

  const mappedUserMarkers = useMemo<MappedUserMarker[]>(() => {
    const markers: MappedUserMarker[] = [];
    for (const rec of trackingUsers) {
      const phoneKey = getUserIdentityKey(rec);
      if (!phoneKey) continue;
      const { lat, lon } = normalizeLatLon(rec.coordinates.latitude, rec.coordinates.longitude);
      if (!isWithinHybBounds(lat, lon)) continue;
      const rawPoint = toSvgPointFromLatLon(lat, lon);

      const markerPoint = {
        x: clampMarkerAwayFromFobs(rawPoint.x),
        y: rawPoint.y,
      };
      markers.push({ phoneKey, record: rec, rawPoint, markerPoint });
    }
    return spreadOverlappingMarkers(markers);
  }, [trackingUsers]);

  // ── Color SVG camera regions based on live analytics ─────────────────────────
  useEffect(() => {
    if (viewMode !== 'live') return;
    const container = liveSvgRef.current;
    if (!container) return;

    const labelsGroup = container.querySelector('#camera-labels');
    if (labelsGroup) labelsGroup.remove();

    const RISK_FILL: Record<RiskLevel | 'UNKNOWN', string> = {
      LOW: '#50C878',
      MEDIUM: '#f6b73c',
      HIGH: '#e2584f',
      CRITICAL: '#b3261e',
      UNKNOWN: '#6b7280',
    };
    const RISK_STROKE: Record<RiskLevel | 'UNKNOWN', string> = {
      LOW: '#50C878',
      MEDIUM: '#f6b73c',
      HIGH: '#e2584f',
      CRITICAL: '#b3261e',
      UNKNOWN: '#6b7280',
    };

    LIVE_CAMERA_IDS.forEach((id) => {
      const el = container.querySelector(`#${id}`) as SVGElement | null;
      if (!el) return;

      const trimmedId = id.trim();
      const sourceCameraId = (CAMERA_DATA_SOURCE_BY_REGION[id] || CAMERA_DATA_SOURCE_BY_REGION[trimmedId] || id).trim();
      const cam = cameraById.get(id) || cameraById.get(trimmedId) || cameraById.get(sourceCameraId);
      const hasLiveData = isLive && !!cam;
      const boxEl = el as SVGRectElement;
      const width = parseFloat(boxEl.getAttribute('width') || '0');
      const height = parseFloat(boxEl.getAttribute('height') || '0');
      const cx = parseFloat(boxEl.getAttribute('x') || '0') + width / 2;
      const cy = parseFloat(boxEl.getAttribute('y') || '0') + height / 2;
      const isNarrow = width < 100;

      const countId = `count_${id}`;
      const iconId = `icon_${id}`;
      const existingCount = container.querySelector(`#${countId}`) as SVGTextElement | null;
      const existingIcon = container.querySelector(`#${iconId}`) as SVGGElement | null;
      const ns = 'http://www.w3.org/2000/svg';

      const iconTx = isNarrow ? cx - 14 : cx - 26;
      const iconTy = isNarrow ? cy - 32 : cy - 14;
      const textX = isNarrow ? cx : cx + 10;
      const textY = isNarrow ? cy + 28 : cy + 8;
      const textAnchor = isNarrow ? 'middle' : 'start';

      const createOrUpdateIcon = () => {
        if (existingIcon) {
          existingIcon.setAttribute('transform', `translate(${iconTx},${iconTy})`);
        } else {
          const grp = document.createElementNS(ns, 'g');
          grp.setAttribute('id', iconId);
          grp.setAttribute('transform', `translate(${iconTx},${iconTy})`);
          const personPath = document.createElementNS(ns, 'path');
          personPath.setAttribute('d', 'M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z');
          personPath.setAttribute('fill', '#ffffff');
          grp.appendChild(personPath);
          el.parentElement?.appendChild(grp);
        }
      };

      const applyCount = (countText: string) => {
        if (existingCount) {
          existingCount.textContent = countText;
          existingCount.setAttribute('x', String(textX));
          existingCount.setAttribute('y', String(textY));
          existingCount.setAttribute('text-anchor', textAnchor);
        } else {
          const txt = document.createElementNS(ns, 'text');
          txt.setAttribute('id', countId);
          txt.setAttribute('x', String(textX));
          txt.setAttribute('y', String(textY));
          txt.setAttribute('font-family', 'Arial, sans-serif');
          txt.setAttribute('font-size', '28');
          txt.setAttribute('font-weight', 'bold');
          txt.setAttribute('fill', '#ffffff');
          txt.setAttribute('stroke', '#111827');
          txt.setAttribute('stroke-width', '1.2');
          txt.setAttribute('paint-order', 'stroke');
          txt.setAttribute('text-anchor', textAnchor);
          txt.setAttribute('pointer-events', 'none');
          txt.textContent = countText;
          el.parentElement?.appendChild(txt);
        }
      };

      if (hasLiveData) {
        const rawLevel = cam.risk_level || getRiskLevel(cam.risk_score || 0);
        const level = (typeof rawLevel === 'string' ? rawLevel.toUpperCase() : 'UNKNOWN') as RiskLevel;
        el.setAttribute('fill', RISK_FILL[level] ?? RISK_FILL['UNKNOWN']);
        el.setAttribute('stroke', RISK_STROKE[level] ?? RISK_STROKE['UNKNOWN']);
        el.setAttribute('stroke-width', level === 'CRITICAL' ? '3' : '2');
        level === 'CRITICAL'
          ? el.classList.add('animate-pulse')
          : el.classList.remove('animate-pulse');
        createOrUpdateIcon();
        applyCount(`${cam.people_count ?? 0}`);
      } else {
        el.setAttribute('fill', RISK_FILL['UNKNOWN']);
        el.setAttribute('stroke', RISK_STROKE['UNKNOWN']);
        el.setAttribute('stroke-width', '2');
        el.classList.remove('animate-pulse');
        createOrUpdateIcon();
        applyCount('0');
      }
    });

    container.querySelectorAll('text[id^="count_"]').forEach(t => t.setAttribute('font-size', '28'));

    // Hide the hardcoded original indicators as they are now handled by the dynamic overlay
    const pfIndicator = container.querySelector('#pf1_status_indicator') as SVGCircleElement | null;
    if (pfIndicator) pfIndicator.style.display = 'none';
    const pfHalo = container.querySelector('#pf1_status_indicator_halo') as SVGCircleElement | null;
    if (pfHalo) pfHalo.style.display = 'none';
    const pfMic = container.querySelector('#pf1_mic_icon') as SVGImageElement | null;
    if (pfMic) pfMic.style.display = 'none';
    const pfMicArrow = container.querySelector('#pf1_mic_arrow') as SVGPathElement | null;
    if (pfMicArrow) pfMicArrow.style.display = 'none';



  }, [viewMode, LIVE_CAMERA_IDS, cameraById, isLive]);



  // ── Hover interactions for live SVG camera regions ────────────────────────────
  useEffect(() => {
    if (viewMode !== 'live') return;
    const container = liveSvgRef.current;
    if (!container) return;
    const cleanups: Array<() => void> = [];

    LIVE_CAMERA_IDS.forEach((id) => {
      const el = container.querySelector(`#${id}`) as SVGElement | null;
      if (!el) return;
      el.style.pointerEvents = 'all';
      el.style.cursor = 'pointer';

      const handleEnter = () => {
        setHoveredCameraId(id);
        const rect = el.getBoundingClientRect();
        const contRect = container.getBoundingClientRect();
        const tooltipWidth = 240;
        let left = rect.right - contRect.left + 8;
        if (left + tooltipWidth > contRect.width) {
          left = rect.left - contRect.left - tooltipWidth - 8;
        }
        const top = Math.max(0, rect.top - contRect.top);
        setTooltipPos({ left, top });
      };
      const handleLeave = () => {
        setHoveredCameraId(null);
        setTooltipPos(null);
      };
      const handleClick = () => {
        openLiveStream(id);
      };

      el.addEventListener('mouseenter', handleEnter);
      el.addEventListener('mouseleave', handleLeave);
      el.addEventListener('click', handleClick);
      cleanups.push(() => {
        el.removeEventListener('mouseenter', handleEnter);
        el.removeEventListener('mouseleave', handleLeave);
        el.removeEventListener('click', handleClick);
      });
    });

    return () => cleanups.forEach((fn) => fn());
  }, [viewMode, LIVE_CAMERA_IDS]);

  // ─────────────────────────────────────────────────────────────────────────────
  return (
    <PageLayout>
      <div className="space-y-5 lg:space-y-6 animate-fade-in max-w-[1600px] 2xl:max-w-[2400px] min-[2560px]:max-w-[98%] mx-auto min-[2560px]:gap-10">

        {/* ================= HEADER ================= */}
        <header className="grid grid-cols-1 lg:grid-cols-[1fr_auto_1fr] items-center gap-4 lg:gap-6 pb-3 lg:pb-4">
          {/* Left: Title */}
          <div className="text-center lg:text-left">
            <h1
              className="text-2xl lg:text-3xl font-bold text-foreground tracking-tight"
              style={{ fontFamily: "'Outfit', sans-serif" }}
            >
              Dashboard
            </h1>
            <p
              className="text-xs lg:text-sm text-muted-foreground mt-0.5"
              style={{ fontFamily: "'Outfit', sans-serif" }}
            >
              Real-time crowd monitoring &amp; analytics
            </p>
          </div>

          {/* Center: placeholder */}
          <div className="flex justify-center" aria-hidden />

          {/* Right: STATUS & ACTIONS */}
          <div className="flex justify-center lg:justify-end items-center gap-3">

            {/* VIEW TRAIN SCHEDULE TOGGLE */}
            <button
              onClick={() => setShowTrainSchedule(!showTrainSchedule)}
              className={`px-3 py-2 rounded-lg border border-border transition-colors flex items-center gap-2 text-sm font-medium ${showTrainSchedule
                ? 'bg-primary/10 border-primary/30 text-primary shadow-sm'
                : 'hover:bg-muted text-muted-foreground'
                }`}
              title={showTrainSchedule ? "Hide Train Schedule" : "View Train Schedule"}
            >
              <CalendarClock className="h-4 w-4" />
              <span className="hidden sm:inline">
                {showTrainSchedule ? "Hide Schedule" : "View Schedule"}
              </span>
            </button>

            {/* SHOW FLOW TOGGLE */}
            <div className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border bg-[#18181b]/90">
              <span className="text-xs font-semibold tracking-widest text-muted-foreground uppercase">
                Show Flow
              </span>
              <button
                onClick={() => setDigitalTwin(v => !v)}
                className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none ${digitalTwin ? 'bg-primary' : 'bg-muted'
                  }`}
                aria-label="Toggle Digital Twin"
              >
                <span
                  className={`inline-block h-4 w-4 rounded-full bg-white shadow transform transition-transform ${digitalTwin ? 'translate-x-4' : 'translate-x-0.5'
                    }`}
                />
              </button>
            </div>

            {/* ADMIN UPLOADS */}
            <Dialog>
              <DialogTrigger asChild>
                <button
                  className="px-3 py-2 rounded-lg border border-border hover:bg-muted transition-colors flex items-center gap-2 text-sm font-medium"
                  title="Upload Train Schedule"
                >
                  <Settings2 className="h-4 w-4 text-muted-foreground" />
                  <span className="hidden sm:inline">Upload Schedule</span>
                </button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-[600px] p-0 overflow-hidden card-black">
                <TrainUpload />
              </DialogContent>
            </Dialog>

            {/* STATUS & LATENCY */}
            <div className="flex items-center gap-3 pl-3 border-l border-border">
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-full card-black border border-border/50 shadow-sm">
                <div className="w-2 h-2 rounded-full animate-pulse bg-primary/50" />
                <LiveClock />
              </div>
              <div className={`status-indicator ${isLive ? "live" : "offline"}`}>
                {isLive ? "LIVE" : <WifiOff size={14} />}
              </div>
              <button
                onClick={refresh}
                className="p-2 rounded-lg border border-border hover:bg-muted transition-colors"
                title="Refresh"
              >
                <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />
              </button>
            </div>
          </div>
        </header>

        {/* ================= LAYOUT / MAP VIEW TABS ================= */}
        <div className="flex justify-center lg:justify-start">
          <Tabs value={dashboardTab} onValueChange={(v) => setDashboardTab(v as 'layout' | 'map')}>
            <TabsList>
              <TabsTrigger value="layout">Layout</TabsTrigger>
              <TabsTrigger value="map">Map View</TabsTrigger>
            </TabsList>
          </Tabs>
        </div>

        {/* ================= MAP WITH TRAINS OVERLAY ================= */}
        <div className="w-full relative">
          {isLoading && zones.length === 0 ? (
            <div className="glass-panel p-6 h-[400px] lg:h-[600px] xl:h-[650px] 2xl:h-[750px] min-[2560px]:h-[950px] flex items-center justify-center rounded-2xl">
              <div className="loader" />
            </div>
          ) : (
            <div className="relative w-full">
              <div className="relative w-full card-black-30 rounded-2xl border border-border/50 overflow-hidden">
                <div className={`grid grid-cols-1 ${showTrainSchedule ? 'grid-cols-[1fr_300px]' : ''}`}>
                  <div id="dashboard-svg-stage" className={`relative w-full flex flex-col ${isSvgFullscreen ? 'h-full' : ''}`}>
                    {!isSvgFullscreen && (
                      <ActionIcon
                        onClick={toggleSvgFullscreen}
                        aria-label="View SVG in full screen"
                        title="View SVG in full screen"
                        variant="filled"
                        color="dark"
                        size="lg"
                        className="absolute right-4 top-4 z-40 border border-border/70 bg-[#0f172a]/90 text-white shadow-lg hover:bg-[#111827]"
                      >
                        <IconMaximize size={18} stroke={1.8} />
                      </ActionIcon>
                    )}

                    {isSvgFullscreen && (
                      <button
                        onClick={toggleSvgFullscreen}
                        className="absolute left-4 top-4 z-40 p-2 rounded-full border border-border/70 bg-[#0f172a]/90 text-white shadow-lg hover:bg-[#111827]"
                        aria-label="Exit full screen"
                        title="Exit full screen"
                      >
                        <ArrowLeft className="h-5 w-5" />
                      </button>
                    )}

                    {/* SVG + overlays */}
                    <div style={{ display: dashboardTab === 'layout' ? undefined : 'none' }} className="w-full h-full">
                    <div
                      key={`svg-scroll-${viewMode}-${fobId}`}
                      ref={svgScrollRef}
                      className={`relative w-full ${isSvgFullscreen ? 'h-full overflow-hidden' : ''}`}
                    >
                      <style>{'.live-svg, .live-svg svg{width:100%;height:100%;display:block;object-fit:contain;}'}</style>

                      {/* ── Base station layout SVG ── */}
                      <div
                        ref={liveSvgRef}
                        className={`live-svg block w-full h-full ${isSvgFullscreen ? '' : 'min-h-[70vh] lg:min-h-[80vh]'}`}
                        dangerouslySetInnerHTML={{ __html: SecLayoutLiveSvgRaw }}
                      />
                      {mappedUserMarkers.length > 0 && (
                        <svg
                          className="absolute inset-0 w-full h-full z-20 pointer-events-none"
                          viewBox={`0 0 ${FLOW_VB_W} ${FLOW_VB_H}`}
                          preserveAspectRatio={isSvgFullscreen ? "none" : "xMidYMid meet"}
                        >
                          {mappedUserMarkers.map((marker) => (
                            <g
                              key={marker.phoneKey}
                              onMouseEnter={() => setHoveredUserPhone(marker.phoneKey)}
                              onMouseLeave={() => setHoveredUserPhone((curr) => (curr === marker.phoneKey ? null : curr))}
                              style={{ cursor: "pointer", pointerEvents: "auto" }}
                            >
                              <image
                                href={MicSvg}
                                x={marker.markerPoint.x - 28}
                                y={marker.markerPoint.y - 58}
                                width="56"
                                height="56"
                                pointerEvents="none"
                              />
                              <circle cx={marker.markerPoint.x} cy={marker.markerPoint.y} r="8" fill="#2563eb" stroke="#ffffff" strokeWidth="2" />
                            </g>
                          ))}
                        </svg>
                      )}
                      {(() => {
                        const marker = mappedUserMarkers.find((m) => m.phoneKey === hoveredUserPhone);
                        if (!marker) return null;
                        const markerXPercent = (marker.markerPoint.x / FLOW_VB_W) * 100;
                        const tooltipTransform =
                          markerXPercent > 72 ? "translate(calc(-100% - 12px), -16px)" : "translate(12px, -16px)";
                        return (
                          <div
                            className="absolute z-30 w-56 rounded-xl border border-border/70 bg-[#121620]/95 text-white shadow-2xl p-3 pointer-events-none"
                            style={{ left: `${markerXPercent}%`, top: `${(marker.markerPoint.y / FLOW_VB_H) * 100}%`, transform: tooltipTransform }}
                          >
                            <p className="text-xs font-semibold tracking-wide">User Position</p>
                            <div className="mt-2 space-y-1.5 text-[11px]">
                              <div className="flex items-center justify-between">
                                <span className="text-white/70">Phone</span>
                                <span className="font-semibold">{marker.record.phoneNumber}</span>
                              </div>
                              <div className="flex items-center justify-between">
                                <span className="text-white/70">Lat/Lon</span>
                                <span className="font-semibold">
                                  {marker.record.coordinates.latitude}, {marker.record.coordinates.longitude}
                                </span>
                              </div>
                            </div>
                          </div>
                        );
                      })()}
                      {/* Crowd flow overlay (only when Digital Twin is on) */}
                      {digitalTwin && (
                        <CrowdFlowOverlay
                          hybFobCount={hybFobCount}
                          midFobCount={midFobCount}
                          kzjFobCount={kzjFobCount}
                          preserveAspectRatio={isSvgFullscreen ? "none" : "xMidYMid meet"}
                        />
                      )}

                      {/* Camera hover tooltip */}
                      {hoveredCamera && tooltipPos && (
                        <div
                          className="absolute z-30 w-56 rounded-xl border border-border/70 bg-[#121620]/95 text-white shadow-2xl p-3 pointer-events-none"
                          style={{ left: `${tooltipPos.left}px`, top: `${tooltipPos.top}px` }}
                        >
                          <p className="text-xs font-semibold tracking-wide">
                            {(hoveredCameraId && CAMERA_TITLES[hoveredCameraId.trim()]) || CAMERA_TITLES[hoveredCamera.camera_id] || hoveredCamera.camera_id}
                          </p>
                          <div className="mt-2 space-y-1.5 text-[11px]">
                            <div className="flex items-center justify-between">
                              <span className="text-white/70">Count</span>
                              <span className="font-semibold">{hoveredCamera.people_count ?? 0}</span>
                            </div>
                            <div className="flex items-center justify-between">
                              <span className="text-white/70">Density</span>
                              <span className="font-semibold">
                                {hoveredCamera.density_level || getDensityLevel(hoveredCamera.density_avg || 0)}
                              </span>
                            </div>
                            <div className="flex items-center justify-between">
                              <span className="text-white/70">Motion</span>
                              <span className="font-semibold">
                                {hoveredCamera.motion_level || getMotionLevel(hoveredCamera.motion_intensity || 0)}
                              </span>
                            </div>
                            <div className="flex items-center justify-between">
                              <span className="text-white/70">Risk</span>
                              <span className="font-semibold text-white">
                                {hoveredCamera.risk_level?.toUpperCase() || getRiskLevel(hoveredCamera.risk_score || 0)}
                              </span>
                            </div>
                          </div>
                        </div>
                      )}
                      {/* Status Indicator Tooltip - Removed in favor of SVG Cards per user request */}

                    </div>
                    </div>

                    {/* ── Google Map station view ── */}
                    <div
                      style={{ display: dashboardTab === 'map' ? undefined : 'none' }}
                      className="w-full h-full min-h-[70vh] lg:min-h-[80vh]"
                    >
                      <StationGoogleMap
                        trackingUsers={trackingUsers}
                        isActive={dashboardTab === 'map'}
                        className="w-full h-full min-h-[70vh] lg:min-h-[80vh]"
                      />
                    </div>

                    {/* ── Live camera stream panel (top-right corner; lives inside the fullscreen element so it stays visible in fullscreen too) ── */}
                    {liveStreamCameraId && (
                      <div
                        className={
                          isLiveStreamMaximized
                            ? "fixed inset-0 z-[100] flex flex-col rounded-none border-0 bg-[#0f172a] shadow-2xl overflow-hidden"
                            : "absolute top-20 right-4 z-50 w-[320px] sm:w-[380px] rounded-2xl border border-border/50 bg-[#0f172a] shadow-2xl overflow-hidden"
                        }
                      >
                        <div className="flex items-center justify-between px-3 py-2 border-b border-border/50 shrink-0">
                          <p className="text-xs font-semibold text-white tracking-wide truncate pr-2">
                            {CAMERA_TITLES[liveStreamCameraId] || liveStreamCameraId}
                          </p>
                          <div className="flex items-center gap-2 shrink-0">
                            <button
                              onClick={() => setIsLiveStreamMaximized((prev) => !prev)}
                              className="p-1 rounded-full border border-border/70 text-white hover:bg-white/10 transition-colors"
                              aria-label={isLiveStreamMaximized ? "Exit full screen" : "View full screen"}
                              title={isLiveStreamMaximized ? "Exit full screen" : "View full screen"}
                            >
                              {isLiveStreamMaximized ? (
                                <Minimize2 className="h-3.5 w-3.5" />
                              ) : (
                                <Maximize2 className="h-3.5 w-3.5" />
                              )}
                            </button>
                            <button
                              onClick={closeLiveStream}
                              className="p-1 rounded-full border border-border/70 text-white hover:bg-white/10 transition-colors"
                              aria-label="Close live camera stream"
                              title="Close"
                            >
                              <X className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        </div>
                        <div
                          className={
                            isLiveStreamMaximized
                              ? "flex items-center justify-center bg-black flex-1 min-h-0"
                              : "flex items-center justify-center bg-black aspect-video"
                          }
                        >
                          {liveStreamStatus === 'connecting' && (
                            <div className="flex flex-col items-center gap-2 text-white/70">
                              <div className="loader" />
                              <p className="text-[10px] uppercase tracking-widest">Connecting…</p>
                            </div>
                          )}
                          {liveStreamStatus === 'error' && (
                            <div className="flex flex-col items-center gap-2 px-4 text-center text-white/70">
                              <p className="text-xs font-medium text-red-400">Stream unavailable</p>
                              <button
                                onClick={() => openLiveStream(liveStreamCameraId)}
                                className="mt-1 px-2.5 py-1 rounded-lg border border-border/70 text-[10px] font-medium text-white hover:bg-white/10 transition-colors"
                              >
                                Retry
                              </button>
                            </div>
                          )}
                          {liveStreamStatus === 'ready' && (
                            <img
                              key={`${liveStreamCameraId}-${liveStreamAttempt}`}
                              src={rtspApi.getLiveStreamUrl(liveStreamCameraId)}
                              alt={`Live stream: ${CAMERA_TITLES[liveStreamCameraId] || liveStreamCameraId}`}
                              className="w-full h-full object-contain"
                              onError={() => setLiveStreamStatus('error')}
                            />
                          )}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* TRAIN SCHEDULE – side panel on the right of the svg */}
                  {showTrainSchedule && (
                    <div className="flex flex-col border-l border-border/50 card-black-10 backdrop-blur-sm z-30 min-h-0">
                      <UpcomingTrains variant="overlay" />
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* ================= CHART + ACTIVE RISK PANEL (commented out) ================= */}
        {/*
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 lg:gap-6">
          <div className="w-full">
            <FOBPeopleCountChart
              currentCount={totalPeople}
              currentDensity={avgDensity}
              title={`${selectedFOB.id} FOB Total Footfall`}
              fobId={selectedFOB.id}
              minimalHeader={true}
            />
          </div>
          <div className="w-full">
            <ActiveRiskPanel
              highRiskZones={highRiskZones}
              alerts={alerts}
              cameras={cameras}
              onAcknowledge={acknowledgeAlert}
              alertLimit={4}
            />
          </div>
        </div>
        */}
      </div>
    </PageLayout>
  );
}
