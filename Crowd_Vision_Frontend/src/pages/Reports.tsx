import { useState, useMemo } from 'react';
import { PageLayout } from '@/components/layout/PageLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, LineChart, Line, Legend,
} from 'recharts';
import {
  subHours, startOfHour, eachHourOfInterval,
  subDays, startOfDay, eachDayOfInterval, format,
} from 'date-fns';
import { FileText, TrendingUp, AlertTriangle, Users, Clock, CalendarClock, Activity, BarChart2, Layers } from 'lucide-react';
import { alertApi, AlertStatsResponse } from '@/services/alertApi';
import { useQueries, useQuery } from '@tanstack/react-query';
import { analyticsApi, AnalyticsHistoryPoint } from '@/services/analyticsApi';
import { Alert } from '@/types/camera';
import { ZoneHistoryGraph } from '@/components/dashboard/ZoneHistoryGraph';
import { CAMERAS, CAMERA_TITLES } from '@/data/cameras';

// ─── Constants ───────────────────────────────────────────────────────────────

const SEVERITY_COLORS = ['hsl(142, 76%, 36%)', 'hsl(38, 92%, 50%)', 'hsl(25, 95%, 53%)', 'hsl(0, 84%, 60%)'];
const ZONE_TYPE_COLORS = { FOB: 'hsl(215, 85%, 60%)', PLATFORM: 'hsl(142, 76%, 46%)', BOOKING: 'hsl(38, 92%, 50%)' };

const REPORT_RANGES = [
  { id: '24h', label: 'Last 24 hours', rangeParam: '24h' as const, hours: 24, interval: '5m' },
  { id: '7d', label: 'Last 7 Days', rangeParam: '7d' as const, hours: 168, interval: '1h' },
  { id: '30d', label: 'Last 30 Days', rangeParam: '30d' as const, hours: 720, interval: '1h' },
];

const getCameraLabel = (id?: string) => {
  if (!id) return '';
  return CAMERA_TITLES[id] || id;
};

const normalizeZoneId = (zoneId?: string): string => (zoneId || '').trim().toLowerCase();

// ═════════════════════════════════════════════════════════════════════════════
// FIX 1: IMPROVED Zone Type Detection Logic
// ═════════════════════════════════════════════════════════════════════════════
const deriveZoneType = (alert: Alert): Alert['zoneType'] | undefined => {
  // First check if zoneType is explicitly provided
  if (alert.zoneType) return alert.zoneType;

  // Check various ID fields for zone type indicators
  const zoneIdStr = (alert.zoneId || alert.cameraId || alert.cameraName || '').toLowerCase().trim();

  // More specific checks - order matters!
  if (zoneIdStr.includes('booking')) return 'BOOKING';
  if (zoneIdStr.includes('pf') || zoneIdStr.includes('platform')) return 'PLATFORM';
  if (zoneIdStr.includes('fob')) return 'FOB';

  return undefined;
};

type HistoryGroup = {
  title: string;
  hue: number;
  zoneIds?: string[];
  cameraIds?: string[];
};

// Camera ids backing the Middle FOB zone, sourced from the camera registry instead
// of being duplicated here.
const MID_FOB_CAMERA_IDS = CAMERAS.filter(c => c.zone_id === 'zone_mid_fob').map(c => c.camera_id);

// FOB footfall groups mapped to zones/cameras
const FOB_GROUPS: HistoryGroup[] = [
  {
    title: 'HYB FOB',
    hue: 215,
    zoneIds: ['zone_hyb_fob'],
  },
  {
    title: 'KZJ FOB',
    hue: 25,
    zoneIds: ['zone_kzj_fob'],
  },
  {
    title: 'Middle FOB',
    hue: 280,
    zoneIds: ['zone_mid_fob'],
    cameraIds: MID_FOB_CAMERA_IDS,
  },
];

