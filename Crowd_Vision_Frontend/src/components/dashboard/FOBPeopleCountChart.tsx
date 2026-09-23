import { useState, useEffect, useMemo, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart';
import { Area, AreaChart, XAxis, YAxis, CartesianGrid, ResponsiveContainer } from 'recharts';
import { TrendingUp, TrendingDown, Activity, CalendarClock } from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { format, subDays, startOfDay } from 'date-fns';
import { analyticsApi } from '@/services/analyticsApi';

// ==========================================
// 1. DATA TYPES (Matches Backend Response)
// ==========================================
interface BackendFobData {
  timestamp: string; // ISO String from backend
  count: number;
}

interface FOBDataPoint {
  time: string;       // Formatted for X-Axis display
  count: number;
  timestamp: Date;    // Object for logic
  isSimulated?: boolean;
}

// Map global "0", "7", "30" to our internal IDs
const GLOBAL_MAP: Record<string, string> = {
  '0': '1h',
  '7': '7d',
  '30': '30d'
};

const RANGES = [
  { id: '1h', label: 'Last 1 Hour', hours: 1, resolutionMinutes: 5 },
  { id: '12h', label: 'Last 12 Hours', hours: 12, resolutionMinutes: 5 },
  { id: '24h', label: 'Last 24 Hours', hours: 24, resolutionMinutes: 10 },
  { id: '48h', label: 'Last 48 Hours', hours: 48, resolutionMinutes: 15 },
  { id: '72h', label: 'Last 72 Hours', hours: 72, resolutionMinutes: 30 },
  { id: '7d', label: 'Last Week', hours: 168, resolutionMinutes: 60 },
  { id: '14d', label: 'Last 2 Weeks', hours: 336, resolutionMinutes: 120 },
  { id: '30d', label: 'Last 30 Days', hours: 720, resolutionMinutes: 240 },
];

// ==========================================
// 2. SIMULATION LOGIC (FALLBACK)
// ==========================================
const getSeed = (str: string) => {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash;
  }
  return Math.abs(hash);
};

const getSimulatedCount = (fobId: string, time: Date) => {
  const seed = getSeed(fobId);
  const hour = time.getHours();
  const minute = time.getMinutes();
  const totalMinutes = hour * 60 + minute;
  const baseLine = 60 + (seed % 70);
  const amplitude = 30 + ((seed >> 2) % 50);
  const phaseShift = ((seed >> 4) % 24) * 60;
  const x = (totalMinutes + phaseShift) * (Math.PI / 720);
  const primaryWave = Math.sin(x);
  const secondaryWave = Math.cos(totalMinutes * (Math.PI / 180));
  const noise = (Math.sin(totalMinutes * 0.5 + seed) * 15);
  const value = baseLine + (primaryWave * amplitude) + (secondaryWave * 8) + noise;
  return Math.max(10, Math.round(value));
};

const CHART_CONFIG = {
  count: {
    label: "People Count",
    color: "hsl(var(--chart-1))",
  },
};

interface FOBPeopleCountChartProps {
  currentCount?: number;
  currentDensity?: number;
  title?: string;
  fobId?: string;
  globalTimeRange?: string; // Optional prop to sync with global filter
  minimalHeader?: boolean;
  hideCurrentCount?: boolean;
}

