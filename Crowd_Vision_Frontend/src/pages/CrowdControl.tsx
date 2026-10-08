import { useEffect, useState } from "react";
import { CircleAlert, Info, TrainFront } from "lucide-react";
import { PageLayout } from "@/components/layout/PageLayout";
import { cn } from "@/lib/utils";
import { CrowdControlResponse, fetchCrowdSummary } from "@/services/crowdControl";


const REFRESH_INTERVAL_MS = 30_000;

/* -------------------------------------------------------------------------- */
/*  Constants & helpers                                                       */
/* -------------------------------------------------------------------------- */

const SAFE_CAPACITY_LIMIT = 85;

type Level = {
  id: 1 | 2 | 3 | 4;
  label: string;
  sop: string;
  chip: string;
  chipActive: string;
};

const LEVELS: Level[] = [
  {
    id: 1,
    label: "Normal",
    sop: "Normal operations. Keep all entries open and monitor platform occupancy.",
    chip: "border-emerald-500/50 text-emerald-400 hover:bg-emerald-500/10",
    chipActive: "bg-emerald-500 border-emerald-500 text-white",
  },
  {
    id: 2,
    label: "Elevated",
    sop: "Deploy staff at FOB landings. Announce platform changes early and keep holding areas ready.",
    chip: "border-amber-500/50 text-amber-400 hover:bg-amber-500/10",
    chipActive: "bg-amber-500 border-amber-500 text-white",
  },
  {
    id: 3,
    label: "High",
    sop: "Regulate platform entry. Open the overflow waiting area. Divert FOB traffic to the wide FOB.",
    chip: "border-orange-500/50 text-orange-400 hover:bg-orange-500/10",
    chipActive: "bg-orange-500 border-orange-500 text-white",
  },
  {
    id: 4,
    label: "Critical",
    sop: "Stop entry at station gates. Hold passengers outside, clear FOBs, and alert RPF / GRP control.",
    chip: "border-red-500/50 text-red-400 hover:bg-red-500/10",
    chipActive: "bg-red-600 border-red-600 text-white",
  },
];

// Backend may send null, undefined or "" for counts — treat anything non-numeric as missing.
const toCount = (value: unknown): number | null => {
  if (value == null || value === "") return null;
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
};

const percentOf = (count?: number | null, capacity?: number | null): number | null => {
  const c = toCount(count);
  const cap = toCount(capacity);
  return c != null && cap != null && cap > 0 ? Math.round((c / cap) * 100) : null;
};

const formatNumber = (value?: number | null) => {
  const num = toCount(value);
  return num == null ? "-" : num.toLocaleString("en-IN");
};

const formatLevel = (value?: string | null) =>
  value ? value.charAt(0).toUpperCase() + value.slice(1) : "—";

/* -------------------------------------------------------------------------- */
/*  UI pieces                                                                 */
/* -------------------------------------------------------------------------- */

function ProgressBar({
  percent,
  barClassName,
  showLimit = false,
}: {
  percent: number;
  barClassName: string;
  showLimit?: boolean;
}) {
  return (
    <div className="relative h-2 w-full rounded-full bg-slate-700/60">
      <div
        className={cn("h-full rounded-full transition-all duration-500", barClassName)}
        style={{ width: `${Math.min(percent, 100)}%` }}
      />
      {showLimit && (
        <div
          className="absolute -top-1 -bottom-1 border-l border-dashed border-slate-300/70"
          style={{ left: `${SAFE_CAPACITY_LIMIT}%` }}
        />
      )}
    </div>
  );
}

function StageHeader({ title }: { title: string }) {
  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
      <h2 className="text-sm sm:text-base font-semibold text-foreground">{title}</h2>
    </div>
  );
}

function CrowdMetricCard({
  name,
  peopleCount,
  capacity,
  level,
  showLimit = false,
}: {
  name?: string | null;
  peopleCount?: number | null;
  capacity?: number | null;
  level?: string | null;
  showLimit?: boolean;
}) {
  const percent = percentOf(peopleCount, capacity);
  const nearCapacity = percent !== null && percent >= 75;
  const overLimit = percent !== null && percent >= SAFE_CAPACITY_LIMIT;

  const accent = nearCapacity ? "border-orange-500/60" : "border-border";
  const barClassName = overLimit
    ? "bg-gradient-to-r from-orange-500 to-red-500"
    : nearCapacity
      ? "bg-orange-500"
      : "bg-emerald-500";
  const badgeClassName = overLimit
    ? "border-red-500/60 bg-red-500/10 text-red-400"
    : nearCapacity
      ? "border-orange-500/60 bg-orange-500/10 text-orange-400"
      : level
        ? "border-emerald-500/60 bg-emerald-500/10 text-emerald-400"
        : "border-border text-muted-foreground";

  return (
    <div className={cn("rounded-lg border border-l-4 bg-secondary/20 p-4", accent)}>
      <p className="text-sm font-semibold text-foreground">{name || "—"}</p>
      <div className="mt-3 flex items-end justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between">
            <p className="text-xl font-bold text-foreground">
              {formatNumber(peopleCount)}
              <span className="ml-1 text-xs font-normal text-muted-foreground">
                / {formatNumber(capacity)}
              </span>
            </p>
            <span className="text-xs text-muted-foreground">
              {percent === null ? "-" : `${percent}%`}
            </span>
          </div>
          {percent !== null && (
            <div className="mt-1.5">
              <ProgressBar percent={percent} barClassName={barClassName} showLimit={showLimit} />
            </div>
          )}
        </div>
        <span
          className={cn(
            "flex-shrink-0 rounded-md border px-2 py-1 text-xs font-medium",
            badgeClassName,
          )}
        >
          {formatLevel(level)}
        </span>
      </div>
    </div>
  );
}

