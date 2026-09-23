import stationZonesRaw from "@/assets/sec_lat_lng.json";

export type LatLngLiteral = { lat: number; lng: number };

export type StationZoneType = "platform" | "fob";

export interface StationZone {
  id: string;
  name: string;
  type: StationZoneType;
  path: LatLngLiteral[];
  center: LatLngLiteral;
  strokeColor: string;
  fillColor: string;
}

interface RawStationZone {
  _id: string;
  name: string;
  gps: Array<{ latitude: number; longitude: number }>;
}

// One fixed neon color per zone type — every platform shares the same
// color, every FOB shares the same (different) color.
const PLATFORM_COLOR = "#00F5FF";
const FOB_COLOR = "#00FFA3";

const classifyZoneType = (name: string): StationZoneType =>
  /fob/i.test(name) ? "fob" : "platform";

const computeCentroid = (path: LatLngLiteral[]): LatLngLiteral => {
  const total = path.reduce(
    (acc, point) => ({ lat: acc.lat + point.lat, lng: acc.lng + point.lng }),
    { lat: 0, lng: 0 },
  );
  return { lat: total.lat / path.length, lng: total.lng / path.length };
};

const buildStationZones = (): StationZone[] =>
  (stationZonesRaw as RawStationZone[]).map((zone) => {
    const type = classifyZoneType(zone.name);
    const path = zone.gps.map((point) => ({ lat: point.latitude, lng: point.longitude }));
    const strokeColor = type === "fob" ? FOB_COLOR : PLATFORM_COLOR;

    return {
      id: zone._id,
      name: zone.name,
      type,
      path,
      center: computeCentroid(path),
      strokeColor,
      fillColor: strokeColor,
    };
  });

export const STATION_ZONES: StationZone[] = buildStationZones();

export const STATION_CENTER: LatLngLiteral = (() => {
  const centroid = computeCentroid(STATION_ZONES.flatMap((zone) => zone.path));
  return centroid.lat && centroid.lng ? centroid : { lat: 17.4332, lng: 78.5017 };
})();

export interface StationBounds {
  north: number;
  south: number;
  east: number;
  west: number;
}

export const STATION_BOUNDS: StationBounds = STATION_ZONES.reduce(
  (bounds, zone) => {
    for (const point of zone.path) {
      bounds.north = Math.max(bounds.north, point.lat);
      bounds.south = Math.min(bounds.south, point.lat);
      bounds.east = Math.max(bounds.east, point.lng);
      bounds.west = Math.min(bounds.west, point.lng);
    }
    return bounds;
  },
  { north: -Infinity, south: Infinity, east: -Infinity, west: Infinity } as StationBounds,
);