// ═════════════════════════════════════════════════════════════════════════════
// FIX 2: CORRECTED Platform Groups - Unique Zone IDs
// ═════════════════════════════════════════════════════════════════════════════
const PLATFORM_GROUPS = [
  { title: 'Platform 1', hue: 142, zoneIds: ['zone_hyb_pf1'] },
  { title: 'Island PF 2&3', hue: 142, zoneIds: ['zone_hyb_pf2'] },
  { title: 'Island PF 4&5', hue: 142, zoneIds: ['zone_hyb_pf4'] },
  //{ title: 'Island PF 6&7',  hue: 142, zoneIds: ['zone_hyb_pf6'] },
  { title: 'Island PF 8&9', hue: 142, zoneIds: ['zone_hyb_pf8'] },
  { title: 'Platform 10', hue: 142, zoneIds: ['zone_hyb_pf10'] },
];

// ═════════════════════════════════════════════════════════════════════════════
// FIX 3: CORRECTED Booking Groups - Unique Zone IDs
// ═════════════════════════════════════════════════════════════════════════════
const BOOKING_GROUPS = [
  { title: 'GATE 2A BOOKING OFFICE', hue: 38, zoneIds: ['zone_hyb_booking'] },
  { title: 'GATE 4 BOOKING OFFICE', hue: 38, zoneIds: ['zone_gate4a_booking'] },
  { title: 'GATE-6 OUTSIDE ENTRANCE', hue: 38, zoneIds: ['zone_gate6_booking'] },
];

interface ZoneHistoryResult {
  chartData: { time: string; count: number; timestamp: Date }[];
  overallPeak: number;
}

interface RangeConfig {
  hours: number;
  interval: string;
  label: string;
}

const formatTimeLabel = (date: Date, hours: number) => {
  if (hours > 24) {
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit' });
  }
  return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
};

const buildChartData = (points: AnalyticsHistoryPoint[], hours: number) => {
  const grouped = new Map<string, number>();
  points.forEach(point => {
    if (!point?.timestamp) return;
    const count = Number(point.count || 0);
    grouped.set(point.timestamp, (grouped.get(point.timestamp) || 0) + count);
  });

  return Array.from(grouped.entries())
    .map(([timestamp, count]) => {
      const date = new Date(timestamp);
      return {
        time: formatTimeLabel(date, hours),
        count,
        timestamp: date,
      };
    })
    .sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());
};

const getRangeConfig = (rangeId: string): RangeConfig => {
  const found = REPORT_RANGES.find(r => r.id === rangeId);
  if (found) {
    return { hours: found.hours, interval: found.interval, label: found.label };
  }
  return { hours: REPORT_RANGES[1].hours, interval: REPORT_RANGES[1].interval, label: REPORT_RANGES[1].label };
};

const fetchZoneHistoryData = async (
  zoneIds: string[],
  rangeConfig: RangeConfig,
  cameraIds: string[] = [],
): Promise<ZoneHistoryResult> => {
  if (zoneIds.length === 0) {
    if (cameraIds.length === 0) return { chartData: [], overallPeak: 0 };
  }
  const now = new Date();
  const start = subHours(now, rangeConfig.hours);
  const startISO = start.toISOString();
  const endISO = now.toISOString();

  const zoneResponses = await Promise.all(zoneIds.map((zoneId) =>
    analyticsApi.getZoneHistory({
      zone_id: zoneId,
      start: startISO,
      end: endISO,
      interval: rangeConfig.interval,
    }),
  ));

  const cameraResponses = await Promise.all(cameraIds.map((cameraId) =>
    analyticsApi.getCameraHistory({
      camera_id: cameraId,
      start: startISO,
      end: endISO,
      interval: rangeConfig.interval,
    }),
  ));

  const hasCameraData = cameraResponses.some(resp => (resp.data?.length || 0) > 0);
  const sourceResponses = hasCameraData ? cameraResponses : zoneResponses;

  const overallPeakFromApi = sourceResponses.reduce((max, resp) => Math.max(max, resp.overall_peak || 0), 0);
  const rawData = sourceResponses.flatMap(resp => resp.data);
  const chartData = buildChartData(rawData, rangeConfig.hours);
  const calculatedPeak = chartData.reduce((max, point) => Math.max(max, point.count), 0);
  // When multiple zones/cameras are summed into one combined series (e.g. Station-Wide
  // Footfall), the API's per-source overall_peak is each source's OWN individual peak,
  // which can happen at a different moment than the combined series' peak — mixing it
  // in via Math.max produces a "peak" the plotted curve can never actually reach.
  // Only trust the API peak when there's a single source, since then it describes the
  // exact same series being plotted (just possibly finer-grained than the bucketed data).
  const overallPeak = sourceResponses.length > 1 ? calculatedPeak : Math.max(overallPeakFromApi, calculatedPeak);

  return {
    chartData: buildChartData(rawData, rangeConfig.hours),
    overallPeak,
  };
};

