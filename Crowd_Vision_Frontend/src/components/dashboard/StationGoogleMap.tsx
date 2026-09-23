
import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { GoogleMap, InfoWindow, Marker, Polygon, useJsApiLoader } from "@react-google-maps/api";
import MicSvg from "@/assets/mic.svg";
import { STATION_BOUNDS, STATION_CENTER, STATION_ZONES } from "@/lib/stationMapGeo";
import { useTheme } from "@/context/ThemeContext";


// Minimal shape of the live tracking-user records already fetched on the
// Dashboard (see Dashboard.tsx `TrackingUserRecord`). Kept structural (not
// imported) so this component has no dependency on the page module.
export interface StationMapUser {
  name?: string;
  phoneNumber: string;
  coordinates: {
    latitude: number;
    longitude: number;
  };
  timestamp?: string;
}

interface StationGoogleMapProps {
  trackingUsers: StationMapUser[];
  isActive: boolean;
  className?: string;
}

const MAP_CONTAINER_STYLE: React.CSSProperties = {
  width: "100%",
  height: "100%",
};

// Moderately dark, professional theme — lighter than pure black so the
// neon zone outlines and live markers stay readable without the map
// itself feeling like a void.
const DARK_MAP_STYLES: google.maps.MapTypeStyle[] = [
  {
    elementType: "geometry",
    stylers: [{ color: "#1b2436" }],
  },
  {
    elementType: "labels.text.stroke",
    stylers: [{ color: "#1b2436" }],
  },
  {
    elementType: "labels.text.fill",
    stylers: [{ color: "#93a3c2" }],
  },
  {
    featureType: "administrative",
    elementType: "geometry",
    stylers: [{ color: "#2a3550" }],
  },
  {
    featureType: "poi",
    stylers: [{ visibility: "off" }],
  },
  {
    featureType: "road",
    elementType: "geometry",
    stylers: [{ color: "#26314a" }],
  },
  {
    featureType: "road",
    elementType: "labels.text.fill",
    stylers: [{ color: "#7d8cad" }],
  },
  {
    featureType: "road.arterial",
    elementType: "geometry",
    stylers: [{ color: "#2c3a58" }],
  },
  {
    featureType: "road.highway",
    elementType: "geometry",
    stylers: [{ color: "#34456a" }],
  },
  {
    featureType: "transit",
    elementType: "geometry",
    stylers: [{ color: "#26314a" }],
  },
  {
    featureType: "water",
    elementType: "geometry",
    stylers: [{ color: "#101826" }],
  },
  {
    featureType: "landscape",
    elementType: "geometry",
    stylers: [{ color: "#182236" }],
  },
];

const LIGHT_MAP_STYLES: google.maps.MapTypeStyle[] = [
  {
    elementType: "geometry",
    stylers: [{ color: "#f5f7fa" }],
  },
  {
    elementType: "labels.text.fill",
    stylers: [{ color: "#5f6b7a" }],
  },
  {
    elementType: "labels.text.stroke",
    stylers: [{ color: "#f5f7fa" }],
  },
  {
    featureType: "administrative",
    elementType: "geometry",
    stylers: [{ color: "#d8dee8" }],
  },
  {
    featureType: "poi",
    stylers: [{ visibility: "off" }],
  },
  {
    featureType: "road",
    elementType: "geometry",
    stylers: [{ color: "#ffffff" }],
  },
  {
    featureType: "road",
    elementType: "labels.text.fill",
    stylers: [{ color: "#6b7280" }],
  },
  {
    featureType: "road.arterial",
    elementType: "geometry",
    stylers: [{ color: "#e9edf2" }],
  },
  {
    featureType: "road.highway",
    elementType: "geometry",
    stylers: [{ color: "#dfe4ea" }],
  },
  {
    featureType: "transit",
    elementType: "geometry",
    stylers: [{ color: "#e1e6ec" }],
  },
  {
    featureType: "water",
    elementType: "geometry",
    stylers: [{ color: "#cfe3f2" }],
  },
  {
    featureType: "landscape",
    elementType: "geometry",
    stylers: [{ color: "#f5f7fa" }],
  },
];

