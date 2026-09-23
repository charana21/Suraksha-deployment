import { useState, useEffect, useMemo, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart';
import { Area, AreaChart, XAxis, YAxis, CartesianGrid, ResponsiveContainer } from 'recharts';
import { Activity, CalendarClock } from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { analyticsApi } from '@/services/analyticsApi';

// ==========================================
// 1. DATA TYPES
// ==========================================
interface FOBDataPoint {
  time: string;       // Formatted for X-Axis display
  count: number;
  timestamp: Date;    // Object for logic
  isSimulated?: boolean;
}

// Map global "0", "7", "30" to our internal IDs
const GLOBAL_MAP: Record<string, string> = {
  '24h': '24h',
  '7d': '7d',
  '30d': '30d'
};

const RANGES = [
  { id: '1h', label: 'Last 1 Hour', hours: 1, resolutionMinutes: 1 },
  { id: '12h', label: 'Last 12 Hours', hours: 12, resolutionMinutes: 5 },
  { id: '24h', label: 'Last 24 Hours', hours: 24, resolutionMinutes: 5 },
  { id: '48h', label: 'Last 48 Hours', hours: 48, resolutionMinutes: 5 },
  { id: '72h', label: 'Last 72 Hours', hours: 72, resolutionMinutes: 30 },
  { id: '7d', label: 'Last 7 Days', hours: 168, resolutionMinutes: 60 },
  { id: '14d', label: 'Last 14 Days', hours: 336, resolutionMinutes: 120 },
  { id: '30d', label: 'Last 30 Days', hours: 720, resolutionMinutes: 240 },
];

const CHART_CONFIG = {
  count: {
    label: "People Count",
    color: "hsl(var(--chart-1))",
  },
};

interface StaticFOBGraphProps {
  title?: string;
  fobId?: string;
  globalTimeRange?: string; // Optional prop to sync with global filter
}

export function StaticFOBGraph({
  title = "FOB Total Footfall",
  fobId = "default",
  globalTimeRange,
}: StaticFOBGraphProps) {

  // Default to 1h locally, but listen to global prop
  const [selectedRangeId, setSelectedRangeId] = useState('1h');
  const [data, setData] = useState<FOBDataPoint[]>([]);
  const [overallPeak, setOverallPeak] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // Sync with global filter if it changes
  useEffect(() => {
    if (globalTimeRange && GLOBAL_MAP[globalTimeRange]) {
      setSelectedRangeId(GLOBAL_MAP[globalTimeRange]);
    }
  }, [globalTimeRange]);

  const selectedRange = RANGES.find(r => r.id === selectedRangeId) || RANGES[0];

  useEffect(() => {
    let isMounted = true;

    const fetchHistory = async () => {
      setIsLoading(true);
      try {
        const now = new Date();
        const start = new Date(now.getTime() - selectedRange.hours * 3600000);

        // Construct interval string based on resolution
        const intervalStr = selectedRange.resolutionMinutes >= 60
          ? '1h'
          : `${selectedRange.resolutionMinutes}m`;

        const response = await analyticsApi.getFobHistory({
          fob_id: fobId,
          start: start.toISOString(),
          end: now.toISOString(),
          interval: intervalStr
        });

        if (isMounted) {
          const mappedPoints: FOBDataPoint[] = response.data.map(h => {
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
          setOverallPeak(response.overall_peak);
        }
      } catch (err) {
      } finally {
        if (isMounted) setIsLoading(false);
      }
    };

    fetchHistory();

    return () => {
      isMounted = false;
    };
  }, [selectedRange, fobId]);

  // Auto-scroll to end when data loads
  useEffect(() => {
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollLeft = scrollContainerRef.current.scrollWidth;
    }
  }, [data]);

  // Stats
  const stats = useMemo(() => {
    if (data.length === 0) return { avg: 0, peak: 0 };
    const sum = data.reduce((acc, curr) => acc + curr.count, 0);
    const avg = Math.round(sum / data.length);
    // Use overall_peak from backend instead of calculating locally
    const peak = overallPeak;
    return { avg, peak };
  }, [data, overallPeak]);

  return (
    <Card className="bg-card/80 backdrop-blur-xl border-border/60 overflow-hidden">
      <CardHeader className="pb-3 px-3 sm:px-6">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 sm:gap-4">
          <div className="flex items-center gap-2 sm:gap-3">
            <div className="p-2 sm:p-2.5 rounded-xl bg-primary/15">
              <Activity className="h-4 w-4 sm:h-5 sm:w-5 text-primary" />
            </div>
            <div>
              <CardTitle className="text-sm sm:text-base font-semibold text-foreground">{title}</CardTitle>
              <div className="flex items-center gap-2 mt-0.5">
                <p className="text-[10px] sm:text-xs text-muted-foreground whitespace-nowrap">History: {selectedRange.label}</p>
              </div>
            </div>
          </div>

          <div className="flex flex-row items-center gap-2 w-full sm:w-auto justify-between sm:justify-end">
            <Select value={selectedRangeId} onValueChange={setSelectedRangeId}>
              <SelectTrigger className="h-7 sm:h-8 w-[110px] sm:w-[130px] text-[10px] sm:text-xs bg-muted/50 border-border/50">
                <CalendarClock className="w-3 h-3 mr-1.5 sm:mr-2 text-muted-foreground" />
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

            <div className="flex items-center gap-3 sm:gap-5 pl-0 sm:pl-2 border-l-0 sm:border-l border-slate-200 ml-auto sm:ml-0">
              <div className="text-center">
                <p className="text-[9px] sm:text-[10px] text-slate-500 uppercase tracking-wider font-medium">AVG</p>
               <p className="text-base sm:text-lg font-bold text-slate-900">{stats.avg}</p>
              </div>
              <div className="text-center">
                <p className="text-[9px] sm:text-[10px] text-slate-500 uppercase tracking-wider font-medium">PEAK</p>
                <p className="text-base sm:text-lg font-bold text-risk-medium">{stats.peak}</p>
              </div>
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="pt-0 pb-4">
        {/* Scrollable Container */}
        <div
          className="w-full overflow-x-auto pb-2"
          ref={scrollContainerRef}
        >
          <div className="min-w-[800px] h-[200px]">
            <ChartContainer config={CHART_CONFIG} className="h-full w-full">
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
                      <linearGradient id="fobGradientDarkStatic" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="hsl(215 85% 60%)" stopOpacity={0.5} />
                        <stop offset="50%" stopColor="hsl(215 85% 60%)" stopOpacity={0.2} />
                        <stop offset="100%" stopColor="hsl(215 85% 60%)" stopOpacity={0.02} />
                      </linearGradient>
                      <linearGradient id="fobStrokeDarkStatic" x1="0" y1="0" x2="1" y2="0">
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
                      stroke="url(#fobStrokeDarkStatic)"
                      strokeWidth={2.5}
                      fill="url(#fobGradientDarkStatic)"
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
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
