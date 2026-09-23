import { MonthData, formatFootfall, getFootfallBgColor, getFootfallTextColor, getLiveFootfall } from "@/data/footfallData";
import { ArrowLeft, Users, TrendingUp, ArrowUp, CalendarDays, Train, Activity } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useState, useEffect } from "react";

interface MonthDetailCalendarProps {
  data: MonthData;
  onBack: () => void;
  googleEvents: Record<string, { name: string; color: string }>;
}

const DAY_NAMES = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"];

const getFirstDayOffset = (year: number, month: number): number => {
  const firstDay = new Date(year, month, 1).getDay();
  // Convert Sunday=0 to Monday=0 format
  return firstDay === 0 ? 6 : firstDay - 1;
};

export const MonthDetailCalendar = ({ data, onBack, googleEvents }: MonthDetailCalendarProps) => {
  const offset = getFirstDayOffset(data.year, data.month);
  const totalCells = Math.ceil((offset + data.days.length) / 7) * 7;

  const cells: (typeof data.days[0] | null)[] = Array(totalCells).fill(null);
  data.days.forEach((day, i) => {
    cells[offset + i] = day;
  });

  const monthShortName = data.name.slice(0, 3);
  const today = new Date();
  const isCurrentMonth = today.getFullYear() === data.year && today.getMonth() === data.month;

  const currentTotal = data.currentLiveTotal || data.totalFootfall;

  return (
    <div className="min-h-screen">
      {/* Header */}
      <div className="bg-background border-b border-border px-6 py-4 flex items-center gap-4 sticky top-0 z-10 shadow-sm">
        <Button variant="ghost" size="icon" onClick={onBack} className="rounded-full hover:bg-gray-800 text-foreground">
          <ArrowLeft className="w-5 h-5" />
        </Button>
        <div>
          <h1 className="text-2xl font-black text-foreground">
            {data.name.charAt(0) + data.name.slice(1).toLowerCase()} {data.year}
          </h1>
          <p className="text-sm text-muted-foreground">Daily Footfall Analysis</p>
        </div>
        <div className="ml-auto flex items-center gap-3">
          <div className="text-right text-foreground">
            <p className="text-xs text-muted-foreground flex items-center justify-end gap-1">
              <Activity className="w-3 h-3 text-green-500 animate-pulse" />
             Total Footfall
            </p>
            <p className="text-lg font-black text-foreground tabular-nums tracking-tighter">
              {formatFootfall(currentTotal)}
            </p>
          </div>
        </div>
      </div>

      <div className="w-full px-4 py-6">
        {/* Stats Row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-card border border-gray-800 rounded-xl p-4 flex items-center gap-3 shadow-sm">
            <div className="p-2.5 rounded-xl bg-blue-900/40">
              <Users className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Total Footfall</p>
              <p className="text-lg font-black text-foreground tabular-nums">{formatFootfall(currentTotal)}</p>
            </div>
          </div>

          <div className="bg-card border border-gray-800 rounded-xl p-4 flex items-center gap-3 shadow-sm">
            <div className="p-2.5 rounded-xl bg-amber-900/40">
              <TrendingUp className="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Average Daily</p>
              <p className="text-lg font-black text-foreground">{formatFootfall(data.avgDaily)}</p>
            </div>
          </div>

          <div className="bg-card border border-gray-800 rounded-xl p-4 flex items-center gap-3 shadow-sm">
            <div className="p-2.5 rounded-xl bg-green-900/40">
              <ArrowUp className="w-5 h-5 text-green-400" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Peak Day</p>
              <p className="text-lg font-black text-foreground">
                {formatFootfall(data.peakFootfall)}
              </p>
              <p className="text-xs text-muted-foreground">({data.peakDay} {monthShortName})</p>
            </div>
          </div>

          <div className="bg-card border border-gray-800 rounded-xl p-4 flex items-center gap-3 shadow-sm">
            <div className="p-2.5 rounded-xl bg-purple-900/40">
              <CalendarDays className="w-5 h-5 text-purple-400" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Key Events</p>
              <p className="text-lg font-black text-foreground">{data.keyEvents.length}</p>
              <p className="text-xs text-muted-foreground truncate max-w-[100px]">
                {data.keyEvents.slice(0, 2).join(", ")}
              </p>
            </div>
          </div>
        </div>
{/* Legend */}
        <div className="mt-6 mb-6 flex justify-end">
          <div className="flex flex-wrap gap-6 items-center bg-card backdrop-blur-md border border-gray-800 rounded-2xl px-6 py-4 shadow-xl">
            <span className="text-xs font-black text-muted-foreground uppercase tracking-wider">Footfall Intensity:</span>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-lg shadow-sm border border-border" style={{ backgroundColor: "#39de76ff" }} />
              <span className="text-xs font-bold text-muted-foreground">&lt; 1.4 Lakhs</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-lg shadow-sm border border-border" style={{ backgroundColor: "#d79c1cff" }} />
              <span className="text-xs font-bold text-muted-foreground">1.4L - 1.6L</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-lg shadow-sm border border-border" style={{ backgroundColor: "#f74545" }} />
              <span className="text-xs font-bold text-muted-foreground">&gt; 1.6 Lakhs</span>
            </div>
          </div>
        </div>
        {/* Calendar Grid */}
        <div className="border border-gray-800 rounded-2xl overflow-hidden shadow-sm">
          {/* Day headers */}
          <div className="grid grid-cols-7 bg-navy text-foreground" style={{ backgroundColor: "hsl(var(--navy))" }}>
            {DAY_NAMES.map((day) => (
              <div key={day} className="text-center py-3 text-xs font-bold tracking-wider">
                {day}
              </div>
            ))}
          </div>

          {/* Calendar cells */}
          <div className="grid grid-cols-7 gap-3 p-3 card-black">
            {cells.map((day, idx) => {
              if (!day) {
                return <div key={`empty-${idx}`} className="bg-gray-900 min-h-[120px] rounded-2xl" />;
              }

              const isToday = isCurrentMonth && day.date === today.getDate();
              const currentCount = day.liveFootfall || day.footfall;
              const dayBgColor = getFootfallBgColor(currentCount); // Use live count for color updates

              return (
                <div
                  key={day.date}
                  className={cn(
                    "min-h-[160px] p-3.5 transition-all duration-300 relative rounded-xl flex flex-col",
                    "hover:scale-[1.02] hover:shadow-xl cursor-default group",
                    "border-t-[4px] border-l border-r border-b",
                    "shadow-md"
                  )}
                  style={{
                    borderTopColor: dayBgColor,
                    borderLeftColor: dayBgColor.slice(0, 7) + "99",
                    borderRightColor: dayBgColor.slice(0, 7) + "99",
                    borderBottomColor: dayBgColor.slice(0, 7) + "99",
                  }}
                >
                  {/* Date Header */}
                  <div className="mb-2.5">
                    <span className={cn(
                      "text-xs font-black text-foreground",
                      isToday && "bg-foreground text-background px-2 py-0.5 rounded-md"
                    )}>
                      {String(day.date).padStart(2, "0")} {monthShortName}
                    </span>
                  </div>

                  {/* Day Type */}
                  <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground mb-2">
                    {day.dayType}
                  </p>

                  {/* Event Badge - only show once, no duplication */}
                  {day.event && (
                    <div
                      className="text-[10px] px-2 py-1 rounded-md font-bold truncate border backdrop-blur-sm w-fit mb-2"
                      style={{
                        borderColor: dayBgColor + "60",
                        backgroundColor: dayBgColor + "15",
                        color: dayBgColor
                      }}
                      title={day.event}
                    >
                      {day.event}
                    </div>
                  )}

                  {/* Spacer - pushes content to bottom */}
                  <div className="flex-1" />

                  {/* Footfall Section - Primary Focus */}
                  <div className="space-y-2">
                    {/* Main footfall number */}
                    <div className="flex items-center gap-2 font-black">
                      <Users className="w-4 h-4 flex-shrink-0" style={{ color: dayBgColor }} />
                      <span className="text-base tabular-nums" style={{ color: dayBgColor }}>
                        {formatFootfall(currentCount)}
                      </span>
                    </div>

                    {/* Specials - only shown if exists */}
                    {day.specials > 0 && (
                      <div className="flex items-center gap-2 text-[10px] font-bold text-muted-foreground">
                        <Train className="w-3 h-3 flex-shrink-0" style={{ color: dayBgColor }} />
                        <span>+{day.specials} Specials</span>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>


      </div>
    </div>
  );
};