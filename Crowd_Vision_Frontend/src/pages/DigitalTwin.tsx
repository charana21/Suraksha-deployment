import { useState, useMemo, useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import { Cpu, Activity, ArrowLeft, AlertTriangle } from "lucide-react";
import { useZoneAnalytics } from "@/hooks/useZoneAnalytics";
import { useAlerts } from "@/hooks/useAlerts";
import { CameraAnalytics, ZoneAnalytics } from "@/types/zone";
import { getRiskLevel } from "@/lib/metrics";


// ─── Blinking live dot ────────────────────────────────────────────────────────
function LiveDot({ active = true }: { active?: boolean }) {
  return (
    <span style={{
      display: "inline-block", width: 7, height: 7, borderRadius: "50%",
      background: active ? "#34d399" : "#6b7280",
      boxShadow: active ? "0 0 6px #34d399" : "none",
      animation: active ? "dt-blink 2s ease-in-out infinite" : "none",
    }}/>
  );
}

// ─── Live clock ───────────────────────────────────────────────────────────────
function DTClock() {
  const [time, setTime] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  return (
    <span style={{ fontFamily: "'Courier New',monospace", fontSize: 12, color: "#22d3ee" }}>
      {time.toLocaleTimeString("en-IN", {
        timeZone: "Asia/Kolkata", hour12: false,
        hour: "2-digit", minute: "2-digit", second: "2-digit",
      })}
    </span>
  );
}

// ─── Theme tokens ─────────────────────────────────────────────────────────────
const T = {
  bg:     "#020912",
  border: "rgba(34,211,238,.20)",
  cyan:   "#22d3ee",
  text:   "#93c5fd",
  dim:    "rgba(148,196,255,.42)",
  green:  "#34d399",
  red:    "#f43f5e",
  orange: "#fb923c",
  yellow: "#fbbf24",
};

// ─── Page ─────────────────────────────────────────────────────────────────────
export default function DigitalTwinPage() {
  const [hoveredCamId, setHoveredCamId] = useState<string | null>(null);
  const [tooltipPos,   setTooltipPos]   = useState<{ x: number; y: number } | null>(null);
  const [showHeatmap,  setShowHeatmap]  = useState(false);
  const mapContainerRef = useRef<HTMLDivElement>(null);

  const { zones, isConnected } = useZoneAnalytics({ stationId: "HYB", enableWebSocket: true });
  const { alerts } = useAlerts();
  const activeAlerts = alerts.filter(a => !a.acknowledged);

  // Build cameraById lookup
  const cameraById = useMemo(() => {
    const map = new Map<string, CameraAnalytics>();
    zones.forEach((zone: ZoneAnalytics) => {
      if (!Array.isArray(zone.cameras)) return;
      zone.cameras.forEach((cam: any) => {
        if (cam && typeof cam === "object" && "camera_id" in cam) {
          map.set(cam.camera_id,     cam as CameraAnalytics);
          map.set(cam.svg_region_id, cam as CameraAnalytics);
        }
      });
    });
    return map;
  }, [zones]);

  const globalRisk = useMemo(() => {
    if (!zones.length) return "NOMINAL";
    if (zones.some(z => z.risk_level === "CRITICAL")) return "CRITICAL";
    if (zones.some(z => z.risk_level === "HIGH"))     return "HIGH";
    if (zones.some(z => z.risk_level === "MEDIUM"))   return "MEDIUM";
    return "NOMINAL";
  }, [zones]);

  const riskColor =
    globalRisk === "CRITICAL" ? T.red :
    globalRisk === "HIGH"     ? T.orange :
    globalRisk === "MEDIUM"   ? T.yellow : T.green;

  // Camera hover — position tooltip relative to map container
  const handleCamHover = (id: string | null, el: SVGGElement | null) => {
    setHoveredCamId(id);
    if (el && mapContainerRef.current) {
      const bbox = el.getBoundingClientRect();
      const cont = mapContainerRef.current.getBoundingClientRect();
      setTooltipPos({ x: bbox.right - cont.left + 12, y: bbox.top - cont.top });
    } else {
      setTooltipPos(null);
    }
  };

  return (
    <div style={{
      minHeight: "100vh", maxHeight: "100vh",
      background: T.bg, display: "flex", flexDirection: "column",
      fontFamily: "'Courier New',monospace", overflow: "hidden",
    }}>
      {/* Global keyframes */}
      <style>{`
        @keyframes dt-blink { 0%,100%{opacity:1} 50%{opacity:.35} }
        @keyframes dt-spin  { to{transform:rotate(360deg)} }
      `}</style>

      {/* ══════════════════════════════════════════════════════ HEADER ══ */}
      <header style={{
        height: 50, flexShrink: 0,
        background: "rgba(0,8,24,.97)",
        borderBottom: `1px solid ${T.border}`,
        display: "flex", alignItems: "center",
        padding: "0 18px", gap: 16,
        boxShadow: "0 0 24px rgba(34,211,238,.07)",
      }}>
        <Link to="/" style={{
          color: T.dim, textDecoration: "none",
          display: "flex", alignItems: "center", gap: 5, fontSize: 11,
        }}>
          <ArrowLeft size={13}/> BACK
        </Link>
        <div style={{ width: 1, height: 22, background: T.border }}/>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Cpu size={15} color={T.cyan} style={{ animation: "dt-spin 8s linear infinite" }}/>
          <span style={{ fontSize: 13, fontWeight: 700, color: T.cyan, letterSpacing: 5 }}>
            DIGITAL TWIN
          </span>
        </div>
        <div style={{ width: 1, height: 22, background: T.border }}/>
        <span style={{ fontSize: 10, color: T.dim, letterSpacing: 2 }}>
          SECUNDERABAD JUNCTION — SEC-JN
        </span>

        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 18 }}>
          {/* Risk badge */}
          <div style={{
            display: "flex", alignItems: "center", gap: 6,
            padding: "3px 10px", borderRadius: 5,
            border: `1px solid ${riskColor}45`, background: `${riskColor}14`,
          }}>
            <span style={{
              width: 6, height: 6, borderRadius: "50%",
              background: riskColor, display: "inline-block",
              boxShadow: `0 0 7px ${riskColor}`,
              animation: "dt-blink 1.5s ease-in-out infinite",
            }}/>
            <span style={{ fontSize: 10, color: riskColor, fontWeight: 700, letterSpacing: 2 }}>
              {globalRisk}
            </span>
          </div>
          {activeAlerts.length > 0 && (
            <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <AlertTriangle size={12} color={T.red}/>
              <span style={{ fontSize: 10, color: T.red, letterSpacing: 1 }}>
                {activeAlerts.length} ALERTS
              </span>
            </div>
          )}
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <LiveDot active={isConnected}/>
            <span style={{ fontSize: 10, color: isConnected ? T.green : T.dim, letterSpacing: 2 }}>
              {isConnected ? "LIVE FEED" : "OFFLINE"}
            </span>
          </div>

          {/* ── Heatmap toggle ── */}
          <div style={{ width: 1, height: 22, background: T.border }}/>
          <button
            onClick={() => setShowHeatmap(h => !h)}
            style={{
              display: "flex", alignItems: "center", gap: 6,
              padding: "4px 11px", borderRadius: 5, cursor: "pointer",
              border: showHeatmap
                ? `1px solid rgba(255,157,0,0.70)`
                : `1px solid ${T.border}`,
              background: showHeatmap
                ? "rgba(255,157,0,0.12)"
                : "transparent",
              transition: "all 0.2s",
              outline: "none",
            }}
          >
            {/* Heat icon — three stacked arcs */}
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
              <path d="M12 2C8 6 8 10 12 12c4 2 4 6 0 10" stroke={showHeatmap ? "#ff9d00" : "rgba(148,196,255,0.45)"}
                strokeWidth="2.2" strokeLinecap="round"/>
              <path d="M7 6C4 9 4 13 7 15c3 2 3 5 0 8" stroke={showHeatmap ? "#ff6b00" : "rgba(148,196,255,0.30)"}
                strokeWidth="1.8" strokeLinecap="round"/>
              <path d="M17 6c3 3 3 7 0 9c-3 2-3 5 0 8" stroke={showHeatmap ? "#ffd000" : "rgba(148,196,255,0.30)"}
                strokeWidth="1.8" strokeLinecap="round"/>
            </svg>
            <span style={{
              fontSize: 10, fontWeight: 700, letterSpacing: 2,
              color: showHeatmap ? "#ff9d00" : T.dim,
              fontFamily: "'Courier New', monospace",
            }}>
              HEATMAP
            </span>
            {/* ON/OFF pill */}
            <span style={{
              fontSize: 8, fontWeight: 800, letterSpacing: 1,
              padding: "1px 5px", borderRadius: 3,
              background: showHeatmap ? "rgba(255,157,0,0.25)" : "rgba(148,196,255,0.08)",
              color: showHeatmap ? "#ff9d00" : "rgba(148,196,255,0.45)",
              border: showHeatmap ? "1px solid rgba(255,157,0,0.4)" : "1px solid rgba(148,196,255,0.15)",
            }}>
              {showHeatmap ? "ON" : "OFF"}
            </span>
          </button>

          <DTClock/>
        </div>
      </header>

      {/* ═══════════════════════════════════════════════ MAP AREA ══════ */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0 }}>

        {/* Scrollable map wrapper */}
        <div style={{ flex: 1, overflow: "auto", minHeight: 0 }}>
          <div ref={mapContainerRef} style={{ position: "relative", width: "100%", height: "100%" }}>

            <div style={{
              width: "100%",
              height: "100%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: T.dim,
              border: `1px dashed ${T.border}`,
              background: "rgba(0,10,25,.35)",
              borderRadius: 8,
              fontSize: 12,
              letterSpacing: 1,
            }}>
              DIGITAL TWIN MAP REMOVED
            </div>

            {/* Camera tooltip — appears on hover */}
            {hoveredCamId && tooltipPos && (() => {
              const cam = cameraById.get(hoveredCamId);
              if (!cam) return null;
              const level = cam.risk_level || getRiskLevel(cam.risk_score || 0);
              const lc =
                level === "CRITICAL" ? T.red :
                level === "HIGH"     ? T.orange :
                level === "MEDIUM"   ? T.yellow : T.green;
              return (
                <div style={{
                  position: "absolute",
                  left: tooltipPos.x, top: tooltipPos.y,
                  background: "rgba(1,10,28,.97)",
                  border: `1px solid ${T.border}`,
                  borderRadius: 8, padding: "10px 14px", minWidth: 190,
                  zIndex: 50, boxShadow: "0 0 26px rgba(0,195,225,.20)",
                  pointerEvents: "none",
                  fontFamily: "'Courier New', monospace",
                }}>
                  <div style={{ fontSize: 10, color: T.cyan, letterSpacing: 2, marginBottom: 8, fontWeight: 700 }}>
                    {hoveredCamId.toUpperCase().replace(/_/g, " ")}
                  </div>
                  {[
                    { label: "PEOPLE",  value: String(cam.people_count ?? 0) },
                    { label: "RISK",    value: level,                color: lc },
                    { label: "DENSITY", value: cam.density_level || "—" },
                    { label: "MOTION",  value: cam.motion_level  || "—" },
                  ].map(({ label, value, color }) => (
                    <div key={label} style={{
                      display: "flex", justifyContent: "space-between",
                      padding: "3px 0", fontSize: 10,
                    }}>
                      <span style={{ color: T.dim }}>{label}</span>
                      <span style={{ color: color || T.text, fontWeight: 700 }}>{value}</span>
                    </div>
                  ))}
                </div>
              );
            })()}
          </div>
        </div>

        {/* ── Bottom status strip ── */}
        <div style={{
          height: 36, flexShrink: 0,
          background: "rgba(0,6,18,.96)",
          borderTop: `1px solid ${T.border}`,
          display: "flex", alignItems: "center",
          padding: "0 16px", gap: 20,
        }}>
          {["PF 1", "PF 2", "PF 4", "PF 6", "PF 8", "PF 10"].map(pf => (
            <div key={pf} style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <span style={{
                width: 5, height: 5, borderRadius: "50%",
                background: T.cyan, display: "inline-block",
                boxShadow: `0 0 5px ${T.cyan}`,
              }}/>
              <span style={{ fontSize: 9, color: T.dim, letterSpacing: 1 }}>{pf}</span>
            </div>
          ))}
          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 6 }}>
            <Activity size={10} color={T.dim}/>
            <span style={{ fontSize: 9, color: T.dim, letterSpacing: 2 }}>
              AI · COMPUTER VISION · ANALYTICS FEED ACTIVE
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