const USER_MARKER_ICON_SIZE = 44;
const FIT_BOUNDS_PADDING_PX = 48;

export function StationGoogleMap({
  trackingUsers,
  isActive,
  className,
}: StationGoogleMapProps) {
  const { theme } = useTheme();

  /*
   * Keep the map options object stable except for the theme-dependent styles.
   * The actual live theme update is handled with map.setOptions() below so
   * Google Maps updates without destroying/recreating the map instance.
   */
  const mapOptions = useMemo<google.maps.MapOptions>(
    () => ({
      styles: theme === "dark" ? DARK_MAP_STYLES : LIGHT_MAP_STYLES,
      disableDefaultUI: false,
      mapTypeControl: false,
      streetViewControl: false,
      fullscreenControl: false,
      clickableIcons: false,
      gestureHandling: "greedy",
      maxZoom: 21,
    }),
    [theme],
  );

  const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY as string | undefined;

  const { isLoaded, loadError } = useJsApiLoader({
    id: "station-google-map-script",
    googleMapsApiKey: apiKey || "",
  });

  const mapRef = useRef<google.maps.Map | null>(null);
  const hasCenteredOnUserRef = useRef(false);
  const hasFitStationBoundsRef = useRef(false);

  const [activeZoneId, setActiveZoneId] = useState<string | null>(null);
  const [activeUserPhone, setActiveUserPhone] = useState<string | null>(null);

  const validUsers = useMemo(
    () =>
      trackingUsers.filter(
        (user) =>
          Number.isFinite(user.coordinates?.latitude) &&
          Number.isFinite(user.coordinates?.longitude),
      ),
    [trackingUsers],
  );

  // Fits the map to the full station once as the initial view. Requires the
  // container to already have its real on-screen size — calling this while
  // the map is inside a `display: none` tab produces a wrong, unusable fit.
  const fitStationBounds = useCallback((map: google.maps.Map) => {
    const bounds = new google.maps.LatLngBounds(
      {
        lat: STATION_BOUNDS.south,
        lng: STATION_BOUNDS.west,
      },
      {
        lat: STATION_BOUNDS.north,
        lng: STATION_BOUNDS.east,
      },
    );

    map.fitBounds(bounds, FIT_BOUNDS_PADDING_PX);
    hasFitStationBoundsRef.current = true;
  }, []);

  const onLoad = useCallback(
    (map: google.maps.Map) => {
      mapRef.current = map;

      /*
       * Apply the current theme immediately when Google Maps finishes loading.
       * This covers the case where the theme effect ran before mapRef existed.
       */
      map.setOptions({
        styles: theme === "dark" ? DARK_MAP_STYLES : LIGHT_MAP_STYLES,
      });

      const container = map.getDiv();

      if (container.clientWidth > 0 && container.clientHeight > 0) {
        fitStationBounds(map);
      }

      // Otherwise the Map View tab isn't active yet (container is
      // `display: none`, so it has no real size to fit to) — deferred to the
      // `isActive` effect below, which runs once the tab becomes visible.
    },
    [fitStationBounds, theme],
  );

  const onUnmount = useCallback(() => {
    mapRef.current = null;
  }, []);

  /*
   * LIVE THEME UPDATE
   *
   * Do not remount GoogleMap when the application theme changes.
   * Google Maps keeps its own internal map instance, so update that instance
   * directly instead.
   */
  useEffect(() => {
    const map = mapRef.current;

    if (!map) return;

    map.setOptions({
      styles: theme === "dark" ? DARK_MAP_STYLES : LIGHT_MAP_STYLES,
    });

    /*
     * Force Google Maps to refresh its rendered tiles/styles immediately.
     * This is especially useful when the map is inside a tab/container.
     */
    google.maps.event.trigger(map, "resize");
  }, [theme]);

  const formatTimestamp = (timestamp?: string) => {
    if (!timestamp) return "-";

    const [date, time] = timestamp.split("T");

    if (!time) return date;

    return `${date}, ${time.split(".")[0]}`;
  };

  // Re-render tiles when returning to a container that was `display: none`
  // while the Layout tab was active, and perform the one-time station fit
  // if it couldn't run at load time for the same reason. Only ever fits
  // once, so a user's manual pan/zoom is never reset on later tab switches.
  useEffect(() => {
    if (!isActive || !mapRef.current) return;

    google.maps.event.trigger(mapRef.current, "resize");

    if (!hasFitStationBoundsRef.current) {
      fitStationBounds(mapRef.current);
    }
  }, [isActive, fitStationBounds]);

  // Center on the user's live location once, on first availability, without
  // disturbing the station-wide zoom level set by fitBounds above.
  useEffect(() => {
    if (hasCenteredOnUserRef.current || !mapRef.current) return;

    const first = validUsers[0];

    if (!first) return;

    mapRef.current.panTo({
      lat: first.coordinates.latitude,
      lng: first.coordinates.longitude,
    });

    hasCenteredOnUserRef.current = true;
  }, [validUsers]);

  const userMarkerIcon = useMemo(() => {
    if (!isLoaded) return undefined;

    return {
      url: MicSvg,
      scaledSize: new google.maps.Size(
        USER_MARKER_ICON_SIZE,
        USER_MARKER_ICON_SIZE,
      ),
      anchor: new google.maps.Point(
        USER_MARKER_ICON_SIZE / 2,
        USER_MARKER_ICON_SIZE,
      ),
    };
  }, [isLoaded]);

  if (!apiKey) {
    return (
      <div
        className={`flex items-center justify-center rounded-2xl border border-border/50 bg-background text-center p-8 ${
          className || ""
        }`}
      >
        <p className="text-sm text-muted-foreground max-w-sm">
          Google Maps API key is not configured. Set{" "}
          <code className="px-1 py-0.5 rounded bg-muted text-foreground">
            VITE_GOOGLE_MAPS_API_KEY
          </code>{" "}
          in your environment to enable Map View.
        </p>
      </div>
    );
  }

  if (loadError) {
    return (
      <div
        className={`flex items-center justify-center rounded-2xl border border-border/50 bg-background text-center p-8 ${
          className || ""
        }`}
      >
        <p className="text-sm text-destructive">
          Failed to load Google Maps. Please check your API key and network
          connection.
        </p>
      </div>
    );
  }

  if (!isLoaded) {
    return (
      <div
        className={`flex items-center justify-center rounded-2xl border border-border/50 bg-background ${
          className || ""
        }`}
      >
        <div className="h-9 w-9 rounded-full border-2 border-primary/30 border-t-primary animate-spin" />
      </div>
    );
  }

  return (
    <div
      className={`relative rounded-2xl overflow-hidden border border-border/50 ${
        className || ""
      }`}
    >
      <GoogleMap
        mapContainerStyle={MAP_CONTAINER_STYLE}
        center={STATION_CENTER}
        zoom={17}
        options={mapOptions}
        onLoad={onLoad}
        onUnmount={onUnmount}
      >
        {STATION_ZONES.map((zone) => (
          <Fragment key={zone.id}>
            {/* Outer glow pass — wide, low-opacity stroke simulates a neon bloom. */}
            <Polygon
              paths={zone.path}
              options={{
                strokeColor: zone.strokeColor,
                strokeOpacity: 0.35,
                strokeWeight: 9,
                fillOpacity: 0,
                clickable: false,
                zIndex: 1,
              }}
            />

            {/* Crisp inner line + subtle fill on top of the glow pass. Hover
                only — no permanent label, no click-to-pin. */}
            <Polygon
              paths={zone.path}
              options={{
                strokeColor: zone.strokeColor,
                strokeOpacity: 1,
                strokeWeight: 2.5,
                fillColor: zone.fillColor,
                fillOpacity: activeZoneId === zone.id ? 0.3 : 0.08,
                clickable: true,
                zIndex: 2,
              }}
              onMouseOver={() =>
                zone.type === "fob" && setActiveZoneId(zone.id)
              }
              onMouseOut={() =>
                setActiveZoneId((curr) =>
                  curr === zone.id ? null : curr,
                )
              }
            />
          </Fragment>
        ))}

        {activeZoneId &&
          (() => {
            const zone = STATION_ZONES.find(
              (z) => z.id === activeZoneId,
            );

            if (!zone || zone.type !== "fob") return null;

            return (
              <InfoWindow
                position={zone.center}
                options={{
                  disableAutoPan: true,
                  pixelOffset: new google.maps.Size(0, -12),
                }}
                onCloseClick={() => setActiveZoneId(null)}
              >
                <div
                  style={{
                    color:
                      theme === "dark" ? "#f5f7fb" : "#0b0f1a",
                    height: "20px",
                    fontSize: 12,
                    fontWeight: 600,
                    whiteSpace: "nowrap",
                    alignItems: "center",
                  }}
                >
                  {zone.name}
                </div>
              </InfoWindow>
            );
          })()}

        {validUsers.map((user) => (
          <Marker
            key={user.phoneNumber}
            position={{
              lat: user.coordinates.latitude,
              lng: user.coordinates.longitude,
            }}
            icon={userMarkerIcon}
            zIndex={10}
            onMouseOver={() =>
              setActiveUserPhone(user.phoneNumber)
            }
            onMouseOut={() =>
              setActiveUserPhone((curr) =>
                curr === user.phoneNumber ? null : curr,
              )
            }
          />
        ))}

        {activeUserPhone &&
          (() => {
            const user = validUsers.find(
              (u) => u.phoneNumber === activeUserPhone,
            );

            if (!user) return null;

            return (
              <InfoWindow
                position={{
                  lat: user.coordinates.latitude,
                  lng: user.coordinates.longitude,
                }}
                options={{
                  disableAutoPan: true,
                  pixelOffset: new google.maps.Size(
                    0,
                    -(USER_MARKER_ICON_SIZE + 8),
                  ),
                }}
                onCloseClick={() => setActiveUserPhone(null)}
              >
                <div
                  style={{
                    color:
                      theme === "dark" ? "#f5f7fb" : "#0b0f1a",
                    fontSize: 12,
                    minWidth: 140,
                  }}
                >
                  {/* <p style={{ fontSize: 12, fontWeight: 700, letterSpacing: 0.3 }}>
                    User Position
                  </p> */}

                  <div
                    style={{
                      marginTop: 6,
                      display: "flex",
                      justifyContent: "space-between",
                      gap: 12,
                    }}
                  >
                    <span style={{ opacity: 0.6 }}>
                      User Name
                    </span>
                    <span style={{ fontWeight: 600 }}>
                      {user.name || "Unknown"}
                    </span>
                  </div>

                  <div
                    style={{
                      marginTop: 6,
                      display: "flex",
                      justifyContent: "space-between",
                      gap: 12,
                    }}
                  >
                    <span style={{ opacity: 0.6 }}>
                      Phone
                    </span>
                    <span style={{ fontWeight: 600 }}>
                      {user.phoneNumber}
                    </span>
                  </div>

                  <div
                    style={{
                      marginTop: 4,
                      display: "flex",
                      justifyContent: "space-between",
                      gap: 12,
                    }}
                  >
                    <span style={{ opacity: 0.6 }}>
                      Lat/Lon
                    </span>
                    <span style={{ fontWeight: 600 }}>
                      {user.coordinates.latitude},{" "}
                      {user.coordinates.longitude}
                    </span>
                  </div>

                  <div
                    style={{
                      marginTop: 6,
                      display: "flex",
                      justifyContent: "space-between",
                      gap: 12,
                    }}
                  >
                    <span style={{ opacity: 0.6 }}>
                      Last Updated
                    </span>
                    <span style={{ fontWeight: 600 }}>
                      {formatTimestamp(user.timestamp)}
                    </span>
                  </div>
                </div>
              </InfoWindow>
            );
          })()}
      </GoogleMap>
    </div>
  );
}