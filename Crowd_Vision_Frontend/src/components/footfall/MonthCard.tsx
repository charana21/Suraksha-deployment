import { MonthData, formatFootfall } from "@/data/footfallData";
import { Users, TrendingUp, ArrowUp, CalendarDays } from "lucide-react";
import { useState } from "react";

interface MonthCardProps {
  data: MonthData;
  index: number;
  onClick: () => void;
}

export const MonthCard = ({ data, index, onClick }: MonthCardProps) => {
  const [hovered, setHovered] = useState(false);

  const currentTotal = data.currentLiveTotal || data.totalFootfall;

  const getFootfallColor = (total: number): string => {
    if (total > 7500000) return "#f67676";
    if (total >= 6000000) return "rgb(245, 201, 106)";
    return "rgb(111, 243, 159)";
  };

  const thresholdColor = getFootfallColor(currentTotal);

  return (
    <div
      className="relative cursor-pointer group"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={onClick}
    >
      {/* Hover Popup */}
      {hovered && (
        <div
          className="absolute z-50 bottom-full mb-3 left-1/2 -translate-x-1/2 
                     w-64 bg-card border border-gray-800 rounded-xl shadow-2xl 
                     p-4 pointer-events-none"
        >
          <div className="text-center mb-3">
            <h3 className="font-bold text-base text-foreground ">
              {data.name} {data.year}
            </h3>
            <div
              className="h-0.5 mt-1 rounded-full"
              style={{ backgroundColor: thresholdColor }}
            />
          </div>

          <div className="space-y-2.5">
            <div className="flex items-center gap-2">
              <div className="p-1.5 rounded-lg bg-blue-900/40">
                <Users className="w-3.5 h-3.5 text-blue-400" />
              </div>
              <div className="flex-1">
                <p className="text-xs text-muted-foreground">Total Footfall</p>
                <p className="font-bold text-sm text-blue-400">
                  {formatFootfall(currentTotal)}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <div className="p-1.5 rounded-lg bg-amber-900/40">
                <TrendingUp className="w-3.5 h-3.5 text-amber-400" />
              </div>
              <div className="flex-1">
                <p className="text-xs text-muted-foreground">Average Daily</p>
                <p className="font-bold text-sm text-amber-400">
                  {formatFootfall(data.avgDaily)}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <div className="p-1.5 rounded-lg bg-green-900/40">
                <ArrowUp className="w-3.5 h-3.5 text-green-400" />
              </div>
              <div className="flex-1">
                <p className="text-xs text-muted-foreground">Peak Day</p>
                <p className="font-bold text-sm text-green-400">
                  {formatFootfall(data.peakFootfall)} ({data.peakDay}{" "}
                  {data.name.slice(0, 3)})
                </p>
              </div>
            </div>

            {data.keyEvents.length > 0 && (
              <div className="flex items-start gap-2">
                <div className="p-1.5 rounded-lg bg-purple-900/40 mt-0.5">
                  <CalendarDays className="w-3.5 h-3.5 text-purple-400" />
                </div>
                <div className="flex-1">
                  <p className="text-xs text-muted-foreground mb-1">Key Events</p>
                  <div className="flex flex-wrap gap-1">
                    {data.keyEvents.slice(0, 3).map((event) => (
                      <span
                        key={event}
                        className="text-xs bg-purple-900/40 text-purple-300 px-2 py-0.5 rounded-full"
                      >
                        {event}
                      </span>
                    ))}
                    {data.keyEvents.length > 3 && (
                      <span className="text-xs text-muted-foreground">
                        +{data.keyEvents.length - 3} more
                      </span>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Arrow */}
          <div className="absolute -bottom-2 left-1/2 -translate-x-1/2 w-4 h-4 bg-card border-r border-b border-gray-800 rotate-45" />
        </div>
      )}

      {/* Calendar Card */}
      <div className="calendar-card bg-card rounded-xl shadow-md overflow-hidden transition-all duration-300 hover:shadow-xl hover:-translate-y-1 border border-gray-800 h-48">
        {/* Rings */}
        <div
          className="flex justify-center gap-3 pt-2 px-4"
          style={{ backgroundColor: thresholdColor }}
        >
          <div className="w-3 h-4 bg-card/20 rounded-b-full" />
          <div className="w-3 h-4 bg-card/20 rounded-b-full" />
          <div className="w-3 h-4 bg-card/20 rounded-b-full" />
        </div>

        {/* Header */}
        <div
          className="text-center py-2 px-3 font-bold text-lg tracking-widest text-foreground"
          style={{ backgroundColor: thresholdColor }}
        >
          {data.name}
        </div>

        {/* Value */}
        <div className="bg-card py-10 px-3 text-center">
          <span className="text-2xl font-black text-foreground">
            {formatFootfall(currentTotal)}
          </span>
        </div>
      </div>
    </div>
  );
};