import React, {
    useCallback,
    useEffect,
    useMemo,
    useRef,
    useState,
} from "react";

import { PageLayout } from "@/components/layout/PageLayout";

import { CalendarUpload } from "@/components/admin/CalendarUpload";

import { SpecialTrainsUpload } from "@/components/admin/SpecialTrainsUpload";

import { UtsUpload } from "@/components/admin/UtsUpload";

import {
    FIXED_KEY_EVENTS_2026_COUNT,
    GOOGLE_CALENDAR_API_KEY,
    fetchGoogleCalendarEvents,
} from "@/services/googleCalendar";

import "./FootfallInsights.css";

import { useLocation } from "react-router-dom";

type DayEntry = {
    d: number;
    lbl: string;
    pax: number;
    sp: number;
    rec: number;
    ev?: string;
    hourlyPax?: number[];
    scheduledPax?: number;
    specialPax?: number;
    specialTrainsTotalPax?: number;
    specialTrainNumbers?: number[];
    estimatedPax?: number | string;
};

type MonthEntry = {
    name: string;
    short: string;
    totalPax: number;
    avgDailyPax: number;
    days: DayEntry[];
};

type PeakEntry = {
    dateLabel: string;
    day: DayEntry;
};

type HolidayEventMap = Record<
    string,
    {
        name: string;
        color: string;
    }
>;

type FootfallApiState = {
    months: MonthEntry[];
    livePax: number;
    lastUpdated: string;
    yoyGrowth: number;
    momGrowth: number;
    dataSource: string;
    annualFootfall: number;
    avgDailyPax: number;
    peakDayPax: number;
    peakDayLabel: string;
    keyEventsCount: number;
    topPeakDays: PeakEntry[];
};

type SelectedDay = {
    mIdx: number;
    d: number;
} | null;

const FOOTFALL_CACHE_KEY = "crowd_vision_calendar_insights";

const loadCachedFootfall = (): FootfallApiState | null => {
    if (typeof sessionStorage === "undefined") return null;

    try {
        const stored = sessionStorage.getItem(FOOTFALL_CACHE_KEY);

        if (!stored) return null;

        return JSON.parse(stored) as FootfallApiState;
    } catch {
        return null;
    }
};

const saveCachedFootfall = (state: FootfallApiState) => {
    if (typeof sessionStorage === "undefined") return;

    try {
        sessionStorage.setItem(
            FOOTFALL_CACHE_KEY,
            JSON.stringify(state)
        );
    } catch {
        // ignore
    }
};

const YEAR = 2026;

const MONTH_META = [
    { name: "January", short: "JAN" },
    { name: "February", short: "FEB" },
    { name: "March", short: "MAR" },
    { name: "April", short: "APR" },
    { name: "May", short: "MAY" },
    { name: "June", short: "JUN" },
    { name: "July", short: "JUL" },
    { name: "August", short: "AUG" },
    { name: "September", short: "SEP" },
    { name: "October", short: "OCT" },
    { name: "November", short: "NOV" },
    { name: "December", short: "DEC" },
];

const API_BASE_URL = (
    (import.meta.env.VITE_API_URL as string) || ""
).replace(/\/+$/, "");

const FOOTFALL_ENDPOINTS = [
    `${API_BASE_URL}/footfall-insights`,
    `${API_BASE_URL}/calendar/insights`,
    `${API_BASE_URL}/footfall/calendar-insights`,
];

function nowTs() {
    return new Date().toLocaleTimeString("en-IN", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
    });
}

function toNumber(value: unknown): number {
    const n = Number(value);

    return Number.isFinite(n) ? Math.max(0, Math.round(n)) : 0;
}

function toPercent(value: unknown): number {
    const n = Number(value);

    return Number.isFinite(n) ? n : 0;
}

function toStringOr(
    value: unknown,
    fallback: string
): string {
    return typeof value === "string" && value.trim()
        ? value
        : fallback;
}

function makeEmptyMonths(): MonthEntry[] {
    return MONTH_META.map((m) => ({
        name: m.name,
        short: m.short,
        totalPax: 0,
        avgDailyPax: 0,
        days: [],
    }));
}

function makeEmptyState(): FootfallApiState {
    return {
        months: makeEmptyMonths(),
        livePax: 0,
        lastUpdated: nowTs(),
        yoyGrowth: 0,
        momGrowth: 0,
        dataSource: "API",
        annualFootfall: 0,
        avgDailyPax: 0,
        peakDayPax: 0,
        peakDayLabel: "0",
        keyEventsCount: 0,
        topPeakDays: [],
    };
}

function fmtPax(n: number) {
    if (n >= 1000000) {
        return (n / 1000000).toFixed(2) + "M";
    }

    if (n >= 1000) {
        return Math.round(n / 1000) + "K";
    }

    return String(n);
}

function fmtDelta(n: number) {
    const sign = n > 0 ? "+" : "";

    return `${sign}${n.toFixed(1)}%`;
}

function lvl(pax: number) {
    if (pax > 160000) return "l3";

    if (pax > 140000) return "l2";

    return "l1";
}

function lvlLabel(pax: number) {
    if (pax > 160000) return "L3 Emergency";

    if (pax > 140000) return "L2 Alert";

    return "L1 Normal";
}