function EmptyState({ loading }: { loading: boolean }) {
  return (
    <p className="text-sm text-muted-foreground">
      {loading ? "Loading live data…" : "No data available."}
    </p>
  );
}

/* -------------------------------------------------------------------------- */
/*  Page                                                                      */
/* -------------------------------------------------------------------------- */

export default function CrowdControl() {
  const [crowdData, setCrowdData] = useState<CrowdControlResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedLevelId, setSelectedLevelId] = useState<Level["id"]>(1);
  const selectedLevel = LEVELS.find((level) => level.id === selectedLevelId) ?? LEVELS[0];

  useEffect(() => {
    const controller = new AbortController();

    const loadCrowdData = async () => {
      try {
        const data = await fetchCrowdSummary(controller.signal);
        setCrowdData(data);
        setLoadError(null);
      } catch (error) {
        if (error instanceof Error && error.name === "AbortError") return;
        setLoadError(error instanceof Error ? error.message : "Failed to fetch crowd summary");
      } finally {
        if (!controller.signal.aborted) setIsLoading(false);
      }
    };

    void loadCrowdData();
    const intervalId = window.setInterval(() => void loadCrowdData(), REFRESH_INTERVAL_MS);

    return () => {
      controller.abort();
      window.clearInterval(intervalId);
    };
  }, []);

  const holdingAreas = crowdData?.holding_areas?.group_level_count ?? [];
  const platforms = crowdData?.platforms?.group_level_count ?? [];
  const bookingOffices = crowdData?.booking_office?.cameras ?? [];
  const fobs = crowdData?.fobs?.group_level_count ?? [];

  return (
    <PageLayout>
      <div className="max-w-[1600px] 2xl:max-w-[2400px] mx-auto space-y-4">
        {/* Title */}
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-secondary/60">
            <TrainFront className="h-5 w-5 text-foreground" />
          </div>
          <h1 className="text-xl sm:text-2xl font-semibold text-foreground">
            SEC Station Crowd Control Board
          </h1>
        </div>

        {/* Alert levels + SOP */}
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex flex-wrap gap-2">
            {LEVELS.map((level) => {
              const isActive = level.id === selectedLevelId;
              return (
                <button
                  key={level.id}
                  type="button"
                  onClick={() => setSelectedLevelId(level.id)}
                  className={cn(
                    "rounded-lg border px-3 py-1 text-xs font-medium transition-colors",
                    isActive ? level.chipActive : level.chip,
                  )}
                >
                  Level {level.id} · {level.label}
                </button>
              );
            })}
          </div>
          <div className="flex items-start gap-2 rounded-lg border border-border bg-card px-4 py-2.5 xl:max-w-xl">
            <Info className="mt-0.5 h-4 w-4 flex-shrink-0 text-sky-400" />
            <p className="text-xs text-muted-foreground">
              <span className="font-semibold text-foreground">
                Level {selectedLevel.id} · {selectedLevel.label} SOP:
              </span>{" "}
              {selectedLevel.sop}
            </p>
          </div>
        </div>

        {/* Stage 1 — Holding areas */}
        <section className="rounded-xl border border-border bg-card p-4">
          <StageHeader title="Outside the station – Holding areas" />
          {holdingAreas.length === 0 ? (
            <EmptyState loading={isLoading} />
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              {holdingAreas.map((area) => (
                <CrowdMetricCard
                  key={area.name}
                  name={area.name}
                  peopleCount={area.people_count}
                  capacity={area.capacity}
                  level={area.level}
                />
              ))}
            </div>
          )}
        </section>

        {/* Stage 2 — Platforms */}
        <section className="rounded-xl border border-border bg-card p-3">
          <StageHeader title="Platforms" />
          {platforms.length === 0 ? (
            <EmptyState loading={isLoading} />
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {platforms.map((platform) => (
                <CrowdMetricCard
                  key={platform.name}
                  name={platform.name}
                  peopleCount={platform.people_count}
                  capacity={platform.capacity}
                  level={platform.level}
                  showLimit
                />
              ))}
            </div>
          )}
          <p className="mt-4 flex items-center gap-2 text-xs text-muted-foreground">
            <CircleAlert className="h-4 w-4 flex-shrink-0 text-amber-400" />
            Dashed line marks the {SAFE_CAPACITY_LIMIT}% safe-capacity limit. Above it, entry to
            that platform is regulated.
          </p>
        </section>

        {/* Stage 3 — Booking offices */}
        <section className="rounded-xl border border-border bg-card p-4">
          <StageHeader title="Booking Offices" />
          {bookingOffices.length === 0 ? (
            <EmptyState loading={isLoading} />
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
              {bookingOffices.map((office) => (
                <CrowdMetricCard
                  key={office.camera_id ?? office.name}
                  name={office.name}
                  peopleCount={office.people_count}
                  capacity={office.capacity}
                  level={office.level}
                />
              ))}
            </div>
          )}
        </section>

        {/* Stage 4 — FOBs */}
        <section className="rounded-xl border border-border bg-card p-4">
          <StageHeader title="FOBs" />
          {fobs.length === 0 ? (
            <EmptyState loading={isLoading} />
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              {fobs.map((fob) => (
                <CrowdMetricCard
                  key={fob.name}
                  name={fob.name}
                  peopleCount={fob.people_count}
                  capacity={fob.capacity}
                  level={fob.level}
                />
              ))}
            </div>
          )}
        </section>
      </div>
    </PageLayout>
  );
}