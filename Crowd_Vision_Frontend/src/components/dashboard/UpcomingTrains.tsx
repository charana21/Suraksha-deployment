import { useState, useEffect, useRef } from "react";

import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/card";

import { Badge } from "@/components/ui/badge";

import { ScrollArea } from "@/components/ui/scroll-area";

import {
  Train,
  ArrowUpRight,
  ArrowDownLeft,
} from "lucide-react";

import { Switch } from "@/components/ui/switch";

import {
  Dialog,
  DialogContent,
  DialogTrigger,
} from "@/components/ui/dialog";

import { Button } from "@/components/ui/button";

import { trainsApi } from "@/services/trainsApi";

import {
  TrainSchedule,
  TrainLiveToggleResponse,
} from "@/types/trains";

import { useAuth } from "@/context/AuthContext";

import { cn } from "@/lib/utils";

import { ArrivalHistoryModal } from "@/components/dashboard/ArrivalHistoryModal";

interface UpcomingTrainsProps {
  variant?: "default" | "overlay";
}

export function UpcomingTrains({
  variant = "default",
}: UpcomingTrainsProps) {
  const { user } = useAuth();

  const canToggleLive = true;

  const [arriving, setArriving] = useState<TrainSchedule[]>([]);
  const [departing, setDeparting] = useState<TrainSchedule[]>([]);

  const [allArriving, setAllArriving] = useState<TrainSchedule[]>([]);
  const [allDeparting, setAllDeparting] = useState<TrainSchedule[]>([]);

  const [loading, setLoading] = useState(true);

  const [lastUpdated, setLastUpdated] = useState<string | null>(
    null
  );

  const [totalCount, setTotalCount] = useState(0);

  const [maxVisiblePerSection, setMaxVisiblePerSection] =
    useState(3);

  const contentRef = useRef<HTMLDivElement>(null);

  const [liveToggleInfo, setLiveToggleInfo] =
    useState<TrainLiveToggleResponse | null>(null);

  const [liveToggleLoading, setLiveToggleLoading] =
    useState(true);

  const [isUpdatingLiveToggle, setIsUpdatingLiveToggle] =
    useState(false);

  const formatTimestamp = (
    value?: string | null
  ) => {
    if (!value) return null;

    const parsed = new Date(value);

    if (Number.isNaN(parsed.getTime())) {
      return value;
    }

    return parsed.toLocaleString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
      hour12: true,
    });
  };

  const liveStatusLabel = liveToggleInfo
    ? liveToggleInfo.live_refresh_enabled
      ? "Live mode active"
      : "Live mode paused"
    : "Live status unavailable";

  const liveFetchLabel = liveToggleInfo?.last_fetch_cycle
    ? `Last live fetch ${formatTimestamp(
        liveToggleInfo.last_fetch_cycle
      )}`
    : "Live fetch pending";

  const liveUpdatedLabel = liveToggleInfo?.last_updated_at
    ? `Updated ${formatTimestamp(
        liveToggleInfo.last_updated_at
      )}`
    : null;

  const processTrains = (trains: TrainSchedule[]) => {
    if (!Array.isArray(trains)) return;

    // Calculate unique total footfall
    const uniqueTrainsMap = new Map<string, number>();

    trains.forEach((t) => {
      if (t.train_number) {
        uniqueTrainsMap.set(
          t.train_number,
          t.total_passengers || 0
        );
      }
    });

    let footfallSum = 0;

    uniqueTrainsMap.forEach((count) => {
      footfallSum += count;
    });

    setTotalCount(footfallSum);

    // Split into arriving and departing
    const arr: TrainSchedule[] = [];
    const dep: TrainSchedule[] = [];

    trains.forEach((t) => {
      if (t.arrival_scheduled) {
        arr.push(t);
      }

      if (t.departure_scheduled) {
        dep.push(t);
      }
    });

    setAllArriving(arr);
    setAllDeparting(dep);

    setArriving(arr);
    setDeparting(dep);
  };

  const fetchTrains = async () => {
    try {
      const data = await trainsApi.getUpcomingTrains();

      processTrains(data.trains || []);

      setLastUpdated(new Date().toLocaleTimeString());

      setLoading(false);
    } catch (error) {
      setLoading(false);
    }
  };

  const fetchLiveToggleState = async () => {
    setLiveToggleLoading(true);

    try {
      const data = await trainsApi.getLiveToggle();

      setLiveToggleInfo(data);
    } catch (error) {
    } finally {
      setLiveToggleLoading(false);
    }
  };

  const handleLiveToggleChange = async (
    enabled: boolean
  ) => {
    if (!canToggleLive) return;

    const originalState =
      liveToggleInfo?.live_refresh_enabled;

    setLiveToggleInfo((prev) =>
      prev
        ? {
            ...prev,
            live_refresh_enabled: enabled,
          }
        : null
    );

    setIsUpdatingLiveToggle(true);

    try {
      const data =
        await trainsApi.setLiveToggle(enabled);

      setLiveToggleInfo(data);

      await fetchTrains();
    } catch (error) {
      if (originalState !== undefined) {
        setLiveToggleInfo((prev) =>
          prev
            ? {
                ...prev,
                live_refresh_enabled:
                  originalState,
              }
            : null
        );
      }
    } finally {
      setIsUpdatingLiveToggle(false);
    }
  };

  useEffect(() => {
    fetchTrains();
    fetchLiveToggleState();

    // Dedicated WebSocket for Train Updates
    const baseUrl =
      import.meta.env.VITE_API_URL ||
      "https://crowdvision-api.tride.live/api";

    const wsUrl =
      baseUrl.replace(/^http/, "ws").replace(/\/$/, "") +
      "/ws/trains";

    let ws: WebSocket | null = null;

    let reconnectTimeout: ReturnType<
      typeof setTimeout
    >;

    const connect = () => {
      try {
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
        };

        ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);

            if (message.type === "train_schedule") {
              if (
                message.event === "upcoming_update" ||
                message.event === "schedule_uploaded"
              ) {
                if (
                  message.data &&
                  Array.isArray(message.data.trains)
                ) {
                  processTrains(
                    message.data.trains
                  );

                  setLastUpdated(
                    new Date().toLocaleTimeString()
                  );
                }
              }
            }
          } catch (err) {
          }
        };

        ws.onclose = () => {
          reconnectTimeout = setTimeout(
            connect,
            3000
          );
        };

        ws.onerror = (err) => {
          ws?.close();
        };
      } catch (error) {
        reconnectTimeout = setTimeout(
          connect,
          3000
        );
      }
    };

    connect();

    return () => {
      if (ws) {
        ws.onclose = null;
        ws.close();
      }

      clearTimeout(reconnectTimeout);
    };
  }, []);

  const isOverlay = variant === "overlay";

  const liveSwitchChecked =
    liveToggleInfo?.live_refresh_enabled ?? false;

  useEffect(() => {
    if (!isOverlay) return;

    const el = contentRef.current;

    if (!el) return;

    const update = () => {
      const height = el.clientHeight;

      const SECTION_HEADER = 36;
      const FOOTER = 36;
      const ITEM_H = 72;

      const available = Math.max(
        0,
        height - SECTION_HEADER - FOOTER
      );

      const maxItems = Math.max(
        4,
        Math.floor(available / ITEM_H)
      );

      setMaxVisiblePerSection(maxItems);
    };

    update();

    const ro = new ResizeObserver(update);

    ro.observe(el);

    return () => ro.disconnect();
  }, [isOverlay]);

  if (
    loading &&
    allArriving.length === 0 &&
    allDeparting.length === 0
  ) {
    if (isOverlay) return null;

    return (
      <Card className="h-full bg-background text-foreground border-border">
        <CardHeader className="pb-2">
          <CardTitle className="text-lg font-medium flex items-center gap-2 text-foreground">
            <Train className="h-5 w-5 text-primary" />
            Scheduled Trains
          </CardTitle>
        </CardHeader>

        <CardContent>
          <div className="flex items-center justify-center h-40 text-muted-foreground">
            Loading schedule...
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card
      className={cn(
        "h-full flex flex-col shadow-sm transition-all duration-200",

        /*
         * LIGHT MODE
         * White Train Schedule card
         */
        !isOverlay &&
          "bg-background text-foreground border-border",

        /*
         * OVERLAY / TRAIN SCHEDULE
         *
         * Light mode:
         * white background + dark text
         *
         * Dark mode:
         * original dark translucent appearance
         */
        isOverlay &&
          "bg-white text-foreground border-border shadow-2xl rounded-xl " +
          "dark:bg-black/40 dark:backdrop-blur-md dark:border-white/10 dark:text-white"
      )}
    >
      <CardHeader
        className={cn(
          "pb-2",

          // Normal card
          !isOverlay &&
            "border-b border-border",

          // Train Schedule card
          isOverlay &&
            "py-2 px-3 border-b border-border dark:border-white/10"
        )}
      >
        <div className="flex items-center justify-between gap-3 w-full">
          <div className="flex items-center gap-3">
            <CardTitle
              className={cn(
                "text-lg font-bold flex items-center gap-2 whitespace-nowrap",

                !isOverlay &&
                  "text-foreground",

                /*
                 * Light mode = dark text
                 * Dark mode = white text
                 */
                isOverlay &&
                  "text-foreground dark:text-white",

                isOverlay && "text-base"
              )}
            >
              <Train
                className={cn(
                  "h-4 w-4",

                  isOverlay
                    ? "text-foreground dark:text-white/80"
                    : "text-primary"
                )}
              />

              {isOverlay
                ? "Train Schedule"
                : "Ongoing & Upcoming Trains"}

              <ArrivalHistoryModal
                searchMode
                overlay={isOverlay}
              />
            </CardTitle>

            {/*
            Live toggle intentionally disabled

            {canToggleLive && (
              <div className="flex items-center rounded-full border border-border p-1 bg-muted/80">
                <Switch
                  checked={liveSwitchChecked}
                  onCheckedChange={(value) =>
                    void handleLiveToggleChange(value)
                  }
                  disabled={
                    !canToggleLive ||
                    liveToggleLoading ||
                    !liveToggleInfo
                  }
                  aria-label="Toggle live train refresh"
                />
              </div>
            )}
            */}
          </div>

          <span
            className={cn(
              "text-xs font-mono opacity-50 whitespace-nowrap",

              isOverlay
                ? "text-muted-foreground dark:text-white/60"
                : "text-muted-foreground"
            )}
          >
            {lastUpdated}
          </span>
        </div>

        {/*
        Live status intentionally disabled

        {liveToggleInfo && (
          <div className="mt-1 flex flex-wrap items-center gap-2 text-[10px] text-muted-foreground">
            <Badge
              variant="outline"
              className={cn(
                "text-[10px] font-bold uppercase tracking-wider",
                isOverlay
                  ? "border-border text-foreground dark:border-white/30 dark:text-white/80"
                  : ""
              )}
            >
              {liveStatusLabel}
            </Badge>

            <span>{liveFetchLabel}</span>

            {liveUpdatedLabel && (
              <span
                className={
                  isOverlay
                    ? "text-muted-foreground dark:text-white/60"
                    : "text-muted-foreground"
                }
              >
                {liveUpdatedLabel}

                {liveToggleInfo.last_updated_by
                  ? ` by ${liveToggleInfo.last_updated_by}`
                  : ""}
              </span>
            )}
          </div>
        )}
        */}

        {/* TOTAL FOOTFALL */}
        <div className="mt-1">
          <span
            className={cn(
              "px-2 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider border",

              isOverlay
                ? "bg-orange-50 text-orange-700 border-orange-200 dark:bg-orange-500/20 dark:text-orange-100 dark:border-orange-500/30 dark:shadow-[0_0_10px_rgba(249,115,22,0.2)]"
                : "bg-orange-50 text-orange-700 border-orange-200"
            )}
          >
            Total Footfall:{" "}
            {totalCount.toLocaleString()}
          </span>
        </div>
      </CardHeader>

      <CardContent
        ref={contentRef}
        className={cn(
          "flex-1 p-0 min-h-0",

          isOverlay && "text-sm"
        )}
      >
        <div
          className={cn(
            "grid grid-cols-1 h-full divide-y",

            isOverlay
              ? "divide-border dark:divide-white/10"
              : "md:grid-cols-2 md:divide-y-0 md:divide-x md:divide-border"
          )}
        >
          {/* ARRIVING */}
          <TrainSection
            title="Arriving"
            count={allArriving.length}
            items={arriving}
            allItems={allArriving}
            type="arrival"
            isOverlay={isOverlay}
            maxVisible={maxVisiblePerSection}
            icon={
              <ArrowDownLeft className="h-3 w-3" />
            }
            colorClass="text-emerald-400"
          />

          {/* DEPARTING */}
          <TrainSection
            title="Departing"
            count={allDeparting.length}
            items={departing}
            allItems={allDeparting}
            type="departure"
            isOverlay={isOverlay}
            maxVisible={maxVisiblePerSection}
            icon={
              <ArrowUpRight className="h-3 w-3" />
            }
            colorClass="text-blue-400"
          />
        </div>
      </CardContent>
    </Card>
  );
}