function monthLvl(
    months: MonthEntry[],
    monthIndex: number
) {
    const m = months[monthIndex];

    if (!m || m.totalPax === 0) {
        return "future";
    }

    const ranked = months
        .map((month, idx) => ({
            idx,
            avg: Math.round(
                month.totalPax /
                    Math.max(
                        1,
                        month.days.length || 30
                    )
            ),
        }))
        .filter(
            (x) =>
                months[x.idx].totalPax > 0
        )
        .sort((a, b) => b.avg - a.avg);

    const pos = ranked.findIndex(
        (x) => x.idx === monthIndex
    );

    if (pos === -1) {
        return "future";
    }

    const topCut = Math.ceil(
        ranked.length / 3
    );

    const midCut = Math.ceil(
        (ranked.length * 2) / 3
    );

    if (pos < topCut) return "l3";

    if (pos < midCut) return "l2";

    return "l1";
}

function daysInMonth(
    year: number,
    monthIndex: number
) {
    return new Date(
        year,
        monthIndex + 1,
        0
    ).getDate();
}

function normalizeDay(
    raw: Record<string, unknown>,
    fallbackDay: number
): DayEntry {
    const evValue =
        raw?.ev ??
        raw?.event ??
        raw?.event_name;

    return {
        d:
            toNumber(
                raw?.d ??
                    raw?.day ??
                    raw?.date
            ) || fallbackDay,

        lbl: String(
            raw?.lbl ??
                raw?.label ??
                raw?.day_label ??
                ""
        ).trim(),

        pax: toNumber(
            raw?.pax ??
                raw?.footfall ??
                raw?.passengers ??
                raw?.count
        ),

        sp: toNumber(
            raw?.sp ??
                raw?.specials ??
                raw?.special_trains
        ),

        rec: toNumber(
            raw?.rec ??
                raw?.recommended_trains ??
                raw?.recommended_specials
        ),

        ev:
            typeof evValue === "string" &&
            evValue.trim()
                ? evValue
                : undefined,

        hourlyPax: Array.isArray(
            raw?.hourlyPax
        )
            ? raw.hourlyPax.map(toNumber)
            : undefined,

        scheduledPax: toNumber(
            raw?.scheduledPax ??
                raw?.scheduled_pax
        ),

        specialPax: toNumber(
            raw?.specialPax ??
                raw?.special_pax
        ),

        specialTrainsTotalPax:
            toNumber(
                raw?.specialTrainsTotalPax ??
                    raw?.special_trains_total_pax
            ),

        specialTrainNumbers:
            Array.isArray(
                raw?.specialTrainNumbers
            )
                ? (raw.specialTrainNumbers as number[])
                : undefined,
    };
}

function normalizeMonth(
    raw: Record<string, unknown>,
    fallbackIdx: number
): {
    index: number;
    month: MonthEntry;
} {
    const rawMonthIndex = Number(
        raw?.monthIndex ??
            raw?.month_idx ??
            raw?.month
    );

    const monthIdx = Number.isInteger(
        rawMonthIndex
    )
        ? rawMonthIndex > 11
            ? rawMonthIndex - 1
            : rawMonthIndex
        : fallbackIdx;

    const safeIdx = Math.max(
        0,
        Math.min(11, monthIdx)
    );

    const daySource =
        raw?.days ??
        raw?.daily ??
        raw?.dayWise;

    const rawDays = Array.isArray(
        daySource
    )
        ? daySource
        : [];

    const days = rawDays
        .map(
            (
                d: unknown,
                i: number
            ) =>
                normalizeDay(
                    typeof d === "object" &&
                        d !== null
                        ? (d as Record<
                              string,
                              unknown
                          >)
                        : {},
                    i + 1
                )
        )
        .sort(
            (a, b) => a.d - b.d
        );

    return {
        index: safeIdx,

        month: {
            name: toStringOr(
                raw?.name ??
                    raw?.monthName,
                MONTH_META[safeIdx]
                    .name
            ),

            short: toStringOr(
                raw?.short ??
                    raw?.monthShort,
                MONTH_META[safeIdx]
                    .short
            ),

            totalPax: toNumber(
                raw?.totalPax ??
                    raw?.total_pax ??
                    raw?.totalFootfall ??
                    raw?.total_footfall
            ),

            avgDailyPax: toNumber(
                raw?.avgDailyPax ??
                    raw?.avg_daily_pax ??
                    raw?.avgDaily ??
                    raw?.avg_daily
            ),

            days,
        },
    };
}