export function FOBPeopleCountChart({
  currentCount = 0,
  title = "FOB Total Footfall",
  fobId = "default",
  globalTimeRange,
  minimalHeader = false,
  hideCurrentCount = false
}: FOBPeopleCountChartProps) {

  // Default to 1h locally, but listen to global prop
  const [selectedRangeId, setSelectedRangeId] = useState('1h');
  const [data, setData] = useState<FOBDataPoint[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [dailyStats, setDailyStats] = useState<{ avg: number; peak: number; peakTime: Date | null }>({ avg: 0, peak: 0, peakTime: null });

  // Sync with global filter if it changes
  useEffect(() => {
    if (globalTimeRange && GLOBAL_MAP[globalTimeRange]) {
      setSelectedRangeId(GLOBAL_MAP[globalTimeRange]);
    }
  }, [globalTimeRange]);

  const selectedRange = RANGES.find(r => r.id === selectedRangeId) || RANGES[0];

  // ==========================================
  // 3. FETCH OR SIMULATE DATA
  // ==========================================
  // ==========================================
  // 3. DATA GENERATION & LIVE UPDATES
  // ==========================================

  // ==========================================
  // 3. DATA PERSISTENCE & LIVE UPDATES
  // ==========================================

  const STORAGE_KEY = `fob_chart_data_${fobId}_1h`;

  // Helper to save to local storage
  const saveToStorage = (points: FOBDataPoint[]) => {
    try {
      // Store only necessary fields to save space
      const simplePoints = points.map(p => ({
        time: p.time,
        count: p.count,
        timestamp: p.timestamp.getTime() // Store as timestamp number
      }));
      localStorage.setItem(STORAGE_KEY, JSON.stringify(simplePoints));
    } catch (e) {
    }
  };

  // Helper to load from local storage
  const loadFromStorage = (): FOBDataPoint[] => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (!stored) return [];
      const parsed = JSON.parse(stored);
      // Rehydrate Dates
      return parsed.map((p: any) => ({
        ...p,
        timestamp: new Date(p.timestamp),
        isSimulated: false
      }));
    } catch (e) {
      return [];
    }
  };

  // Keep track of latest count without triggering effect re-runs
  const currentCountRef = useRef(currentCount);
  useEffect(() => {
    currentCountRef.current = currentCount;
  }, [currentCount]);

  useEffect(() => {
    let isMounted = true;
    let intervalId: NodeJS.Timeout;

    // Clear data immediately to prevent stale view
    setData([]);

    const initData = async () => {
      // 1. Try loading from local storage first
      let localData = loadFromStorage();

      // 2. Filter out data older than 1 hour immediately
      const now = new Date();
      const oneHourAgo = new Date(now.getTime() - 60 * 60 * 1000);
      localData = localData.filter(d => d.timestamp > oneHourAgo);

      // 3. If we have very little data (e.g. < 5 mins), fetch history to fill gap
      // Otherwise, trust local data to avoid gaps/jumps
      if (localData.length < 5) {
        setIsLoading(true);
        try {
          const start = new Date(now.getTime() - selectedRange.hours * 3600000);
          // Construct interval string based on resolution
          const intervalStr = selectedRange.resolutionMinutes >= 60
            ? '1h'
            : `${selectedRange.resolutionMinutes}m`;

          const history = await analyticsApi.getFobHistory({
            fob_id: fobId,
            start: start.toISOString(),
            end: now.toISOString(),
            interval: intervalStr
          });

          if (isMounted) {
            const mappedPoints: FOBDataPoint[] = history.map(h => {
              const d = new Date(h.timestamp);
              return {
                time: selectedRange.hours > 24
                  ? d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit' })
                  : d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }),
                count: h.count,
                timestamp: d,
                isSimulated: false
              };
            });
            // Prefer API history if local was empty/stale
            localData = mappedPoints;
          }
        } catch (err) {
        } finally {
          if (isMounted) setIsLoading(false);
        }
      }

      if (isMounted) {
        setData(localData);
      }
    };

    // Only init data if we are in 1h mode (live mode) or switching to it
    if (selectedRange.id === '1h') {
      initData();

      // Live Update Loop
      intervalId = setInterval(() => {
        setData(prevData => {
          const now = new Date();
          // Create new point
          const newPoint: FOBDataPoint = {
            time: now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }),
            count: currentCountRef.current,
            timestamp: now,
            isSimulated: false
          };

          // STRICT ROLLING WINDOW: Filter strictly last 60 minutes
          // We do this relative to 'now'
          const windowStart = new Date(now.getTime() - 60 * 60 * 1000);

          let newData = [...prevData, newPoint];
          newData = newData.filter(p => p.timestamp >= windowStart);

          // Save to storage side-effect
          saveToStorage(newData);

          return newData;
        });
      }, 5000);
    } else {
      // ... (Existing logic for other ranges can remain or call fetchHistory directly)
      // For brevity, using the original fetch logic for non-1h ranges
      const fetchHistory = async () => {
        setIsLoading(true);
        try {
          const now = new Date();
          const start = new Date(now.getTime() - selectedRange.hours * 3600000);
          // Construct interval string based on resolution
          const intervalStr = selectedRange.resolutionMinutes >= 60 ? '1h' : `${selectedRange.resolutionMinutes}m`;
          const history = await analyticsApi.getFobHistory({
            fob_id: fobId,
            start: start.toISOString(),
            end: now.toISOString(),
            interval: intervalStr
          });
          if (isMounted) {
            const mappedPoints: FOBDataPoint[] = history.map(h => {
              const d = new Date(h.timestamp);
              return {
                time: selectedRange.hours > 24
                  ? d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit' })
                  : d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }),
                count: h.count,
                timestamp: d,
                isSimulated: false
              };
            });
            setData(mappedPoints);
          }
        } catch (err) {
        } finally {
          if (isMounted) setIsLoading(false);
        }
      };
      fetchHistory();
    }

    return () => {
      isMounted = false;
      if (intervalId) clearInterval(intervalId);
    };
  }, [selectedRange, fobId]); // Re-run when range or ID changes

  // Fetch 24h stats specifically for dashboard view (Unchanged)
  useEffect(() => {
    if (minimalHeader) {
      const fetch24hStats = async () => {
        try {
          const now = new Date();
          const start = new Date(now.getTime() - 24 * 3600000);
          const history = await analyticsApi.getFobHistory({
            fob_id: fobId,
            start: start.toISOString(),
            end: now.toISOString(),
            interval: '1h' // Coarse grain is fine for stats
          });

          if (history.length > 0) {
            const counts = history.map(h => h.count);
            const sum = counts.reduce((a, b) => a + b, 0);
            const avg = Math.round(sum / counts.length);

            let peak = 0;
            let peakTime: Date | null = null;
            history.forEach(h => {
              if (h.count >= peak) {
                peak = h.count;
                peakTime = new Date(h.timestamp);
              }
            });

            setDailyStats({ avg, peak, peakTime });
          }
        } catch (e) {
        }
      };

      fetch24hStats();
      // Poll every 5 minutes for stats updates
      const statsInterval = setInterval(fetch24hStats, 5 * 60 * 1000);
      return () => clearInterval(statsInterval);
    }
  }, [minimalHeader, fobId]);


  // ==========================================
  // 4. STATS CALCULATION (Client-Side)
  // ==========================================
  const stats = useMemo(() => {
    // For 1h view, strictly use the visible data for calculation
    // This ensures what you see is what you get for AVG/PEAK
    if (data.length === 0) return { avg: 0, peak: 0, trend: 0, peakTime: null };

    const sum = data.reduce((acc, curr) => acc + curr.count, 0);
    const avg = Math.round(sum / data.length);

    let peak = 0;
    let peakTime: Date | null = null;
    data.forEach(d => {
      if (d.count >= peak) {
        peak = d.count;
        peakTime = d.timestamp;
      }
    });

    const trend = data.length > 1 ? data[data.length - 1].count - data[0].count : 0;

    return { avg, peak, trend, peakTime };
  }, [data]); // Strictly depend on data

  // ==========================================
  // 5. DAILY STATS PERSISTENCE (Peak/Avg)
  // ==========================================
  const DAILY_STATS_KEY = `fob_daily_stats_${fobId}`;

  // Helper to load daily stats
  const loadDailyStats = () => {
    try {
      const stored = localStorage.getItem(DAILY_STATS_KEY);
      if (!stored) return null;
      const parsed = JSON.parse(stored);
      // VALIDATE DATE (Reset at midnight)
      const storedDate = new Date(parsed.timestamp);
      const today = new Date();
      if (storedDate.toDateString() !== today.toDateString()) {
        return null; // Stats are from yesterday, discard
      }
      return {
        ...parsed,
        peakTime: parsed.peakTime ? new Date(parsed.peakTime) : null
      };
    } catch (e) {
      return null;
    }
  };

  const saveToDailyStorage = (peak: number, peakTime: Date | null, avg: number) => {
    try {
      const payload = {
        peak,
        peakTime: peakTime ? peakTime.getTime() : null,
        avg,
        timestamp: new Date().getTime() // Store current time to check date later
      };
      localStorage.setItem(DAILY_STATS_KEY, JSON.stringify(payload));
    } catch (e) {
    }
  };


  // Persistent high-water mark for live visualization
  // Persistent high-water mark for live visualization
  const [maxSeen, setMaxSeen] = useState(0);
  const [maxSeenTime, setMaxSeenTime] = useState<Date | null>(null);
  const [isInitialized, setIsInitialized] = useState(false);

  // Load initial state from storage
  useEffect(() => {
    // Reset state for the new FOB ID immediately
    setMaxSeen(0);
    setMaxSeenTime(null);
    setIsInitialized(false);

    const stored = loadDailyStats();
    if (stored) {
      if (stored.peak > 0) {
        setMaxSeen(stored.peak);
        setMaxSeenTime(stored.peakTime);
      }
      // Also ensure we respect the stored avg if it exists and is valid
      if (stored.avg > 0) {
        setDailyStats({ avg: stored.avg, peak: stored.peak, peakTime: stored.peakTime });
      }
    } else {
      setDailyStats({ avg: 0, peak: 0, peakTime: null });
    }

    setIsInitialized(true);
  }, [fobId]); // Re-run if FOB changes

  useEffect(() => {
    // Prevent overwriting storage with 0 or low values before initialization is done
    if (!isInitialized) return;

    if (currentCount > maxSeen) {
      setMaxSeen(currentCount);
      const now = new Date();
      setMaxSeenTime(now);
      // Persist immediately on new peak
      saveToDailyStorage(currentCount, now, dailyStats.avg);
    }
  }, [currentCount, maxSeen, dailyStats.avg, isInitialized]);

  // Sync maxSeen with historical peak when it loads from API
  useEffect(() => {
    if (dailyStats.peak > maxSeen) {
      setMaxSeen(dailyStats.peak);
      if (dailyStats.peakTime) {
        setMaxSeenTime(dailyStats.peakTime);
        // Persist the API's historical peak as it's higher
        saveToDailyStorage(dailyStats.peak, dailyStats.peakTime, dailyStats.avg);
      }
    }
  }, [dailyStats.peak, dailyStats.peakTime, maxSeen, dailyStats.avg]);

  // Rolling 24h Stats (for Dashboard view minimal header)
  const stats24h = useMemo(() => {
    // If we have a live peak (maxSeen) that is higher, use it.
    const isLivePeak = maxSeen >= dailyStats.peak;

    // Check if we have stored daily stats that might be better than valid state
    // (This is covered by the initial load effect updating maxSeen)

    return {
      avg: dailyStats.avg, // Avg typically comes from historical API or 24h calc
      peak: isLivePeak ? maxSeen : dailyStats.peak,
      peakTime: isLivePeak ? maxSeenTime : dailyStats.peakTime
    };
  }, [dailyStats, maxSeen, maxSeenTime]);

  // IF minimal header (dashboard), show 24h stats.
  // IF NOT minimal header (details page), show stats derived from current view (1h typically)
  const displayStats = minimalHeader ? stats24h : stats;
  // Fallback to "today" if we have valid daily stats
  const finalDisplayPeak = minimalHeader ? Math.max(displayStats.peak, maxSeen) : displayStats.peak;

  const avgLabel = minimalHeader ? "AVG (24H)" : `AVG (${selectedRange.label})`;
  const peakLabel = minimalHeader ? "PEAK (24H)" : `PEAK (${selectedRange.label})`;

  return (
    <Card className="bg-card/80 backdrop-blur-xl border-border/60 overflow-hidden">
      <CardHeader className="pb-2 px-3 sm:px-6">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3 w-full sm:w-auto">
            {/* Icon */}
            <div className="p-2 rounded-lg bg-primary/15 shrink-0">
              <Activity className="h-4 w-4 sm:h-5 sm:w-5 text-primary" />
            </div>
            {/* Title & Subtitle */}
            <div className="min-w-0">
              <CardTitle className="text-sm sm:text-base font-semibold text-foreground truncate">Total Footfall</CardTitle>
              <div className="flex items-center gap-2 mt-0.5">
                <p className="text-[10px] sm:text-xs text-muted-foreground truncate">{minimalHeader ? 'Live Monitoring' : stats.peakTime ? `Peak at ${stats.peakTime.toLocaleTimeString("en-IN")}` : 'Analyzing...'}</p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 sm:gap-4 w-full sm:w-auto justify-between sm:justify-end">
            {/* Selector (Hidden in Dashboard/Minimal Mode) */}
            {!minimalHeader && (
              <Select value={selectedRangeId} onValueChange={setSelectedRangeId}>
                <SelectTrigger className="h-8 w-[110px] sm:w-[130px] text-xs bg-muted/50 border-border/50">
                  <CalendarClock className="w-3 h-3 mr-2 text-muted-foreground" />
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {RANGES.map(r => (
                    <SelectItem key={r.id} value={r.id} className="text-xs">
                      {r.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}

            {/* Quick Stats Block */}
            <div className={`flex items-center gap-3 sm:gap-5 flex-1 sm:flex-initial justify-end ${!minimalHeader ? 'pl-2 border-l border-border/50' : ''}`}>

              {/* Current Value & Trend */}
              {!hideCurrentCount && (
                <div className="text-right">
                  <p className="metric-value text-foreground text-lg">{currentCount}</p>
                  <div className="flex items-center justify-end gap-1.5 text-xs mt-0.5">
                    {stats.trend >= 0 ? (
                      <TrendingUp className="h-3.5 w-3.5 text-status-active" />
                    ) : (
                      <TrendingDown className="h-3.5 w-3.5 text-risk-high" />
                    )}
                    <span className={stats.trend >= 0 ? 'text-status-active font-medium' : 'text-risk-high font-medium'}>
                      {stats.trend > 0 ? '+' : ''}{stats.trend}
                    </span>
                  </div>
                </div>
              )}

              {!hideCurrentCount && <div className="h-10 w-px bg-border/50" />}

              {/* Avg */}
              <div className="text-center">
                <p className="text-[10px] text-muted-foreground uppercase tracking-wider font-medium">{avgLabel}</p>
                <p className="text-lg font-bold text-foreground">{displayStats.avg}</p>
              </div>

              {/* Peak */}
              <div className="text-center">
                <p className="text-[10px] text-muted-foreground uppercase tracking-wider font-medium">{peakLabel}</p>
                <div className="flex flex-col items-center">
                  <p className="text-lg font-bold text-risk-medium leading-none">{displayStats.peak}</p>
                  {/* @ts-ignore */}
                  {displayStats.peakTime && (
                    <p className="text-[10px] text-muted-foreground mt-1">
                      {/* @ts-ignore */}
                      {displayStats.peakTime.toLocaleTimeString("en-IN", {
                        hour: "2-digit",
                        minute: "2-digit",
                        hour12: true,
                        timeZone: "Asia/Kolkata"
                      })}
                    </p>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="pt-0 pb-4">
        <ChartContainer config={CHART_CONFIG} className="h-[200px] w-full">
          {isLoading ? (
            <div className="h-full w-full flex items-center justify-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={data}
                margin={{ top: 10, right: 15, left: 5, bottom: 25 }}
              >
                <defs>
                  <linearGradient id="fobGradientDark" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="hsl(215 85% 60%)" stopOpacity={0.5} />
                    <stop offset="50%" stopColor="hsl(215 85% 60%)" stopOpacity={0.2} />
                    <stop offset="100%" stopColor="hsl(215 85% 60%)" stopOpacity={0.02} />
                  </linearGradient>
                  <linearGradient id="fobStrokeDark" x1="0" y1="0" x2="1" y2="0">
                    <stop offset="0%" stopColor="hsl(215 85% 55%)" stopOpacity={0.7} />
                    <stop offset="50%" stopColor="hsl(215 85% 65%)" stopOpacity={1} />
                    <stop offset="100%" stopColor="hsl(215 85% 55%)" stopOpacity={0.8} />
                  </linearGradient>
                </defs>
                <CartesianGrid
                  strokeDasharray="3 3"
                  vertical={false}
                  stroke="hsl(225 20% 20%)"
                  strokeOpacity={0.6}
                />
                <XAxis
                  dataKey="time"
                  axisLine={{ stroke: 'hsl(220 15% 30%)', strokeWidth: 1 }}
                  tickLine={{ stroke: 'hsl(220 15% 30%)' }}
                  tick={{ fontSize: 10, fill: 'hsl(220 15% 60%)' }}
                  tickMargin={10}
                  minTickGap={30}
                />
                <YAxis
                  axisLine={{ stroke: 'hsl(220 15% 30%)', strokeWidth: 1 }}
                  tickLine={{ stroke: 'hsl(220 15% 30%)' }}
                  tick={{ fontSize: 10, fill: 'hsl(220 15% 60%)' }}
                  tickCount={6}
                  tickMargin={10}
                  width={35}
                  domain={[0, 'auto']}
                />
                <ChartTooltip
                  content={
                    <ChartTooltipContent
                      labelFormatter={(value) => `Time: ${value}`}
                      formatter={(value) => [`${value} people`, 'Count']}
                    />
                  }
                  cursor={{
                    stroke: 'hsl(215 85% 60%)',
                    strokeWidth: 1,
                    strokeDasharray: '4 4',
                    strokeOpacity: 0.5,
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="count"
                  stroke="url(#fobStrokeDark)"
                  strokeWidth={2.5}
                  fill="url(#fobGradientDark)"
                  dot={false}
                  activeDot={{
                    r: 5,
                    fill: 'hsl(215 85% 60%)',
                    stroke: 'hsl(225 35% 6%)',
                    strokeWidth: 2,
                  }}
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </ChartContainer>
      </CardContent>
    </Card>
  );
}