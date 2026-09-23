"""
WebSocket connection manager for real-time analytics push
Supports room-based subscriptions (per-camera or all-cameras)
"""
from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder
from typing import Dict, List, Any
from datetime import UTC, datetime
import asyncio
import logging
from config.config import get_settings
logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    WebSocket connection manager with room subscriptions

    Architecture:
    - Camera-specific rooms: {camera_id: [websocket1, websocket2, ...]}
    - Global room: [websocket1, websocket2, ...] (subscribes to all cameras)
    - Zone rooms: {station_id: [websocket1, websocket2, ...]} (for SVG rendering)
    - Global zone room: [websocket1, ...] (subscribes to all zone updates)
    - Train schedule subscribers: [websocket1, ...] (for upcoming trains)
    - Auto-cleanup of dead connections
    - Concurrent broadcast to all subscribers
    """

    def __init__(self):
        self.settings = get_settings()
        self.verbose_logging = bool(getattr(self.settings, "websocket_verbose_logging", False))

        # Camera-specific subscribers: {camera_id: [websocket1, websocket2, ...]}
        self.active_connections: Dict[str, List[WebSocket]] = {}

        # Global subscribers (receive updates from all cameras)
        self.global_subscribers: List[WebSocket] = []

        # Zone/station-specific subscribers: {station_id: [websocket1, websocket2, ...]}
        self.zone_connections: Dict[str, List[WebSocket]] = {}

        # Global zone subscribers (receive zone updates from all stations)
        self.global_zone_subscribers: List[WebSocket] = []

        # Train schedule subscribers
        self.train_subscribers: List[WebSocket] = []

        # Statistics
        self.stats = {
            "total_connections": 0,
            "messages_sent": 0,
            "connection_errors": 0
        }

    def _debug(self, message: str):
        if self.verbose_logging:
            logger.info(message)


    async def connect(self, websocket: WebSocket, camera_id: str = None):
        """
        Connect WebSocket client to camera room or global room

        Args:
            websocket: WebSocket connection
            camera_id: Camera ID to subscribe to (None = subscribe to all cameras)
        """
        await websocket.accept()

        if camera_id:
            # Subscribe to specific camera
            if camera_id not in self.active_connections:
                self.active_connections[camera_id] = []

            self.active_connections[camera_id].append(websocket)
            self.stats["total_connections"] += 1

            logger.info(f"[WebSocket] Client connected to camera: {camera_id} "
                        f"(Total: {len(self.active_connections[camera_id])} for this camera)")
        else:
            # Subscribe to all cameras
            self.global_subscribers.append(websocket)
            self.stats["total_connections"] += 1

            logger.info(f"[WebSocket] Client connected to all cameras "
                        f"(Total global subscribers: {len(self.global_subscribers)})")


    async def disconnect(self, websocket: WebSocket, camera_id: str = None):
        """
        Disconnect WebSocket client

        Args:
            websocket: WebSocket connection
            camera_id: Camera ID (None = global room)
        """
        if camera_id:
            if camera_id in self.active_connections:
                if websocket in self.active_connections[camera_id]:
                    self.active_connections[camera_id].remove(websocket)
                    self.stats["total_connections"] -= 1

                    logger.info(f"[WebSocket] Client disconnected from camera: {camera_id} "
                          f"(Remaining: {len(self.active_connections[camera_id])})")

                # Clean up empty camera rooms
                if len(self.active_connections[camera_id]) == 0:
                    del self.active_connections[camera_id]
        else:
            if websocket in self.global_subscribers:
                self.global_subscribers.remove(websocket)
                self.stats["total_connections"] -= 1

                logger.info(f"[WebSocket] Client disconnected from all cameras "
                      f"(Remaining global: {len(self.global_subscribers)})")


    async def broadcast_analytics(self, camera_id: str, stream_id: str, analytics_data: Dict[str, Any]):
        """
        Broadcast analytics data to all subscribed clients

        Args:
            camera_id: Camera ID (e.g., "camera_entry_stair")
            stream_id: Stream ID (UUID for frontend tracking)
            analytics_data: Analytics document (simplified, JSON-safe)

        Flow:
        1. Send to camera-specific subscribers
        2. Send to global subscribers
        3. Remove dead connections
        """
        # Debug: Log broadcast attempt
        camera_subs = len(self.active_connections.get(camera_id, []))
        global_subs = len(self.global_subscribers)
        total_subs = camera_subs + global_subs

        if total_subs > 0:
            self._debug(f"[WebSocket] Broadcasting to {total_subs} subs (camera:{camera_subs}, global:{global_subs})")

        message = {
            "type": "analytics",
            "camera_id": camera_id,
            "stream_id": stream_id,
            "timestamp": analytics_data.get("timestamp"),
            "data": analytics_data
        }

        # Send to camera-specific subscribers
        if camera_id in self.active_connections:
            await self._send_to_connections(
                self.active_connections[camera_id],
                message,
                f"camera-{camera_id}"
            )

        # Send to global subscribers
        await self._send_to_connections(
            self.global_subscribers,
            message,
            "global"
        )


    async def broadcast_alert(self, camera_id: str, stream_id: str, alert_data: Dict[str, Any]):
        """
        Broadcast alert to all subscribed clients

        Args:
            camera_id: Camera ID
            stream_id: Stream ID (UUID for frontend tracking)
            alert_data: Alert document (with timestamp field)

        Flow: Same as analytics broadcast
        """
        message = {
            "type": "alert",
            "camera_id": camera_id,
            "stream_id": stream_id,
            "data": alert_data,
            "timestamp": alert_data.get("timestamp")
        }

        # Send to camera-specific subscribers
        if camera_id in self.active_connections:
            await self._send_to_connections(
                self.active_connections[camera_id],
                message,
                f"camera-{camera_id}"
            )

        # Send to global subscribers
        await self._send_to_connections(
            self.global_subscribers,
            message,
            "global"
        )


    async def broadcast_camera_update(self, camera_id: str, event_type: str, camera_data: Dict[str, Any]):
        """
        Broadcast camera configuration/status update to global subscribers

        Args:
            camera_id: Camera Identifier
            event_type: 'created', 'updated', 'started', 'stopped', 'deleted'
            camera_data: Current camera data/status
        """
        message = {
            "type": "camera_update",
            "event": event_type,
            "camera_id": camera_id,
            "data": jsonable_encoder(camera_data),
            "timestamp": datetime.now(UTC).isoformat()
        }
        
        # Updates typically go to global dashboard monitoring all cameras
        await self._send_to_connections(
            self.global_subscribers,
            message,
            "global-updates"
        )


    async def _send_to_connections(
        self,
        connections: List[WebSocket],
        message: Dict,
        room_name: str
    ):
        """
        Send message to list of WebSocket connections

        Args:
            connections: List of WebSocket connections
            message: Message to send
            room_name: Room name (for logging)

        Note: Dead connections are tracked for removal
        """
        if not connections:
            return

        dead_connections = []

        # Send to all connections concurrently
        tasks = []
        for websocket in connections:
            tasks.append(self._send_message(websocket, message, dead_connections))

        # Wait for all sends to complete
        await asyncio.gather(*tasks, return_exceptions=True)

        # Calculate successful sends BEFORE removing dead connections
        # (len(connections) still includes dead ones at this point conceptually,
        # but dead_connections were appended during send, so subtract them)
        successful_sends = len(connections) - len(dead_connections)

        # Remove dead connections
        for websocket in dead_connections:
            if websocket in connections:
                connections.remove(websocket)
                self.stats["total_connections"] -= 1

        if dead_connections:
            self._debug(f"[WebSocket] Removed {len(dead_connections)} dead connections from {room_name}")

        # Update stats with correct count
        self.stats["messages_sent"] += successful_sends


    async def _send_message(
        self,
        websocket: WebSocket,
        message: Dict,
        dead_connections: List[WebSocket]
    ):
        """
        Send message to single WebSocket connection

        Args:
            websocket: WebSocket connection
            message: Message to send
            dead_connections: List to append to if connection is dead
        """
        try:
            await websocket.send_json(message)
            self._debug("[WebSocket] message sent")
        except Exception:
            # Connection is dead - log the actual error
            logger.exception("[WebSocket] ✗ Send failed")
            dead_connections.append(websocket)
            self.stats["connection_errors"] += 1


    def get_connection_count(self, camera_id: str = None) -> int:
        """
        Get number of connections for camera or all cameras

        Args:
            camera_id: Camera ID (None = all cameras)

        Returns:
            Connection count
        """
        if camera_id:
            return len(self.active_connections.get(camera_id, []))
        else:
            total = len(self.global_subscribers)
            for connections in self.active_connections.values():
                total += len(connections)
            return total


    def get_stats(self) -> Dict[str, Any]:
        """
        Get WebSocket statistics

        Returns:
            Statistics dictionary
        """
        return {
            **self.stats,
            "active_cameras": len(self.active_connections),
            "global_subscribers": len(self.global_subscribers),
            "total_active_connections": self.get_connection_count()
        }


    def get_camera_subscribers(self, camera_id: str) -> int:
        """
        Get number of subscribers for specific camera

        Args:
            camera_id: Camera ID

        Returns:
            Subscriber count (includes global subscribers)
        """
        camera_specific = len(self.active_connections.get(camera_id, []))
        global_subs = len(self.global_subscribers)
        return camera_specific + global_subs


    # =========================================================================
    # ZONE WEBSOCKET METHODS (for SVG rendering)
    # =========================================================================

    async def connect_zone(self, websocket: WebSocket, station_id: str = None):
        """
        Connect WebSocket client to zone updates

        Args:
            websocket: WebSocket connection
            station_id: Station ID to subscribe to (None = all stations)
        """
        await websocket.accept()

        if station_id:
            # Subscribe to specific station's zones
            if station_id not in self.zone_connections:
                self.zone_connections[station_id] = []

            self.zone_connections[station_id].append(websocket)
            self.stats["total_connections"] += 1

            logger.info(f"[WebSocket] Client connected to zone updates for station: {station_id} "
                        f"(Total: {len(self.zone_connections[station_id])} for this station)")
        else:
            # Subscribe to all zone updates
            self.global_zone_subscribers.append(websocket)
            self.stats["total_connections"] += 1

            logger.info(f"[WebSocket] Client connected to all zone updates "
                        f"(Total global zone subscribers: {len(self.global_zone_subscribers)})")


    async def disconnect_zone(self, websocket: WebSocket, station_id: str = None):
        """
        Disconnect WebSocket client from zone updates

        Args:
            websocket: WebSocket connection
            station_id: Station ID (None = global room)
        """
        if station_id:
            if station_id in self.zone_connections:
                if websocket in self.zone_connections[station_id]:
                    self.zone_connections[station_id].remove(websocket)
                    self.stats["total_connections"] -= 1

                    logger.info(f"[WebSocket] Client disconnected from zone updates for station: {station_id} "
                                f"(Remaining: {len(self.zone_connections[station_id])})")

                # Clean up empty station rooms
                if len(self.zone_connections[station_id]) == 0:
                    del self.zone_connections[station_id]
        else:
            if websocket in self.global_zone_subscribers:
                self.global_zone_subscribers.remove(websocket)
                self.stats["total_connections"] -= 1

                logger.info(f"[WebSocket] Client disconnected from all zone updates "
                      f"(Remaining global zone: {len(self.global_zone_subscribers)})")


    async def broadcast_zone_analytics(self, station_id: str, zone_data: Dict[str, Any]):
        """
        Broadcast zone analytics to subscribed clients

        Args:
            station_id: Station ID
            zone_data: Zone analytics data (timestamp, zones list)

        Flow:
        1. Send to station-specific zone subscribers
        2. Send to global zone subscribers
        3. Remove dead connections
        """
        station_subs = len(self.zone_connections.get(station_id, []))
        global_zone_subs = len(self.global_zone_subscribers)
        total_subs = station_subs + global_zone_subs

        if total_subs > 0:
            self._debug(f"[WebSocket] Broadcasting zone analytics to {total_subs} subs "
                  f"(station:{station_subs}, global_zone:{global_zone_subs})")

        message = {
            "type": "zone_analytics",
            "station_id": station_id,
            "timestamp": zone_data.get("timestamp"),
            "zones": zone_data.get("zones", []),
        }
        # Include congestion block when present (from flow analysis)
        if "congestion" in zone_data:
            message["congestion"] = zone_data["congestion"]

        # Send to station-specific zone subscribers
        if station_id in self.zone_connections:
            await self._send_to_connections(
                self.zone_connections[station_id],
                message,
                f"zone-{station_id}"
            )

        # Send to global zone subscribers
        await self._send_to_connections(
            self.global_zone_subscribers,
            message,
            "global-zone"
        )


    def get_zone_subscribers(self, station_id: str = None) -> int:
        """
        Get number of zone subscribers

        Args:
            station_id: Station ID (None = all)

        Returns:
            Subscriber count
        """
        if station_id:
            return len(self.zone_connections.get(station_id, [])) + len(self.global_zone_subscribers)
        else:
            total = len(self.global_zone_subscribers)
            for connections in self.zone_connections.values():
                total += len(connections)
            return total


    # =========================================================================
    # TRAIN SCHEDULE WEBSOCKET METHODS
    # =========================================================================

    async def connect_trains(self, websocket: WebSocket):
        """
        Connect WebSocket client to train schedule updates

        Args:
            websocket: WebSocket connection
        """
        await websocket.accept()
        self.train_subscribers.append(websocket)
        self.stats["total_connections"] += 1

        logger.info(f"[WebSocket] Client connected to train updates "
                    f"(Total train subscribers: {len(self.train_subscribers)})")


    async def disconnect_trains(self, websocket: WebSocket):
        """
        Disconnect WebSocket client from train schedule updates

        Args:
            websocket: WebSocket connection
        """
        if websocket in self.train_subscribers:
            self.train_subscribers.remove(websocket)
            self.stats["total_connections"] -= 1

            logger.info(f"[WebSocket] Client disconnected from train updates "
                        f"(Remaining train subscribers: {len(self.train_subscribers)})")


    async def broadcast_train_schedule_update(self, event: str, data: Dict[str, Any]):
        """
        Broadcast train schedule update to subscribers

        Args:
            event: Event type ('upcoming_update', 'schedule_uploaded', 'schedule_changed')
            data: Event-specific data (upcoming trains or upload info)
        """
        if not self.train_subscribers:
            return

        message = {
            "type": "train_schedule",
            "event": event,
            "timestamp": datetime.now(UTC).isoformat(),
            "data": data
        }

        logger.info(f"[WebSocket] Broadcasting train {event} to {len(self.train_subscribers)} subscribers")

        await self._send_to_connections(
            self.train_subscribers,
            message,
            "trains"
        )


    def get_train_subscribers(self) -> int:
        """
        Get number of train schedule subscribers

        Returns:
            Subscriber count
        """
        return len(self.train_subscribers)


# Global singleton
_connection_manager = None


def get_connection_manager() -> ConnectionManager:
    """
    Get singleton ConnectionManager instance

    Returns:
        ConnectionManager instance
    """
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = ConnectionManager()
        logger.info("[WebSocket] ConnectionManager initialized")
    return _connection_manager

