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
import BulletCamIcon from "@/assets/Bullet.png";
import DomeCamIcon from "@/assets/Dome.png";
import PtzCamIcon from "@/assets/Ptz.png";
import {
  LIVE_VIEWBOX_HEIGHT,
  VIEWBOX_WIDTH,
} from "@/data/secLayoutLiveBoxes";

import { CameraAnalytics, ZoneAnalytics } from "@/types/zone";
import { LIVE_CAMERA_IDS, CAMERA_TITLES, CAMERA_BY_ID } from "@/data/cameras";


// Each source PNG is an 800x800 canvas, but the drawn glyph occupies a different
// portion of it per type (the bullet icon is wide/short, dome & ptz are narrow/tall).
// Rendering all three at the same width/height box therefore makes them look like
// different sizes. `bbox` is the tight pixel rect of the actual artwork in each PNG
// (measured once from the source files) so we can scale by its longest side and
// center it, making every camera-type icon read as the same visual size.
const CAM_TYPE_ICON_NATURAL_SIZE = 800;
// Single source of truth for every camera-type glyph's on-map size (FOB bullet-cam
// glyph and the bullet/dome/ptz PNGs alike) — change this one value to resize all of them.
const CAMERA_TYPE_ICON_SIZE = 35;
// The angle (clockwise degrees, 0 = up/12 o'clock) each source PNG's glyph
// already faces by default, so it can be rotated to match a camera's real-world
// facing direction: the bullet lens points left, the dome's curved face points
// right, and the PTZ head sits on top pointing up.
const CAM_TYPE_ICONS: Record<string, { url: string; bbox: { x: number; y: number; w: number; h: number }; defaultAngle: number }> = {
  static: { url: BulletCamIcon, bbox: { x: 180, y: 280, w: 491, h: 241 }, defaultAngle: 270 },
  dome: { url: DomeCamIcon, bbox: { x: 310, y: 200, w: 211, h: 401 }, defaultAngle: 90 },
  ptz: { url: PtzCamIcon, bbox: { x: 300, y: 180, w: 201, h: 391 }, defaultAngle: 0 },
};

// Maps a camera's free-text `direction` (e.g. "left", "up/slant to left") to a
// clockwise angle in the same 0 = up system as `defaultAngle` above.
const DIRECTION_ANGLES: Array<{ match: RegExp; angle: number }> = [
  { match: /up.*left|left.*up/, angle: 315 },
  { match: /up.*right|right.*up/, angle: 45 },
  { match: /down.*left|left.*down/, angle: 225 },
  { match: /down.*right|right.*down/, angle: 135 },
  { match: /up/, angle: 0 },
  { match: /right/, angle: 90 },
  { match: /down/, angle: 180 },
  { match: /left/, angle: 270 },
];

function directionToAngle(direction: string | null | undefined): number | null {
  if (!direction) return null;
  const normalized = direction.toLowerCase();
  const entry = DIRECTION_ANGLES.find(({ match }) => match.test(normalized));
  return entry ? entry.angle : null;
}

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
const FLOW_VB_W = 2100;
const FLOW_VB_H = 1856;

// FOB centre-X positions (re-measured from the current sec-layout-1-2-layout.svg
// FOB bridge rects — HYD/NEW KZJ/KZJ are x=370/1300/1680, width=130 each — after
// the platform/facility repositioning moved them from their old x=355/1355/1655).
const FOB_HYB_CX = 435;
const FOB_MID_CX = 1365;
const FOB_KZJ_CX = 1745;

// Flow path Y levels
const SPINE_Y = 330;   // horizontal spine in the white gap above PF-1
const ENTRY_TOP_Y = 260;   // Gate 4 booking office drop-in Y (below count)
const FOB_BOTTOM_Y = 470;  // stop above the person icon
// FOB_ROUTE_TOP_Y / FOB_ROUTE_BOTTOM_Y re-measured against the FOB bridge rects'
// actual rendered top/bottom edge (y=345/28-offset to y=1325/28-offset -> 373/1353)
// after the same repositioning.
const FOB_ROUTE_TOP_Y = 373;  // stop at the top outline of the FOB box
const FOB_ROUTE_BOTTOM_Y = 1353;  // stop at the bottom outline of the FOB box
const ENTRY_SOURCE_X = 485;  // Gate 4 booking office X
const ENTRY_2A_SOURCE_X = 1010; // Gate 2A booking counter X

// The line has a 26-wide glow layer around its centre (±13), so a bare few-px
// gap to either neighbour still reads as touching. There's only ~60px of clear
// space here (PF10 bottom at 1348, South Block/Gate 6/VIP Entry Gate tops at
// ~1408) to fit the spine + its glow into, so 1380 splits that gap evenly
// instead of matching SPINE_Y's much roomier ~40px margin at the top.
const SPINE_BOTTOM_Y = 1380; // bottom spine below PF10, above the south-side facilities
const ENTRY_BOTTOM_Y = 1430; // drop-up Y for Gate 6 and 8
// Gate 6's booking-office hitbox (cam_hyb_booking_gate6) is now x=608 width=150,
// centre 683 — was 770 before the facility repositioning moved it.
const ENTRY_6_SOURCE_X = 683; // Gate 6 X
const ENTRY_8_SOURCE_X = 1425; // Gate 8 X

// CORRECTED: Threshold value for detecting high crowd density in FOBs (120 people)
const FOB_THRESHOLD = 120;

const CAMERA_DATA_SOURCE_BY_REGION: Record<string, string> = {};

const HYD_CAMERA_IDS = [
  "cam_middle_fob_4_5",
  "cam_pf1_fob_kzj",
  "cam_hyb_pf1_a",
];

const KZJ_NEW_CAMERA_ID = "cam_mid_fob_pf1";

const KZJ_CAMERA_IDS = [
  "cam_kzj_pf1_fob_pf10",
  "cam_kzj_pf1_fob_kzj",
];

type SvgPoint = {
  x: number;
  y: number;
};

type GeoPoint = {
  lat: number;
  lon: number;
};

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

  return Math.max(
    MARKER_MIN_X,
    Math.min(MARKER_MAX_X, adjusted)
  );
};

// ─── Lat/lon → SVG mapping ─────────────────────────────────────────────────
const PF1_SVG_RECT = {
  left: 140,
  right: 1840,
  top: 348,
  bottom: 438,
};

const PF10_SVG_RECT = {
  left: 140,
  right: 1840,
  top: 1248,
  bottom: 1338,
};

const STATION_TOP_SVG_Y = 90;

const PF1_GEO = {
  leftUpper: { lat: 17.432936, lon: 78.499125 },
  leftBottom: { lat: 17.432834, lon: 78.499123 },
  rightUpper: { lat: 17.433767, lon: 78.503199 },
  rightBottom: { lat: 17.4339786, lon: 78.5032991 },
};

const PF10_GEO = {
  leftUpper: { lat: 17.432222, lon: 78.499669 },
  leftBottom: { lat: 17.432208, lon: 78.499205 },
  rightUpper: { lat: 17.43328, lon: 78.504644 },
  rightBottom: { lat: 17.433266, lon: 78.504645 },
};

const STATION_GEO = {
  topLeft: { lat: 17.433748, lon: 78.499739 },
  topRight: { lat: 17.434623, lon: 78.504426 },
};

const clamp01 = (n: number) =>
  Math.min(1, Math.max(0, n));

type LocalFitPoint = SvgPoint & {
  u: number;
  v: number;
};

type SvgRect = {
  left: number;
  right: number;
  top: number;
  bottom: number;
};

const makeLocalFit = (
  origin: GeoPoint,
  uCorner: GeoPoint,
  vCorner: GeoPoint,
  rect: SvgRect
) => {
  const uAxis = {
    lon: uCorner.lon - origin.lon,
    lat: uCorner.lat - origin.lat,
  };

  const vAxis = {
    lon: vCorner.lon - origin.lon,
    lat: vCorner.lat - origin.lat,
  };

  const det =
    uAxis.lon * vAxis.lat -
    uAxis.lat * vAxis.lon;

  return (
    latitude: number,
    longitude: number
  ): LocalFitPoint => {
    const dLon = longitude - origin.lon;
    const dLat = latitude - origin.lat;

    const u =
      (dLon * vAxis.lat -
        dLat * vAxis.lon) /
      det;

    const v =
      (uAxis.lon * dLat -
        uAxis.lat * dLon) /
      det;

    return {
      x:
        rect.left +
        clamp01(u) *
          (rect.right - rect.left),

      y:
        rect.top +
        clamp01(v) *
          (rect.bottom - rect.top),

      u,
      v,
    };
  };
};

const entranceFit = makeLocalFit(
  STATION_GEO.topLeft,
  STATION_GEO.topRight,
  PF1_GEO.leftUpper,
  {
    left: PF1_SVG_RECT.left,
    right: PF1_SVG_RECT.right,
    top: STATION_TOP_SVG_Y,
    bottom: PF1_SVG_RECT.top,
  }
);

const pf1Fit = makeLocalFit(
  PF1_GEO.leftUpper,
  PF1_GEO.rightUpper,
  PF1_GEO.leftBottom,
  {
    left: PF1_SVG_RECT.left,
    right: PF1_SVG_RECT.right,
    top: PF1_SVG_RECT.top,
    bottom: PF1_SVG_RECT.bottom,
  }
);