const useZoneHistoryQuery = (
  zoneIds: string[],
  key: string,
  rangeId: string,
  rangeConfig: RangeConfig,
  cameraIds: string[] = [],
) => {
  return useQuery<ZoneHistoryResult>({
    queryKey: ['reports-history', key, rangeId],
    queryFn: () => fetchZoneHistoryData(zoneIds, rangeConfig, cameraIds),
    enabled: zoneIds.length > 0 || cameraIds.length > 0,
    staleTime: 5 * 60 * 1000,
    cacheTime: 10 * 60 * 1000,
  });
};

const useZoneHistoryQueries = (groups: HistoryGroup[], rangeId: string, rangeConfig: RangeConfig) => {
  return useQueries({
    queries: groups.map(group => ({
      queryKey: ['reports-history', group.title, rangeId],
      queryFn: () => fetchZoneHistoryData(group.zoneIds || [], rangeConfig, group.cameraIds || []),
      enabled: (group.zoneIds?.length || 0) > 0 || (group.cameraIds?.length || 0) > 0,
      staleTime: 5 * 60 * 1000,
      cacheTime: 10 * 60 * 1000,
    })),
  });
};

const normalizeId = (id?: string): string => (id || '').trim().toLowerCase();

// ─── Component ────────────────────────────────────────────────────────────────

