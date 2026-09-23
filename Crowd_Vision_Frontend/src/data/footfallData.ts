export interface DayData {
    date: number;
    dayType: string;
    footfall: number;
    specials: number;
    event?: string;
    eventColor?: string;
    liveFootfall?: number;
}

export interface MonthData {
    month: number;
    year: number;
    name: string;
    totalFootfall: number;
    avgDaily: number;
    peakDay: number;
    peakFootfall: number;
    keyEvents: string[];
    days: DayData[];
    color: string;
    headerColor: string;
    currentLiveTotal?: number;
}

// ─────────────────────────────────────────────────────────────────
// Configurable footfall threshold ranges (daily values)
// ─────────────────────────────────────────────────────────────────
export const FOOTFALL_THRESHOLDS = {
    normal: { min: 0, max: 140000, label: "<1.4L", bg: "#39de76ff", text: "#31ef70ff" },
    high: { min: 140000, max: 160000, label: "1.4L–1.6L", bg: "#d79c1cff", text: "#f8f2eeff" },
    veryHigh: { min: 160000, max: Infinity, label: ">1.6L", bg: "#f74545", text: "#f1f0e3ff" },
} as const;

export function getFootfallBgColor(value: number): string {
    if (value >= FOOTFALL_THRESHOLDS.veryHigh.min) return FOOTFALL_THRESHOLDS.veryHigh.bg;
    if (value >= FOOTFALL_THRESHOLDS.high.min) return FOOTFALL_THRESHOLDS.high.bg;
    return FOOTFALL_THRESHOLDS.normal.bg; // green for <1.4L
}

export function getFootfallTextColor(value: number): string {
    if (value >= FOOTFALL_THRESHOLDS.veryHigh.min) return FOOTFALL_THRESHOLDS.veryHigh.text;
    if (value >= FOOTFALL_THRESHOLDS.high.min) return FOOTFALL_THRESHOLDS.high.text;
    return FOOTFALL_THRESHOLDS.normal.text;
}

// ─────────────────────────────────────────────────────────────────
// Simulation engine constants
//   • Each "step" = 2 minutes of real time
//   • Cycle = SIMULATION_CYCLE_STEPS steps (25 × 2 min = 50 min)
//   • Within one cycle: values ramp from ~0 → peak (~5 M monthly)
//   • After reaching peak, cycle resets automatically
// ─────────────────────────────────────────────────────────────────
export const SIMULATION_STEP_MS = 2 * 60 * 1000; // 2 minutes per step
export const SIMULATION_CYCLE_STEPS = 25;           // 25 steps per full cycle

/** Fast refresh for festival halo days: 30 seconds per step */

/** Target monthly peak footfall at the top of each cycle */
const SIMULATION_PEAK_MONTHLY = 5_000_000;


/**
 * Per-month peak scale: fraction of SIMULATION_PEAK_MONTHLY each month's
 * total reaches at the top of the cycle.
 * Jan = static; Aug–Dec = 0 (no data).
 * Deliberately different values to make each month feel unique.
 */
const MONTH_PEAK_SCALES = [
    1.00, // 0  Jan  — static, value unused
    0.92, // 1  Feb  — starts mid-cycle, moderate demand
    1.55, // 2  Mar  — Regular days peak ~250k
    1.50, // 3  Apr
    1.45, // 4  May  — Regular days peak ~235k
    1.42, // 5  Jun  — Regular days peak ~236k
    1.40, // 6  Jul
    0.00, // 7  Aug  — no data
    0.00, // 8  Sep  — no data
    0.00, // 9  Oct  — no data
    0.00, // 10 Nov  — no data
    0.00, // 11 Dec  — no data
];

/**
 * Per-month growth curve exponent.
 * exponent > 1 = slow start, fast burst near peak (exponential ramp).
 * exponent < 1 = fast initial gain, slow approach to peak (log-like).
 * Each month gets a deliberately different shape.
 */
const MONTH_CURVE_EXPONENT = [
    1.0, // Jan  — static
    1.8, // Feb  — gradual ramp
    1.3, // Mar  — moderate early surge (Holi effect)
    2.4, // Apr  — slow build, fast late burst
    1.6, // May  — steady growth
    2.0, // Jun  — slow then explosive (Eid run-up)
    1.5, // Jul  — moderate
    1.0, 1.0, 1.0, 1.0, 1.0, // Aug–Dec unused
];