function normalizePayload(
    raw: unknown
): FootfallApiState {
    const outer =
        typeof raw === "object" &&
        raw !== null
            ? (raw as Record<
                  string,
                  unknown
              >)
            : {};

    const rootCandidate =
        outer?.data;

    const root =
        typeof rootCandidate ===
            "object" &&
        rootCandidate !== null
            ? (rootCandidate as Record<
                  string,
                  unknown
              >)
            : outer;

    const calendar =
        typeof root?.calendar ===
            "object" &&
        root.calendar !== null
            ? (root.calendar as Record<
                  string,
                  unknown
              >)
            : {};

    const monthsSource = Array.isArray(
        root?.months
    )
        ? root.months
        : Array.isArray(
                calendar?.months
            )
            ? calendar.months
            : [];

    const months =
        makeEmptyMonths();

    monthsSource.forEach(
        (
            m: unknown,
            idx: number
        ) => {
            const normalized =
                normalizeMonth(
                    typeof m ===
                        "object" &&
                        m !== null
                        ? (m as Record<
                              string,
                              unknown
                          >)
                        : {},
                    idx
                );

            months[normalized.index] =
                normalized.month;
        }
    );

    const peakSource =
        root?.topPeakDays ??
        root?.top_peak_days ??
        root?.peakDays ??
        root?.peak_days;

    const topPeakDays: PeakEntry[] =
        (
            Array.isArray(
                peakSource
            )
                ? peakSource
                : []
        ).map(
            (
                r: unknown,
                idx: number
            ) => {
                const row =
                    typeof r ===
                        "object" &&
                    r !== null
                        ? (r as Record<
                              string,
                              unknown
                          >)
                        : {};

                const day =
                    normalizeDay(
                        row,
                        idx + 1
                    );

                return {
                    dateLabel:
                        toStringOr(
                            row?.dateLabel ??
                                row?.date ??
                                row?.label,
                            `${MONTH_META[0].short} ${day.d}`
                        ),
                    day,
                };
            }
        );

    return {
        months,

        livePax: toNumber(
            root?.livePax ??
                root?.live_pax
        ),

        lastUpdated: toStringOr(
            root?.lastUpdated ??
                root?.last_updated ??
                root?.updatedAt,
            nowTs()
        ),

        yoyGrowth: toPercent(
            root?.yoyGrowth ??
                root?.yoy_growth
        ),

        momGrowth: toPercent(
            root?.momGrowth ??
                root?.mom_growth
        ),

        dataSource: toStringOr(
            root?.dataSource ??
                root?.source,
            "API"
        ),

        annualFootfall:
            toNumber(
                root?.annualFootfall ??
                    root?.annual_footfall ??
                    root?.totalFootfall ??
                    root?.total_footfall ??
                    root?.kpi_annual_footfall
            ),

        avgDailyPax:
            toNumber(
                root?.avgDailyPax ??
                    root?.avg_daily_pax ??
                    root?.kpi_avg_daily_pax
            ),

        peakDayPax:
            toNumber(
                root?.peakDayPax ??
                    root?.peak_day_pax ??
                    root?.kpi_peak_day_pax
            ),

        peakDayLabel:
            toStringOr(
                root?.peakDayLabel ??
                    root?.peak_day_label,
                "0"
            ),

        keyEventsCount:
            toNumber(
                root?.keyEventsCount ??
                    root?.key_events_count ??
                    root?.kpi_key_events_count
            ),

        topPeakDays,
    };
}

async function fetchFootfallInsights(): Promise<FootfallApiState> {
    for (
        const endpoint of FOOTFALL_ENDPOINTS
    ) {
        try {
            const res = await fetch(
                endpoint,
                {
                    method: "GET",
                }
            );

            if (!res.ok) {
                continue;
            }

            return normalizePayload(
                await res.json()
            );
        } catch {
            continue;
        }
    }

    return makeEmptyState();
}

async function fetchHourlyBuckets(
    date: string
) {
    try {
        const res = await fetch(
            `${API_BASE_URL}/footfall/hourly-buckets?date=${date}`
        );

        if (!res.ok) {
            throw new Error("Failed");
        }

        return await res.json();
    } catch (err) {
        return null;
    }
}

function applyGoogleEventsToMonths(
    months: MonthEntry[],
    events: HolidayEventMap
): MonthEntry[] {
    return months.map(
        (month, mIdx) => {
            const days = month.days.map(
                (day) => {
                    const dateKey =
                        `${YEAR}-${String(
                            mIdx + 1
                        ).padStart(
                            2,
                            "0"
                        )}-${String(
                            day.d
                        ).padStart(
                            2,
                            "0"
                        )}`;

                    const holiday =
                        events[dateKey];

                    let evLabel =
                        holiday?.name;

                    let estimatedPax:
                        | number
                        | string
                        | undefined =
                        undefined;

                    if (
                        dateKey ===
                        "2026-06-20"
                    ) {
                        evLabel =
                            "Day Before NEET";
                        estimatedPax =
                            "2k";
                    } else if (
                        dateKey ===
                        "2026-06-21"
                    ) {
                        evLabel =
                            "NEET Exam";
                        estimatedPax =
                            "2k";
                    } else if (
                        dateKey ===
                        "2026-06-22"
                    ) {
                        evLabel =
                            "Day After NEET";
                        estimatedPax =
                            "2k";
                    }

                    if (evLabel) {
                        return {
                            ...day,
                            lbl: evLabel,
                            ev: evLabel,
                            estimatedPax,
                        };
                    }

                    return {
                        ...day,
                        ev: undefined,
                        estimatedPax,
                    };
                }
            );

            return {
                ...month,
                days,
            };
        }
    );
}

