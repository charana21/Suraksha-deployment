import { useState, useEffect, useMemo } from "react";

import { PageLayout } from "@/components/layout/PageLayout";

import { useAlerts } from "@/hooks/useAlerts";

import { useCameras } from "@/hooks/useCameras";

import { useLocation } from "react-router-dom";

import { Button } from "@/components/ui/button";

import { Input } from "@/components/ui/input";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import {
  Pagination as MantinePagination,
  Select as MantineSelect,
  Group,
  Text,
} from "@mantine/core";

import {
  AlertTriangle,
  Check,
  Clock,
  MapPin,
  Search,
  Filter,
  Users,
  Tag,
  Loader2,
} from "lucide-react";

import { alertApi, IslandAlert } from "@/services/alertApi";

import { cn } from "@/lib/utils";

import { Alert } from "@/types/camera";

import fobZones from "@/data/fob_zones.json";

/* =========================================================
   CONSTANTS
   ========================================================= */

const severityColors = {
  LOW: "border-l-risk-low",
  MEDIUM: "border-l-risk-medium",
  HIGH: "border-l-risk-high",
  CRITICAL: "border-l-risk-critical",
};

// Zone reference from the API docs
const ZONE_CATALOG = [
  {
    zone_id: "zone_hyb_fob",
    label:
      "HYB FOB (HYD FOB FC PF10, HYD FOB FC PF1, HYB FOB MIDDLE FC4&5)",
    type: "FOB",
  },
  {
    zone_id: "zone_kzj_fob",
    label: "KZJ FOB (KZJ FOB FC PF 10, KZJ FOB ESCL FC PF 1)",
    type: "FOB",
  },
  {
    zone_id: "zone_mid_fob",
    label:
      "Middle FOB (KZJ SIDE NEW FOB FC PF10, MID FOB FC PF-10)",
    type: "FOB",
  },
  {
    zone_id: "zone_hyb_pf1",
    label:
      "Platform 1 (PF-1 NEAR KZJ FOB FC GATE 2, PF1 NEARGATE-4 FC HYB)",
    type: "PLATFORM",
  },
  {
    zone_id: "zone_hyb_pf2",
    label: "Island PF 2&3 (PF 2 KZJ FOB FC RRI)",
    type: "PLATFORM",
  },
  {
    zone_id: "zone_hyb_pf3",
    label: "Island PF 2&3 (PF 2 KZJ FOB FC RRI)",
    type: "PLATFORM",
  },
  {
    zone_id: "zone_hyb_pf4",
    label: "Island PF 4&5 (PF.NO.4&5 MIDDLE PTZ)",
    type: "PLATFORM",
  },
  {
    zone_id: "zone_hyb_pf5",
    label: "Island PF 4&5 (PF.NO.4&5 MIDDLE PTZ)",
    type: "PLATFORM",
  },
  {
    zone_id: "zone_hyb_pf6",
    label: "Island PF 6&7 (PF 6 NEAR NEAR MID FOB)",
    type: "PLATFORM",
  },
  {
    zone_id: "zone_hyb_pf7",
    label: "Island PF 6&7 (PF 6 NEAR NEAR MID FOB)",
    type: "PLATFORM",
  },
  {
    zone_id: "zone_hyb_pf8",
    label: "Island PF 8&9 (PF 8 MIDDLE FC KZJ)",
    type: "PLATFORM",
  },
  {
    zone_id: "zone_hyb_pf9",
    label: "Island PF 8&9 (PF 8 MIDDLE FC KZJ)",
    type: "PLATFORM",
  },
  {
    zone_id: "zone_hyb_pf10",
    label: "Platform 10 (PF10 (OPP GATE-8) FC KZJ FOB)",
    type: "PLATFORM",
  },
  {
    zone_id: "zone_hyb_booKing",
    label: "GATE 2A BOOKING OFFICE",
    type: "BOOKING",
  },
  {
    zone_id: "zone_hyb_booking",
    label: "GATE 4 BOOKING OFFICE",
    type: "BOOKING",
  },
  {
    zone_id: "zone_hyb_booking_gate6",
    label: "GATE 6 BOOKING OFFICE",
    type: "BOOKING",
  },
] as const;

const ZONE_TYPE_BADGE: Record<
  string,
  {
    label: string;
    bg: string;
    text: string;
    border: string;
  }