// ─────────────────────────────────────────────────────────────────
// Month colours (card header colour, used in YearCalendarView)
// ─────────────────────────────────────────────────────────────────
const MONTH_COLORS = [
    { color: "#6b7280", headerColor: "#4b5563" }, // Jan  – slate
    { color: "#9ca3af", headerColor: "#6b7280" }, // Feb  – light gray
    { color: "#ef4444", headerColor: "#dc2626" }, // Mar  – red (Holi)
    { color: "#22c55e", headerColor: "#16a34a" }, // Apr  – green
    { color: "#f59e0b", headerColor: "#d97706" }, // May  – amber
    { color: "#f97316", headerColor: "#ea580c" }, // Jun  – orange
    { color: "#a78bfa", headerColor: "#7c3aed" }, // Jul  – violet
    { color: "#ca8a04", headerColor: "#a16207" }, // Aug  – khaki
    { color: "#3b82f6", headerColor: "#2563eb" }, // Sep  – blue
    { color: "#8b5cf6", headerColor: "#7c3aed" }, // Oct  – purple
    { color: "#ec4899", headerColor: "#db2777" }, // Nov  – pink
    { color: "#a855f7", headerColor: "#9333ea" }, // Dec  – fuchsia
];

const MONTH_NAMES = [
    "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE",
    "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER",
];

// ─────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────

const getDayType = (date: Date): string => {
    const dow = date.getDay();
    if (dow === 0 || dow === 6) return "Weekend";
    if (dow === 5) return "Friday Rush";
    return "Regular";
};

/** Seeded deterministic pseudo-random — same output for same seed every render */
const seededRand = (seed: number): number => {
    const x = Math.sin(seed + 1) * 43758.5453123;
    return x - Math.floor(x);
};

const getDaysInMonth = (year: number, month: number): number =>
    new Date(year, month + 1, 0).getDate();

/**
 * Festival "halo" demand multiplier for a specific calendar day.
 *
 * Rules:
 *  – On a major festival day (Diwali, Holi, Maha Shivratri, Eid):  2.0×
 *  – 1–3 days BEFORE a festival:  1.8× → 1.4× (surge as people book ahead)
 *  – 1–2 days AFTER  a festival:  1.3× → 1.15× (cool-down)
 *  – Minor event / holiday:       1.5× on day, 1.3× / 1.1× halo
 *  – Weekend:                     1.18×
 *  – Friday Rush:                 1.12×
 *  – Regular:                     1.0×
 *
 * The function returns the HIGHEST applicable multiplier.
 */
function getHaloDemandMultiplier(dayDate: number, month: number, year: number): number {
    const target = new Date(year, month, dayDate);
    let bestMult = 1.0;

    // Base day-type multiplier
    const dow = target.getDay();
    if (dow === 0 || dow === 6) bestMult = Math.max(bestMult, 1.18);
    else if (dow === 5) bestMult = Math.max(bestMult, 1.12);

    // Add a day-specific jitter (±5%) to make each day feel unique
    const jitter = 0.95 + seededRand(month * 100 + dayDate) * 0.10;
    return Math.max(1.0, bestMult * jitter);
}

/**
 * Returns the current simulation step index [0, SIMULATION_CYCLE_STEPS).
 * Changes every SIMULATION_STEP_MS (2 minutes).
 */
export function getSimulationStep(): number {
    return Math.floor(Date.now() / SIMULATION_STEP_MS) % SIMULATION_CYCLE_STEPS;
}

/**
 * Returns the simulation progress fraction [0.0, 1.0].
 * 0.0 = start of cycle (low values), 1.0 = peak (~5 M total).
 */
export function getSimulationProgress(): number {
    return getSimulationStep() / (SIMULATION_CYCLE_STEPS - 1);
}

// ─────────────────────────────────────────────────────────────────
// Static month data generator (used as baseline weights)
// ─────────────────────────────────────────────────────────────────

