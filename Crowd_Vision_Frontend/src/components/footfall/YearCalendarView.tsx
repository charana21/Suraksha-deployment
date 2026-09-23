import { MonthData, formatFootfall } from "@/data/footfallData";
import { MonthCard } from "@/components/footfall/MonthCard";
import { Users, TrendingUp, ArrowUp, CalendarDays, RefreshCw } from "lucide-react";

interface YearCalendarViewProps {
    yearData: MonthData[];
    year: number;
    onMonthClick: (month: number) => void;
    onYearChange: (year: number) => void;
    googleEventsLoading: boolean;
}

export const YearCalendarView = ({
    yearData,
    year,
    onMonthClick,
    onYearChange,
    googleEventsLoading,
}: YearCalendarViewProps) => {
    const totalYearFootfall = yearData.reduce((sum, m) => sum + (m.currentLiveTotal || m.totalFootfall), 0);
    const avgDailyYear = Math.round(
        yearData.reduce((sum, m) => sum + (m.currentLiveTotal ? Math.round(m.currentLiveTotal / m.days.length) : m.avgDaily), 0) / 12
    );
    const peakMonth = yearData.reduce((best, m) => {
        const currentPeak = m.currentLiveTotal || m.peakFootfall;
        const bestPeak = best.currentLiveTotal || best.peakFootfall;
        return currentPeak > bestPeak ? m : best;
    });
    const totalEvents = yearData.reduce((sum, m) => sum + m.keyEvents.length, 0);

    return (
        <div className="min-h-screen">
            {/* Top Header */}
            <div className="bg-background border-b border-border shadow-sm sticky top-0 z-10">
                <div className="w-full px-4 sm:px-6 py-4">
                    <div className="flex items-center justify-between">
                        <div>
                            <h1 className="text-2xl sm:text-3xl font-black text-accent-orange">
                                Calendar Analytics
                            </h1>
                            <p className="text-sm text-muted-foreground mt-0.5">
                                Railway Station Annual Footfall Report
                            </p>
                        </div>
                        <div className="flex items-center gap-2">
                            {/* <button
                                onClick={() => onYearChange(year - 1)}
                                className="px-3 py-1.5 rounded-lg border border-border hover:bg-muted transition-colors text-sm font-semibold"
                            >
                                ◀ {year - 1}
                            </button> */}
                            <div
                                className="px-5 py-1.5 rounded-lg text-foreground font-black text-lg"
                                style={{ backgroundColor: "hsl(var(--navy))" }}
                            >
                                {year}
                            </div>
                            {/* <button
                                onClick={() => onYearChange(year + 1)}
                                className="px-3 py-1.5 rounded-lg border border-border hover:bg-muted transition-colors text-sm font-semibold"
                            >
                                {year + 1} ▶
                            </button> */}
                        </div>
                    </div>
                </div>
            </div>

            <div className="w-full px-4 sm:px-6 py-6 font-primary text-foreground">
                {/* Annual Summary Stats */}
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                    <div className="bg-card border border-gray-800 rounded-2xl p-5 shadow-sm">
                        <div className="flex items-center gap-3 mb-3">
                            <div className="p-2.5 rounded-xl bg-blue-900/40">
                                <Users className="w-5 h-5 text-blue-400" />
                            </div>
                            <span className="text-sm font-semibold text-muted-foreground">Annual Footfall</span>
                        </div>
                        <p className="text-2xl font-black text-foreground">{formatFootfall(totalYearFootfall)}</p>
                        <p className="text-xs text-muted-foreground mt-1">Total for {year}</p>
                    </div>

                    <div className="bg-card border border-gray-800 rounded-2xl p-5 shadow-sm">
                        <div className="flex items-center gap-3 mb-3">
                            <div className="p-2.5 rounded-xl bg-amber-900/40">
                                <TrendingUp className="w-5 h-5 text-amber-400" />
                            </div>
                            <span className="text-sm font-semibold text-muted-foreground">Avg Daily</span>
                        </div>
                        <p className="text-2xl font-black text-foreground">{formatFootfall(avgDailyYear)}</p>
                        <p className="text-xs text-muted-foreground mt-1">Across all months</p>
                    </div>

                    <div className="bg-card border border-gray-800 rounded-2xl p-5 shadow-sm">
                        <div className="flex items-center gap-3 mb-3">
                            <div className="p-2.5 rounded-xl bg-green-900/40">
                                <ArrowUp className="w-5 h-5 text-green-400" />
                            </div>
                            <span className="text-sm font-semibold text-muted-foreground">Peak Month</span>
                        </div>
                        <p className="text-2xl font-black text-foreground">{formatFootfall(peakMonth.peakFootfall)}</p>
                        <p className="text-xs text-muted-foreground mt-1">
                            {peakMonth.name.charAt(0) + peakMonth.name.slice(1).toLowerCase()} — Day {peakMonth.peakDay}
                        </p>
                    </div>

                    <div className="bg-card border border-gray-800 rounded-2xl p-5 shadow-sm">
                        <div className="flex items-center gap-3 mb-3">
                            <div className="p-2.5 rounded-xl bg-purple-900/40">
                                <CalendarDays className="w-5 h-5 text-purple-400" />
                            </div>
                            <span className="text-sm font-semibold text-muted-foreground">Key Events</span>
                        </div>
                        <p className="text-2xl font-black text-foreground">{totalEvents}</p>
                        <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                            {googleEventsLoading ? (
                                <>
                                    <RefreshCw className="w-3 h-3 animate-spin" />
                                    Syncing Google Calendar...
                                </>
                            ) : (
                                "From Google Calendar"
                            )}
                        </p>
                    </div>
                </div>

                {/* Section title */}
                <div className="flex items-center justify-between mb-5">
                    <h2 className="text-lg font-bold text-foreground">Monthly Overview</h2>
                </div>

                {/* Month grid */}
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
                    {yearData.map((monthData, index) => (
                        <MonthCard
                            key={monthData.month}
                            data={monthData}
                            index={index}
                            onClick={() => onMonthClick(monthData.month)}
                        />
                    ))}
                </div>

                {/* Festival Summary Section */}
                <div className="mt-8">
                    <h2 className="text-lg font-bold text-foreground mb-4">Festival Period Summary</h2>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        {[
                            {
                                name: "New Year",
                                period: "31 Dec - 01 Jan",
                                footfall: "580K",
                                avg: "290K",
                                peak: "310K (31 Dec)",
                                specials: 45,
                                color: "border-gray-800 bg-card",
                                accentColor: "#3d7ee7",
                            },
                            {
                                name: "Sankranthi",
                                period: "13 Jan - 15 Jan",
                                footfall: "512K",
                                avg: "  170K",
                                peak: "250K (14 Jan)",
                                specials: 12,
                                color: "border-gray-800 bg-background",
                                 accentColor: "#e9a329",
                               
                            },
                            {
                                name: "Maha Shivaratri",
                                period: "15 Feb",
                                footfall: "2.10M",
                                avg: "210K",
                                peak: "2.10M (15 Feb)",
                                specials: 98,
                                color: "border-gray-800 bg-background",
                                 accentColor: "#7948ea",
                            },

                        ].map((festival) => (
                            <div
                                key={festival.name}
                                className={`rounded-2xl border-2 p-5 ${festival.color}`}
                            >
                                <div className="flex items-center gap-2 mb-2">
                                    <CalendarDays className="w-4 h-4 text-foreground" />
                                    <h3 className="font-bold text-foreground" >
                                        {festival.name}
                                    </h3>
                                </div>
                                <p className="text-xs text-foreground mb-3">Period: <strong className="text-foreground">{festival.period}</strong></p>
                                <div className="card-black-50 rounded-xl p-3 space-y-1.5 mb-3">
                                    <div className="flex justify-between text-sm">
                                        <span className="text-muted-foreground flex items-center gap-1">
                                            <Users className="w-3.5 h-3.5" /> Total Footfall
                                        </span>
                                        <span className="font-bold text-muted-foreground">{festival.footfall}</span>
                                    </div>
                                    <div className="flex justify-between text-sm">
                                        <span className="text-muted-foreground flex items-center gap-1">
                                            <TrendingUp className="w-3.5 h-3.5" /> Avg Daily
                                        </span>
                                        <span className="font-bold text-muted-foreground">{festival.avg}</span>
                                    </div>
                                    <div className="flex justify-between text-sm">
                                        <span className="text-muted-foreground flex items-center gap-1">
                                            <ArrowUp className="w-3.5 h-3.5" /> Peak Day
                                        </span>
                                        <span className="font-bold text-muted-foreground">{festival.peak}</span>
                                    </div>
                                </div>
                                <div
                                    className="rounded-xl py-3 text-center text-foreground"
                                    style={{ backgroundColor: festival.accentColor }}
                                >
                                    <p className="text-xs font-semibold opacity-90">Special Trains Operated</p>
                                    <p className="text-2xl font-black">{festival.specials}</p>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
};