function TrainSection({
  title,
  count,
  items,
  allItems,
  type,
  isOverlay,
  icon,
  colorClass,
  maxVisible,
}: any) {
  const visibleItems =
    isOverlay && maxVisible
      ? items.slice(0, maxVisible)
      : items;

  const hiddenCount = Math.max(
    0,
    allItems.length - visibleItems.length
  );

  return (
    <div className="flex flex-col min-h-0 overflow-hidden">
      {/* SECTION HEADER */}
      <div
        className={cn(
          "px-3 py-2 text-xs font-bold uppercase tracking-wider flex justify-between items-center sticky top-0 z-10",

          isOverlay
            ? "bg-muted/20 dark:bg-white/5"
            : "bg-muted/20"
        )}
      >
        <span
          className={cn(
            "flex items-center gap-1.5",

            isOverlay
              ? `${colorClass}`
              : "text-foreground"
          )}
        >
          {icon}
          {title}
        </span>

        <Badge
          variant="outline"
          className={cn(
            "text-[10px] h-4 px-1",

            isOverlay
              ? "border-border text-muted-foreground dark:border-white/20 dark:text-white/60"
              : "border-border text-muted-foreground"
          )}
        >
          {count}
        </Badge>
      </div>

      {isOverlay ? (
        <div className="flex-1 overflow-hidden">
          <div className="divide-y divide-border dark:divide-white/5">
            {visibleItems.length === 0 ? (
              <div className="p-4 text-center text-xs italic text-muted-foreground dark:text-white/50">
                No {title.toLowerCase()} trains
              </div>
            ) : (
              visibleItems.map(
                (
                  train: TrainSchedule,
                  idx: number
                ) => (
                  <TrainItem
                    key={`${train.train_number}-${type}-${idx}`}
                    train={train}
                    type={type}
                    overlay={isOverlay}
                  />
                )
              )
            )}
          </div>
        </div>
      ) : (
        <ScrollArea className="flex-1">
          {/* LIGHT MODE DIVIDER */}
          <div className="divide-y divide-border">
            {items.length === 0 ? (
              <div className="p-4 text-center text-xs italic text-muted-foreground">
                No {title.toLowerCase()} trains
              </div>
            ) : (
              items.map(
                (
                  train: TrainSchedule,
                  idx: number
                ) => (
                  <TrainItem
                    key={`${train.train_number}-${type}-${idx}`}
                    train={train}
                    type={type}
                    overlay={isOverlay}
                  />
                )
              )
            )}
          </div>
        </ScrollArea>
      )}

      {/* VIEW ALL BUTTON */}
      {hiddenCount > 0 && (
        <div
          className={cn(
            "p-2 border-t",

            isOverlay
              ? "border-border dark:border-white/10"
              : "border-border"
          )}
        >
          <Dialog>
            <DialogTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className={cn(
                  "w-full h-7 text-xs",

                  isOverlay
                    ? "text-foreground hover:bg-muted hover:text-foreground dark:text-white/70 dark:hover:bg-white/10 dark:hover:text-white"
                    : "text-foreground hover:bg-muted"
                )}
              >
                {isOverlay
                  ? `Show more (+${hiddenCount})`
                  : `View All ${count} Trains`}
              </Button>
            </DialogTrigger>

            <DialogContent
              className={cn(
                "max-w-3xl max-h-[85vh] flex flex-col",

                /*
                 * Light mode
                 */
                "bg-white text-gray-900 border-gray-200",

                /*
                 * Dark mode
                 */
                "dark:bg-background dark:text-foreground dark:border-border"
              )}
            >
              <div className="flex items-center gap-2 mb-4">
                <span
                  className={cn(
                    "font-bold text-lg",

                    colorClass
                  )}
                >
                  {title} Trains
                </span>

                <Badge variant="secondary">
                  {count}
                </Badge>
              </div>

              <div className="flex-1 overflow-y-auto max-h-[60vh] pr-2">
                <div className="grid grid-cols-1 gap-2 pb-10">
                  {allItems.map(
                    (
                      train: TrainSchedule,
                      idx: number
                    ) => (
                      <TrainItem
                        key={`modal-${train.train_number}-${type}-${idx}`}
                        train={train}
                        type={type}
                        overlay={isOverlay}
                      />
                    )
                  )}
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      )}
    </div>
  );
}