export default function Reports() {
  const [timeRange, setTimeRange] = useState('7d');
  const [showAllPlatforms, setShowAllPlatforms] = useState(false);

  const selectedRangeObj = useMemo(
    () => REPORT_RANGES.find(r => r.id === timeRange) || REPORT_RANGES[1],
    [timeRange],
  );

  // Fetch server-side stats (cached by React Query – no re-fetch on page revisit within staleTime)
  const { data: statsData = null, isFetching: isLoadingStats } = useQuery<AlertStatsResponse | null>({
    queryKey: ['alertStats', selectedRangeObj.rangeParam],
    queryFn: () => alertApi.getAlertStats(selectedRangeObj.rangeParam),
    staleTime: 5 * 60 * 1000,
    cacheTime: 10 * 60 * 1000,
  });

  // Fetch raw alerts (cached by React Query)
  const { data: alertsRes = null, isFetching: isLoadingAlerts } = useQuery({
    queryKey: ['alertsList', selectedRangeObj.hours],
    queryFn: () => alertApi.listAlerts({ hours: selectedRangeObj.hours, limit: 5000 }),
    staleTime: 5 * 60 * 1000,
    cacheTime: 10 * 60 * 1000,
  });

  const isLoading = isLoadingStats || isLoadingAlerts;

  const rawAlerts = useMemo<Alert[]>(() => {
    if (!alertsRes) return [];
    return alertsRes.alerts.map(a => ({
      id: a.alert_id,
      cameraId: a.camera_id,
      cameraName: a.camera_name || a.camera_id,
      zoneId: a.zone_id,
      zoneType: a.zone_type,
      type: a.severity === 'CRITICAL' ? 'stampede' : 'density',
      severity: a.severity as Alert['severity'],
      message: a.trigger_reason || 'Alert triggered',
      triggerReason: a.trigger_reason || `Risk Score: ${a.risk_score}`,
      timestamp: new Date(a.timestamp.endsWith('Z') ? a.timestamp : a.timestamp + 'Z'),
      acknowledged: a.status === 'acknowledged',
      peopleCount: a.people_count,
      fobId: a.fob_id,
    }));
  }, [alertsRes]);


  // ─── Client-side aggregations (fallback when server stats unavailable) ───
  const filteredAlerts = useMemo(() => {
    const start = subHours(new Date(), selectedRangeObj.hours);
    return rawAlerts.filter(a => a.timestamp >= start);
  }, [rawAlerts, selectedRangeObj]);

  const trendData = useMemo(() => {
    const now = new Date();
    const start = subHours(now, selectedRangeObj.hours);
    const isShort = selectedRangeObj.hours <= 48;

    if (isShort) {
      return eachHourOfInterval({ start, end: now }).map(date => {
        const next = new Date(date.getTime() + 3_600_000);
        const bin = filteredAlerts.filter(a => a.timestamp >= date && a.timestamp < next);
        return { date: format(date, 'HH:mm'), total: bin.length, critical: bin.filter(a => a.severity === 'CRITICAL').length };
      });
    } else {
      return eachDayOfInterval({ start, end: now }).map(date => {
        const dayStr = format(date, 'yyyy-MM-dd');
        const bin = filteredAlerts.filter(a => format(a.timestamp, 'yyyy-MM-dd') === dayStr);
        return { date: format(date, 'MMM d'), total: bin.length, critical: bin.filter(a => a.severity === 'CRITICAL').length };
      });
    }
  }, [filteredAlerts, selectedRangeObj]);

  const hourlyData = useMemo(() => {
    const h = new Array(24).fill(0);
    filteredAlerts.forEach(a => h[a.timestamp.getHours()]++);
    return h.map((count, i) => ({ hour: `${String(i).padStart(2, '0')}:00`, alerts: count }));
  }, [filteredAlerts]);

  // Prefer server stats, fall back to client-side
  const summary = statsData?.summary;
  const stats = {
    totalAlerts: summary?.total_alerts ?? filteredAlerts.length,
    critical: summary?.critical_incidents ?? filteredAlerts.filter(a => a.severity === 'CRITICAL').length,
    avgPerDay: summary?.avg_alerts_per_day?.toFixed(1)
      ?? (filteredAlerts.length / Math.max(1, selectedRangeObj.hours / 24)).toFixed(1),
    peakHour: summary?.peak_hour ?? hourlyData.reduce((m, c) => c.alerts > m.alerts ? c : m, hourlyData[0])?.hour,
  };

  // Severity distribution
  const severityData = useMemo(() => {
    const src = statsData?.severity_distribution;
    if (src) return Object.entries(src).map(([name, value]) => ({ name, value })).filter(x => x.value > 0);
    const counts: Record<string, number> = { MEDIUM: 0, HIGH: 0, CRITICAL: 0 };
    filteredAlerts.forEach(a => { if (counts[a.severity] !== undefined) counts[a.severity]++; });
    return Object.entries(counts).map(([name, value]) => ({ name, value })).filter(x => x.value > 0);
  }, [statsData, filteredAlerts]);

  // ═════════════════════════════════════════════════════════════════════════════
  // FIX 4: IMPROVED Zone Type Distribution Logic
  // ═════════════════════════════════════════════════════════════════════════════
  // Verify that zoneTypeData is properly populated with all three types
  const zoneTypeData = useMemo(() => {
    // Try server stats first
    const src = statsData?.zone_type_distribution;
    if (src && Object.keys(src).length > 0) {
      return Object.entries(src)
        .map(([name, value]) => ({ name, value }))
        .filter(x => x.value > 0);
    }

    // Fall back to client-side aggregation
    const counts: Record<string, number> = { FOB: 0, PLATFORM: 0, BOOKING: 0 };

    filteredAlerts.forEach(a => {
      // Use improved deriveZoneType function
      const t = deriveZoneType(a);

      if (t && counts.hasOwnProperty(t)) {
        counts[t]++;
      }
    });

    // Return all non-zero entries
    return Object.entries(counts)
      .map(([name, value]) => ({ name, value }))
      .filter(x => x.value > 0);
  }, [statsData, filteredAlerts]);

  // Top cameras
  const cameraData = useMemo(() => {
    const src = statsData?.top_cameras;
    if (src) return src.slice(0, 5).map(c => ({ name: getCameraLabel(c.camera_id), value: c.count }));
    const counts: Record<string, number> = {};
    filteredAlerts.forEach(a => {
      const key = getCameraLabel(a.cameraId || a.cameraName);
      counts[key] = (counts[key] || 0) + 1;
    });
    return Object.entries(counts).map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value).slice(0, 5);
  }, [statsData, filteredAlerts]);

  // Server hourly distribution (falls back to client)
  const hourlyChartData = useMemo(() => {
    const src = statsData?.hourly_distribution;
    if (src) return src.map(h => ({ hour: h.hour, alerts: h.count }));
    return hourlyData;
  }, [statsData, hourlyData]);

  const tooltipStyle = {
  backgroundColor: 'hsl(var(--card))',
  border: '1px solid hsl(var(--border))',
  borderRadius: '8px',
  color: 'hsl(var(--foreground))',
};

  const stationZoneIds = useMemo(
    () => Array.from(new Set([
      ...FOB_GROUPS.flatMap(g => g.zoneIds),
      ...PLATFORM_GROUPS.flatMap(g => g.zoneIds),
      ...BOOKING_GROUPS.flatMap(g => g.zoneIds),
    ].filter(Boolean).map(normalizeZoneId))),
    []);

  const rangeConfig = selectedRangeObj;
  const stationHistoryQuery = useZoneHistoryQuery(
    stationZoneIds,
    'station-wide-footfall',
    timeRange,
    rangeConfig,
    [],
  );
  const fobHistoryQueries = useZoneHistoryQueries(FOB_GROUPS, timeRange, rangeConfig);
  const platformHistoryQueries = useZoneHistoryQueries(PLATFORM_GROUPS, timeRange, rangeConfig);
  const bookingHistoryQueries = useZoneHistoryQueries(BOOKING_GROUPS, timeRange, rangeConfig);

  const visiblePlatforms = showAllPlatforms
    ? PLATFORM_GROUPS
    : PLATFORM_GROUPS.slice(0, 4);

  return (
    <PageLayout>
      <div className="space-y-6 animate-fade-in w-full">

        {/* ── Page Header ── */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <h1
              className="text-xl font-bold text-foreground tracking-tight"
              style={{ fontFamily: "'Outfit', sans-serif" }}
            >
              Analytics Reports
            </h1>
            <p
              className="text-xs text-muted-foreground mt-0.5"
              style={{ fontFamily: "'Outfit', sans-serif" }}
            >
              Historical data analysis and safety insights
            </p>
          </div>
          <Select value={timeRange} onValueChange={setTimeRange}>
           <SelectTrigger className="h-9 w-[180px] bg-card border-border text-foreground">
  <CalendarClock className="w-4 h-4 mr-2 text-muted-foreground" />
  <SelectValue />
</SelectTrigger>
            <SelectContent>
              {REPORT_RANGES.map(r => (
                <SelectItem key={r.id} value={r.id}>{r.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* ── Summary Stats ── */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 sm:gap-4">
          {[
            { icon: AlertTriangle, label: 'Total Alerts', value: stats.totalAlerts, className: 'text-foreground', iconClass: 'text-primary' },
{ icon: TrendingUp, label: 'Critical', value: stats.critical, className: 'text-risk-critical', iconClass: 'text-risk-critical' },
{ icon: Users, label: 'Avg / Day', value: stats.avgPerDay, className: 'text-foreground', iconClass: 'text-primary' },
{ icon: Clock, label: 'Peak Hour', value: stats.peakHour, className: 'text-foreground', iconClass: 'text-primary' },
          ].map(({ icon: Icon, label, value, className, iconClass }) => (
            <div key={label} className="rounded-lg border border-border bg-card p-3 sm:p-5 shadow-sm">
              <div className="flex items-center gap-1.5 sm:gap-2 mb-1 sm:mb-2">
                <Icon className={`w-3.5 h-3.5 sm:w-4 sm:h-4 ${iconClass}`} />
                <span className="text-muted-foreground text-[10px] sm:text-xs uppercase tracking-wider">{label}</span>
              </div>
              <p className={`metric-value text-lg sm:text-2xl font-bold ${className}`}>
                {isLoading ? '—' : value ?? '—'}
              </p>
            </div>
          ))}
        </div>

        {/* ── Station-Wide Footfall ── */}
        <div>
          <div className="flex items-center gap-2 mb-3">
            <Layers className="w-4 h-4 text-primary" />
            <h2 className="text-base font-semibold text-foreground">Station-Wide Footfall</h2>
            <span className="text-xs text-muted-foreground">(All cameras combined)</span>
          </div>
          <ZoneHistoryGraph
            title="SECUNDERABAD STATION - TOTAL FOOTFALL"
            hue={215}
            rangeLabel={selectedRangeObj.label}
            data={stationHistoryQuery.data?.chartData ?? []}
            isLoading={stationHistoryQuery.isLoading}
            overallPeak={stationHistoryQuery.data?.overallPeak ?? 0}
          />
        </div>

        {/* ── FOB Zones ── */}
        <div>
          <div className="flex items-center gap-2 mb-3">
            <Activity className="w-4 h-4 text-primary" />
            <h2 className="text-base font-semibold text-foreground">FOB Zone Footfall</h2>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {FOB_GROUPS.map((z, idx) => {
              const query = fobHistoryQueries[idx];
              return (
                <ZoneHistoryGraph
                  key={z.title}
                  title={z.title}
                  hue={z.hue}
                  rangeLabel={selectedRangeObj.label}
                  data={query?.data?.chartData ?? []}
                  isLoading={query?.isLoading ?? false}
                  overallPeak={query?.data?.overallPeak ?? 0}
                />
              );
            })}
          </div>
        </div>

        {/* ── Platform Zones ── */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <BarChart2 className="w-4 h-4 text-primary" />
              <h2 className="text-base font-semibold text-foreground">Platform Footfall</h2>
            </div>
            <button
              onClick={() => setShowAllPlatforms(p => !p)}
              className="text-xs text-primary hover:underline"
            >
              {showAllPlatforms ? 'Show less' : `Show all ${PLATFORM_GROUPS.length}`}
            </button>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            {visiblePlatforms.map(z => {
              const platformIndex = PLATFORM_GROUPS.findIndex(group => group.title === z.title);
              if (platformIndex === -1) return null;
              const query = platformHistoryQueries[platformIndex];
              return (
                <ZoneHistoryGraph
                  key={z.title}
                  title={z.title}
                  hue={z.hue}
                  rangeLabel={selectedRangeObj.label}
                  data={query?.data?.chartData ?? []}
                  isLoading={query?.isLoading ?? false}
                  overallPeak={query?.data?.overallPeak ?? 0}
                />
              );
            })}
          </div>
        </div>

        {/* ── Booking Counter Footfall ── */}
        <div>
          <div className="flex items-center gap-2 mb-3">
            <BarChart2 className="w-4 h-4 text-primary" />
            <h2 className="text-base font-semibold text-foreground">Booking Counter Footfall</h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
            {BOOKING_GROUPS.map((z, idx) => {
              const query = bookingHistoryQueries[idx];
              return (
                <ZoneHistoryGraph
                  key={z.title}
                  title={z.title}
                  hue={z.hue}
                  rangeLabel={selectedRangeObj.label}
                  data={query?.data?.chartData ?? []}
                  isLoading={query?.isLoading ?? false}
                  overallPeak={query?.data?.overallPeak ?? 0}
                />
              );
            })}
          </div>
        </div>

        {/* ── Alert Analytics Section ── */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">

          {/* Alert Trend */}
          <Card className="bg-card border border-border shadow-sm">
  <CardHeader>
    <CardTitle className="text-base text-foreground">Alert Trend</CardTitle>
              <CardDescription className="text-muted-foreground">
                {selectedRangeObj.hours <= 48 ? 'Hourly' : 'Daily'} alerts over {selectedRangeObj.label.toLowerCase()}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={250}>
                <LineChart data={trendData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="date" stroke="hsl(var(--muted-foreground))" fontSize={12} minTickGap={30} />
                  <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} allowDecimals={false} />
                  <Tooltip contentStyle={tooltipStyle} itemStyle={{ color: 'hsl(var(--foreground))' }}/>
                  <Legend />
                  <Line type="monotone" dataKey="total" stroke="#3b82f6" name="Total Alerts" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="critical" stroke="#ef4444" name="Critical" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          {/* Severity Distribution */}
          <Card className="bg-card border border-border shadow-sm">
  <CardHeader>
    <CardTitle className="text-base text-foreground">Severity Distribution</CardTitle>
              <CardDescription className="text-muted-foreground ">Breakdown by importance</CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie
                    data={severityData}
                    cx="50%" cy="50%"
                    innerRadius={50} outerRadius={80}
                    paddingAngle={2}
                    dataKey="value"
                    label={({ name, value }) => `${name}: ${value}`}
                  >
                    {severityData.map((_, i) => (
                      <Cell key={i} fill={SEVERITY_COLORS[i % SEVERITY_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={tooltipStyle} itemStyle={{ color: 'hsl(var(--foreground))' }} />
                </PieChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          {/* Zone Type Distribution */}
          <Card className="bg-card border border-border shadow-sm">
  <CardHeader>
    <CardTitle className="text-base text-foreground">Zone Type Distribution</CardTitle>
              <CardDescription className="text-muted-foreground">Alerts breakdown by zone type</CardDescription>
            </CardHeader>
            <CardContent>
              {zoneTypeData.length === 0 ? (
                <div className="h-[250px] flex items-center justify-center text-sm text-muted-foreground">

  No zone-type data available for this range
</div>
              ) : (
                <ResponsiveContainer width="100%" height={250}>
                  <PieChart>
                    <Pie
                      data={zoneTypeData}
                      cx="50%" cy="50%"
                      innerRadius={50} outerRadius={80}
                      paddingAngle={2}
                      dataKey="value"
                      label={({ name, value }) => `${name}: ${value}`}
                    >
                      {zoneTypeData.map((entry) => (
                        <Cell
                          key={entry.name}
                          fill={ZONE_TYPE_COLORS[entry.name as keyof typeof ZONE_TYPE_COLORS] ?? 'hsl(var(--primary))'}
                        />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={tooltipStyle} itemStyle={{ color: 'hsl(var(--foreground))' }} />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>

          {/* Top Alert Sources */}
          <Card className="bg-card border border-border shadow-sm">
  <CardHeader>
    <CardTitle className="text-base text-foreground">Top Alert Sources</CardTitle>
              <CardDescription className="text-muted-foreground">Cameras with highest frequency</CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={cameraData} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis type="number" stroke="hsl(var(--muted-foreground))" fontSize={12} allowDecimals={false} />
                  <YAxis type="category" dataKey="name" stroke="hsl(var(--muted-foreground))" fontSize={11} width={120} />
                  <Tooltip contentStyle={tooltipStyle} itemStyle={{ color: 'hsl(var(--foreground))' }} />
                  <Bar dataKey="value" fill="#3b82f6" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          {/* Time Distribution */}
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle className="text-base text-foreground">Time Distribution</CardTitle>
              <CardDescription className="text-muted-foreground">Alerts by hour of day (00–23h)</CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={hourlyChartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="hour" stroke="hsl(var(--muted-foreground))" fontSize={10} interval={1} />
                  <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} allowDecimals={false} />
                  <Tooltip contentStyle={tooltipStyle} itemStyle={{ color: 'hsl(var(--foreground))' }} />
                  <Bar dataKey="alerts" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

        </div>

        {/* ── Info Note ── */}
        <div className="rounded-lg border border-border bg-card p-3 sm:p-5 shadow-sm">
          <FileText className="w-5 h-5 text-slate-500 flex-shrink-0 mt-0.5" />
<div className="text-sm text-muted-foreground">
  <p className="font-medium text-foreground mb-1">Live Analytics Data</p>
            <p>
              Reports are generated based on the selected time range: <strong>{selectedRangeObj.label}</strong>.
              Station-wide and zone footfall charts have their own independent time range selectors.
            </p>
          </div>
        </div>
      </div>
    </PageLayout>
  );
}
