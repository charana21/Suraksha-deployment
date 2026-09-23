const GEO_TO_SVG = {
  minLat: 17.43225,
  minLon: 78.4995,
  scale: 369523.80952354544,
  offsetX: 80,
  svgHeight: 1856,
  offsetY: 586.1904761905325,
};

const toSvgPointFromLatLon = (latitude, longitude) => {
  const x = GEO_TO_SVG.offsetX + (longitude - GEO_TO_SVG.minLon) * GEO_TO_SVG.scale;
  const y = GEO_TO_SVG.svgHeight - (GEO_TO_SVG.offsetY + (latitude - GEO_TO_SVG.minLat) * GEO_TO_SVG.scale);
  return { x, y };
};

const PLATFORM_GEO_ZONES = [
  {
    id: "pf1",
    label: "Platform 1",
    polygon: [{ x: 80.00, y: 797.56 }, { x: 523.43, y: 881.81 }, { x: 1761.33, y: 667.49 }, { x: 1853.71, y: 586.19 }],
    preferredZoneIds: ["zone_hyb_pf1"],
  },
  {
    id: "pf2_3",
    label: "Platform 2 & 3",
    polygon: [{ x: 80.00, y: 1011.14 }, { x: 135.43, y: 1029.62 }, { x: 1761.33, y: 641.62 }, { x: 1816.76, y: 660.10 }],
    preferredZoneIds: ["zone_hyb_pf2", "zone_hyb_pf3"],
  },
  {
    id: "pf4_5",
    label: "Platform 4 & 5",
    polygon: [{ x: 109.56, y: 1122.00 }, { x: 161.30, y: 1140.48 }, { x: 1779.81, y: 689.66 }, { x: 1835.24, y: 704.44 }],
    preferredZoneIds: ["zone_hyb_pf4", "zone_hyb_pf5"],
  },
  {
    id: "pf6_7",
    label: "Platform 6 & 7",
    polygon: [{ x: 116.95, y: 1133.09 }, { x: 172.38, y: 1151.56 }, { x: 1964.57, y: 704.44 }, { x: 2020.00, y: 722.91 }],
    preferredZoneIds: ["zone_hyb_pf6", "zone_hyb_pf7"],
  },
  {
    id: "pf8_9",
    label: "Platform 8 & 9",
    polygon: [{ x: 560.38, y: 1125.70 }, { x: 615.81, y: 1140.48 }, { x: 1798.29, y: 826.38 }, { x: 1742.86, y: 807.90 }],
    preferredZoneIds: ["zone_hyb_pf8", "zone_hyb_pf9"],
  },
  {
    id: "pf10",
    label: "Platform 10",
    polygon: [{ x: 346.80, y: 1228.79 }, { x: 357.14, y: 1269.81 }, { x: 1714.77, y: 860.75 }, { x: 1948.31, y: 889.94 }],
    preferredZoneIds: ["zone_hyb_pf10"],
  },
];

const isPointOnSegment = (point, a, b, epsilon = 1e-6) => {
  const cross = (point.y - a.y) * (b.x - a.x) - (point.x - a.x) * (b.y - a.y);
  if (Math.abs(cross) > epsilon) return false;

  const dot = (point.x - a.x) * (b.x - a.x) + (point.y - a.y) * (b.y - a.y);
  if (dot < -epsilon) return false;

  const lenSq = (b.x - a.x) * (b.x - a.x) + (b.y - a.y) * (b.y - a.y);
  if (dot - lenSq > epsilon) return false;

  return true;
};

const isPointInsidePolygon = (point, polygon) => {
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    if (isPointOnSegment(point, polygon[j], polygon[i])) {
      return true;
    }
  }

  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const xi = polygon[i].x;
    const yi = polygon[i].y;
    const xj = polygon[j].x;
    const yj = polygon[j].y;
    const intersects = ((yi > point.y) !== (yj > point.y))
      && (point.x < ((xj - xi) * (point.y - yi)) / ((yj - yi) || Number.EPSILON) + xi);
    if (intersects) inside = !inside;
  }
  return inside;
};

const coords = [
  { lon: 78.50103, lat: 17.433495 },
  { lon: 78.5005686, lat: 17.4336146 },
  { lon: 78.502381, lat: 17.433702 }
];

coords.forEach((coord) => {
  const pt = toSvgPointFromLatLon(coord.lat, coord.lon);
  let zone = PLATFORM_GEO_ZONES.find((z) => isPointInsidePolygon(pt, z.polygon));
  console.log(`Lat: ${coord.lat}, Lon: ${coord.lon} -> SVG(x: ${pt.x.toFixed(2)}, y: ${pt.y.toFixed(2)}) -> Platform: ${zone ? zone.label : 'None'}`);
});