const middleFit = makeLocalFit(
  PF1_GEO.leftBottom,
  PF1_GEO.rightBottom,
  PF10_GEO.leftUpper,
  {
    left: PF1_SVG_RECT.left,
    right: PF1_SVG_RECT.right,
    top: PF1_SVG_RECT.bottom,
    bottom: PF10_SVG_RECT.top,
  }
);

const pf10Fit = makeLocalFit(
  PF10_GEO.leftUpper,
  PF10_GEO.rightUpper,
  PF10_GEO.leftBottom,
  {
    left: PF10_SVG_RECT.left,
    right: PF10_SVG_RECT.right,
    top: PF10_SVG_RECT.top,
    bottom: PF10_SVG_RECT.bottom,
  }
);

const BAND_TOLERANCE = 0.12;

const isWithinBandTolerance = (
  p: LocalFitPoint
) =>
  p.u >= -BAND_TOLERANCE &&
  p.u <= 1 + BAND_TOLERANCE &&
  p.v >= -BAND_TOLERANCE &&
  p.v <= 1 + BAND_TOLERANCE;

const bandViolation = (p: LocalFitPoint) =>
  Math.max(0, -p.u) +
  Math.max(0, p.u - 1) +
  Math.max(0, -p.v) +
  Math.max(0, p.v - 1);

const toSvgPointFromLatLon = (
  latitude: number,
  longitude: number
): SvgPoint => {
  const candidates = [
    pf1Fit(latitude, longitude),
    pf10Fit(latitude, longitude),
    middleFit(latitude, longitude),
    entranceFit(latitude, longitude),
  ];

  const confidentMatch =
    candidates.find(
      isWithinBandTolerance
    );

  if (confidentMatch) {
    return confidentMatch;
  }

  return candidates.reduce(
    (best, candidate) =>
      bandViolation(candidate) <
      bandViolation(best)
        ? candidate
        : best
  );
};

const HYB_GEO_BOUNDS = {
  minLat: 17.42,
  maxLat: 17.45,
  minLon: 78.49,
  maxLon: 78.51,
};

const isWithinHybBounds = (
  lat: number,
  lon: number
) =>
  lat >= HYB_GEO_BOUNDS.minLat &&
  lat <= HYB_GEO_BOUNDS.maxLat &&
  lon >= HYB_GEO_BOUNDS.minLon &&
  lon <= HYB_GEO_BOUNDS.maxLon;

const normalizeLatLon = (
  lat: number,
  lon: number
) => {
  if (isWithinHybBounds(lat, lon)) {
    return { lat, lon };
  }

  if (isWithinHybBounds(lon, lat)) {
    return {
      lat: lon,
      lon: lat,
    };
  }

  return {
    lat,
    lon,
  };
};

const getUserIdentityKey = (
  rec: {
    phoneNumber?: string;
  }
) => {
  const raw =
    (rec.phoneNumber || "").trim();

  return raw || null;
};

// ─── Spread overlapping user markers ─────────────────────────────────
const MARKER_CLUSTER_RADIUS = 34;
const MARKER_SPREAD_SPACING = 40;

const spreadOverlappingMarkers = (
  markers: MappedUserMarker[]
): MappedUserMarker[] => {
  const used = new Array(
    markers.length
  ).fill(false);

  const result: MappedUserMarker[] =
    new Array(markers.length);

  for (
    let i = 0;
    i < markers.length;
    i++
  ) {
    if (used[i]) continue;

    const clusterIdx = [i];

    used[i] = true;

    for (
      let j = i + 1;
      j < markers.length;
      j++
    ) {
      if (used[j]) continue;

      const dx =
        markers[j].markerPoint.x -
        markers[i].markerPoint.x;

      const dy =
        markers[j].markerPoint.y -
        markers[i].markerPoint.y;

      if (
        Math.sqrt(
          dx * dx +
            dy * dy
        ) <=
        MARKER_CLUSTER_RADIUS
      ) {
        clusterIdx.push(j);
        used[j] = true;
      }
    }

    if (clusterIdx.length === 1) {
      result[i] = markers[i];
      continue;
    }

    const cx =
      clusterIdx.reduce(
        (sum, idx) =>
          sum +
          markers[idx].markerPoint.x,
        0
      ) /
      clusterIdx.length;

    const cy =
      clusterIdx.reduce(
        (sum, idx) =>
          sum +
          markers[idx].markerPoint.y,
        0
      ) /
      clusterIdx.length;

    const radius = Math.max(
      MARKER_SPREAD_SPACING,
      (clusterIdx.length *
        MARKER_SPREAD_SPACING) /
        (2 * Math.PI)
    );

    clusterIdx.forEach(
      (idx, k) => {
        const angle =
          (2 * Math.PI * k) /
          clusterIdx.length;

        result[idx] = {
          ...markers[idx],
          markerPoint: {
            x:
              cx +
              Math.cos(angle) *
                radius,
            y:
              cy +
              Math.sin(angle) *
                radius,
          },
        };
      }
    );
  }

  return result;
};

// ─── CrowdFlowOverlay ─────────────────────────────────
interface FlowOverlayProps {
  hybFobCount: number;
  midFobCount: number;
  kzjFobCount: number;
  preserveAspectRatio?: string;
}