function TrainItem({
  train,
  type,
  overlay,
}: {
  train: TrainSchedule;
  type: "arrival" | "departure";
  overlay?: boolean;
}) {
  const isArrival = type === "arrival";

  // Use scheduled time from API
  const timeDisplay = isArrival
    ? train.arrival_scheduled ||
      train.arrival_actual ||
      "N/A"
    : train.departure_scheduled ||
      train.departure_actual ||
      "N/A";

  return (
    <div
      className={cn(
        "px-4 py-3 transition-colors group border-b last:border-0",

        /*
         * Light mode
         */
        !overlay &&
          "border-border hover:bg-muted/30",

        /*
         * Train Schedule:
         * Light = light border/background
         * Dark = original dark styling
         */
        overlay &&
          "border-border hover:bg-muted/40 dark:border-white/5 dark:hover:bg-white/5"
      )}
    >
      <div className="flex justify-between items-start mb-1">
        <div className="flex flex-col gap-1 w-full">

          {/* TOP ROW */}
          <div className="flex justify-between items-center w-full">

            {/* TRAIN NUMBER */}
            <span
              className={cn(
                "font-bold text-xs tracking-wide",

                overlay
                  ? "text-muted-foreground dark:text-white/60"
                  : "text-muted-foreground"
              )}
            >
              {train.train_number}
            </span>

            <div className="flex items-center gap-2">

              {/* EXPECTED ARRIVAL / DEPARTURE */}
              <span
                className={cn(
                  "text-[10px] uppercase font-bold tracking-wider opacity-70",

                  isArrival
                    ? "text-emerald-500 dark:text-emerald-400"
                    : "text-blue-500 dark:text-blue-400"
                )}
              >
                {isArrival
                  ? "EXP ARRIVAL"
                  : "EXP DEPARTURE"}
              </span>

              {/* TIME */}
              <span
                className={cn(
                  "font-mono text-base font-black tracking-wider",

                  overlay
                    ? "text-foreground dark:text-white"
                    : "text-foreground"
                )}
              >
                {timeDisplay}
              </span>
            </div>
          </div>

          {/* ARRIVAL HISTORY */}
          {isArrival && (
            <div className="flex justify-end">
              <ArrivalHistoryModal
                trainNumber={train.train_number}
                trainName={train.train_name}
                overlay={overlay}
              />
            </div>
          )}

          {/* TRAIN NAME */}
          <div
            className={cn(
              "text-sm font-black truncate",

              overlay
                ? "text-foreground dark:text-white"
                : "text-foreground"
            )}
            title={train.train_name}
          >
            {train.train_name}
          </div>
        </div>
      </div>

      {/* BOTTOM STATUS ROW */}
      <div className="flex items-center gap-2 text-[10px] mt-1">

        {/* PLATFORM */}
        {train.platform && (
          <span
            className={cn(
              "px-1.5 py-0.5 rounded text-[10px] font-bold border",

              overlay
                ? "border-border bg-muted/40 text-foreground dark:border-white/20 dark:bg-white/10 dark:text-white"
                : "border-border bg-muted/40 text-muted-foreground"
            )}
          >
            PF {train.platform}
          </span>
        )}

        {/* TOTAL PASSENGERS */}
        {train.total_passengers !== undefined &&
          train.total_passengers !== null && (
            <span
              className={cn(
                "px-1.5 py-0.5 rounded text-[10px] font-bold border flex items-center gap-1",

                overlay
                  ? "border-blue-200 bg-blue-50 text-blue-700 dark:border-white/20 dark:bg-blue-500/20 dark:text-blue-200"
                  : "border-blue-200 bg-blue-50 text-blue-700"
              )}
            >
              Total: {train.total_passengers}
            </span>
          )}

        {/* DELAY */}
        {train.delay_status && (
          <span
            className={cn(
              "font-bold flex items-center gap-1 animate-pulse bg-red-400/10 px-1.5 py-0.5 rounded",

              "text-red-500"
            )}
          >
            {train.delay_status}
          </span>
        )}
      </div>
    </div>
  );
}