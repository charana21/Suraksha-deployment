import React, { useMemo, useRef, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ChartContainer, ChartTooltip } from '@/components/ui/chart';
import {
  ResponsiveContainer,
  AreaChart,
  CartesianGrid,
  XAxis,
  YAxis,
  Area,
  ReferenceLine,
} from 'recharts';
import { Activity } from 'lucide-react';

interface DataPoint {
  time: string;
  count: number;
  timestamp: Date;
}

interface ZoneHistoryGraphProps {
  title?: string;
  hue?: number;
  rangeLabel: string;
  data: DataPoint[];
  isLoading: boolean;
  overallPeak: number;
}

export function ZoneHistoryGraph({
  title = 'Zone Footfall',
  hue = 215,
  rangeLabel,
  data,
  isLoading,
  overallPeak,
}: ZoneHistoryGraphProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollLeft = scrollRef.current.scrollWidth;
    }
  }, [data]);

  const stats = useMemo(() => {
    if (data.length === 0) return { avg: 0 };

    const sum = data.reduce((total, entry) => total + entry.count, 0);

    return {
      avg: Math.round(sum / data.length),
    };
  }, [data]);

  // Y-axis must always stretch to cover the true peak
  // which can come from finer-grained server data and
  // not be present as a literal point in the binned chart series.
  const dataMax = useMemo(
    () => data.reduce((max, entry) => Math.max(max, entry.count), 0),
    [data]
  );

  const yMax = useMemo(() => {
    const rawMax = Math.max(dataMax, overallPeak, 1);
    return Math.ceil((rawMax * 1.15) / 10) * 10;
  }, [dataMax, overallPeak]);

  // Taller charts get more vertical room so the peak isn't
  // squashed into a sliver at the top.
  const chartHeight = useMemo(() => {
    const base = 180;

    if (yMax <= 60) return base;

    return Math.min(320, base + Math.round((yMax - 60) * 0.6));
  }, [yMax]);

  const chartConfig = {
    count: {
      label: 'People Count',
      color: `hsl(${hue} 85% 60%)`,
    },
  };

  const baseId = title.replace(/[^a-z0-9]/gi, '').substring(0, 20);
  const gradientId = `zoneGrad-${baseId}`;
  const strokeId = `zoneStroke-${baseId}`;

  return (
    <Card className="bg-card border-border shadow-sm overflow-hidden">
      <CardHeader className="pb-3 px-3 sm:px-6">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2 sm:gap-3">
            <div
              className="p-2 rounded-xl"
              style={{
                backgroundColor: `hsl(${hue} 85% 60% / 0.15)`,
              }}
            >
              <Activity
                className="h-4 w-4 sm:h-5 sm:w-5"
                style={{
                  color: `hsl(${hue} 85% 60%)`,
                }}
              />
            </div>

            <div>
              <CardTitle className="text-sm sm:text-base font-semibold text-muted-foreground">
                {title}
              </CardTitle>

              <p className="text-[10px] sm:text-xs text-slate-500 whitespace-nowrap mt-0.5">
                History: {rangeLabel}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 sm:gap-5 pl-0 sm:pl-2 border-l-0 sm:border-l border-slate-200 ml-auto sm:ml-0">
            <div className="text-center">
              <p className="text-[9px] sm:text-[10px] text-slate-500 uppercase tracking-wider font-medium">
                AVG
              </p>

              <p className="text-base sm:text-lg font-bold text-foreground">
                {stats.avg}
              </p>
            </div>

            <div className="text-center">
              <p className="text-[9px] sm:text-[10px] text-slate-500 uppercase tracking-wider font-medium">
                PEAK
              </p>

              <p
                className="text-base sm:text-lg font-bold"
                style={{
                  color: `hsl(${hue} 85% 60%)`,
                }}
              >
                {overallPeak}
              </p>
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="pt-0 pb-4">
        <div
          className="w-full overflow-x-auto overflow-y-auto pb-2 max-h-[220px]"
          ref={scrollRef}
          style={{
            scrollbarColor: '#94a3b8 transparent',
            scrollbarWidth: 'thin',
          }}
        >
          <div className="min-w-[600px]" style={{ height: chartHeight }}>
            <ChartContainer config={chartConfig} className="h-full w-full">
              {isLoading ? (
                <div className="h-full w-full flex items-center justify-center">
                  <div
                    className="animate-spin rounded-full h-6 w-6 border-b-2"
                    style={{
                      borderColor: `hsl(${hue} 85% 60%)`,
                    }}
                  />
                </div>
              ) : data.length === 0 ? (
                <div className="h-full w-full flex items-center justify-center text-slate-500 text-sm">
                  No data available
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart
                    data={data}
                    margin={{
                      top: 18,
                      right: 15,
                      left: 5,
                      bottom: 25,
                    }}
                  >
                    <defs>
                      <linearGradient
                        id={gradientId}
                        x1="0"
                        y1="0"
                        x2="0"
                        y2="1"
                      >
                        <stop
                          offset="0%"
                          stopColor={`hsl(${hue} 85% 60%)`}
                          stopOpacity={0.5}
                        />
                        <stop
                          offset="50%"
                          stopColor={`hsl(${hue} 85% 60%)`}
                          stopOpacity={0.2}
                        />
                        <stop
                          offset="100%"
                          stopColor={`hsl(${hue} 85% 60%)`}
                          stopOpacity={0.02}
                        />
                      </linearGradient>

                      <linearGradient
                        id={strokeId}
                        x1="0"
                        y1="0"
                        x2="1"
                        y2="0"
                      >
                        <stop
                          offset="0%"
                          stopColor={`hsl(${hue} 85% 55%)`}
                          stopOpacity={0.7}
                        />
                        <stop
                          offset="50%"
                          stopColor={`hsl(${hue} 85% 65%)`}
                          stopOpacity={1}
                        />
                        <stop
                          offset="100%"
                          stopColor={`hsl(${hue} 85% 55%)`}
                          stopOpacity={0.8}
                        />
                      </linearGradient>
                    </defs>

                    <CartesianGrid
                      strokeDasharray="3 3"
                      vertical={false}
                      stroke="#E2E8F0"
                      strokeOpacity={1}
                    />

                    <XAxis
                      dataKey="time"
                      axisLine={{
                        stroke: '#CBD5E1',
                        strokeWidth: 1,
                      }}
                      tickLine={{
                        stroke: '#CBD5E1',
                      }}
                      tick={{
                        fontSize: 10,
                        fill: '#475569',
                      }}
                      tickMargin={10}
                      minTickGap={30}
                    />

                    <YAxis
                      axisLine={{
                        stroke: '#CBD5E1',
                        strokeWidth: 1,
                      }}
                      tickLine={{
                        stroke: '#CBD5E1',
                      }}
                      tick={{
                        fontSize: 10,
                        fill: '#475569',
                      }}
                      tickCount={5}
                      tickMargin={8}
                      width={35}
                      domain={[0, yMax]}
                      allowDataOverflow={false}
                    />

                   <ChartTooltip
  cursor={{
    stroke: `hsl(${hue} 85% 60%)`,
    strokeWidth: 1,
    strokeDasharray: '4 4',
    strokeOpacity: 0.5,
  }}
  content={({ active, payload, label }) => {
    if (!active || !payload || payload.length === 0) {
      return null;
    }

    const value = payload[0]?.value;

    return (
      <div className="rounded-xl border border-border bg-background px-3 py-2 shadow-lg">
        <p className="text-xs font-medium text-muted-foreground">
          Time: {label}
        </p>

        <p
          className="mt-1 text-sm font-semibold"
          style={{
            color: `hsl(${hue} 85% 60%)`,
          }}
        >
          {value} people
        </p>
      </div>
    );
  }}
/>

                    <Area
                      type="monotone"
                      dataKey="count"
                      stroke={`url(#${strokeId})`}
                      strokeWidth={2.5}
                      fill={`url(#${gradientId})`}
                      dot={false}
                      activeDot={{
                        r: 4,
                        fill: `hsl(${hue} 85% 60%)`,
                        stroke: '#FFFFFF',
                        strokeWidth: 2,
                      }}
                    />

                    {overallPeak > 0 && (
                      <ReferenceLine
                        y={overallPeak}
                        stroke={`hsl(${hue} 85% 60%)`}
                        strokeDasharray="5 4"
                        strokeOpacity={0.8}
                        label={{
                          value: `Peak: ${overallPeak}`,
                          position: 'insideTopRight',
                          fill: '#334155',
                          fontSize: 10,
                          fontWeight: 600,
                        }}
                      />
                    )}
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