function CrowdFlowOverlay({
  hybFobCount,
  midFobCount,
  kzjFobCount,
  preserveAspectRatio = "xMidYMid meet",
}: FlowOverlayProps) {
  const fobs = useMemo(
    () => [
      {
        id: "HYB",
        fobX: FOB_HYB_CX,
        count: hybFobCount,
      },
      {
        id: "MID",
        fobX: FOB_MID_CX,
        count: midFobCount,
      },
      {
        id: "KZJ",
        fobX: FOB_KZJ_CX,
        count: kzjFobCount,
      },
    ],
    [
      hybFobCount,
      midFobCount,
      kzjFobCount,
    ]
  );

  const anyCongest = useMemo(
    () =>
      fobs.some(
        (f) =>
          f.count >
          FOB_THRESHOLD
      ),
    [fobs]
  );

  const spineColor = "#50C878";
  const spineGlow = "url(#flo-glow-g)";
  const entryColor =
    anyCongest
      ? "#e2584f"
      : spineColor;
  const entryGlow =
    anyCongest
      ? "url(#flo-glow-r)"
      : spineGlow;

  return (
    <svg
      className="absolute top-0 left-0 w-full h-full pointer-events-none"
      viewBox={`0 0 ${FLOW_VB_W} ${FLOW_VB_H}`}
      preserveAspectRatio={
        preserveAspectRatio
      }
      style={{ zIndex: 20 }}
    >
      <defs>
        <style>{`
          @keyframes flow-dash {
            from {
              stroke-dashoffset: 48;
            }
            to {
              stroke-dashoffset: 0;
            }
          }

          @keyframes badge-pulse {
            0%, 100% {
              opacity: 1;
            }

            50% {
              opacity: 0.55;
            }
          }

          .fda {
            animation:
              flow-dash 0.8s linear infinite;
          }

          .fdas {
            animation:
              flow-dash 1.6s linear infinite;
          }

          .bp {
            animation:
              badge-pulse 1.3s ease-in-out infinite;
          }
        `}</style>

        <filter
          id="flo-glow-g"
          x="-40%"
          y="-40%"
          width="180%"
          height="180%"
        >
          <feGaussianBlur
            stdDeviation="6"
            result="b"
          />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>

        <filter
          id="flo-glow-r"
          x="-40%"
          y="-40%"
          width="180%"
          height="180%"
        >
          <feGaussianBlur
            stdDeviation="6"
            result="b"
          />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>

        <filter
          id="flo-shadow"
          x="-20%"
          y="-40%"
          width="140%"
          height="200%"
        >
          <feDropShadow
            dx="0"
            dy="2"
            stdDeviation="4"
            floodColor="#000"
            floodOpacity="0.6"
          />
        </filter>

        <marker
          id="flo-arrow-green"
          viewBox="0 0 12 12"
          refX="9"
          refY="6"
          markerWidth="6"
          markerHeight="6"
          orient="auto-start-reverse"
        >
          <path
            d="M1 1 L11 6 L1 11 Z"
            fill="#50C878"
          />
        </marker>

        <marker
          id="flo-arrow-red"
          viewBox="0 0 12 12"
          refX="9"
          refY="6"
          markerWidth="6"
          markerHeight="6"
          orient="auto-start-reverse"
        >
          <path
            d="M1 1 L11 6 L1 11 Z"
            fill="#e2584f"
          />
        </marker>

        <marker
          id="flo-arrow-w"
          viewBox="0 0 12 12"
          refX="9"
          refY="6"
          markerWidth="4"
          markerHeight="4"
          orient="auto-start-reverse"
        >
          <path
            d="M1 1 L11 6 L1 11 Z"
            fill="rgba(255,255,255,0.9)"
          />
        </marker>
      </defs>

      {/* Gate 4A → top spine */}
      <g>
        <line
          x1={ENTRY_SOURCE_X}
          y1={ENTRY_TOP_Y}
          x2={ENTRY_SOURCE_X}
          y2={SPINE_Y}
          stroke={entryColor}
          strokeOpacity="0.20"
          strokeWidth="26"
          strokeLinecap="round"
          filter={entryGlow}
        />

        <line
          x1={ENTRY_SOURCE_X}
          y1={ENTRY_TOP_Y}
          x2={ENTRY_SOURCE_X}
          y2={SPINE_Y}
          stroke="#0b3b1b"
          strokeOpacity="0.9"
          strokeWidth="14"
          strokeLinecap="round"
        />

        <line
          x1={ENTRY_SOURCE_X}
          y1={ENTRY_TOP_Y}
          x2={ENTRY_SOURCE_X}
          y2={SPINE_Y}
          stroke={entryColor}
          strokeWidth="10"
          strokeLinecap="round"
        />

        <line
          x1={ENTRY_SOURCE_X}
          y1={ENTRY_TOP_Y}
          x2={ENTRY_SOURCE_X}
          y2={SPINE_Y}
          stroke="rgba(255,255,255,0.9)"
          strokeWidth="4"
          strokeDasharray="2 14"
          strokeLinecap="round"
          className={
            anyCongest
              ? "fdas"
              : "fda"
          }
        />
      </g>

      {/* Gate 2A → top spine */}
      <g>
        <line
          x1={ENTRY_2A_SOURCE_X}
          y1={ENTRY_TOP_Y}
          x2={ENTRY_2A_SOURCE_X}
          y2={SPINE_Y}
          stroke={entryColor}
          strokeOpacity="0.20"
          strokeWidth="26"
          strokeLinecap="round"
          filter={entryGlow}
        />

        <line
          x1={ENTRY_2A_SOURCE_X}
          y1={ENTRY_TOP_Y}
          x2={ENTRY_2A_SOURCE_X}
          y2={SPINE_Y}
          stroke="#0b3b1b"
          strokeOpacity="0.9"
          strokeWidth="14"
          strokeLinecap="round"
        />

        <line
          x1={ENTRY_2A_SOURCE_X}
          y1={ENTRY_TOP_Y}
          x2={ENTRY_2A_SOURCE_X}
          y2={SPINE_Y}
          stroke={entryColor}
          strokeWidth="10"
          strokeLinecap="round"
        />

        <line
          x1={ENTRY_2A_SOURCE_X}
          y1={ENTRY_TOP_Y}
          x2={ENTRY_2A_SOURCE_X}
          y2={SPINE_Y}
          stroke="rgba(255,255,255,0.9)"
          strokeWidth="4"
          strokeDasharray="2 14"
          strokeLinecap="round"
          className={
            anyCongest
              ? "fdas"
              : "fda"
          }
        />
      </g>

      {/* Gate 6 */}
      <g>
        <line
          x1={ENTRY_6_SOURCE_X}
          y1={ENTRY_BOTTOM_Y}
          x2={ENTRY_6_SOURCE_X}
          y2={SPINE_BOTTOM_Y}
          stroke={entryColor}
          strokeOpacity="0.20"
          strokeWidth="26"
          strokeLinecap="round"
          filter={entryGlow}
        />

        <line
          x1={ENTRY_6_SOURCE_X}
          y1={ENTRY_BOTTOM_Y}
          x2={ENTRY_6_SOURCE_X}
          y2={SPINE_BOTTOM_Y}
          stroke="#0b3b1b"
          strokeOpacity="0.9"
          strokeWidth="14"
          strokeLinecap="round"
        />

        <line
          x1={ENTRY_6_SOURCE_X}
          y1={ENTRY_BOTTOM_Y}
          x2={ENTRY_6_SOURCE_X}
          y2={SPINE_BOTTOM_Y}
          stroke={entryColor}
          strokeWidth="10"
          strokeLinecap="round"
        />

        <line
          x1={ENTRY_6_SOURCE_X}
          y1={ENTRY_BOTTOM_Y}
          x2={ENTRY_6_SOURCE_X}
          y2={SPINE_BOTTOM_Y}
          stroke="rgba(255,255,255,0.9)"
          strokeWidth="4"
          strokeDasharray="2 14"
          strokeLinecap="round"
          className={
            anyCongest
              ? "fdas"
              : "fda"
          }
        />
      </g>

      {/* Gate 8 */}
      <g>
        <line
          x1={ENTRY_8_SOURCE_X}
          y1={ENTRY_BOTTOM_Y}
          x2={ENTRY_8_SOURCE_X}
          y2={SPINE_BOTTOM_Y}
          stroke={entryColor}
          strokeOpacity="0.20"
          strokeWidth="26"
          strokeLinecap="round"
          filter={entryGlow}
        />

        <line
          x1={ENTRY_8_SOURCE_X}
          y1={ENTRY_BOTTOM_Y}
          x2={ENTRY_8_SOURCE_X}
          y2={SPINE_BOTTOM_Y}
          stroke="#0b3b1b"
          strokeOpacity="0.9"
          strokeWidth="14"
          strokeLinecap="round"
        />

        <line
          x1={ENTRY_8_SOURCE_X}
          y1={ENTRY_BOTTOM_Y}
          x2={ENTRY_8_SOURCE_X}
          y2={SPINE_BOTTOM_Y}
          stroke={entryColor}
          strokeWidth="10"
          strokeLinecap="round"
        />

        <line
          x1={ENTRY_8_SOURCE_X}
          y1={ENTRY_BOTTOM_Y}
          x2={ENTRY_8_SOURCE_X}
          y2={SPINE_BOTTOM_Y}
          stroke="rgba(255,255,255,0.9)"
          strokeWidth="4"
          strokeDasharray="2 14"
          strokeLinecap="round"
          className={
            anyCongest
              ? "fdas"
              : "fda"
          }
        />
      </g>

      {/* Top spine */}
      <g>
        <line
          x1={FOB_HYB_CX}
          y1={SPINE_Y}
          x2={FOB_KZJ_CX}
          y2={SPINE_Y}
          stroke={spineColor}
          strokeOpacity="0.20"
          strokeWidth="26"
          strokeLinecap="round"
          filter={spineGlow}
        />

        <line
          x1={FOB_HYB_CX}
          y1={SPINE_Y}
          x2={FOB_KZJ_CX}
          y2={SPINE_Y}
          stroke="#0b3b1b"
          strokeOpacity="0.9"
          strokeWidth="14"
          strokeLinecap="round"
        />

        <line
          x1={FOB_HYB_CX}
          y1={SPINE_Y}
          x2={FOB_KZJ_CX}
          y2={SPINE_Y}
          stroke={spineColor}
          strokeWidth="10"
          strokeLinecap="round"
        />

        <line
          x1={FOB_HYB_CX}
          y1={SPINE_Y}
          x2={FOB_KZJ_CX}
          y2={SPINE_Y}
          stroke="rgba(255,255,255,0.9)"
          strokeWidth="4"
          strokeDasharray="2 14"
          strokeLinecap="round"
          className="fda"
        />

        {fobs.map(
          ({
            id,
            fobX,
            count,
          }) => {
            if (
              count <=
              FOB_THRESHOLD
            ) {
              return null;
            }

            const x1 =
              Math.min(
                ENTRY_SOURCE_X,
                fobX
              );

            const x2 =
              Math.max(
                ENTRY_SOURCE_X,
                fobX
              );

            return (
              <g
                key={`spine-congested-${id}`}
              >
                <line
                  x1={x1}
                  y1={SPINE_Y}
                  x2={x2}
                  y2={SPINE_Y}
                  stroke="#e2584f"
                  strokeOpacity="0.20"
                  strokeWidth="26"
                  strokeLinecap="round"
                  filter="url(#flo-glow-r)"
                />

                <line
                  x1={x1}
                  y1={SPINE_Y}
                  x2={x2}
                  y2={SPINE_Y}
                  stroke="#0b3b1b"
                  strokeOpacity="0.9"
                  strokeWidth="14"
                  strokeLinecap="round"
                />

                <line
                  x1={x1}
                  y1={SPINE_Y}
                  x2={x2}
                  y2={SPINE_Y}
                  stroke="#e2584f"
                  strokeWidth="10"
                  strokeLinecap="round"
                />

                <line
                  x1={x1}
                  y1={SPINE_Y}
                  x2={x2}
                  y2={SPINE_Y}
                  stroke="rgba(255,255,255,0.9)"
                  strokeWidth="4"
                  strokeDasharray="2 14"
                  strokeLinecap="round"
                  className="fdas"
                />
              </g>
            );
          }
        )}
      </g>

      {/* Bottom spine */}
      <g>
        <line
          x1={FOB_HYB_CX}
          y1={SPINE_BOTTOM_Y}
          x2={FOB_KZJ_CX}
          y2={SPINE_BOTTOM_Y}
          stroke={spineColor}
          strokeOpacity="0.20"
          strokeWidth="26"
          strokeLinecap="round"
          filter={spineGlow}
        />

        <line
          x1={FOB_HYB_CX}
          y1={SPINE_BOTTOM_Y}
          x2={FOB_KZJ_CX}
          y2={SPINE_BOTTOM_Y}
          stroke="#0b3b1b"
          strokeOpacity="0.9"
          strokeWidth="14"
          strokeLinecap="round"
        />

        <line
          x1={FOB_HYB_CX}
          y1={SPINE_BOTTOM_Y}
          x2={FOB_KZJ_CX}
          y2={SPINE_BOTTOM_Y}
          stroke={spineColor}
          strokeWidth="10"
          strokeLinecap="round"
        />

        <line
          x1={FOB_HYB_CX}
          y1={SPINE_BOTTOM_Y}
          x2={FOB_KZJ_CX}
          y2={SPINE_BOTTOM_Y}
          stroke="rgba(255,255,255,0.9)"
          strokeWidth="4"
          strokeDasharray="2 14"
          strokeLinecap="round"
          className="fda"
        />

        {fobs.map(
          ({
            id,
            fobX,
            count,
          }) => {
            if (
              count <=
              FOB_THRESHOLD
            ) {
              return null;
            }

            const x1_g6 =
              Math.min(
                ENTRY_6_SOURCE_X,
                fobX
              );

            const x2_g6 =
              Math.max(
                ENTRY_6_SOURCE_X,
                fobX
              );

            const x1_g8 =
              Math.min(
                ENTRY_8_SOURCE_X,
                fobX
              );

            const x2_g8 =
              Math.max(
                ENTRY_8_SOURCE_X,
                fobX
              );

            return (
              <g
                key={`bottom-spine-congested-${id}`}
              >
                <line
                  x1={x1_g6}
                  y1={SPINE_BOTTOM_Y}
                  x2={x2_g6}
                  y2={SPINE_BOTTOM_Y}
                  stroke="#e2584f"
                  strokeOpacity="0.20"
                  strokeWidth="26"
                  strokeLinecap="round"
                  filter="url(#flo-glow-r)"
                />

                <line
                  x1={x1_g6}
                  y1={SPINE_BOTTOM_Y}
                  x2={x2_g6}
                  y2={SPINE_BOTTOM_Y}
                  stroke="#0b3b1b"
                  strokeOpacity="0.9"
                  strokeWidth="14"
                  strokeLinecap="round"
                />

                <line
                  x1={x1_g6}
                  y1={SPINE_BOTTOM_Y}
                  x2={x2_g6}
                  y2={SPINE_BOTTOM_Y}
                  stroke="#e2584f"
                  strokeWidth="10"
                  strokeLinecap="round"
                />

                <line
                  x1={x1_g6}
                  y1={SPINE_BOTTOM_Y}
                  x2={x2_g6}
                  y2={SPINE_BOTTOM_Y}
                  stroke="rgba(255,255,255,0.9)"
                  strokeWidth="4"
                  strokeDasharray="2 14"
                  strokeLinecap="round"
                  className="fdas"
                />

                <line
                  x1={x1_g8}
                  y1={SPINE_BOTTOM_Y}
                  x2={x2_g8}
                  y2={SPINE_BOTTOM_Y}
                  stroke="#e2584f"
                  strokeOpacity="0.20"
                  strokeWidth="26"
                  strokeLinecap="round"
                  filter="url(#flo-glow-r)"
                />

                <line
                  x1={x1_g8}
                  y1={SPINE_BOTTOM_Y}
                  x2={x2_g8}
                  y2={SPINE_BOTTOM_Y}
                  stroke="#0b3b1b"
                  strokeOpacity="0.9"
                  strokeWidth="14"
                  strokeLinecap="round"
                />

                <line
                  x1={x1_g8}
                  y1={SPINE_BOTTOM_Y}
                  x2={x2_g8}
                  y2={SPINE_BOTTOM_Y}
                  stroke="#e2584f"
                  strokeWidth="10"
                  strokeLinecap="round"
                />

                <line
                  x1={x1_g8}
                  y1={SPINE_BOTTOM_Y}
                  x2={x2_g8}
                  y2={SPINE_BOTTOM_Y}
                  stroke="rgba(255,255,255,0.9)"
                  strokeWidth="4"
                  strokeDasharray="2 14"
                  strokeLinecap="round"
                  className="fdas"
                />
              </g>
            );
          }
        )}
      </g>

      {/* Per-FOB vertical paths */}
      {fobs.map(
        ({
          id,
          fobX,
          count,
        }) => {
          const congested =
            count >
            FOB_THRESHOLD;

          const isAlt =
            anyCongest &&
            !congested;

          const color =
            congested
              ? "#e2584f"
              : "#50C878";

          const glowFilter =
            congested
              ? "url(#flo-glow-r)"
              : "url(#flo-glow-g)";

          const animCls =
            congested
              ? "fdas"
              : "fda";

        const vertPath = `M ${fobX} ${SPINE_Y} L ${fobX} ${FOB_ROUTE_TOP_Y}`;
        const badgeX = fobX;
        const badgeY = SPINE_Y + (FOB_BOTTOM_Y - SPINE_Y) * 0.38;

        return (
          <g key={id}>
            {/* Glow layer */}
        <path d={vertPath} fill="none" stroke={color} strokeOpacity="0.20"
              strokeWidth="26" strokeLinecap="butt" filter={glowFilter} />
        {/* Dark border */}
        <path d={vertPath} fill="none" stroke="#0b3b1b" strokeOpacity="0.9"
              strokeWidth="14" strokeLinecap="butt" />
        {/* Solid line */}
        <path d={vertPath} fill="none" stroke={color} strokeWidth="10"
              strokeLinecap="butt" />
        {/* Dotted inner path - animated dashed line */}
        <path d={vertPath} fill="none" stroke="rgba(255,255,255,0.9)"
              strokeWidth="4" strokeDasharray="2 14" strokeLinecap="butt"
              className={animCls} />

            {/* Short vertical drop into the FOB from the bottom spine */}
            <path d={`M ${fobX} ${FOB_ROUTE_BOTTOM_Y} L ${fobX} ${SPINE_BOTTOM_Y}`} fill="none" stroke={color} strokeOpacity="0.20"
              strokeWidth="26" strokeLinecap="butt" filter={glowFilter} />
            <path d={`M ${fobX} ${FOB_ROUTE_BOTTOM_Y} L ${fobX} ${SPINE_BOTTOM_Y}`} fill="none" stroke="#0b3b1b" strokeOpacity="0.9"
              strokeWidth="14" strokeLinecap="butt" />
            <path d={`M ${fobX} ${FOB_ROUTE_BOTTOM_Y} L ${fobX} ${SPINE_BOTTOM_Y}`} fill="none" stroke={color} strokeWidth="10"
              strokeLinecap="butt" />
            <path d={`M ${fobX} ${FOB_ROUTE_BOTTOM_Y} L ${fobX} ${SPINE_BOTTOM_Y}`} fill="none" stroke="rgba(255,255,255,0.9)"
              strokeWidth="4" strokeDasharray="2 14" strokeLinecap="butt"
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

              {isAlt && (
                <g
                  filter="url(#flo-shadow)"
                >
                  <rect
                    x={
                      badgeX -
                      102
                    }
                    y={
                      badgeY -
                      20
                    }
                    width="204"
                    height="34"
                    rx="17"
                    fill="#052e16"
                    stroke="#50C878"
                    strokeWidth="2"
                  />

                  <text
                    x={badgeX}
                    y={
                      badgeY +
                      3
                    }
                    fontFamily="Arial, sans-serif"
                    fontWeight="bold"
                    fontSize="15"
                    fill="#50C878"
                    textAnchor="middle"
                  >
                    ALTERNATE ROUTE
                  </text>
                </g>
              )}
            </g>
          );
        }
      )}
    </svg>
  );
}