const generateFootfall = (
    dayType: string,
    month: number,
    hasEvent: boolean,
    dayNum: number
): number => {
    const base = 200_000;
    const monthFactor = [1.05, 1.02, 1.08, 0.95, 0.92, 0.88, 0.85, 0.90, 1.0, 1.15, 1.10, 1.12][month];
    let multiplier = 1.0;
    if (dayType === "Weekend") multiplier = 1.15;
    else if (dayType === "Friday Rush") multiplier = 1.12;
    else if (dayType === "Festival" || hasEvent) multiplier = 1.35;
    else if (dayType !== "Regular") multiplier = 1.25;
    const rand = 0.95 + seededRand(month * 31 + dayNum) * 0.1;
    return Math.round((base * monthFactor * multiplier * rand) / 1000) * 1000;
};

export const generateMonthData = (year: number, month: number): MonthData => {
    const daysInMonth = getDaysInMonth(year, month);
    const days: DayData[] = [];
    let totalFootfall = 0;
    let peakFootfall = 0;
    let peakDay = 1;
    const keyEvents: string[] = [];

    for (let day = 1; day <= daysInMonth; day++) {
        const date = new Date(year, month, day);
        const dayType = getDayType(date);
        const isNoDataMonth = month >= 7;
        const footfall = isNoDataMonth ? 0 : generateFootfall(dayType, month, false, day);

        let specials = 0;
        if (!isNoDataMonth) {
            if (dayType === "Weekend") specials = 2;
            else if (dayType === "Friday Rush" || dayType !== "Regular")
                specials = Math.floor(seededRand(month * 100 + day) * 3) + 1;
        }

        days.push({ date: day, dayType, footfall, specials });

        totalFootfall += footfall;
        if (footfall > peakFootfall) { peakFootfall = footfall; peakDay = day; }
    }

    return {
        month, year,
        name: MONTH_NAMES[month],
        totalFootfall,
        avgDaily: Math.round(totalFootfall / daysInMonth),
        peakDay, peakFootfall, keyEvents, days,
        color: MONTH_COLORS[month].color,
        headerColor: MONTH_COLORS[month].headerColor,
    };
};

export const generateYearData = (year: number): MonthData[] =>
    Array.from({ length: 12 }, (_, i) => generateMonthData(year, i));

// ─────────────────────────────────────────────────────────────────
// Formatters
// ─────────────────────────────────────────────────────────────────
export const formatFootfall = (n: number): string => {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
    if (n >= 1_000) return `${Math.round(n / 1_000)}K`;
    return n.toString();
};

// ─────────────────────────────────────────────────────────────────
// CORE ENGINE — getLiveFootfall
//
// Simulation behavior:
//  Normal, weekend, and Friday patterns refresh every two minutes.
//  Event effects are provided by the backend calendar-insights API.
//  Special rules:
//    • January (0)  → always static (return base `total`)
//    • Aug–Dec (7-11) → always 0
// ─────────────────────────────────────────────────────────────────
export const getLiveFootfall = (
    total: number,
    dayDate: number,
    month: number,
    year: number
): number => {
    // ── January: always static ──────────────────────────────────────
    if (month === 0) return total;

    // ── Aug–Dec: no simulation data yet ────────────────────────────
    if (month >= 7) return 0;

    // ── Demand multiplier (used by both paths) ──────────────────────
    const demandMult = getHaloDemandMultiplier(dayDate, month, year);

    // ════════════════════════════════════════════════════════════════
    // SLOW PATH — Regular / weekend / non-festival days
    // Refresh every 2 minutes, grows from 0 → monthly peak.
    // ════════════════════════════════════════════════════════════════
    const step = getSimulationStep();                   // 0..24
    const rawProgress = step / (SIMULATION_CYCLE_STEPS - 1);  // 0.0 → 1.0

    const exp = MONTH_CURVE_EXPONENT[month];
    const curvedProgress = Math.pow(rawProgress, exp);

    const peakScale = MONTH_PEAK_SCALES[month];
    const daysInMonth = getDaysInMonth(year, month);
    const avgDayPeak = (SIMULATION_PEAK_MONTHLY * peakScale) / daysInMonth;

    const dayPeakTarget = avgDayPeak * demandMult;
    const simValue = dayPeakTarget * curvedProgress;

    const noiseSeed = step * 10000 + month * 100 + dayDate;
    const noise = 0.990 + seededRand(noiseSeed) * 0.020;

    return Math.max(0, Math.round(simValue * noise));
};
