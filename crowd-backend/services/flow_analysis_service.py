"""
Flow Analysis Service — Station-wide crowd flow detection & congestion advisory.

Periodically:
1. Snapshots zone people counts into a rolling window (deque per zone)
2. Computes delta_1min / delta_5min / flow_status for each zone
3. Detects congested FOB zones (density >= threshold, sustained)
4. Attributes congestion sources via adjacency graph walk
5. Stores the latest analysis result in-memory (read by zone_analytics broadcaster)

The result is merged into the zone_analytics WebSocket payload — no separate routes.
"""
import time
import logging
from collections import deque
from typing import Dict, List, Optional, Any, Tuple
logger = logging.getLogger(__name__)

# Module-level singleton (set by main.py lifespan, read by zone_analytics.py)
_flow_service_instance: Optional["FlowAnalysisService"] = None


def get_flow_service() -> Optional["FlowAnalysisService"]:
    """Get the singleton FlowAnalysisService instance (or None if not initialized)."""
    return _flow_service_instance


def set_flow_service(instance: "FlowAnalysisService") -> None:
    """Set the singleton FlowAnalysisService instance."""
    global _flow_service_instance
    _flow_service_instance = instance


class FlowAnalysisService:
    """Station-wide flow analysis with congestion detection and source attribution."""

    def __init__(self, settings):
        self._settings = settings

        # Rolling count history: {id: deque of (timestamp, people_count)}
        max_snapshots = int(settings.flow_history_window_seconds / settings.flow_snapshot_interval) + 1
        self._max_snapshots = max(10, max_snapshots)  # at least 10 snapshots
        self._zone_history: Dict[str, deque] = {}
        self._camera_history: Dict[str, deque] = {}  # per-camera history for micro flow

        # Per-station congestion persistence: {station_id: {zone_id: first_congested_ts}}
        self._congestion_start: Dict[str, Dict[str, float]] = {}

        # Per-station advisory cooldown: {station_id: last_advisory_ts}
        self._last_advisory_time: Dict[str, float] = {}

        # Latest analysis result per station (read by zone_analytics)
        # {station_id: {"zone_deltas": {...}, "congestion": {...} or None}}
        self._latest: Dict[str, Dict[str, Any]] = {}

        # Zone adjacency graph cache: {zone_id: [adjacent_zone_ids]}
        self._adjacency_graph: Dict[str, List[str]] = {}
        self._adjacency_loaded_at: float = 0
        self._adjacency_ttl: float = 300  # refresh every 5 min

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run_cycle(self) -> None:
        """Main cycle — called every N seconds from the lifespan task.

        For each station:
        1. Snapshot current zone counts
        2. Compute deltas + flow_status
        3. Detect congestion + attribute sources
        4. Store result for the zone_analytics broadcaster to read
        """
        from services.zone_analytics import get_zone_analytics

        # Refresh adjacency graph if stale
        await self._refresh_adjacency_graph()

        for station_id in await self._get_station_ids():
            try:
                await self._analyze_station(station_id)
            except Exception:
                logger.exception("Flow analysis failed for %s", station_id)

    def get_latest(self, station_id: str) -> Optional[Dict[str, Any]]:
        """Return the latest analysis result for a station (called by zone_analytics)."""
        return self._latest.get(station_id)

    # ------------------------------------------------------------------
    # Internal — station analysis
    # ------------------------------------------------------------------

    async def _analyze_station(self, station_id: str) -> None:
        from services.zone_analytics import get_zone_analytics

        zones_data = await get_zone_analytics(station_id=station_id)
        if not zones_data or not zones_data.get("zones"):
            return

        now = time.time()
        zones = zones_data["zones"]

        self._snapshot_counts(zones, now)
        zone_deltas = self._compute_zone_deltas(zones, now)
        camera_deltas = self._compute_camera_deltas(zones, now)
        congestion = self._detect_congestion(zones, zone_deltas, station_id, now)

        self._latest[station_id] = {
            "zone_deltas": zone_deltas,
            "camera_deltas": camera_deltas,
            "congestion": congestion,
        }

    def _snapshot_counts(self, zones: List[Dict], now: float) -> None:
        """Record current zone and per-camera people counts into rolling history."""
        for z in zones:
            zone_id = z["zone_id"]
            count = z.get("people_count", 0)
            if zone_id not in self._zone_history:
                self._zone_history[zone_id] = deque(maxlen=self._max_snapshots)
            self._zone_history[zone_id].append((now, count))

            for cam in z.get("cameras", []):
                cam_id = cam.get("camera_id") if isinstance(cam, dict) else cam
                cam_count = cam.get("people_count", 0) if isinstance(cam, dict) else 0
                if cam_id not in self._camera_history:
                    self._camera_history[cam_id] = deque(maxlen=self._max_snapshots)
                self._camera_history[cam_id].append((now, cam_count))

    def _compute_zone_deltas(self, zones: List[Dict], now: float) -> Dict[str, Dict]:
        zone_deltas = {}
        for z in zones:
            zone_id = z["zone_id"]
            d1 = self._compute_delta(zone_id, now, 60)
            d5 = self._compute_delta(zone_id, now, 300)
            zone_deltas[zone_id] = {
                "delta_1min": d1,
                "delta_5min": d5,
                "flow_status": self._classify_flow(d5),
            }
        return zone_deltas

    def _compute_camera_deltas(self, zones: List[Dict], now: float) -> Dict[str, Dict]:
        camera_deltas = {}
        for z in zones:
            for cam in z.get("cameras", []):
                cam_id = cam.get("camera_id") if isinstance(cam, dict) else cam
                d1 = self._compute_delta(cam_id, now, 60, self._camera_history)
                d5 = self._compute_delta(cam_id, now, 300, self._camera_history)
                camera_deltas[cam_id] = {
                    "delta_1min": d1,
                    "delta_5min": d5,
                    "flow_status": self._classify_flow(d5),
                }
        return camera_deltas

    # ------------------------------------------------------------------
    # Delta computation
    # ------------------------------------------------------------------

    def _compute_delta(self, entity_id: str, now: float, window_sec: float,
                       history_store: Optional[Dict] = None) -> int:
        """Compute people count change over the given window.

        Args:
            entity_id: zone_id or camera_id
            history_store: Which history dict to use. Defaults to _zone_history.
        """
        store = history_store if history_store is not None else self._zone_history
        history = store.get(entity_id)
        if not history or len(history) < 2:
            return 0

        current_count = history[-1][1]
        target_ts = now - window_sec

        # Find the snapshot closest to target_ts (but not newer than it)
        past_count = None
        for ts, count in history:
            if ts <= target_ts:
                past_count = count
            else:
                break

        if past_count is None:
            # Window hasn't filled yet — use oldest snapshot
            past_count = history[0][1]

        return current_count - past_count

    def _classify_flow(self, delta_5min: int) -> str:
        """Classify flow status from 5-minute delta."""
        filling_threshold = self._settings.flow_filling_threshold
        emptying_threshold = self._settings.flow_emptying_threshold
        if delta_5min >= filling_threshold:
            return "filling"
        elif delta_5min <= -emptying_threshold:
            return "emptying"
        return "stable"

    # ------------------------------------------------------------------
    # Congestion detection + source attribution
    # ------------------------------------------------------------------

    def _detect_congestion(
        self,
        zones: List[Dict],
        zone_deltas: Dict[str, Dict],
        station_id: str,
        now: float,
    ) -> Optional[Dict[str, Any]]:
        """Detect FOB congestion and attribute sources from upstream platforms."""
        density_threshold = self._settings.flow_congestion_density_threshold
        alt_threshold = self._settings.flow_alternative_density_threshold

        fob_zones = [z for z in zones if z.get("zone_type") == "FOB"]
        if not fob_zones:
            return None

        congested = [z for z in fob_zones if z.get("density_avg", 0) >= density_threshold]
        alternatives = [z for z in fob_zones if z.get("density_avg", 0) < alt_threshold]

        if not congested:
            self._congestion_start.pop(station_id, None)
            return None

        # --- Persistence gate ---
        station_state = self._congestion_start.setdefault(station_id, {})
        congested_ids = {z["zone_id"] for z in congested}

        # Remove zones that recovered
        for zone_id in list(station_state.keys()):
            if zone_id not in congested_ids:
                del station_state[zone_id]

        # Mark new congestions
        for z in congested:
            if z["zone_id"] not in station_state:
                station_state[z["zone_id"]] = now

        # Filter to sustained congestion
        persist_threshold = self._settings.flow_congestion_min_persist_seconds
        sustained = [
            z for z in congested
            if (now - station_state.get(z["zone_id"], now)) >= persist_threshold
        ]

        if not sustained:
            return None

        # --- Cooldown gate ---
        cooldown = self._settings.flow_congestion_cooldown_seconds
        last_time = self._last_advisory_time.get(station_id, 0)
        if (now - last_time) < cooldown:
            return None

        self._last_advisory_time[station_id] = now

        # --- Build congestion block with source attribution ---
        all_congested = len(congested) == len(fob_zones)

        congested_details = []
        for z in sustained:
            sources = self._attribute_sources(z["zone_id"], zone_deltas, zones)
            congested_details.append({
                "zone_id": z["zone_id"],
                "zone_name": z.get("zone_name", z["zone_id"]),
                "density_avg": round(z.get("density_avg", 0), 2),
                "risk_level": z.get("risk_level", "LOW"),
                "people_count": z.get("people_count", 0),
                "sources": sources,
            })

        alternative_details = [
            {
                "zone_id": z["zone_id"],
                "zone_name": z.get("zone_name", z["zone_id"]),
                "density_avg": round(z.get("density_avg", 0), 2),
            }
            for z in alternatives
        ]

        advisory_text = self._build_advisory_text(congested_details, alternative_details, all_congested)

        logger.info(
            f"[FlowAdvisory] {station_id}: {len(sustained)} congested zone(s), "
            f"{len(alternatives)} alternative(s), all_congested={all_congested}"
        )

        return {
            "active": True,
            "congested_zones": congested_details,
            "alternative_zones": alternative_details,
            "all_congested": all_congested,
            "advisory_text": advisory_text,
        }

    def _find_emptying_platform_candidates(
        self,
        congested_zone_id: str,
        zone_deltas: Dict[str, Dict],
        zone_type_map: Dict[str, str],
    ) -> List[Tuple[str, float]]:
        """BFS the adjacency graph for upstream PLATFORM zones with negative deltas."""
        max_hops = self._settings.flow_adjacency_max_hops
        min_threshold = self._settings.flow_delta_min_threshold

        visited = set()
        queue: List[Tuple[str, int]] = [(congested_zone_id, 0)]
        platform_candidates = []

        while queue:
            current_id, depth = queue.pop(0)
            if current_id in visited:
                continue
            visited.add(current_id)

            if current_id != congested_zone_id and zone_type_map.get(current_id) == "PLATFORM":
                d5 = zone_deltas.get(current_id, {}).get("delta_5min", 0)
                if d5 < -min_threshold:
                    platform_candidates.append((current_id, abs(d5)))

            if depth < max_hops:
                for adj_id in self._adjacency_graph.get(current_id, []):
                    if adj_id not in visited:
                        queue.append((adj_id, depth + 1))

        return platform_candidates

    def _attribute_sources(
        self,
        congested_zone_id: str,
        zone_deltas: Dict[str, Dict],
        zones: List[Dict],
    ) -> List[Dict[str, Any]]:
        """Walk adjacency graph to find upstream PLATFORM zones with negative deltas."""
        zone_type_map = {z["zone_id"]: z.get("zone_type", "") for z in zones}
        zone_name_map = {z["zone_id"]: z.get("zone_name", z["zone_id"]) for z in zones}

        platform_candidates = self._find_emptying_platform_candidates(
            congested_zone_id, zone_deltas, zone_type_map
        )
        if not platform_candidates:
            return []

        total_delta = sum(d for _, d in platform_candidates)
        sources = []
        for zone_id, delta in sorted(platform_candidates, key=lambda x: -x[1]):
            pct = round((delta / total_delta) * 100) if total_delta > 0 else 0
            sources.append({
                "zone_id": zone_id,
                "zone_name": zone_name_map.get(zone_id, zone_id),
                "contribution_pct": pct,
                "delta_5min": -delta,  # negative = emptying
            })

        return sources

    # ------------------------------------------------------------------
    # Adjacency graph
    # ------------------------------------------------------------------

    async def _refresh_adjacency_graph(self) -> None:
        """Refresh adjacency graph from DB if stale."""
        now = time.time()
        if (now - self._adjacency_loaded_at) < self._adjacency_ttl:
            return

        try:
            from db.mongodb import get_database
            db = get_database()
            if db is None:
                return

            cursor = db.zones.find(
                {"is_active": True, "adjacent_zones": {"$exists": True, "$ne": []}},
                {"zone_id": 1, "adjacent_zones": 1}
            )
            docs = await cursor.to_list(length=500)

            graph = {}
            for doc in docs:
                graph[doc["zone_id"]] = doc.get("adjacent_zones", [])

            self._adjacency_graph = graph
            self._adjacency_loaded_at = now
            if not graph:
                logger.warning(
                    "[FlowAnalysis] Adjacency graph is empty — no zones have adjacent_zones configured. "
                    "Flow source attribution will not work until adjacency is set via PUT /zones/{zone_id}/adjacency"
                )
            else:
                logger.debug(f"Adjacency graph refreshed: {len(graph)} zones with adjacency data")
        except Exception:
            logger.exception("Failed to refresh adjacency graph")

    async def _get_station_ids(self) -> List[str]:
        """Get active station IDs from DB."""
        try:
            from db.mongodb import get_database
            db = get_database()
            if db is None:
                return ["HYB", "KZJ"]  # fallback

            station_ids = await db.zones.distinct("station_id", {"is_active": True})
            return station_ids if station_ids else ["HYB", "KZJ"]
        except Exception:
            return ["HYB", "KZJ"]

    # ------------------------------------------------------------------
    # Advisory text
    # ------------------------------------------------------------------

    @staticmethod
    def _build_advisory_text(
        congested: List[Dict],
        alternatives: List[Dict],
        all_congested: bool,
    ) -> str:
        if all_congested:
            return "All FOBs are congested. Activate crowd control measures."

        names = ", ".join(z["zone_name"] for z in congested)

        # Add source info if available
        source_parts = []
        for z in congested:
            if z.get("sources"):
                top_source = z["sources"][0]
                source_parts.append(f"{z['zone_name']} (mainly from {top_source['zone_name']})")

        if source_parts:
            congested_text = ", ".join(source_parts)
        else:
            congested_text = names

        if alternatives:
            alt_names = ", ".join(z["zone_name"] for z in alternatives)
            return f"{congested_text} congested. Use {alt_names} instead."
        return f"{congested_text} congested. No clear alternatives available."