// ─── LiveClock ────────────────────────────────────────────────────────────────
const LiveClock = () => {
  const [time, setTime] =
    useState(new Date());

  useEffect(() => {
    const timer =
      setInterval(
        () =>
          setTime(
            new Date()
          ),
        1000
      );

    return () =>
      clearInterval(timer);
  }, []);

  return (
    <span className="text-xs font-mono font-medium text-foreground">
      {time.toLocaleTimeString(
        "en-IN",
        {
          timeZone:
            "Asia/Kolkata",
          hour12: true,
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        }
      )}
    </span>
  );
};

const FOB_OPTIONS = [
  {
    id: "HYB",
    name: "Hyderabad FOB",
    shortName: "HYD",
  },
  {
    id: "KZJ",
    name: "Kazipet FOB",
    shortName: "KZJ",
  },
];

export default function Dashboard() {
  const [fobId, setFobId] =
    useState<string>("HYB");

  const [viewMode, setViewMode] =
    useState<
      | "cameraLayout"
      | "layout"
      | "live"
      | "withoutFobs"
    >("live");

  const [showTrainSchedule, setShowTrainSchedule] =
    useState(true);

  const [isSvgFullscreen, setIsSvgFullscreen] =
    useState(false);

  const [digitalTwin, setDigitalTwin] =
    useState(true);

  const [hoveredCameraId, setHoveredCameraId] =
    useState<string | null>(null);

  const [tooltipPos, setTooltipPos] =
    useState<{
      left: number;
      top: number;
    } | null>(null);

  const [liveStreamCameraId, setLiveStreamCameraId] =
    useState<string | null>(null);

  const [liveStreamStatus, setLiveStreamStatus] =
    useState<
      "connecting" |
      "ready" |
      "error"
    >("connecting");

  const [liveStreamAttempt, setLiveStreamAttempt] =
    useState(0);

  const [isLiveStreamMaximized, setIsLiveStreamMaximized] =
    useState(false);

  const [trackingUsers, setTrackingUsers] =
    useState<TrackingUserRecord[]>([]);

  const [hoveredUserPhone, setHoveredUserPhone] =
    useState<string | null>(null);

  const [dashboardTab, setDashboardTab] =
    useState<
      "layout" |
      "map"
    >("layout");

  const location =
    useLocation();

  const prevPathRef =
    useRef(location.pathname);

  const liveSvgRef =
    useRef<HTMLDivElement>(null);

  const svgScrollRef =
    useRef<HTMLDivElement>(null);

  const openLiveStream =
    useCallback(
      async (id: string) => {
        setLiveStreamCameraId(id);
        setLiveStreamStatus(
          "connecting"
        );
        setLiveStreamAttempt(
          (n) => n + 1
        );

        try {
          const status =
            await rtspApi.getCameraRuntimeStatus(
              id
            );

          if (
            status.runtime_status !==
            "running"
          ) {
            await rtspApi.startCamera(
              id
            );
          }

          setLiveStreamStatus(
            "ready"
          );
        } catch (err) {
          setLiveStreamStatus(
            "error"
          );
        }
      },
      []
    );

  const closeLiveStream =
    () => {
      setLiveStreamCameraId(
        null
      );

      setLiveStreamStatus(
        "connecting"
      );

      setIsLiveStreamMaximized(
        false
      );
    };

  const resetMapScroll =
    () => {
      const scroller =
        svgScrollRef.current;

      if (!scroller) return;

      scroller.scrollTop = 0;
      scroller.scrollLeft = 0;
    };

  const handleViewModeChange =
    (
      mode:
        | "cameraLayout"
        | "layout"
        | "live"
        | "withoutFobs"
    ) => {
      setViewMode(mode);

      requestAnimationFrame(
        () => {
          resetMapScroll();

          requestAnimationFrame(
            resetMapScroll
          );
        }
      );
    };

  const toggleSvgFullscreen =
    async () => {
      const target =
        document.getElementById(
          "dashboard-svg-stage"
        );

      if (!target) return;

      if (
        !document.fullscreenElement
      ) {
        try {
          await target.requestFullscreen();
        } catch {
          setIsSvgFullscreen(
            true
          );
        }

        return;
      }

      try {
        await document.exitFullscreen();
      } catch {
        setIsSvgFullscreen(
          false
        );
      }
    };

  useEffect(() => {
    const handleFullscreenChange =
      () => {
        setIsSvgFullscreen(
          Boolean(
            document.fullscreenElement?.id ===
              "dashboard-svg-stage"
          )
        );
      };

    document.addEventListener(
      "fullscreenchange",
      handleFullscreenChange
    );

    return () =>
      document.removeEventListener(
        "fullscreenchange",
        handleFullscreenChange
      );
  }, []);

  useEffect(() => {
    const svgEl =
      liveSvgRef.current?.querySelector(
        "svg"
      );

    if (!svgEl) return;

    if (isSvgFullscreen) {
      svgEl.setAttribute(
        "preserveAspectRatio",
        "none"
      );
    } else {
      svgEl.removeAttribute(
        "preserveAspectRatio"
      );
    }
  }, [
    isSvgFullscreen,
    viewMode,
    fobId,
  ]);

  const {
    zones: rawZones,
    isLoading,
    isConnected,
    refresh,
    lastUpdate,
    dataTimestamp,
  } =
    useZoneAnalytics({
      stationId: fobId,
      enableWebSocket: true,
    });

  useEffect(() => {
    if (
      location.pathname === "/" &&
      prevPathRef.current !== "/"
    ) {
      refresh();
    }

    prevPathRef.current =
      location.pathname;
  }, [
    location.pathname,
    refresh,
  ]);

  const {
    alerts,
    acknowledgeAlert,
    checkForAlerts,
  } =
    useAlerts();

  const { cameras } =
    useCameras();

  const selectedFOB =
    FOB_OPTIONS.find(
      (f) => f.id === fobId
    ) ||
    FOB_OPTIONS[0];

  const zones =
    useMemo(
      () => rawZones,
      [rawZones]
    );

  const globalRisk =
    useMemo(() => {
      if (!zones.length)
        return "LOW";

      if (
        zones.some(
          (z) =>
            z.risk_level ===
            "CRITICAL"
        )
      ) {
        return "CRITICAL";
      }

      if (
        zones.some(
          (z) =>
            z.risk_level ===
            "HIGH"
        )
      ) {
        return "HIGH";
      }

      if (
        zones.some(
          (z) =>
            z.risk_level ===
            "MEDIUM"
        )
      ) {
        return "MEDIUM";
      }

      return "LOW";
    }, [zones]);

  const highRiskZones =
    zones.filter(
      (z) =>
        z.risk_level ===
          "HIGH" ||
        z.risk_level ===
          "CRITICAL"
    );

  const riskCounts: RiskCounts =
    useMemo(
      () => ({
        LOW: zones.filter(
          (z) =>
            z.risk_level ===
            "LOW"
        ).length,

        MEDIUM: zones.filter(
          (z) =>
            z.risk_level ===
            "MEDIUM"
        ).length,

        HIGH: zones.filter(
          (z) =>
            z.risk_level ===
            "HIGH"
        ).length,

        CRITICAL: zones.filter(
          (z) =>
            z.risk_level ===
            "CRITICAL"
        ).length,
      }),
      [zones]
    );

  const totalPeople =
    zones.reduce(
      (acc, z) =>
        acc +
        (z.people_count ||
          0),
      0
    );

  const hybFobCount =
    zones.find(
      (z) =>
        z.zone_id ===
        "zone_hyb_fob"
    )?.people_count ||
    0;

  const kzjFobCount =
    zones.find(
      (z) =>
        z.zone_id ===
        "zone_kzj_fob"
    )?.people_count ||
    0;

  const midFobCount =
    zones.find(
      (z) =>
        z.zone_id ===
        "zone_mid_fob"
    )?.people_count ||
    0;

  const avgDensity =
    zones.length > 0
      ? zones.reduce(
          (a, z) =>
            a +
            (z.density_avg ||
              0),
          0
        ) / zones.length
      : 0;

  const dashboardStats =
    useMemo(() => {
      const avgMotionIntensity =
        zones.length > 0
          ? zones.reduce(
              (a, z) =>
                a +
                (z.motion_intensity ||
                  0),
              0
            ) /
            zones.length
          : 0;

      const avgRiskScore =
        zones.length > 0
          ? zones.reduce(
              (a, z) =>
                a +
                (z.risk_score ||
                  0),
              0
            ) /
            zones.length
          : 0;

      return {
        peopleCount:
          totalPeople,

        density:
          avgDensity,

        motionIntensity:
          avgMotionIntensity,

        motionLevel:
          getMotionLevel(
            avgMotionIntensity
          ),

        riskLevel:
          globalRisk,

        riskScore:
          avgRiskScore,

        densityLevel:
          globalRisk,
      };
    }, [
      zones,
      totalPeople,
      avgDensity,
      globalRisk,
    ]);

  useEffect(() => {
    if (zones.length > 0) {
      const stats = {
        cameraId: fobId,

        riskLevel:
          dashboardStats.riskLevel,

        riskScore:
          dashboardStats.riskScore,

        density:
          dashboardStats.density,

        motionIntensity:
          dashboardStats.motionIntensity,

        zones: zones.map(
          (z) => ({
            id: z.zone_id,
            name: z.zone_name,
            riskLevel:
              z.risk_level,
            peopleCount:
              z.people_count,
            density:
              z.density_avg,
            motionIntensity:
              z.motion_intensity,
          })
        ),
      };

      checkForAlerts(
        stats as any,
        `${selectedFOB.name} System`
      );
    }
  }, [
    zones,
    dashboardStats,
    checkForAlerts,
    fobId,
    selectedFOB.name,
  ]);

  const isLive =
    useMemo(() => {
      if (isConnected)
        return true;

      if (
        lastUpdate &&
        !isLoading
      ) {
        return (
          new Date().getTime() -
            lastUpdate.getTime() <
          10000
        );
      }

      return false;
    }, [
      isConnected,
      lastUpdate,
      isLoading,
    ]);

  const activeSvg =
    viewMode ===
    "withoutFobs"
      ? SecLayoutNoFobSvg
      : viewMode === "live"
        ? SecLayoutLiveCleanSvg
        : viewMode === "layout"
          ? SecLayoutLayoutSvg
          : SecLayoutSvg;

  const activeSvgHeight =
    viewMode === "layout" ||
    viewMode === "withoutFobs"
      ? LAYOUT_VIEWBOX_HEIGHT
      : LIVE_VIEWBOX_HEIGHT;

  useLayoutEffect(() => {
    const scroller =
      svgScrollRef.current;

    if (!scroller) return;

    resetMapScroll();
    requestAnimationFrame(resetMapScroll);
    setTimeout(resetMapScroll, 60);
  }, [viewMode, activeSvgHeight, fobId]);

  const cameraById =
    useMemo(() => {
      const map =
        new Map<
          string,
          CameraAnalytics
        >();

      zones.forEach(
        (
          zone: ZoneAnalytics
        ) => {
          if (
            !Array.isArray(
              zone.cameras
            )
          ) {
            return;
          }

          zone.cameras.forEach(
            (cam: any) => {
              if (
                cam &&
                typeof cam ===
                  "object" &&
                "camera_id" in cam
              ) {
                map.set(
                  cam.camera_id,
                  cam as CameraAnalytics
                );

                map.set(
                  cam.svg_region_id,
                  cam as CameraAnalytics
                );
              }
            }
          );
        }
      );

      return map;
    }, [zones]);

  const hybRouteCongested =
    useMemo(
      () =>
        hybFobCount >
        FOB_THRESHOLD,
      [hybFobCount]
    );

  const midRouteCongested =
    useMemo(
      () =>
        midFobCount >
        FOB_THRESHOLD,
      [midFobCount]
    );

  const kzjRouteCongested =
    useMemo(
      () =>
        kzjFobCount >
        FOB_THRESHOLD,
      [kzjFobCount]
    );

  const routeStatus =
    useMemo(
      () => ({
        HYB:
          hybRouteCongested,
        MID:
          midRouteCongested,
        KZJ:
          kzjRouteCongested,
      }),
      [
        hybRouteCongested,
        midRouteCongested,
        kzjRouteCongested,
      ]
    );

  const hoveredCamera =
    useMemo(() => {
      if (
        !hoveredCameraId
      ) {
        return undefined;
      }

      const sourceCameraId =
        CAMERA_DATA_SOURCE_BY_REGION[
          hoveredCameraId
        ] ||
        hoveredCameraId;

      return (
        cameraById.get(
          sourceCameraId
        ) ||
        cameraById.get(
          hoveredCameraId
        ) ||
        ({
          camera_id:
            sourceCameraId,

          people_count: 0,

          density_avg: 0,

          motion_intensity: 0,

          risk_score: 0,
        } as CameraAnalytics)
      );
    }, [
      hoveredCameraId,
      cameraById,
    ]);

  useEffect(() => {
    let mounted = true;

    const fetchTrackingUsers =
      async () => {
        try {
          const records =
            await trackingUserApi.getTrackingUsers();

          if (!mounted)
            return;

          setTrackingUsers(
            records
          );
        } catch {
          if (!mounted) return;
        }
      };

    fetchTrackingUsers();

    const timer =
      setInterval(
        fetchTrackingUsers,
        10000
      );

    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, []);

  const mappedUserMarkers =
    useMemo<
      MappedUserMarker[]
    >(() => {
      const markers:
        MappedUserMarker[] =
        [];

      for (
        const rec of
          trackingUsers
      ) {
        const phoneKey =
          getUserIdentityKey(
            rec
          );

        if (!phoneKey)
          continue;

        const {
          lat,
          lon,
        } = normalizeLatLon(
          rec.coordinates
            .latitude,
          rec.coordinates
            .longitude
        );

        if (
          !isWithinHybBounds(
            lat,
            lon
          )
        ) {
          continue;
        }

        const rawPoint =
          toSvgPointFromLatLon(
            lat,
            lon
          );

        const markerPoint = {
          x:
            clampMarkerAwayFromFobs(
              rawPoint.x
            ),

          y:
            rawPoint.y,
        };

        markers.push({
          phoneKey,
          record: rec,
          rawPoint,
          markerPoint,
        });
      }

      return spreadOverlappingMarkers(
        markers
      );
    }, [
      trackingUsers,
    ]);

  // ── Color SVG camera regions based on live analytics ─────────────────────────
  useEffect(() => {
    if (
      viewMode !== "live"
    ) {
      return;
    }

    const container =
      liveSvgRef.current;

    if (!container)
      return;

    const labelsGroup =
      container.querySelector(
        "#camera-labels"
      );

    if (labelsGroup)
      labelsGroup.remove();

    const RISK_FILL: Record<RiskLevel | 'UNKNOWN', string> = {
      LOW: '#00c853',
      MEDIUM: '#ffca00',
      HIGH: '#ff6d00',
      CRITICAL: '#e50914',
      UNKNOWN: '#374151',
    };
    const RISK_STROKE: Record<RiskLevel | 'UNKNOWN', string> = {
      LOW: '#14532d',
      MEDIUM: '#78350f',
      HIGH: '#7c2d12',
      CRITICAL: '#450a0a',
      UNKNOWN: '#1f2937',
    };

    const ns = 'http://www.w3.org/2000/svg';

    LIVE_CAMERA_IDS.forEach((id) => {
      const el = container.querySelector(`#${id}`) as SVGElement | null;
      if (!el) return;

      const sourceCameraId = CAMERA_DATA_SOURCE_BY_REGION[id] || id;
      const cam = cameraById.get(sourceCameraId) || cameraById.get(id);
      const hasLiveData = isLive && !!cam;
      const boxEl = el as SVGRectElement;
      const width = parseFloat(boxEl.getAttribute('width') || '0');
      const height = parseFloat(boxEl.getAttribute('height') || '0');
      const cx = parseFloat(boxEl.getAttribute('x') || '0') + width / 2;
      const cy = parseFloat(boxEl.getAttribute('y') || '0') + height / 2;

      // The zone box itself is now just an invisible hit-area for hover/click -
      // the colored camera-type indicator drawn below replaces its old solid fill.
      el.setAttribute('fill', 'transparent');
      el.setAttribute('stroke', 'transparent');
      el.classList.remove('animate-pulse');

      const iconId = `icon_${id}`;
      const existingIcon = container.querySelector(`#${iconId}`) as SVGGElement | null;

      // Renders the camera indicator as a colored pill with the live count inside
      // (matching the reference layout).
      const createOrUpdateIndicator = (fill: string, stroke: string, pulse: boolean, countText: string) => {
        const grp = existingIcon || document.createElementNS(ns, 'g');
        if (!existingIcon) {
          grp.setAttribute('id', iconId);
          grp.setAttribute('pointer-events', 'none');
          el.parentElement?.appendChild(grp);
        }
        while (grp.firstChild) grp.removeChild(grp.firstChild);

        const digits = countText.length;
        const pillR = digits >= 3 ? 28 : digits === 2 ? 24 : 21;

        // The camera-type glyph (bullet/dome/ptz) always sits just below the
        // pill at this same box, regardless of whether iconSource resolves -
        // computed up front so the coverage beam below can originate from the
        // glyph's own center rather than the pill's.
        const iconSize = CAMERA_TYPE_ICON_SIZE;
        const iconX = cx - iconSize / 2;
        const iconY = cy + pillR + 4;
        const iconCenterX = cx;
        const iconCenterY = iconY + iconSize / 2;

        // Directional coverage beam (subtle torch-light cone) drawn behind the
        // camera glyph, originating from the glyph itself (not the pill),
        // pointing the same way it faces and tinted with the same color as
        // the pill/status indicator.
        const beamCamType = CAMERA_BY_ID[id]?.cam_type;
        const beamIconSource = beamCamType ? CAM_TYPE_ICONS[beamCamType] : undefined;
        const beamTargetAngle = directionToAngle(CAMERA_BY_ID[id]?.direction);
        const beamAngle = beamTargetAngle !== null ? beamTargetAngle : (beamIconSource?.defaultAngle ?? 0);

        const BEAM_LENGTH = 100;
        const BEAM_HALF_ANGLE_DEG = 28;
        const toRad = (deg: number) => (deg * Math.PI) / 180;
        const leftRad = toRad(beamAngle - BEAM_HALF_ANGLE_DEG);
        const rightRad = toRad(beamAngle + BEAM_HALF_ANGLE_DEG);
        // 0deg = up (12 o'clock), clockwise, matching directionToAngle's convention.
        const leftX = iconCenterX + BEAM_LENGTH * Math.sin(leftRad);
        const leftY = iconCenterY - BEAM_LENGTH * Math.cos(leftRad);
        const rightX = iconCenterX + BEAM_LENGTH * Math.sin(rightRad);
        const rightY = iconCenterY - BEAM_LENGTH * Math.cos(rightRad);

        const beam = document.createElementNS(ns, 'path');
        beam.setAttribute(
          'd',
          `M ${iconCenterX} ${iconCenterY} L ${leftX} ${leftY} A ${BEAM_LENGTH} ${BEAM_LENGTH} 0 0 1 ${rightX} ${rightY} Z`
        );
        beam.setAttribute('fill', fill);
        beam.setAttribute('fill-opacity', '0.18');
        beam.setAttribute('stroke', 'none');
        beam.setAttribute('pointer-events', 'none');
        grp.appendChild(beam);

        const pill = document.createElementNS(ns, 'circle');
        pill.setAttribute('cx', String(cx));
        pill.setAttribute('cy', String(cy));
        pill.setAttribute('r', String(pillR));
        pill.setAttribute('fill', fill);
        pill.setAttribute('stroke', stroke);
        pill.setAttribute('stroke-width', '2');
        grp.appendChild(pill);

        const txt = document.createElementNS(ns, 'text');
        txt.setAttribute('x', String(cx));
        txt.setAttribute('y', String(cy + 1));
        txt.setAttribute('font-family', 'Arial, sans-serif');
        txt.setAttribute('font-size', digits >= 3 ? '20' : '22');
        txt.setAttribute('font-weight', 'bold');
        txt.setAttribute('fill', '#ffffff');
        txt.setAttribute('text-anchor', 'middle');
        txt.setAttribute('dominant-baseline', 'middle');
        txt.textContent = countText;
        grp.appendChild(txt);

        // Every camera - FOB or not - shows its camera-type glyph (bullet/dome/ptz)
        // just below the pill, at the same size and position.
        const camType = CAMERA_BY_ID[id]?.cam_type;
        const iconSource = camType ? CAM_TYPE_ICONS[camType] : undefined;

        if (iconSource) {
          // Scale by the artwork's longest side (not the full canvas) and
          // center it in the icon box, so bullet/dome/ptz all render at the
          // same apparent size regardless of how much each PNG's canvas is
          // padded around its glyph.
          const { bbox } = iconSource;
          const scale = iconSize / Math.max(bbox.w, bbox.h);
          const renderedImgSize = CAM_TYPE_ICON_NATURAL_SIZE * scale;
          const imgLocalX = (iconSize - bbox.w * scale) / 2 - bbox.x * scale;
          const imgLocalY = (iconSize - bbox.h * scale) / 2 - bbox.y * scale;

          // A nested <svg> viewport clips the oversized <image> to exactly
          // iconSize x iconSize, so only the centered glyph is visible.
          const iconViewport = document.createElementNS(ns, 'svg');
          iconViewport.setAttribute('x', String(iconX));
          iconViewport.setAttribute('y', String(iconY));
          iconViewport.setAttribute('width', String(iconSize));
          iconViewport.setAttribute('height', String(iconSize));

          const iconImg = document.createElementNS(ns, 'image');
          iconImg.setAttribute('href', iconSource.url);
          iconImg.setAttribute('x', String(imgLocalX));
          iconImg.setAttribute('y', String(imgLocalY));
          iconImg.setAttribute('width', String(renderedImgSize));
          iconImg.setAttribute('height', String(renderedImgSize));

          iconViewport.appendChild(iconImg);

          // Rotate the whole viewport (not just the image) around the icon's own
          // center so it points the way the camera actually faces, relative to
          // the artwork's default facing direction for that camera type.
          const targetAngle = directionToAngle(CAMERA_BY_ID[id]?.direction);
          if (targetAngle !== null) {
            const rotation = (targetAngle - iconSource.defaultAngle + 360) % 360;
            iconViewport.setAttribute('transform', `rotate(${rotation} ${iconCenterX} ${iconCenterY})`);
          }

          grp.appendChild(iconViewport);
        }

        pulse ? grp.classList.add('animate-pulse') : grp.classList.remove('animate-pulse');
      };

      if (hasLiveData) {
        const rawLevel = cam.risk_level || getRiskLevel(cam.risk_score || 0);
        const level = (typeof rawLevel === 'string' ? rawLevel.toUpperCase() : 'UNKNOWN') as RiskLevel;
        createOrUpdateIndicator(RISK_FILL[level] ?? RISK_FILL['UNKNOWN'], RISK_STROKE[level] ?? RISK_STROKE['UNKNOWN'], level === 'CRITICAL', `${cam.people_count ?? 0}`);
      } else {
        createOrUpdateIndicator(RISK_FILL['UNKNOWN'], RISK_STROKE['UNKNOWN'], false, '0');
      }
    });

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
    if (
      viewMode !== "live"
    ) {
      return;
    }

    const container =
      liveSvgRef.current;

    if (!container)
      return;

    const cleanups:
      Array<() => void> =
      [];

    LIVE_CAMERA_IDS.forEach(
      (id) => {
        const el =
          container.querySelector(
            `#${id}`
          ) as SVGElement | null;

        if (!el) return;

        el.style.pointerEvents =
          "all";

        el.style.cursor =
          "pointer";

        const handleEnter =
          () => {
            setHoveredCameraId(
              id
            );

            const rect =
              el.getBoundingClientRect();

            const contRect =
              container.getBoundingClientRect();

            const tooltipWidth =
              240;

            let left =
              rect.right -
              contRect.left +
              8;

            if (
              left +
                tooltipWidth >
              contRect.width
            ) {
              left =
                rect.left -
                contRect.left -
                tooltipWidth -
                8;
            }

            const top =
              Math.max(
                0,
                rect.top -
                  contRect.top
              );

            setTooltipPos({
              left,
              top,
            });
          };

        const handleLeave =
          () => {
            setHoveredCameraId(
              null
            );

            setTooltipPos(
              null
            );
          };

        const handleClick =
          () => {
            openLiveStream(
              id
            );
          };

        el.addEventListener(
          "mouseenter",
          handleEnter
        );

        el.addEventListener(
          "mouseleave",
          handleLeave
        );

        el.addEventListener(
          "click",
          handleClick
        );

        cleanups.push(
          () => {
            el.removeEventListener(
              "mouseenter",
              handleEnter
            );

            el.removeEventListener(
              "mouseleave",
              handleLeave
            );

            el.removeEventListener(
              "click",
              handleClick
            );
          }
        );
      }
    );

    return () =>
      cleanups.forEach(
        (fn) => fn()
      );
  }, [
    viewMode,
    LIVE_CAMERA_IDS,
  ]);

  return (
    <PageLayout>
      <div className="space-y-1 lg:space-y-2 animate-fade-in max-w-[1600px] 2xl:max-w-[2400px] min-[2560px]:max-w-[98%] mx-auto min-[2560px]:gap-10">

        {/* ================= HEADER ================= */}
        <header className="grid grid-cols-1 lg:grid-cols-[1fr_auto_1fr] items-center gap-4 lg:gap-6 pb-1 lg:pb-2">
          {/* Left: Title */}
          <div className="text-center lg:text-left">
            <h1
              className="text-xl lg:text-xl font-bold text-foreground tracking-tight"
              style={{ fontFamily: "'Outfit', sans-serif" }}
            >
              Dashboard
            </h1>

            <p
              className="text-xs lg:text-xs text-muted-foreground mt-0.5"
              style={{ fontFamily: "'Outfit', sans-serif" }}
            >
              Real-time crowd monitoring &amp; analytics
            </p>
          </div>

          {/* Center: placeholder */}
          <div
            className="flex justify-center"
            aria-hidden
          />

          {/* Right: STATUS & ACTIONS */}

<div className="flex justify-center lg:justify-end items-center gap-2 text-xs">

  {/* VIEW TRAIN SCHEDULE TOGGLE */}
  <button
    onClick={() => setShowTrainSchedule(!showTrainSchedule)}
    className={`px-1.5 py-1 rounded-md border border-border transition-colors flex items-center gap-1 text-xs font-medium ${showTrainSchedule
      ? 'bg-primary/10 border-primary/30 text-primary shadow-sm'
      : 'hover:bg-muted text-muted-foreground'
      }`}
    title={showTrainSchedule ? "Hide Train Schedule" : "View Train Schedule"}
  >
    <CalendarClock className="h-3.5 w-3.5" />
    <span className="hidden sm:inline">
      {showTrainSchedule ? "Hide" : "View"}
    </span>
  </button>

  {/* SHOW FLOW TOGGLE */}
  {dashboardTab !== 'map' && (
    <div className="flex items-center gap-1 px-1.5 py-1 rounded-md border border-border bg-card text-xs">
      <span className="text-xs font-medium tracking-wide text-muted-foreground">
        Flow
      </span>

      <button
        onClick={() => setDigitalTwin(v => !v)}
        className={`relative inline-flex h-4 w-7 items-center rounded-full transition-colors focus:outline-none ${digitalTwin ? 'bg-primary' : 'bg-muted'
          }`}
        aria-label="Toggle Digital Twin"
      >
        <span
          className={`inline-block h-2 w-2 rounded-full bg-white shadow transform transition-transform ${digitalTwin ? 'translate-x-4' : 'translate-x-0.5'
            }`}
        />
      </button>
    </div>
  )}

  {/* ADMIN UPLOADS */}
  <Dialog>
    <DialogTrigger asChild>
      <button
        className="px-1.5 py-1 rounded-md border border-border hover:bg-muted transition-colors flex items-center gap-1 text-xs font-medium"
        title="Upload Train Schedule"
      >
        <Settings2 className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="hidden sm:inline">
          Upload
        </span>
      </button>
    </DialogTrigger>

    <DialogContent className="sm:max-w-[600px] p-0 overflow-hidden card-black">
      <TrainUpload />
    </DialogContent>
  </Dialog>

  {/* STATUS & LATENCY */}
  <div className="flex items-center gap-2 pl-2 border-l border-border text-xs">

    {/* LIVE CLOCK */}
    <div className="flex items-center gap-1 px-2 py-1 rounded-full card-black border border-border/50 shadow-sm text-xs">
      <div className="w-1.5 h-1.5 rounded-full animate-pulse bg-primary/50" />
      <LiveClock />
    </div>

    {/* LIVE STATUS */}
    <div className={`status-indicator ${isLive ? "live" : "offline"} text-xs`}>
      {isLive ? "LIVE" : <WifiOff size={12} />}
    </div>

    {/* REFRESH */}
    <button
      onClick={refresh}
      className="p-1.5 rounded-md border border-border hover:bg-muted transition-colors"
      title="Refresh"
    >
      <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
    </button>

  </div>
</div>

        </header>

        {/* ================= LAYOUT / MAP VIEW TABS ================= */}
        <div className="flex justify-center lg:justify-start">
          <Tabs value={dashboardTab} onValueChange={(v) => setDashboardTab(v as 'layout' | 'map')}>
            <TabsList className="h-7 p-0.5 gap-0.5">
              <TabsTrigger value="layout" className="h-6 px-2 text-xs font-medium">Layout</TabsTrigger>
              <TabsTrigger value="map" className="h-6 px-2 text-xs font-medium">Map View</TabsTrigger>
            </TabsList>
          </Tabs>
        </div>

        {/* ================= MAP WITH TRAINS OVERLAY ================= */}
        <div className="w-full relative">

          {isLoading &&
          zones.length === 0 ? (
            <div className="glass-panel bg-card text-foreground p-6 h-[400px] lg:h-[600px] xl:h-[650px] 2xl:h-[750px] min-[2560px]:h-[950px] flex items-center justify-center rounded-2xl">
              <div className="loader" />
            </div>
          ) : (
            <div className="relative w-full">
              <div className="relative w-full card-black-30  border border-border/50 overflow-hidden">
                <div className={`grid grid-cols-1 ${showTrainSchedule ? 'grid-cols-[1fr_300px]' : ''}`}>
                  <div id="dashboard-svg-stage" className={`relative w-full flex flex-col ${isSvgFullscreen ? 'h-full' : ''}`}>
                    {!isSvgFullscreen && (
                      <ActionIcon
                        onClick={
                          toggleSvgFullscreen
                        }
                        aria-label="View SVG in full screen"
                        title="View SVG in full screen"
                        variant="default"
                        size="lg"
                        className="absolute right-4 top-4 z-40 border border-border bg-card text-foreground shadow-lg hover:bg-secondary transition-colors"
                      >
                        <IconMaximize
                          size={18}
                          stroke={1.8}
                        />
                      </ActionIcon>
                    )}

                    {isSvgFullscreen && (
                      <button
                        onClick={
                          toggleSvgFullscreen
                        }
                        className="absolute left-4 top-4 z-40 p-2 rounded-full border border-border bg-card/95 text-foreground shadow-lg hover:bg-secondary transition-colors"
                        aria-label="Exit full screen"
                        title="Exit full screen"
                      >
                        <ArrowLeft className="h-5 w-5" />
                      </button>
                    )}

                    {/* SVG + overlays */}
                    <div
                      style={{
                        display:
                          dashboardTab ===
                          "layout"
                            ? undefined
                            : "none",
                      }}
                      className="w-full h-full"
                    >
                      <div
                        key={`svg-scroll-${viewMode}-${fobId}`}
                        ref={
                          svgScrollRef
                        }
                        className={`relative w-full ${
                          isSvgFullscreen
                            ? "h-full overflow-hidden"
                            : ""
                        }`}
                      >

                        <style>
                          {`
                            .live-svg,
                            .live-svg svg {
                              width: 100%;
                              height: 100%;
                              display: block;
                              object-fit: contain;
                            }
                          `}
                        </style>

                      {/* ── Base station layout SVG ── */}
                      <div
                        ref={liveSvgRef}
                        className={`live-svg block w-full h-full ${isSvgFullscreen ? '' : 'min-h-[70vh] lg:min-h-[80vh]'}`}
                        dangerouslySetInnerHTML={{ __html: SecLayoutLiveSvgRaw }}
                      />
                      {/* user position related code
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
                      */}
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
                        {hoveredCamera &&
                          tooltipPos && (
                            <div
                              className="absolute z-30 w-56 rounded-xl border border-border bg-card text-foreground shadow-2xl p-3 pointer-events-none transition-colors duration-300"
                              style={{
                                left: `${tooltipPos.left}px`,
                                top: `${tooltipPos.top}px`,
                              }}
                            >
                              <p className="text-xs font-semibold tracking-wide">
                                {
                                  CAMERA_TITLES[
                                    hoveredCamera
                                      .camera_id
                                  ] ||
                                  hoveredCamera.camera_id
                                }
                              </p>

                              <div className="mt-2 space-y-1.5 text-[11px]">

                                <div className="flex items-center justify-between">
                                  <span className="text-muted-foreground">
                                    Count
                                  </span>

                                  <span className="font-semibold text-foreground">
                                    {
                                      hoveredCamera.people_count ??
                                      0
                                    }
                                  </span>
                                </div>

                                <div className="flex items-center justify-between">
                                  <span className="text-muted-foreground">
                                    Density
                                  </span>

                                  <span className="font-semibold text-foreground">
                                    {
                                      hoveredCamera.density_level ||
                                      getDensityLevel(
                                        hoveredCamera.density_avg ||
                                          0
                                      )
                                    }
                                  </span>
                                </div>

                                <div className="flex items-center justify-between">
                                  <span className="text-muted-foreground">
                                    Motion
                                  </span>

                                  <span className="font-semibold text-foreground">
                                    {
                                      hoveredCamera.motion_level ||
                                      getMotionLevel(
                                        hoveredCamera.motion_intensity ||
                                          0
                                      )
                                    }
                                  </span>
                                </div>

                                <div className="flex items-center justify-between">
                                  <span className="text-muted-foreground">
                                    Risk
                                  </span>

                                  <span className="font-semibold text-foreground">
                                    {
                                      hoveredCamera.risk_level?.toUpperCase() ||
                                      getRiskLevel(
                                        hoveredCamera.risk_score ||
                                          0
                                      )
                                    }
                                  </span>
                                </div>

                              </div>
                            </div>
                          )}

                      </div>
                    </div>

                    {/* Google Map station view */}
                    <div
                      style={{
                        display:
                          dashboardTab ===
                          "map"
                            ? undefined
                            : "none",
                      }}
                      className="w-full h-full min-h-[70vh] lg:min-h-[80vh]"
                    >
                      <StationGoogleMap
                        trackingUsers={
                          trackingUsers
                        }
                        isActive={
                          dashboardTab ===
                          "map"
                        }
                        className="w-full h-full min-h-[70vh] lg:min-h-[80vh]"
                      />
                    </div>

                    {/* Live camera stream */}
                    {liveStreamCameraId && (
                      <div
                        className={
                          isLiveStreamMaximized
                            ? "fixed inset-0 z-[100] flex flex-col rounded-none border-0 bg-background text-foreground shadow-2xl overflow-hidden transition-colors duration-300"
                            : "absolute top-20 right-4 z-50 w-[320px] sm:w-[380px] rounded-2xl border border-border bg-card text-foreground shadow-2xl overflow-hidden transition-colors duration-300"
                        }
                      >

                        <div className="flex items-center justify-between px-3 py-2 border-b border-border shrink-0">

                          <p className="text-xs font-semibold text-foreground tracking-wide truncate pr-2">
                            {
                              CAMERA_TITLES[
                                liveStreamCameraId
                              ] ||
                              liveStreamCameraId
                            }
                          </p>

                          <div className="flex items-center gap-2 shrink-0">

                            <button
                              onClick={() =>
                                setIsLiveStreamMaximized(
                                  (prev) =>
                                    !prev
                                )
                              }
                              className="p-1 rounded-full border border-border bg-card text-foreground hover:bg-secondary transition-colors"
                              aria-label={
                                isLiveStreamMaximized
                                  ? "Exit full screen"
                                  : "View full screen"
                              }
                              title={
                                isLiveStreamMaximized
                                  ? "Exit full screen"
                                  : "View full screen"
                              }
                            >
                              {isLiveStreamMaximized ? (
                                <Minimize2 className="h-3.5 w-3.5" />
                              ) : (
                                <Maximize2 className="h-3.5 w-3.5" />
                              )}
                            </button>

                            <button
                              onClick={
                                closeLiveStream
                              }
                              className="p-1 rounded-full border border-border bg-card text-foreground hover:bg-secondary transition-colors"
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
                              ? "flex items-center justify-center bg-background flex-1 min-h-0"
                              : "flex items-center justify-center bg-background aspect-video"
                          }
                        >

                          {liveStreamStatus ===
                            "connecting" && (
                            <div className="flex flex-col items-center gap-2 text-muted-foreground">
                              <div className="loader" />

                              <p className="text-[10px] uppercase tracking-widest">
                                Connecting…
                              </p>
                            </div>
                          )}

                          {liveStreamStatus ===
                            "error" && (
                            <div className="flex flex-col items-center gap-2 px-4 text-center text-muted-foreground">

                              <p className="text-xs font-medium text-destructive">
                                Stream unavailable
                              </p>

                              <button
                                onClick={() =>
                                  openLiveStream(
                                    liveStreamCameraId
                                  )
                                }
                                className="mt-1 px-2.5 py-1 rounded-lg border border-border bg-card text-[10px] font-medium text-foreground hover:bg-secondary transition-colors"
                              >
                                Retry
                              </button>

                            </div>
                          )}

                          {liveStreamStatus ===
                            "ready" && (
                            <img
                              key={`${liveStreamCameraId}-${liveStreamAttempt}`}
                              src={rtspApi.getLiveStreamUrl(
                                liveStreamCameraId
                              )}
                              alt={`Live stream: ${
                                CAMERA_TITLES[
                                  liveStreamCameraId
                                ] ||
                                liveStreamCameraId
                              }`}
                              className="w-full h-full object-contain"
                              onError={() =>
                                setLiveStreamStatus(
                                  "error"
                                )
                              }
                            />
                          )}

                        </div>
                      </div>
                    )}

                  </div>

                  {/* TRAIN SCHEDULE */}
                  {showTrainSchedule && (
                    <div className="flex flex-col border-l border-border/50 bg-card text-foreground z-30 min-h-0 transition-colors duration-300">
                      <UpcomingTrains
                        variant="overlay"
                      />
                    </div>
                  )}

                </div>
              </div>
            </div>
          )}
        </div>

        {/* ================= CHART + ACTIVE RISK PANEL ================= */}
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