> = {
  FOB: {
    label: "FOB",
    bg: "bg-blue-500/10 dark:bg-blue-500/10",
    text: "text-blue-600 dark:text-blue-400",
    border: "border-blue-500/20",
  },
  PLATFORM: {
    label: "Platform",
    bg: "bg-green-500/10 dark:bg-green-500/10",
    text: "text-green-600 dark:text-green-400",
    border: "border-green-500/20",
  },
  BOOKING: {
    label: "Booking",
    bg: "bg-amber-500/10 dark:bg-amber-500/10",
    text: "text-amber-600 dark:text-amber-400",
    border: "border-amber-500/20",
  },
};

/* =========================================================
   HELPERS
   ========================================================= */

const stripHexColors = (text: string): string => {
  if (!text) return text;

  return text
    .replace(/#[0-9A-Fa-f]{3,6}\s*/g, "")
    .trim();
};

const normalizeZoneId = (zoneId?: string): string => {
  if (!zoneId) return "";

  return zoneId.trim().toLowerCase();
};

const zoneIdToLabel = (zoneId?: string): string => {
  if (!zoneId) return "";

  const normalized = normalizeZoneId(zoneId);

  return (
    ZONE_CATALOG.find(
      (z) => normalizeZoneId(z.zone_id) === normalized
    )?.label ??
    zoneId.replace(/\_/g, " ").toUpperCase()
  );
};

// Derive zone_type from zoneId or fobId when not provided by API
const deriveZoneType = (
  alert: Alert
): Alert["zoneType"] | undefined => {
  if (alert.zoneType) return alert.zoneType;

  const id = (
    alert.zoneId ||
    alert.cameraId ||
    alert.cameraName
  ).toLowerCase();

  if (id.includes("pf")) return "PLATFORM";
  if (id.includes("booking")) return "BOOKING";
  if (id.includes("fob") || alert.fobId) return "FOB";

  return undefined;
};

/* =========================================================
   COMPONENT
   ========================================================= */

export default function Alerts() {
  const {
    alerts,
    acknowledgeAlert,
    refresh,
    isLoading,
    page,
    setPage,
    pageSize,
    setPageSize,
    totalCount,
    totalPages,
    setCameraNameQuery,
  } = useAlerts();

  const { cameras } = useCameras();

  const location = useLocation();

  const [searchQuery, setSearchQuery] = useState("");
  const [severityFilter, setSeverityFilter] = useState("all");
  const [zoneTypeFilter, setZoneTypeFilter] = useState("all");
  const [zoneFilter, setZoneFilter] = useState("all");

  const [islandAlerts, setIslandAlerts] =
    useState<IslandAlert[]>([]);

  /* =========================================================
     ISLAND ALERTS
     ========================================================= */

  useEffect(() => {
    const fetch = async () => {
      try {
        const r = await alertApi.getLiveIslandAlerts(2);

        if (r?.alerts) {
          setIslandAlerts(r.alerts);
        }
      } catch (e) {
      }
    };

    fetch();

    const id = setInterval(fetch, 30_000);

    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (location.pathname !== "/alerts") return;

    refresh();
  }, [location.pathname, refresh]);

  // Debounce search input before sending camera_name to the API
  useEffect(() => {
    const id = setTimeout(
      () => setCameraNameQuery(searchQuery),
      400
    );

    return () => clearTimeout(id);
  }, [searchQuery, setCameraNameQuery]);

  /* =========================================================
     RELEVANT ALERTS
     ========================================================= */

  const relevantAlerts = useMemo(
    () =>
      alerts.filter(
        (a) =>
          a.severity === "HIGH" ||
          a.severity === "CRITICAL"
      ),
    [alerts]
  );

  /* =========================================================
     ZONE TYPE COUNTS
     ========================================================= */

  const zoneTypeCounts = useMemo(() => {
    const c = {
      FOB: 0,
      PLATFORM: 0,
      BOOKING: 0,
    };

    relevantAlerts.forEach((a) => {
      const t = deriveZoneType(a);

      if (t && t in c) {
        c[t as keyof typeof c]++;
      }
    });

    return c;
  }, [relevantAlerts]);

  /* =========================================================
     STATS
     ========================================================= */

  const stats = useMemo(
    () => ({
      total: relevantAlerts.length,
      critical: relevantAlerts.filter(
        (a) => a.severity === "CRITICAL"
      ).length,
      high: relevantAlerts.filter(
        (a) => a.severity === "HIGH"
      ).length,
      unacknowledged: relevantAlerts.filter(
        (a) => !a.acknowledged
      ).length,
    }),
    [relevantAlerts]
  );

  /* =========================================================
     FILTERED LIST
     ========================================================= */

  const filteredAlerts = useMemo(() => {
    return relevantAlerts.filter((alert) => {
      const effectiveZoneType =
        deriveZoneType(alert);

      const matchesSearch =
        stripHexColors(alert.message)
          .toLowerCase()
          .includes(searchQuery.toLowerCase()) ||
        stripHexColors(alert.cameraName)
          .toLowerCase()
          .includes(searchQuery.toLowerCase()) ||
        alert.id
          .toLowerCase()
          .includes(searchQuery.toLowerCase());

      const matchesSeverity =
        severityFilter === "all" ||
        alert.severity === severityFilter;

      const matchesZoneType =
        zoneTypeFilter === "all" ||
        effectiveZoneType === zoneTypeFilter;

      const matchesZone =
        zoneFilter === "all" ||
        normalizeZoneId(alert.zoneId) ===
          normalizeZoneId(zoneFilter);

      return (
        matchesSearch &&
        matchesSeverity &&
        matchesZoneType &&
        matchesZone
      );
    });
  }, [
    relevantAlerts,
    searchQuery,
    severityFilter,
    zoneTypeFilter,
    zoneFilter,
  ]);

  /* =========================================================
     AVAILABLE ZONES
     ========================================================= */

  const zoneOptions = useMemo(() => {
    if (zoneTypeFilter === "all") {
      return ZONE_CATALOG;
    }

    return ZONE_CATALOG.filter(
      (z) => z.type === zoneTypeFilter
    );
  }, [zoneTypeFilter]);

  /* =========================================================
     RANGE LABEL
     ========================================================= */

  const rangeStart =
    filteredAlerts.length === 0
      ? 0
      : (page - 1) * pageSize + 1;

  const rangeEnd =
    (page - 1) * pageSize +
    filteredAlerts.length;

  const rangeLabel = `${rangeStart}-${rangeEnd} of ${totalCount}`;

  return (
    <PageLayout>
      <div
        className="
          space-y-6
          animate-fade-in
          bg-white
          text-slate-900
          dark:bg-background
          dark:text-foreground
          min-h-full
        "
      >
        {/* =====================================================
            HEADER
            ===================================================== */}

        <div className="flex items-center justify-between">
          <div>
            <h1
              className="text-xl font-bold text-slate-900 dark:text-foreground tracking-tight"
              style={{ fontFamily: "'Outfit', sans-serif" }}
            >
              Active Alerts
            </h1>

            <p
              className="text-xs text-slate-500 dark:text-muted-foreground mt-0.5"
              style={{ fontFamily: "'Outfit', sans-serif" }}
            >
              Real-time high severity incidents and warnings
            </p>
          </div>

          <div className="flex items-center text-sm font-semibold text-foreground">
  <Clock className="w-4 h-4 mr-2 text-primary" />
  <span>24 Hours Alerts</span>
</div>
        </div>

        {/* =====================================================
            SUMMARY STATS
            ===================================================== */}

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="stat-card bg-white dark:bg-card">
            <p className="metric-label text-slate-700 dark:text-foreground">
              Total Active
            </p>

            <p className="metric-value text-slate-900 dark:text-foreground">
              {stats.total}
            </p>
          </div>

          <div className="stat-card bg-white dark:bg-card">
            <p className="metric-label text-slate-700 dark:text-foreground">
              Critical
            </p>

            <p className="metric-value text-risk-critical">
              {stats.critical}
            </p>
          </div>

          <div className="stat-card bg-white dark:bg-card">
            <p className="metric-label text-slate-700 dark:text-foreground">
              High Priority
            </p>

            <p className="metric-value text-risk-high">
              {stats.high}
            </p>
          </div>

          <div className="stat-card bg-white dark:bg-card">
            <p className="metric-label text-slate-700 dark:text-foreground">
              Unacknowledged
            </p>

            <p className="metric-value text-primary">
              {stats.unacknowledged}
            </p>
          </div>
        </div>

        {/* =====================================================
            ZONE-TYPE BREAKDOWN
            ===================================================== */}

        <div className="grid grid-cols-3 gap-3">
          {(Object.entries(zoneTypeCounts) as [
            string,
            number
          ][]).map(([type, count]) => {
            const badge = ZONE_TYPE_BADGE[type];

            return (
              <button
                key={type}
                onClick={() =>
                  setZoneTypeFilter((p) =>
                    p === type ? "all" : type
                  )
                }
                className={cn(
                  `
                    stat-card
                    bg-white
                    dark:bg-card
                    text-left
                    transition-all
                    border-2
                  `,
                  zoneTypeFilter === type
                    ? `border-primary/60 ${badge.bg}`
                    : "border-transparent"
                )}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span
                    className={cn(
                      "text-[10px] font-bold px-1.5 py-0.5 rounded border",
                      badge.bg,
                      badge.text,
                      badge.border
                    )}
                  >
                    {badge.label}
                  </span>
                </div>

                <p
                  className={cn(
                    "text-2xl font-bold",
                    badge.text
                  )}
                >
                  {count}
                </p>

                <p className="metric-label text-[10px] mt-0.5 text-slate-500 dark:text-muted-foreground">
                  alerts
                </p>
              </button>
            );
          })}
        </div>

        {/* =====================================================
            FILTERS
            ===================================================== */}

        <div
          className="
            flex flex-col
            sm:flex-row
            items-stretch
            sm:items-center
            gap-3
            bg-white
            dark:bg-card
            p-3
            sm:p-3
            rounded-lg
            border
            border-slate-200
            dark:border-border
            shadow-sm
          "
        >
          {/* Search */}

          <div className="relative flex-1 min-w-[180px]">
            <Search
              className="
                absolute left-3 top-1/2
                -translate-y-1/2
                w-4 h-4
                text-slate-400
                dark:text-muted-foreground
              "
            />

            <Input
              placeholder="Search alerts…"
              value={searchQuery}
              onChange={(e) =>
                setSearchQuery(e.target.value)
              }
              className="
                pl-9 pr-9 w-full
                bg-white
                dark:bg-card
                border-slate-300
                dark:border-border
                text-slate-900
                dark:text-foreground
                placeholder:text-slate-400
                dark:placeholder:text-muted-foreground
              "
            />

            {isLoading && (
              <Loader2
                className="
                  absolute right-3 top-1/2
                  -translate-y-1/2
                  w-4 h-4
                  text-slate-400
                  dark:text-muted-foreground
                  animate-spin
                "
              />
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            {/* Severity */}

            <Select
              value={severityFilter}
              onValueChange={setSeverityFilter}
            >
              <SelectTrigger
                className="
                  w-[150px]
                  bg-white
                  dark:bg-card
                  border-slate-300
                  dark:border-border
                  text-slate-900
                  dark:text-foreground
                "
              >
                <Filter className="w-3.5 h-3.5 mr-1.5 text-slate-500 dark:text-muted-foreground" />

                <SelectValue placeholder="Severity" />
              </SelectTrigger>

              <SelectContent
                className="
                  bg-white
                  dark:bg-card
                  border-slate-200
                  dark:border-border
                  text-slate-900
                  dark:text-foreground
                "
              >
                <SelectItem
                  value="all"
                  className="
                    text-slate-900
                    dark:text-foreground
                    focus:text-slate-900
                    dark:focus:text-foreground
                  "
                >
                  All (High/Critical)
                </SelectItem>

                <SelectItem value="CRITICAL">
                  Critical Only
                </SelectItem>

                <SelectItem value="HIGH">
                  High Only
                </SelectItem>
              </SelectContent>
            </Select>

            {/* Zone Type */}

            <Select
              value={zoneTypeFilter}
              onValueChange={(v) => {
                setZoneTypeFilter(v);
                setZoneFilter("all");
              }}
            >
              <SelectTrigger
                className="
                  w-[150px]
                  bg-white
                  dark:bg-card
                  border-slate-300
                  dark:border-border
                  text-slate-900
                  dark:text-foreground
                "
              >
                <Tag className="w-3.5 h-3.5 mr-1.5 text-slate-500 dark:text-muted-foreground" />

                <SelectValue placeholder="Zone Type" />
              </SelectTrigger>

              <SelectContent
                className="
                  bg-white
                  dark:bg-card
                  border-slate-200
                  dark:border-border
                  text-slate-900
                  dark:text-foreground
                "
              >
                <SelectItem value="all">
                  All Zone Types
                </SelectItem>

                <SelectItem value="FOB">
                  FOB
                </SelectItem>

                <SelectItem value="PLATFORM">
                  Platform
                </SelectItem>

                <SelectItem value="BOOKING">
                  Booking
                </SelectItem>
              </SelectContent>
            </Select>

            {/* Zone */}

            <Select
              value={zoneFilter}
              onValueChange={setZoneFilter}
            >
              <SelectTrigger
                className="
                  w-[150px]
                  bg-white
                  dark:bg-card
                  border-slate-300
                  dark:border-border
                  text-slate-900
                  dark:text-foreground
                "
              >
                <MapPin className="w-3.5 h-3.5 mr-1.5 text-slate-500 dark:text-muted-foreground" />

                <SelectValue placeholder="Zone" />
              </SelectTrigger>

              <SelectContent
                className="
                  bg-white
                  dark:bg-card
                  border-slate-200
                  dark:border-border
                  text-slate-900
                  dark:text-foreground
                "
              >
                <SelectItem value="all">
                  All Zones
                </SelectItem>

                {zoneOptions.map((z) => (
                  <SelectItem
                    key={z.zone_id}
                    value={z.zone_id}
                  >
                    {z.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* =====================================================
            ALERT LIST
            ===================================================== */}

        <div className="space-y-1.5">
          {filteredAlerts.length > 0 ? (
            filteredAlerts.map((alert) => {
              const effectiveZoneType =
                deriveZoneType(alert);

              const badge = effectiveZoneType
                ? ZONE_TYPE_BADGE[effectiveZoneType]
                : null;

              return (
                <div
                  key={alert.id}
                  className={cn(
                    `
                      relative
                      overflow-hidden
                      rounded-lg
                      border
                      bg-white
                      dark:bg-card
                      border-slate-200
                      dark:border-border
                      transition-all
                      hover:shadow-md
                    `,
                    severityColors[alert.severity],
                    alert.acknowledged
                      ? `
                        bg-slate-50
                        dark:bg-slate-800/40
                        border-l-4
                        opacity-75
                      `
                      : `
                        bg-white
                        dark:bg-card
                        border-l-4
                        shadow-sm
                      `
                  )}
                >
                  <div className="p-2 sm:p-2.5 flex flex-col sm:flex-row gap-2 items-start">
                    {/* Icon */}

                    <div className="flex-shrink-0 flex items-center justify-between w-full sm:w-auto">
                      <div
                        className={cn(
                          `
                            w-6 h-6
                            sm:w-7 sm:h-7
                            rounded-full
                            flex items-center
                            justify-center
                          `,
                          alert.severity === "CRITICAL"
                            ? `
                              bg-risk-critical/20
                              text-risk-critical
                            `
                            : `
                              bg-risk-high/20
                              text-risk-high
                            `
                        )}
                      >
                        <AlertTriangle className="w-3 h-3 sm:w-3.5 sm:h-3.5" />
                      </div>

                      <span
                        className="
                          sm:hidden
                          text-[10px]
                          font-mono
                          text-slate-500
                          dark:text-slate-400
                          bg-slate-100
                          dark:bg-slate-800
                          px-1 py-0.5
                          rounded
                        "
                      >
                        #{alert.id.slice(-6)}
                      </span>
                    </div>

                    {/* Content */}

                    <div className="flex-1 min-w-0 w-full">
                      {/* Badges row */}

                      <div className="flex items-center gap-1 flex-wrap mb-1">
                        <span
                          className="
                            hidden sm:inline-block
                            text-[10px]
                            font-mono
                            text-slate-500
                            dark:text-slate-400
                            bg-slate-100
                            dark:bg-slate-800
                            px-1 py-0.5
                            rounded
                          "
                        >
                          #{alert.id.slice(-6)}
                        </span>

                        {/* Zone Type Badge */}

                        {badge && (
                          <span
                            className={cn(
                              `
                                text-[9px]
                                font-bold
                                px-1 py-0.5
                                rounded
                                border
                                leading-none
                              `,
                              badge.bg,
                              badge.text,
                              badge.border
                            )}
                          >
                            {badge.label}
                          </span>
                        )}

                        {/* Zone ID */}

                        {alert.zoneId && (
                          <span
                            className="
                              text-[9px]
                              text-slate-600
                              dark:text-slate-300
                              bg-slate-100
                              dark:bg-slate-800
                              px-1 py-0.5
                              rounded
                              border
                              border-slate-200
                              dark:border-slate-700
                              leading-none
                            "
                          >
                            {zoneIdToLabel(alert.zoneId)}
                          </span>
                        )}
                      </div>

                      {/* Camera Name / Title */}

                      <h3
                        className="
                          font-bold
                          text-slate-900
                          dark:text-foreground
                          text-sm
                          truncate
                          mb-0.5
                        "
                      >
                        {stripHexColors(
                          alert.cameraName ||
                            alert.cameraId
                        )}
                      </h3>

                      <p
                        className="
                          text-[11px]
                          font-medium
                          text-slate-600
                          dark:text-slate-300
                          mb-1.5
                        "
                      >
                        {stripHexColors(alert.message)}
                      </p>

                      <div
                        className="
                          grid
                          grid-cols-1
                          sm:grid-cols-2
                          gap-y-1
                          gap-x-6
                          text-[11px]
                          sm:text-xs
                          text-slate-600
                          dark:text-slate-300
                        "
                      >
                        {/* Time */}

                        <div className="flex items-center gap-1.5">
                          <Clock className="w-3 h-3 text-primary/70" />

                          <span className="font-medium">
                            Time:
                          </span>

                          <span className="text-slate-900 dark:text-foreground">
                            {new Date(
                              alert.timestamp
                            ).toLocaleString("en-IN", {
                              timeZone: "Asia/Kolkata",
                              dateStyle: "medium",
                              timeStyle: "short",
                            })}
                          </span>
                        </div>

                        {/* People Count */}

                        <div className="flex items-center gap-1.5">
                          <div
                            className="
                              flex items-center
                              justify-center
                              w-3.5 h-3.5
                              rounded-full
                              bg-primary/20
                            "
                          >
                            <Users className="w-2.5 h-2.5 text-primary" />
                          </div>

                          <span className="font-medium">
                            People Count:
                          </span>

                          <span
                            className="
                              font-bold
                              text-slate-900
                              dark:text-foreground
                              text-[11px]
                              sm:text-xs
                            "
                          >
                            {alert.peopleCount ?? "N/A"}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Acknowledge Button */}

                    <div className="flex-shrink-0 self-start sm:self-center w-full sm:w-auto mt-1 sm:mt-0">
                      {!alert.acknowledged ? (
                        <Button
                          size="sm"
                          onClick={() =>
                            acknowledgeAlert(alert.id)
                          }
                          className={cn(
                            `
                              w-full
                              sm:min-w-[110px]
                              h-7
                              text-xs
                            `,
                            alert.severity === "CRITICAL"
                              ? `
                                bg-risk-critical
                                hover:bg-risk-critical/90
                              `
                              : `
                                bg-risk-high
                                hover:bg-risk-high/90
                              `
                          )}
                        >
                          <Check className="w-3 h-3 mr-1.5" />
                          Acknowledge
                        </Button>
                      ) : (
                        <Button
                          variant="ghost"
                          disabled
                          size="sm"
                          className="
                            w-full
                            sm:min-w-[110px]
                            h-7
                            text-xs
                            opacity-50
                          "
                        >
                          <span className="text-slate-500 dark:text-slate-400">
                            Acknowledged
                          </span>
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })
          ) : isLoading ? (
            <div
              className="
                flex flex-col
                items-center
                justify-center
                p-16
                text-center
                border-2
                border-dashed
                border-slate-200
                dark:border-border/50
                rounded-2xl
                bg-white
                dark:bg-card
              "
            >
              <Loader2 className="w-8 h-8 text-slate-500 animate-spin mb-4" />

              <h3 className="text-lg font-medium text-slate-900 dark:text-foreground">
                Loading alerts…
              </h3>
            </div>
          ) : searchQuery.trim() ? (
            <div
              className="
                flex flex-col
                items-center
                justify-center
                p-16
                text-center
                border-2
                border-dashed
                border-slate-200
                dark:border-border/50
                rounded-2xl
                bg-white
                dark:bg-card
              "
            >
              <div
                className="
                  w-16 h-16
                  bg-slate-100
                  dark:bg-slate-800
                  rounded-full
                  flex items-center
                  justify-center
                  mb-4
                "
              >
                <Search className="w-8 h-8 text-slate-500" />
              </div>

              <h3 className="text-lg font-medium text-slate-900 dark:text-foreground">
                No records
              </h3>

              <p className="text-slate-500 dark:text-slate-400 mt-2 max-w-sm">
                No alerts found for "{searchQuery}".
              </p>
            </div>
          ) : (
            <div
              className="
                flex flex-col
                items-center
                justify-center
                p-16
                text-center
                border-2
                border-dashed
                border-slate-200
                dark:border-border/50
                rounded-2xl
                bg-white
                dark:bg-card
              "
            >
              <div
                className="
                  w-16 h-16
                  bg-slate-100
                  dark:bg-slate-800
                  rounded-full
                  flex items-center
                  justify-center
                  mb-4
                "
              >
                <Check className="w-8 h-8 text-slate-500" />
              </div>

              <h3 className="text-lg font-medium text-slate-900 dark:text-foreground">
                No active alerts
              </h3>

              <p className="text-slate-500 dark:text-slate-400 mt-2 max-w-sm">
                No{" "}
                {severityFilter !== "all"
                  ? severityFilter.toLowerCase()
                  : "high or critical"}{" "}
                alerts
                {zoneTypeFilter !== "all"
                  ? ` in ${zoneTypeFilter} zones`
                  : ""}
                {zoneFilter !== "all"
                  ? ` for ${zoneIdToLabel(zoneFilter)}`
                  : ""}{" "}
                at this moment.
              </p>
            </div>
          )}
        </div>

        {/* =====================================================
            PAGINATION
            ===================================================== */}

        <div
          className="
            bg-white
            dark:bg-card
            p-3
            sm:p-4
            rounded-lg
            border
            border-slate-200
            dark:border-border
            shadow-sm
          "
        >
          <Group
            justify="space-between"
            align="center"
            gap={12}
            wrap="wrap"
          >
            <Group gap={8} align="center">
              <Text
                size="sm"
                c="hsl(var(--muted-foreground))"
              >
                Records per page
              </Text>

              <MantineSelect
                data={["10", "20", "30", "50", "100"]}
                value={String(pageSize)}
                onChange={(value) => {
                  setPageSize(Number(value ?? "10"));
                  setPage(1);
                }}
                w={70}
                styles={{
                  input: {
                    background: "hsl(var(--background))",
                    border:
                      "1px solid hsl(var(--border))",
                    color: "hsl(var(--foreground))",
                  },

                  dropdown: {
                    background: "hsl(var(--card))",
                    border:
                      "1px solid hsl(var(--border))",
                  },

                  option: {
                    background: "transparent",
                    color: "hsl(var(--foreground))",

                    "&:hover": {
                      background:
                        "transparent !important",
                      color:
                        "hsl(var(--foreground)) !important",
                    },

                    "&[data-combobox-active]": {
                      background:
                        "transparent !important",
                      color:
                        "hsl(var(--foreground)) !important",
                    },

                    "&[data-combobox-selected]": {
                      background:
                        "transparent !important",
                      color:
                        "hsl(var(--foreground)) !important",
                    },
                  },
                }}
              />

              <Text
                size="sm"
                c="hsl(var(--muted-foreground))"
              >
                {rangeLabel}
              </Text>
            </Group>

            <MantinePagination
              value={page}
              onChange={setPage}
              total={totalPages}
              siblings={0}
              boundaries={1}
              size="sm"
              color="blue"
              styles={{
                control: {
                  background:
                    "hsl(var(--card))",
                  borderColor:
                    "hsl(var(--border))",
                  color:
                    "hsl(var(--foreground))",
                },
              }}
            />
          </Group>
        </div>

        {/* =====================================================
            ISLAND PLATFORM ALERTS
            ===================================================== */}

        <div className="space-y-6">
          <h2 className="text-xl font-semibold text-slate-900 dark:text-foreground">
            Island Platform Alerts
          </h2>

          {islandAlerts.length > 0 ? (
            <div className="flex flex-col gap-6">
              {islandAlerts.map((alert) => (
                <div
                  key={alert.alert_id}
                  className="
                    bg-white
                    dark:bg-card
                    border
                    border-slate-200
                    dark:border-border
                    rounded-xl
                    overflow-hidden
                    shadow-sm
                  "
                >
                  {/* Header */}

                  <div
                    className="
                      bg-slate-50
                      dark:bg-slate-800/50
                      p-4
                      border-b
                      border-slate-200
                      dark:border-border
                      flex
                      flex-col
                      md:flex-row
                      md:items-center
                      justify-between
                      gap-4
                    "
                  >
                    <div className="flex items-center gap-3">
                      <div className="bg-primary/10 p-2 rounded-lg">
                        <MapPin className="w-5 h-5 text-primary" />
                      </div>

                      <div>
                        <h3 className="font-bold text-lg text-slate-900 dark:text-foreground">
                          Island Platform:{" "}
                          <span className="text-primary">
                            {alert.island_name}
                          </span>
                        </h3>

                        <p className="text-sm text-slate-600 dark:text-slate-300">
                          {
                            alert.contributing_trains
                              .length
                          }{" "}
                          Train
                          {alert.contributing_trains
                            .length !== 1
                            ? "s"
                            : ""}{" "}
                          approaching
                          <span className="ml-2 text-xs opacity-70">
                            (
                            {alert.window_start.slice(
                              11,
                              16
                            )}{" "}
                            –{" "}
                            {alert.window_end.slice(
                              11,
                              16
                            )}
                            )
                          </span>
                        </p>
                      </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-4 text-sm">
                      <div className="flex flex-col items-end">
                        <span className="text-xs text-slate-600 dark:text-slate-400 font-medium uppercase">
                          Threshold
                        </span>

                        <span className="font-mono font-bold text-slate-900 dark:text-foreground">
                          {alert.threshold}
                        </span>
                      </div>

                      <div className="h-8 w-px bg-slate-200 dark:bg-border hidden md:block" />

                      <div className="flex flex-col items-end">
                        <span className="text-xs text-slate-600 dark:text-slate-400 font-medium uppercase">
                          Total Footfall
                        </span>

                        <span
                          className={cn(
                            "font-mono font-bold",
                            alert.total_footfall >
                              alert.threshold
                              ? "text-risk-high"
                              : "text-slate-900 dark:text-foreground"
                          )}
                        >
                          {alert.total_footfall}
                        </span>
                      </div>

                      <div
                        className={cn(
                          `
                            px-3 py-1.5
                            rounded-lg
                            border
                            font-bold
                            flex flex-col
                            items-center
                            min-w-[80px]
                          `,
                          alert.risk_level === "CRITICAL"
                            ? "bg-risk-critical/10 text-risk-critical border-risk-critical/20"
                            : alert.risk_level === "HIGH"
                            ? "bg-risk-high/10 text-risk-high border-risk-high/20"
                            : alert.risk_level === "MEDIUM"
                            ? "bg-risk-medium/10 text-risk-medium border-risk-medium/20"
                            : "bg-risk-low/10 text-risk-low border-risk-low/20"
                        )}
                      >
                        <span className="text-[10px] uppercase opacity-70">
                          Risk Level
                        </span>

                        <span>{alert.risk_level}</span>
                      </div>
                    </div>
                  </div>

                  {/* Train Table */}

                  <div className="p-0 overflow-x-auto">
                    <table className="w-full text-sm text-left">
                      <thead
                        className="
                          text-xs
                          text-slate-500
                          dark:text-slate-400
                          uppercase
                          bg-slate-50
                          dark:bg-slate-800/50
                          border-b
                          border-slate-200
                          dark:border-border
                        "
                      >
                        <tr>
                          <th className="px-6 py-3 font-medium">
                            Live Platform
                          </th>

                          <th className="px-6 py-3 font-medium">
                            Train Number
                          </th>

                          <th className="px-6 py-3 font-medium">
                            Train Name
                          </th>

                          <th className="px-6 py-3 font-medium">
                            Arrival
                          </th>

                          <th className="px-6 py-3 font-medium">
                            Departure
                          </th>

                          <th className="px-6 py-3 font-medium text-right">
                            Passengers
                          </th>
                        </tr>
                      </thead>

                      <tbody className="divide-y divide-slate-200 dark:divide-border">
                        {alert.contributing_trains.map(
                          (train, idx) => (
                            <tr
                              key={`${train.train_number}-${idx}`}
                              className="
                                bg-white
                                dark:bg-card
                                hover:bg-slate-50
                                dark:hover:bg-slate-800/50
                                transition-colors
                              "
                            >
                              <td className="px-6 py-4 font-bold text-slate-900 dark:text-foreground">
                                {train.platform ||
                                  "Pending"}
                              </td>

                              <td className="px-6 py-4 font-mono text-slate-600 dark:text-slate-300">
                                {train.train_number}
                              </td>

                              <td className="px-6 py-4 font-medium text-slate-900 dark:text-foreground">
                                {train.train_name}
                              </td>

                              <td className="px-6 py-4 text-slate-600 dark:text-slate-300">
                                <div className="flex items-center gap-2">
                                  <Clock className="w-3.5 h-3.5 opacity-70" />

                                  {train.arrival_time
                                    ? train.arrival_time.slice(
                                        0,
                                        5
                                      )
                                    : "--:--"}
                                </div>
                              </td>

                              <td className="px-6 py-4 text-slate-600 dark:text-slate-300">
                                <div className="flex items-center gap-2">
                                  <Clock className="w-3.5 h-3.5 opacity-70" />

                                  {train.departure_time
                                    ? train.departure_time.slice(
                                        0,
                                        5
                                      )
                                    : "--:--"}
                                </div>
                              </td>

                              <td className="px-6 py-4 text-right font-bold text-slate-900 dark:text-foreground">
                                {train.passengers}
                              </td>
                            </tr>
                          )
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div
              className="
                flex flex-col
                items-center
                justify-center
                p-12
                text-center
                border-2
                border-dashed
                border-slate-200
                dark:border-border
                rounded-xl
                bg-white
                dark:bg-card
              "
            >
              <div
                className="
                  w-12 h-12
                  bg-slate-100
                  dark:bg-slate-800
                  rounded-full
                  flex items-center
                  justify-center
                  mb-3
                "
              >
                <Check className="w-6 h-6 text-slate-500" />
              </div>

              <p className="text-slate-500 dark:text-slate-400 text-sm">
                No active island platform risks detected.
              </p>
            </div>
          )}
        </div>
      </div>
    </PageLayout>
  );
}