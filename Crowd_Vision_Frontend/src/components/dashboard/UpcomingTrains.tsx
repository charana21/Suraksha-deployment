import { useState, useEffect, useRef } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Train, ArrowUpRight, ArrowDownLeft } from 'lucide-react';
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { trainsApi } from '@/services/trainsApi';
import { TrainSchedule, TrainLiveToggleResponse } from '@/types/trains';
import { useAuth } from "@/context/AuthContext";
import { cn } from "@/lib/utils";
import { ArrivalHistoryModal } from "@/components/dashboard/ArrivalHistoryModal";

interface UpcomingTrainsProps {
  variant?: 'default' | 'overlay';
}

export function UpcomingTrains({ variant = 'default' }: UpcomingTrainsProps) {
  const { user } = useAuth();
  const canToggleLive = true;

  const [arriving, setArriving] = useState<TrainSchedule[]>([]);
  const [departing, setDeparting] = useState<TrainSchedule[]>([]);
  const [allArriving, setAllArriving] = useState<TrainSchedule[]>([]);
  const [allDeparting, setAllDeparting] = useState<TrainSchedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [totalCount, setTotalCount] = useState(0);
  const [maxVisiblePerSection, setMaxVisiblePerSection] = useState(3);
  const contentRef = useRef<HTMLDivElement>(null);
  const [liveToggleInfo, setLiveToggleInfo] = useState<TrainLiveToggleResponse | null>(null);
  const [liveToggleLoading, setLiveToggleLoading] = useState(true);
  const [isUpdatingLiveToggle, setIsUpdatingLiveToggle] = useState(false);

  const formatTimestamp = (value?: string | null) => {
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
    ? `Last live fetch ${formatTimestamp(liveToggleInfo.last_fetch_cycle)}`
    : "Live fetch pending";

  const liveUpdatedLabel = liveToggleInfo?.last_updated_at
    ? `Updated ${formatTimestamp(liveToggleInfo.last_updated_at)}`
    : null;

  const processTrains = (trains: TrainSchedule[]) => {
    if (!Array.isArray(trains)) return;
    
    // Calculate unique total footfall (sum of total_passengers for unique trains)
    const uniqueTrainsMap = new Map<string, number>();
    trains.forEach(t => {
      if (t.train_number) {
         // Store passenger count for this train number. 
         // Using Map ensures we only count each train once even if it's in both arr/dep lists (if raw list has duplicates)
         // We assume total_passengers is present. If distinct records have diff counts, taking last one is acceptable.
         uniqueTrainsMap.set(t.train_number, t.total_passengers || 0);
      }
    });

    let footfallSum = 0;
    uniqueTrainsMap.forEach(count => {
      footfallSum += count;
    });
    setTotalCount(footfallSum);

    // Split into arriving and departing
    // Arriving: Has arrival time
    // Departing: Has departure time
    const arr: TrainSchedule[] = [];
    const dep: TrainSchedule[] = [];

    trains.forEach(t => {
      // Logic: A train is arriving if it has a scheduled arrival
      if (t.arrival_scheduled) {
        arr.push(t);
      }
      // A train is departing if it has a scheduled departure
      if (t.departure_scheduled) {
        dep.push(t);
      }
    });

    // Sort by time (closest first) - already sorted by backend usually, but good to ensure
    // Here we just trust backend order or simplified filtering
    setAllArriving(arr);
    setAllDeparting(dep);
    // Dynamic Limit Logic for Overlay
    // Goal: Show max 4 items total. Ideally 2 Arriving + 2 Departing.
    // If one side has fewer than 2, the other side can take the extra space.
    
    let arrLimit = 3;
    let depLimit = 3;

    if (variant === 'overlay') {
      const MAX_TOTAL = 4;
      const IDEAL_SPLIT = 2;
      
      const arrAvailable = arr.length;
      const depAvailable = dep.length;

      // Start with ideal split
      arrLimit = IDEAL_SPLIT;
      depLimit = IDEAL_SPLIT;

      // If Arriving has fewer than 2, give extra to Departing
      if (arrAvailable < IDEAL_SPLIT) {
        arrLimit = arrAvailable;
        depLimit = MAX_TOTAL - arrLimit;
      }
      // If Departing has fewer than 2, give extra to Arriving
      else if (depAvailable < IDEAL_SPLIT) {
        depLimit = depAvailable;
        arrLimit = MAX_TOTAL - depLimit;
      }
    }

    setArriving(arr);
    setDeparting(dep);
  };

  const fetchTrains = async () => {
    try {
      const data = await trainsApi.getUpcomingTrains();
      // data.trains is the flat list now
      processTrains(data.trains || []);
      setLastUpdated(new Date().toLocaleTimeString());
      setLoading(false);
    } catch (error) {
      console.error("Failed to fetch trains:", error);
      setLoading(false);
    }
  };

  const fetchLiveToggleState = async () => {
    setLiveToggleLoading(true);
    try {
      const data = await trainsApi.getLiveToggle();
      setLiveToggleInfo(data);
    } catch (error) {
      console.error("[Trains] Live toggle fetch failed:", error);
    } finally {
      setLiveToggleLoading(false);
    }
  };

  const handleLiveToggleChange = async (enabled: boolean) => {
    if (!canToggleLive) return;
    
    // Store original state for fallback
    const originalState = liveToggleInfo?.live_refresh_enabled;
    
    // Optimistic update
    setLiveToggleInfo(prev => prev ? { ...prev, live_refresh_enabled: enabled } : null);
    setIsUpdatingLiveToggle(true);
    
    try {
      const data = await trainsApi.setLiveToggle(enabled);
      setLiveToggleInfo(data);
      await fetchTrains();
    } catch (error) {
      console.error("[Trains] Live toggle update failed:", error);
      // Revert optimistic update on failure
      if (originalState !== undefined) {
         setLiveToggleInfo(prev => prev ? { ...prev, live_refresh_enabled: originalState } : null);
      }
    } finally {
      setIsUpdatingLiveToggle(false);
    }
  };

  useEffect(() => {
    fetchTrains();
    fetchLiveToggleState();

    // Dedicated WebSocket for Train Updates
    const apiHost = import.meta.env.VITE_API_URL 
      ? import.meta.env.VITE_API_URL.replace(/^http(s)?:\/\//, '') 
      : 'localhost:6006/api';
      
    // Handle protocol (switching http->ws, https->wss)
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // Construct full WS URL: e.g. wss://api.example.com/api/ws/trains or ws://localhost:8000/api/ws/trains
    // Note: VITE_API_URL might include /api path already, so we need to be careful
    
    // Simpler approach: build from base URL logic similar to existing services
    const baseUrl = import.meta.env.VITE_API_URL || 'https://crowdvision-api.tride.live/api';
    const wsUrl = baseUrl.replace(/^http/, 'ws').replace(/\/$/, '') + '/ws/trains';
    
    console.log('[Trains] Connecting to WebSocket:', wsUrl);
    
    let ws: WebSocket | null = null;
    let reconnectTimeout: NodeJS.Timeout;

    const connect = () => {
      try {
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          console.log('[Trains] Connected to Train WebSocket');
        };

        ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            
            // Handle Train Schedule Updates
            if (message.type === 'train_schedule') {
              // Accept both upcoming_update and schedule_uploaded
              if (message.event === 'upcoming_update' || message.event === 'schedule_uploaded') {
                console.log('[Trains] Received update:', message.data);
                if (message.data && Array.isArray(message.data.trains)) {
                   processTrains(message.data.trains);
                   setLastUpdated(new Date().toLocaleTimeString());
                }
              }
            }
          } catch (err) {
            console.error('[Trains] Error parsing WebSocket message:', err);
          }
        };

        ws.onclose = () => {
          console.log('[Trains] WebSocket disconnected, reconnecting in 3s...');
          reconnectTimeout = setTimeout(connect, 3000);
        };
        
        ws.onerror = (err) => {
           console.error('[Trains] WebSocket error:', err);
           ws?.close();
        };

      } catch (error) {
        console.error('[Trains] Connection error:', error);
        reconnectTimeout = setTimeout(connect, 3000);
      }
    };

    connect();

    return () => {
      if (ws) {
        ws.onclose = null; // Prevent reconnect on cleanup
        ws.close();
      }
      clearTimeout(reconnectTimeout);
    };
  }, []);

  const isOverlay = variant === 'overlay';

  const liveSwitchChecked = liveToggleInfo?.live_refresh_enabled ?? false;

  useEffect(() => {
    if (!isOverlay) return;
    const el = contentRef.current;
    if (!el) return;

    const update = () => {
      const height = el.clientHeight;
      const SECTION_HEADER = 36;
      const FOOTER = 36;
      const ITEM_H = 72;
      const available = Math.max(0, height - SECTION_HEADER - FOOTER);
      const maxItems = Math.max(4, Math.floor(available / ITEM_H));
      setMaxVisiblePerSection(maxItems);
    };

    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, [isOverlay]);

  if (loading && allArriving.length === 0 && allDeparting.length === 0) {
    if (isOverlay) return null;
    return (
      <Card className="h-full">
        <CardHeader className="pb-2">
          <CardTitle className="text-lg font-medium flex items-center gap-2">
            <Train className="h-5 w-5" />
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
    <Card className={cn(
      "h-full flex flex-col shadow-sm transition-all duration-200",
      isOverlay ? "bg-black/40 backdrop-blur-md border-white/10 text-white shadow-2xl rounded-xl" : ""
    )}>
      <CardHeader className={cn("pb-2", isOverlay ? "py-2 px-3 border-b border-white/10" : "border-b")}>
        <div className="flex items-center justify-between gap-3 w-full">
          <div className="flex items-center gap-3">
            <CardTitle className={cn("text-lg font-bold flex items-center gap-2 whitespace-nowrap", isOverlay ? "text-base" : "")}>
              <Train className={cn("h-4 w-4", isOverlay ? "text-white/80" : "text-primary")} />
              {isOverlay ? "Train Schedule" : "Ongoing & Upcoming Trains"}
              <ArrivalHistoryModal searchMode overlay={isOverlay} />
            </CardTitle>
            {/* {canToggleLive && (
              <div className="flex items-center rounded-full border border-border p-1 bg-muted/80">
                <Switch
                  checked={liveSwitchChecked}
                  onCheckedChange={(value) => void handleLiveToggleChange(value)}
                  disabled={!canToggleLive || liveToggleLoading || !liveToggleInfo}
                  aria-label="Toggle live train refresh"
                />
              </div>
            )} */}
          </div>
          <span className={cn(
            "text-xs font-mono opacity-50 whitespace-nowrap",
            isOverlay ? "text-white/60" : "text-muted-foreground"
          )}>
            {lastUpdated}
          </span>
        </div>
        {/* {liveToggleInfo && (
          <div className="mt-1 flex flex-wrap items-center gap-2 text-[10px] text-muted-foreground">
            <Badge variant="outline" className={cn("text-[10px] font-bold uppercase tracking-wider", isOverlay ? "border-white/30 text-white/80" : "")}>
              {liveStatusLabel}
            </Badge>
            <span>{liveFetchLabel}</span>
            {liveUpdatedLabel && (
              <span className="text-white/60">
                {liveUpdatedLabel}
                {liveToggleInfo.last_updated_by ? ` by ${liveToggleInfo.last_updated_by}` : ""}
              </span>
            )}
          </div>
        )} */}
        <div className="mt-1">
          <span className={cn(
            "px-2 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider border",
            isOverlay
              ? "bg-orange-500/20 text-orange-100 border-orange-500/30 shadow-[0_0_10px_rgba(249,115,22,0.2)]"
              : "bg-orange-50 text-orange-700 border-orange-200"
          )}>
            Total Footfall: {totalCount.toLocaleString()}
          </span>
        </div>
      </CardHeader>
      <CardContent ref={contentRef} className={cn("flex-1 p-0 min-h-0", isOverlay ? "text-sm" : "")}>
        <div className={cn("grid grid-cols-1 h-full divide-y", isOverlay ? "divide-white/10" : "md:grid-cols-2 md:divide-y-0 md:divide-x")}>
          
          {/* Arriving Section */}
          <TrainSection 
            title="Arriving" 
            count={allArriving.length} 
            items={arriving} 
            allItems={allArriving} 
            type="arrival" 
            isOverlay={isOverlay}
            maxVisible={maxVisiblePerSection}
            icon={<ArrowDownLeft className="h-3 w-3" />}
            colorClass="text-emerald-400"
          />

          {/* Departing Section */}
          <TrainSection 
            title="Departing" 
            count={allDeparting.length} 
            items={departing} 
            allItems={allDeparting} 
            type="departure" 
            isOverlay={isOverlay}
            maxVisible={maxVisiblePerSection}
            icon={<ArrowUpRight className="h-3 w-3" />}
            colorClass="text-blue-400"
          />
        </div>
      </CardContent>
    </Card>
  );
}

function TrainSection({ title, count, items, allItems, type, isOverlay, icon, colorClass, maxVisible }: any) {
  const visibleItems = isOverlay && maxVisible ? items.slice(0, maxVisible) : items;
  const hiddenCount = Math.max(0, allItems.length - visibleItems.length);
  return (
    <div className="flex flex-col min-h-0 overflow-hidden">
      <div className={cn(
        "px-3 py-2 text-xs font-bold uppercase tracking-wider flex justify-between items-center sticky top-0 z-10",
        isOverlay ? "bg-white/5" : "bg-muted/20"
      )}>
        <span className={cn("flex items-center gap-1.5", isOverlay ? colorClass : "text-foreground")}>
          {icon} {title}
        </span>
        <Badge variant="outline" className={cn("text-[10px] h-4 px-1", isOverlay ? "border-white/20 text-white/60" : "")}>
          {count}
        </Badge>
      </div>
      
      {isOverlay ? (
        <div className="flex-1 overflow-hidden">
          <div className="divide-y divide-white/5">
            {visibleItems.length === 0 ? (
              <div className={cn("p-4 text-center text-xs italic opacity-50")}>
                No {title.toLowerCase()} trains
              </div>
            ) : (
              visibleItems.map((train: TrainSchedule, idx: number) => (
                <TrainItem key={`${train.train_number}-${type}-${idx}`} train={train} type={type} overlay={isOverlay} />
              ))
            )}
          </div>
        </div>
      ) : (
        <ScrollArea className="flex-1">
          <div className="divide-y divide-white/5">
            {items.length === 0 ? (
              <div className={cn("p-4 text-center text-xs italic opacity-50")}>
                No {title.toLowerCase()} trains
              </div>
            ) : (
              items.map((train: TrainSchedule, idx: number) => (
                <TrainItem key={`${train.train_number}-${type}-${idx}`} train={train} type={type} overlay={isOverlay} />
              ))
            )}
          </div>
        </ScrollArea>
      )}

      {/* View All Button */}
      {hiddenCount > 0 && (
        <div className={cn("p-2 border-t", isOverlay ? "border-white/10" : "border-border")}>
           <Dialog>
            <DialogTrigger asChild>
              <Button variant="ghost" size="sm" className={cn("w-full h-7 text-xs", isOverlay ? "hover:bg-white/10 text-white/70 hover:text-white" : "")}>
                {isOverlay ? `Show more (+${hiddenCount})` : `View All ${count} Trains`}
              </Button>
            </DialogTrigger>
            <DialogContent className={cn("max-w-2xl max-h-[80vh] flex flex-col", isOverlay ? "bg-zinc-900 text-white border-white/20" : "")}>
              <div className="flex items-center gap-2 mb-4">
                <span className={cn("font-bold text-lg", colorClass)}>{title} Trains</span>
                <Badge variant="secondary">{count}</Badge>
              </div>
              <div className="flex-1 overflow-y-auto max-h-[60vh] pr-2">
                <div className="grid grid-cols-1 gap-2 pb-10">
                  {allItems.map((train: TrainSchedule, idx: number) => (
                    <TrainItem key={`modal-${train.train_number}-${type}-${idx}`} train={train} type={type} overlay={isOverlay} />
                  ))}
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      )}
    </div>
  );
}

function TrainItem({ train, type, overlay }: { train: TrainSchedule; type: 'arrival' | 'departure'; overlay?: boolean }) {
  const isArrival = type === 'arrival';
  // Use scheduled time from API; fallback to empty string if missing
  const timeDisplay = isArrival 
    ? (train.arrival_scheduled || train.arrival_actual || "N/A") 
    : (train.departure_scheduled || train.departure_actual || "N/A");

  
  return (
    <div className={cn("px-4 py-3 transition-colors group border-b border-white/5 last:border-0", overlay ? "hover:bg-white/5" : "hover:bg-muted/30")}>
      <div className="flex justify-between items-start mb-1">
        <div className="flex flex-col gap-1 w-full">
          {/* Top Row: Train No & Time with Label */}
          <div className="flex justify-between items-center w-full">
            <span className="text-white/60 font-bold text-xs tracking-wide">{train.train_number}</span>
            
            <div className="flex items-center gap-2">
              <span className={cn("text-[10px] uppercase font-bold tracking-wider opacity-70", isArrival ? "text-emerald-400" : "text-blue-400")}>
                {isArrival ? "EXP ARRIVAL" : "EXP DEPARTURE"}
              </span>
              <span className={cn(
                "font-mono text-base font-black tracking-wider text-white",
              )}>
                {timeDisplay}
              </span>
            </div>
          </div>

          {/* Arrival History: shown below the EXP ARRIVAL field for arriving trains */}
          {isArrival && (
            <div className="flex justify-end">
              <ArrivalHistoryModal
                trainNumber={train.train_number}
                trainName={train.train_name}
                overlay={overlay}
              />
            </div>
          )}

          {/* Middle Row: Train Name (White & Bold) */}
          <div className={cn("text-sm font-black text-white truncate", overlay ? "text-white" : "text-foreground")} title={train.train_name}>
            {train.train_name}
          </div>
        </div>
      </div>
      
      {/* Bottom Status Row */}
      <div className="flex items-center gap-2 text-[10px] mt-1">
        {train.platform && (
          <span className={cn(
            "px-1.5 py-0.5 rounded text-[10px] font-bold border", 
            overlay ? "border-white/20 bg-white/10 text-white" : "border-border bg-muted/40 text-muted-foreground"
          )}>
            PF {train.platform}
          </span>
        )}

        {train.total_passengers !== undefined && train.total_passengers !== null && (
           <span className={cn(
            "px-1.5 py-0.5 rounded text-[10px] font-bold border flex items-center gap-1", 
            overlay ? "border-white/20 bg-blue-500/20 text-blue-200" : "border-blue-200 bg-blue-50 text-blue-700"
          )}>
            Total: {train.total_passengers}
          </span>
        )}
        
        {train.delay_status && (
          <span className="text-red-400 font-bold flex items-center gap-1 animate-pulse bg-red-400/10 px-1.5 py-0.5 rounded">
            {train.delay_status}
          </span>
        )}
      </div>
    </div>
  );
}