export default function FootfallInsights() {
    const getToday = () => {
        const now = new Date();

        return {
            monthIndex: now.getMonth(),
            day: now.getDate(),
        };
    };

    const today = getToday();

    const [
        selectedMonth,
        setSelectedMonth,
    ] = useState<number>(
        today.monthIndex
    );

    const [
        selectedDay,
        setSelectedDay,
    ] = useState<SelectedDay>({
        mIdx: today.monthIndex,
        d: today.day,
    });

    const [
        apiData,
        setApiData,
    ] = useState<FootfallApiState>(
        () =>
            loadCachedFootfall() ??
            makeEmptyState()
    );

    const [
        holidayEvents,
        setHolidayEvents,
    ] = useState<HolidayEventMap>(
        {}
    );

    const location =
        useLocation();

    const mountedRef =
        useRef(false);

    const loadApiData =
        useCallback(
            async () => {
                const data =
                    await fetchFootfallInsights();

                saveCachedFootfall(data);

                return data;
            },
            []
        );

    useEffect(() => {
        mountedRef.current = true;

        return () => {
            mountedRef.current =
                false;
        };
    }, []);

    useEffect(() => {
        if (
            location.pathname !==
                "/calendar" &&
            location.pathname !==
                "/calendar-insight"
        ) {
            return;
        }

        let active = true;

        const load = async () => {
            const data =
                await loadApiData();

            if (active) {
                setApiData(data);
            }
        };

        load();

        const timer =
            setInterval(
                load,
                15000
            );

        return () => {
            active = false;
            clearInterval(timer);
        };
    }, [
        location.pathname,
        loadApiData,
    ]);

    useEffect(() => {
        if (
            typeof window ===
            "undefined"
        ) {
            return;
        }

        const handler =
            async () => {
                const data =
                    await loadApiData();

                if (
                    mountedRef.current
                ) {
                    setApiData(data);
                }
            };

        window.addEventListener(
            "crowdvision:reports-exit",
            handler
        );

        return () => {
            window.removeEventListener(
                "crowdvision:reports-exit",
                handler
            );
        };
    }, [loadApiData]);

    useEffect(() => {
        let mounted = true;

        const loadHolidays =
            async () => {
                const events =
                    await fetchGoogleCalendarEvents(
                        YEAR,
                        GOOGLE_CALENDAR_API_KEY
                    );

                if (mounted) {
                    setHolidayEvents(
                        events
                    );
                }
            };

        loadHolidays();

        return () => {
            mounted = false;
        };
    }, []);

    const monthsWithEvents =
        useMemo(
            () =>
                applyGoogleEventsToMonths(
                    apiData.months,
                    holidayEvents
                ),
            [
                apiData.months,
                holidayEvents,
            ]
        );

    const allDays =
        useMemo(() => {
            const rows: Array<{
                mIdx: number;
                day: DayEntry;
                dateLabel: string;
            }> = [];

            monthsWithEvents.forEach(
                (m, mIdx) => {
                    m.days.forEach(
                        (day) => {
                            rows.push({
                                mIdx,
                                day,
                                dateLabel: `${MONTH_META[mIdx].short} ${day.d}`,
                            });
                        }
                    );
                }
            );

            return rows;
        }, [monthsWithEvents]);

    const annualFootfall =
        useMemo(
            () =>
                monthsWithEvents.reduce(
                    (sum, m) =>
                        sum + m.totalPax,
                    0
                ),
            [monthsWithEvents]
        );

    const avgDailyPax =
        useMemo(() => {
            if (
                allDays.length ===
                0
            ) {
                return 0;
            }

            const total =
                allDays.reduce(
                    (sum, x) =>
                        sum + x.day.pax,
                    0
                );

            return Math.round(
                total /
                    allDays.length
            );
        }, [allDays]);

    const peakDay =
        useMemo(() => {
            if (
                allDays.length ===
                0
            ) {
                return null;
            }

            return allDays.reduce(
                (a, b) =>
                    a.day.pax >
                    b.day.pax
                        ? a
                        : b
            );
        }, [allDays]);

    const keyEventsCount =
        useMemo(() => {
            if (
                YEAR === 2026
            ) {
                return FIXED_KEY_EVENTS_2026_COUNT;
            }

            return Object.keys(
                holidayEvents
            ).length;
        }, [holidayEvents]);

    return (
        <PageLayout>
            <div
                style={{
                    overflowX:
                        "hidden",
                    width: "100%",
                }}
            >
                <div className="cr-body">
                    <div className="page-title-row">
                        <div className="flex items-center justify-between w-full">
                            <div>
                                <h2>
                                    Calendar Analytics
                                </h2>

                                <p>
                                    Secunderabad Station Rolling Crowd Management Dashboard -{" "}
                                    {YEAR}
                                </p>
                            </div>

                            <div className="flex items-center gap-4">
                                <div className="last-updated">
                                    Last updated:{" "}
                                    {
                                        apiData.lastUpdated
                                    }
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="kpi-row">
                        <div className="kpi-card">
                            <div className="kpi-top">
                                <div
                                    className="kpi-icon"
                                    style={{
                                        background:
                                            "#1d3a6e22",
                                    }}
                                >
                                    👥
                                </div>
                            </div>

                            <div className="kpi-val">
                                {fmtPax(
                                    annualFootfall
                                )}
                            </div>

                            <div className="kpi-lbl">
                                Annual Footfall
                            </div>

                            <div className="kpi-sub">
                                Total PAX -{" "}
                                {YEAR} YTD
                            </div>
                        </div>

                        <div className="kpi-card">
                            <div className="kpi-top">
                                <div
                                    className="kpi-icon"
                                    style={{
                                        background:
                                            "#92400e22",
                                    }}
                                >
                                    📈
                                </div>
                            </div>

                            <div className="kpi-val">
                                {fmtPax(
                                    avgDailyPax
                                )}
                            </div>

                            <div className="kpi-lbl">
                                Avg Daily PAX
                            </div>

                            <div className="kpi-sub">
                                Across all active months
                            </div>
                        </div>

                        <div className="kpi-card">
                            <div className="kpi-top">
                                <div
                                    className="kpi-icon"
                                    style={{
                                        background:
                                            "#7c3aed22",
                                    }}
                                >
                                    🏔️
                                </div>

                                <span className="kpi-badge blue">
                                    {
                                        peakDay?.dateLabel ??
                                        "0"
                                    }
                                </span>
                            </div>

                            <div className="kpi-val">
                                {fmtPax(
                                    peakDay?.day
                                        .pax ??
                                        0
                                )}
                            </div>

                            <div className="kpi-lbl">
                                Peak Day PAX
                            </div>

                            <div className="kpi-sub">
                                {peakDay
                                    ? `${peakDay.dateLabel}${
                                          peakDay
                                              .day
                                              .ev
                                              ? ` - ${peakDay.day.ev}`
                                              : ""
                                      }`
                                    : "No peak data"}
                            </div>
                        </div>

                        <div className="kpi-card">
                            <div className="kpi-top">
                                <div
                                    className="kpi-icon"
                                    style={{
                                        background:
                                            "#1d4ed822",
                                    }}
                                >
                                    📅
                                </div>
                            </div>

                            <div className="kpi-val">
                                {
                                    keyEventsCount
                                }
                            </div>

                            <div className="kpi-lbl">
                                Key Events
                            </div>

                            <div className="kpi-sub">
                                Synced from API
                            </div>
                        </div>
                    </div>

                    <div className="main-layout">
                        <div id="left-col">
                            <div className="sec-hdr">
                                <div>
                                    <h3>
                                        Monthly Overview
                                    </h3>

                                    <p>
                                        Click a month to view day-level PAX breakdown
                                    </p>
                                </div>

                                <span className="sec-tag">
                                    12 months -{" "}
                                    {YEAR}
                                </span>
                            </div>

                            <div className="month-grid">
                                {monthsWithEvents.map(
                                    (
                                        m,
                                        i
                                    ) => {
                                        const ml =
                                            monthLvl(
                                                monthsWithEvents,
                                                i
                                            );

                                        const isSelected =
                                            selectedMonth ===
                                            i;

                                        const dotCount =
                                            ml ===
                                            "l3"
                                                ? 3
                                                : ml ===
                                                    "l2"
                                                ? 2
                                                : ml ===
                                                    "l1"
                                                ? 1
                                                : 0;

                                        const avgPerDay =
                                            Math.round(
                                                m.totalPax /
                                                    Math.max(
                                                        1,
                                                        m.days.length ||
                                                            30
                                                    )
                                            );

                                        return (
                                            <div
                                                key={
                                                    i
                                                }
                                                className={`month-card mc-${ml} ${
                                                    isSelected
                                                        ? "selected"
                                                        : ""
                                                }`}
                                                onClick={() => {
                                                    setSelectedMonth(
                                                        i
                                                    );

                                                    setSelectedDay(
                                                        null
                                                    );
                                                }}
                                            >
                                                <div className="mc-head">
                                                    <span className="mc-name">
                                                        {
                                                            m.short
                                                        }
                                                    </span>

                                                    <div className="mc-dots">
                                                        {[0, 1, 2].map(
                                                            (
                                                                k
                                                            ) => (
                                                                <span
                                                                    key={
                                                                        k
                                                                    }
                                                                    className={
                                                                        k <
                                                                        dotCount
                                                                            ? "on"
                                                                            : ""
                                                                    }
                                                                />
                                                            )
                                                        )}
                                                    </div>
                                                </div>

                                                <div className="mc-body">
                                                    <div className="mc-pax">
                                                        {fmtPax(
                                                            m.totalPax
                                                        )}
                                                    </div>

                                                    <div className="mc-sub">
                                                        Avg{" "}
                                                        {fmtPax(
                                                            avgPerDay
                                                        )}
                                                        /day
                                                    </div>

                                                    <div className="mc-bar" />
                                                </div>
                                            </div>
                                        );
                                    }
                                )}
                            </div>

                            <DayCalendar
                                mIdx={
                                    selectedMonth
                                }
                                months={
                                    monthsWithEvents
                                }
                                selectedDay={
                                    selectedDay
                                }
                                onSelectDay={(
                                    d
                                ) =>
                                    setSelectedDay(
                                        {
                                            mIdx: selectedMonth,
                                            d,
                                        }
                                    )
                                }
                            />

                            <div className="legend">
                                <h4>
                                    CROWD LEVEL INDICATORS
                                </h4>

                                <div className="legend-grid">
                                    <div className="lg-item">
                                        <div className="lg-dot l1c" />
                                        <span>
                                            L1 Normal - &lt; 1.4 Lakhs PAX/day
                                        </span>
                                    </div>

                                    <div className="lg-item">
                                        <div className="lg-dot l2c" />
                                        <span>
                                            L2 Alert - 1.4 Lakhs to 1.6 Lakhs PAX/day
                                        </span>
                                    </div>

                                    <div className="lg-item">
                                        <div className="lg-dot l3c" />
                                        <span>
                                            L3 Emergency - &gt; 1.6 Lakhs PAX/day
                                        </span>
                                    </div>

                                    <div className="lg-item">
                                        <div className="lg-dot fc" />
                                        <span>
                                            Future - No data available
                                        </span>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div id="right-col">
                            <div className="sec-hdr">
                                <div>
                                    <h3>
                                        Insights &amp; Recommendations
                                    </h3>
                                </div>
                            </div>

                            <MonthOverviewCard
                                mIdx={
                                    selectedMonth
                                }
                                months={
                                    monthsWithEvents
                                }
                            />

                            <HourlyBreakdownCard
                                selectedDay={
                                    selectedDay
                                }
                                months={
                                    monthsWithEvents
                                }
                            />

                            <DayDetailCard
                                selectedDay={
                                    selectedDay
                                }
                                months={
                                    monthsWithEvents
                                }
                            />
                        </div>
                    </div>
                </div>
            </div>
        </PageLayout>
    );
}

function DayCalendar({
    mIdx,
    months,
    selectedDay,
    onSelectDay,
}: {
    mIdx: number;
    months: MonthEntry[];
    selectedDay: SelectedDay;
    onSelectDay: (
        d: number
    ) => void;
}) {
    const m =
        months[mIdx] ??
        makeEmptyMonths()[mIdx];

    const monthTotalDays =
        daysInMonth(
            YEAR,
            mIdx
        );

    const dmap: Record<
        number,
        DayEntry
    > = {};

    m.days.forEach((d) => {
        dmap[d.d] = d;
    });

    const firstDow =
        new Date(
            YEAR,
            mIdx,
            1
        ).getDay();

    const offset =
        (firstDow + 6) % 7;

    return (
        <div className="day-cal">
            <div className="day-cal-title">
                {m.name} {YEAR}{" "}
                <span>
                    Day-level PAX breakdown - Click a day for details
                </span>
            </div>

            <div className="dow-hdr">
                <div>MON</div>
                <div>TUE</div>
                <div>WED</div>
                <div>THU</div>
                <div>FRI</div>

                <div
                    style={{
                        color: "#fb923c",
                    }}
                >
                    SAT
                </div>

                <div
                    style={{
                        color: "#fb923c",
                    }}
                >
                    SUN
                </div>
            </div>

            <div className="day-grid">
                {Array.from(
                    {
                        length: offset,
                    },
                    (_, i) => (
                        <div
                            key={`e-${i}`}
                            className="dc empty"
                        />
                    )
                )}

                {Array.from(
                    {
                        length:
                            monthTotalDays,
                    },
                    (_, i) =>
                        i + 1
                ).map((d) => {
                    const day =
                        dmap[d] || {
                            d,
                            lbl: "",
                            pax: 0,
                            sp: 0,
                            rec: 0,
                            scheduledPax:
                                0,
                            specialPax:
                                0,
                            specialTrainsTotalPax:
                                0,
                            specialTrainNumbers:
                                [],
                        };

                    const lv =
                        lvl(day.pax);

                    const isSelected =
                        !!selectedDay &&
                        selectedDay.mIdx ===
                            mIdx &&
                        selectedDay.d ===
                            d;

                    const specialTrainCount =
                        day
                            .specialTrainNumbers
                            ?.length ??
                        day.sp ??
                        0;

                    return (
                        <div
                            key={`d-${d}`}
                            className={`dc ${lv} ${
                                isSelected
                                    ? "day-selected"
                                    : ""
                            } relative`}
                            onClick={() =>
                                onSelectDay(
                                    d
                                )
                            }
                        >
                            <div className="dc-date">
                                {d}{" "}
                                {
                                    MONTH_META[
                                        mIdx
                                    ]
                                        .short
                                }
                            </div>

                            <div className="dc-pax">
                                {day.pax}
                            </div>

                            {day.lbl && (
                                <div className="dc-lbl">
                                    {
                                        day.lbl
                                    }
                                </div>
                            )}

                            {specialTrainCount >
                                0 && (
                                <div
                                    className="dc-specials"
                                    style={{
                                        backgroundColor:
                                            "hsl(var(--card))",
                                        color:
                                            "hsl(var(--primary))",
                                        border:
                                            "1px solid hsl(var(--border))",
                                    }}
                                >
                                    +
                                    {
                                        specialTrainCount
                                    }
                                </div>
                            )}

                            {day.estimatedPax && (
                                <div className="absolute top-[4px] right-[4px] text-[10px] text-orange-400 font-bold z-10">
                                    +
                                    {
                                        day.estimatedPax
                                    }{" "}
                                    estimated
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

function MonthOverviewCard({
    mIdx,
    months,
}: {
    mIdx: number;
    months: MonthEntry[];
}) {
    const m =
        months[mIdx] ??
        makeEmptyMonths()[mIdx];

    const avgPerDay =
        Math.round(
            m.totalPax /
                Math.max(
                    1,
                    m.days.length ||
                        30
                )
        );

    const peakDay =
        m.days.length > 0
            ? m.days.reduce(
                  (a, b) =>
                      a.pax > b.pax
                          ? a
                          : b
              )
            : {
                  d: 0,
                  lbl: "",
                  pax: 0,
                  sp: 0,
                  rec: 0,
                  scheduledPax: 0,
                  specialPax: 0,
                  specialTrainsTotalPax:
                      0,
                  specialTrainNumbers:
                      [],
              };

    const lowDay =
        m.days.length > 0
            ? m.days.reduce(
                  (a, b) =>
                      a.pax < b.pax
                          ? a
                          : b
              )
            : {
                  d: 0,
                  lbl: "",
                  pax: 0,
                  sp: 0,
                  rec: 0,
                  scheduledPax: 0,
                  specialPax: 0,
                  specialTrainsTotalPax:
                      0,
                  specialTrainNumbers:
                      [],
              };

    const uniqueEvents =
        m.days.filter(
            (d) =>
                (
                    d.ev ||
                    d.lbl
                ).trim?.() ||
                d.ev ||
                d.lbl
        );

    const keyEventItems =
        uniqueEvents
            .map((d) => ({
                day: d.d,
                label: (
                    d.ev ||
                    d.lbl ||
                    ""
                ).trim(),
            }))
            .filter(
                (d) =>
                    d.label.length >
                    0
            )
            .sort(
                (a, b) =>
                    a.day - b.day
            );

    return (
        <div
            className="insight-card"
            id="month-overview-card"
        >
            <div className="ic-title">
                <div
                    className="ic-icon"
                    style={{
                        background:
                            "#1e3a6e22",
                        color:
                            "#93c5fd",
                    }}
                >
                    📅
                </div>

                {m.name} {YEAR} -
                Overview
            </div>

            <div className="mo-stat-row">
                <div className="mo-stat">
                    <div
                        className="mo-stat-val"
                        style={{
                            color: "#93c5fd",
                        }}
                    >
                        {fmtPax(
                            m.totalPax
                        )}
                    </div>

                    <div className="mo-stat-lbl">
                        Total PAX
                    </div>
                </div>

                <div className="mo-stat">
                    <div
                        className="mo-stat-val"
                        style={{
                            color: "#a78bfa",
                        }}
                    >
                        {fmtPax(
                            avgPerDay
                        )}
                    </div>

                    <div className="mo-stat-lbl">
                        Avg / Day
                    </div>
                </div>

                <div className="mo-stat mo-stat-tooltip">
                    <div
                        className="mo-stat-val"
                        style={{
                            color: "#fb923c",
                        }}
                    >
                        {
                            uniqueEvents.length
                        }
                    </div>

                    <div className="mo-stat-lbl">
                        Key Events
                    </div>

                    <div className="mo-tooltip">
                        <div className="mo-tooltip-title">
                            Key Events -{" "}
                            {
                                MONTH_META[
                                    mIdx
                                ].short
                            }{" "}
                            {YEAR}
                        </div>

                        {keyEventItems.length ===
                        0 ? (
                            <div className="mo-tooltip-empty">
                                No key events found for this month.
                            </div>
                        ) : (
                            <div className="mo-tooltip-list">
                                {keyEventItems.map(
                                    (
                                        item
                                    ) => (
                                        <div
                                            key={`${item.day}-${item.label}`}
                                            className="mo-tooltip-item"
                                        >
                                            <span className="mo-tooltip-date">
                                                {
                                                    MONTH_META[
                                                        mIdx
                                                    ]
                                                        .short
                                                }{" "}
                                                {
                                                    item.day
                                                }
                                            </span>

                                            <span className="mo-tooltip-name">
                                                {
                                                    item.label
                                                }
                                            </span>
                                        </div>
                                    )
                                )}
                            </div>
                        )}
                    </div>
                </div>
            </div>

            <div className="mo-peak-low">
                <div className="mo-pl-card peak">
                    <div className="mo-pl-label">
                        Peak Day
                    </div>

                    <div
                        className="mo-pl-val"
                        style={{
                            color: "#fb923c",
                        }}
                    >
                        {fmtPax(
                            peakDay.pax
                        )}
                    </div>

                    <div className="mo-pl-day">
                        {
                            MONTH_META[
                                mIdx
                            ].short
                        }{" "}
                        {peakDay.d ||
                            0}
                    </div>
                </div>

                <div className="mo-pl-card low">
                    <div className="mo-pl-label">
                        Low Day
                    </div>

                    <div
                        className="mo-pl-val"
                        style={{
                            color: "#4ade80",
                        }}
                    >
                        {fmtPax(
                            lowDay.pax
                        )}
                    </div>

                    <div className="mo-pl-day">
                        {
                            MONTH_META[
                                mIdx
                            ].short
                        }{" "}
                        {lowDay.d || 0}
                    </div>
                </div>
            </div>
        </div>
    );
}

function DayDetailCard({
    selectedDay,
    months,
}: {
    selectedDay: SelectedDay;
    months: MonthEntry[];
}) {
    const [
        bucketData,
        setBucketData,
    ] = useState<any>(null);

    useEffect(() => {
        if (!selectedDay) return;

        const dateStr = `${YEAR}-${String(
            selectedDay.mIdx + 1
        ).padStart(
            2,
            "0"
        )}-${String(
            selectedDay.d
        ).padStart(
            2,
            "0"
        )}`;

        fetchHourlyBuckets(
            dateStr
        ).then(setBucketData);
    }, [selectedDay]);

    if (!selectedDay) {
        return (
            <div className="dd-card text-center">
                Click any day
            </div>
        );
    }

    const m =
        months[selectedDay.mIdx];

    const day =
        m.days.find(
            (x) =>
                x.d ===
                selectedDay.d
        ) || {
            d: selectedDay.d,
            lbl: "",
            pax: 0,
            sp: 0,
            rec: 0,
            scheduledPax: 0,
            specialPax: 0,
            specialTrainsTotalPax:
                0,
            specialTrainNumbers:
                [],
        };

    const scheduled =
        day.pax ??
        bucketData?.totalScheduledPax ??
        0;

    const special =
        day.specialTrainsTotalPax ??
        bucketData?.totalSpecialPax ??
        0;

    return (
        <div className="dd-card">
            <div className="dd-title">
                Day Detail -{" "}
                {selectedDay.d}{" "}
                {m.name}
            </div>

            <div className="dd-pax-big">
                {day.pax}{" "}
                <span>PAX</span>
            </div>

            <div className="dd-divider" />

            <div className="dd-row">
                <span className="dd-lbl">
                    Special Trains Count
                </span>

                <span className="dd-val">
                    {
                        day
                            .specialTrainNumbers
                            ?.length ??
                        day.sp ??
                        0
                    }
                </span>
            </div>

            <div className="dd-row">
                <span className="dd-lbl">
                    Special Trains Footfall
                </span>

                <span
                    className="dd-val"
                    style={{
                        color: "#fb923c",
                    }}
                >
                    {special}
                </span>
            </div>

            <div className="dd-row">
                <span className="dd-lbl">
                    Scheduled Footfall
                </span>

                <span
                    className="dd-val"
                    style={{
                        color: "#4ade80",
                    }}
                >
                    {scheduled}
                </span>
            </div>
        </div>
    );
}

function HourlyBreakdownCard({
    selectedDay,
    months,
}: {
    selectedDay: SelectedDay;
    months: MonthEntry[];
}) {
    const [
        bucketData,
        setBucketData,
    ] = useState<any>(null);

    useEffect(() => {
        if (!selectedDay) return;

        const mIdx =
            selectedDay.mIdx;

        const day =
            selectedDay.d;

        const dateStr = `${YEAR}-${String(
            mIdx + 1
        ).padStart(
            2,
            "0"
        )}-${String(
            day
        ).padStart(
            2,
            "0"
        )}`;

        fetchHourlyBuckets(
            dateStr
        ).then(setBucketData);
    }, [selectedDay]);

    if (!selectedDay) {
        return null;
    }

    const m =
        months[selectedDay.mIdx];

    const dayLabel = `${selectedDay.d} ${m.name}`;

    if (!bucketData) {
        return (
            <div className="insight-card">
                <div className="ic-title">
                    Loading hourly data...
                </div>
            </div>
        );
    }

    const buckets =
        bucketData.buckets ||
        [];

    let max = 0;
    let maxIndex = -1;

    buckets.forEach(
        (
            b: any,
            i: number
        ) => {
            if (b.pax > max) {
                max = b.pax;
                maxIndex = i;
            }
        }
    );

    return (
        <div className="insight-card">
            <div className="ic-title">
                <div
                    className="ic-icon"
                    style={{
                        background:
                            "#1d4ed822",
                        color:
                            "#93c5fd",
                    }}
                >
                    🕒
                </div>

                Hourly Breakdown -
                {" "}
                {dayLabel}
            </div>

            <div className="hourly-buckets">
                {buckets.map(
                    (
                        b: any,
                        i: number
                    ) => {
                        const isMax =
                            i ===
                            maxIndex;

                        return (
                            <div
                                key={
                                    i
                                }
                                className="bucket-item"
                            >
                                <div className="bucket-time">
                                    {b.label.includes(
                                        " - "
                                    ) ? (
                                        <>
                                            <div>
                                                {
                                                    b.label.split(
                                                        " - "
                                                    )[0]
                                                }
                                            </div>

                                            <div
                                                style={{
                                                    color:
                                                        "#475569",
                                                    margin:
                                                        "1px 0",
                                                }}
                                            >
                                                -
                                            </div>

                                            <div>
                                                {
                                                    b.label.split(
                                                        " - "
                                                    )[1]
                                                }
                                            </div>
                                        </>
                                    ) : (
                                        b.label
                                    )}
                                </div>

                                <div
                                    className="bucket-box"
                                    style={
                                        isMax
                                            ? {
                                                  backgroundColor:
                                                      "#ef4444",
                                                  color:
                                                      "#fff",
                                                  fontWeight:
                                                      "bold",
                                              }
                                            : {}
                                    }
                                >
                                    {
                                        b.pax
                                    }
                                </div>
                            </div>
                        );
                    }
                )}
            </div>
        </div>
    );
}

function TrainRecommenderList({
    peakDays,
}: {
    peakDays: PeakEntry[];
}) {
    const rows =
        peakDays.length > 0
            ? peakDays
            : [
                  {
                      dateLabel:
                          "N/A",
                      day: {
                          d: 0,
                          lbl: "No data",
                          pax: 0,
                          sp: 0,
                          rec: 0,
                          scheduledPax:
                              0,
                          specialPax:
                              0,
                          specialTrainsTotalPax:
                              0,
                          specialTrainNumbers:
                              [],
                      },
                  },
              ];

    return (
        <div className="tr-list">
            {rows.map(
                (p, i) => (
                    <div
                        key={i}
                        className={`tr-item ${lvl(
                            p.day.pax
                        )}`}
                    >
                        <div>
                            <div className="tri-date">
                                {
                                    p.dateLabel
                                }
                            </div>

                            <div className="tri-evt">
                                {p.day
                                    .ev ||
                                    p.day
                                        .lbl ||
                                    "No event"}
                            </div>
                        </div>

                        <div>
                            <div className="tri-count">
                                +
                                {
                                    p.day
                                        .rec
                                }
                            </div>

                            <div className="tri-sub">
                                specials rec.
                            </div>
                        </div>
                    </div>
                )
            )}
        </div>
    );
}

function ForecastList({
    days,
}: {
    days: PeakEntry[];
}) {
    const rows =
        days.length > 0
            ? days
            : [
                  {
                      dateLabel:
                          "N/A",
                      day: {
                          d: 0,
                          lbl: "No data",
                          pax: 0,
                          sp: 0,
                          rec: 0,
                          scheduledPax:
                              0,
                          specialPax:
                              0,
                          specialTrainsTotalPax:
                              0,
                          specialTrainNumbers:
                              [],
                      },
                  },
              ];

    const maxP = Math.max(
        1,
        ...rows.map(
            (r) =>
                r.day.pax
        )
    );

    return (
        <div className="fc-rows">
            {rows.map(
                (f, i) => {
                    const lv =
                        lvl(
                            f.day
                                .pax
                        );

                    const pct =
                        Math.round(
                            (f.day
                                .pax /
                                maxP) *
                                100
                        );

                    return (
                        <div
                            key={i}
                            className={`fc-item ${lv}`}
                        >
                            <span className="fc-lbl">
                                {
                                    f.dateLabel
                                }
                                <br />
                                {f.day
                                    .ev ||
                                    f.day
                                        .lbl ||
                                    "No event"}
                            </span>

                            <div className="fc-bar-wrap">
                                <div
                                    className={`fc-bar ${lv}c`}
                                    style={{
                                        width: `${pct}%`,
                                    }}
                                />
                            </div>

                            <span className="fc-val">
                                {fmtPax(
                                    f
                                        .day
                                        .pax
                                )}
                            </span>
                        </div>
                    );
                }
            )}
        </div>
    );
}