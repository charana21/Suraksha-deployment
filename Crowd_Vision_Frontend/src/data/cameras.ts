// Central registry of every camera plotted in Dashboard.tsx.
//
// name is taken verbatim from Dashboard.tsx's old CAMERA_TITLES map.
// zone_id / type are cross-referenced from the Reports module:
//   - Reports.tsx: PLATFORM_GROUPS, FOB_GROUPS, BOOKING_GROUPS, CAMERA_LABELS
//   - Alerts.tsx:  ZONE_CATALOG
//   - lib/defaultZoneAnalytics.ts (for a few FOB/stairs/entry zone ids)
//
// Entries whose zone_id/type could not be confirmed in any of those modules are
// marked `// verify` — they're a best-effort guess from naming convention and
// should be checked against the live API's zone list before being relied on.
// Entries with camera_name: null are cameras plotted from the marked-up reference
// layout in Dashboard.tsx whose names/zones are still pending (cam_new_XX).

export type ZoneType = 'PLATFORM' | 'FOB' | 'BOOKING';

export interface CameraDefinition {
  camera_id: string;
  name: string | null;
  zone_id: string | null;
  type: ZoneType | null;
  cam_type:string | null;
  direction?: string | null;
}

export const CAMERAS: CameraDefinition[] = [
  // ── Platforms ──────────────────────────────────────────────────────────────
  { camera_id: 'cam_hyb_pf1', name: 'PF 1 NEAR KZJ END FACING GATE 2', zone_id: 'zone_hyb_pf1', type: 'PLATFORM',cam_type:'static',direction:'up' },
  { camera_id: 'cam_hyb_pf1_a', name: 'PF 1 NEAR GATE 4 FACING HYB', zone_id: 'zone_hyb_pf1', type: 'PLATFORM',cam_type:'static',direction:'left' },
  { camera_id: 'cam_hyb_pf2', name: 'PF 2 KZJ FOB FACING RRI', zone_id: 'zone_hyb_pf2', type: 'PLATFORM',cam_type:'static',direction:'right' },
  { camera_id: 'cam_hyb_pf4', name: 'PF 4&5 NEAR KZJ FOB FACING HYB', zone_id: 'zone_hyb_pf4', type: 'PLATFORM',cam_type:'static',direction:'left' },
  { camera_id: 'cam_hyb_pf8', name: 'PF 8 NEAR KZJ FOB FACING HYB', zone_id: 'zone_hyb_pf8', type: 'PLATFORM',cam_type:'static',direction:'left' },
  { camera_id: 'cam_hyb_pf10', name: 'PF 10 OPPOSITE TO GATE 8 FACING KZJ END', zone_id: 'zone_hyb_pf10', type: 'PLATFORM',cam_type:'static',direction:'left' },

  // New cameras
 { camera_id: 'cam_pf2_fc_hyd_side', name: 'PF 2 FACING HYD SIDE', zone_id: 'zone_hyb_pf2', type: 'PLATFORM', cam_type: 'static', direction: 'left' },

  { camera_id: 'cam_pf6_near_mid_fob', name: 'PF 6 NEAR MID FOB', zone_id: 'zone_hyd_pf6', type: 'PLATFORM', cam_type: 'static', direction: 'left' },

  { camera_id: 'cam_pf6_near_kzj_fob_fc_hyd', name: 'PF 6 NEAR KZJ FOB FACING HYD', zone_id: 'zone_hyd_pf6', type: 'PLATFORM', cam_type: 'static', direction: 'left' },

  { camera_id: 'cam_pf7_hyd_end', name: 'PF 7 HYD END', zone_id: 'zone_hyb_pf7', type: 'PLATFORM', cam_type: 'static', direction: 'left' },

  { camera_id: 'cam_pf8_mid_fc_kzj', name: 'PF 8 MID FACING KZJ', zone_id: 'zone_hyb_pf8', type: 'PLATFORM', cam_type: 'static', direction: 'right' },

  { camera_id: 'cam_pf8_9_fc_hyd_end', name: 'PF 8&9 FACING HYD END', zone_id: 'zone_hyb_pf8', type: 'PLATFORM', cam_type: 'dome', direction: 'left' },

  { camera_id: 'cam_pf10_hyd_end', name: 'PF 10 HYD END', zone_id: 'zone_hyb_pf10', type: 'PLATFORM', cam_type: 'static', direction: 'left' },

  { camera_id: 'cam_pf10_hyd_end_fc_kzj', name: 'PF 10 HYD END FACING KZJ', zone_id: 'zone_hyb_pf10', type: 'PLATFORM', cam_type: 'static', direction: 'right' },

  { camera_id: 'cam_outward_parcel_pf1_entr', name: 'OUTWARD PARCEL PF 1 ENTRANCE', zone_id: 'zone_hyb_pf1', type: 'PLATFORM', cam_type: 'static', direction: 'left' },

  // ── FOBs ───────────────────────────────────────────────────────────────────
  { camera_id: 'cam_middle_fob_4_5', name: 'HYB FOB MIDDLE FACING PF 4&5', zone_id: 'zone_hyb_fob', type: 'FOB',cam_type:'static',direction:'up' },
  { camera_id: 'cam_pf1_fob_pf10', name: 'HYB FOB FACING PF 10', zone_id: 'zone_hyb_fob', type: 'FOB',cam_type:'static',direction:'down' },
  { camera_id: 'cam_pf1_fob_hyb_end', name: 'PF 10 HYB FOB PATHWAY FACING PF 1', zone_id: 'zone_hyb_fob', type: 'FOB',cam_type:'static',direction:'up' },
  { camera_id: 'cam_kzj_pf1_fob_kzj', name: 'PF 1 KZJ FOB FACING PF 10', zone_id: 'zone_kzj_fob', type: 'FOB',cam_type:'static',direction:'down' },
  { camera_id: 'cam_kzj_pf1_fob_pf10', name: 'KZJ FOB ESCALATOR FACING PF 1', zone_id: 'zone_kzj_fob', type: 'FOB',cam_type:'static',direction:'up' },
  { camera_id: 'cam_mid_fob_center', name: 'NEW KZJ FOB MIDDLE FACING PF 10', zone_id: 'zone_mid_fob', type: 'FOB',cam_type:'static',direction:'down' },
  { camera_id: 'cam_mid_fob_pf1', name: 'NEW KZJ FOB FACING PF 10', zone_id: 'zone_mid_fob', type: 'FOB',cam_type:'static',direction:'down' },

  // New cameras

 { camera_id: 'cam_pf1_hyd_fob_fc_hyd_end', name: 'PF 1 HYD FOB FACING HYD END', zone_id: 'zone_hyb_fob', type: 'FOB', cam_type: 'static', direction: 'left' },

  { camera_id: 'cam_pf1_hyd_fob_fc_kzj_end', name: 'PF 1 HYD FOB FACING KZJ END', zone_id: 'zone_hyb_fob', type: 'FOB', cam_type: 'static', direction: 'right' },

  { camera_id: 'cam_hyd_fob_fc_6_7', name: 'HYD FOB MID FACING 6&7', zone_id: 'zone_hyd_fob', type: 'FOB', cam_type: 'static', direction: 'down' },

  { camera_id: 'cam_kzj_fob_pf1_fc_hyd_end', name: 'PF 1 KZJ FOB FACING HYD END', zone_id: 'zone_kzj_fob', type: 'FOB', cam_type: 'static', direction: 'left' },

  { camera_id: 'cam_kzj_fob_pf1_fc_kzj_end', name: 'PF 1 KZJ FOB FACING KZJ END', zone_id: 'zone_kzj_fob', type: 'FOB', cam_type: 'static', direction: 'right' },

  { camera_id: 'cam_kzj_fob_mid_4_5', name: 'KZJ FOB MID FACING 4&5', zone_id: 'zone_kzj_fob', type: 'FOB', cam_type: 'dome', direction: 'up' },

  { camera_id: 'cam_kzj_fob_mid_8_9', name: 'KZJ FOB MID FACING 8&9', zone_id: 'zone_kzj_fob', type: 'FOB', cam_type: 'static', direction: 'down' },

  { camera_id: 'cam_pf8_near_kzj_fob_fc_hyd_end', name: 'PF 8 NEAR KZJ FOB FACING HYD', zone_id: 'zone_kzj_fob', type: 'FOB', cam_type: 'static', direction: 'left' },

  { camera_id: 'cam_pf10_fob_steps', name: 'PF 10 HYD FOB FACING HYD STEPS', zone_id: 'zone_hyd_fob', type: 'FOB', cam_type: 'static', direction: 'left' },

  { camera_id: 'cam_pf10_fob_vip', name: 'PF 10 HYD FOB FACING VIP ENTRANCE', zone_id: 'zone_hyd_fob', type: 'FOB', cam_type: 'static', direction: 'right' },


  // ── Booking / Gates ────────────────────────────────────────────────────────
  { camera_id: 'cam_hyb_booking', name: 'GATE 2A BOOKING COUNTER', zone_id: 'zone_hyb_booking', type: 'BOOKING',cam_type:'static',direction:'down' },
  { camera_id: 'cam_hyb_booking_gate4a', name: 'GATE 4 GENERAL WAITING HALL', zone_id: 'zone_gate4a_booking', type: 'BOOKING',cam_type:'static',direction:'left' },
  { camera_id: 'cam_hyb_booking_gate6', name: 'GATE 6 BOOKING OFFICE', zone_id: 'zone_gate6_booking', type: 'BOOKING',cam_type:'static',direction:'left' },
  { camera_id: 'cam_hyb_booking_gate8', name: 'GATE 8 OUTSIDE', zone_id: 'zone_hyd_booking', type: 'BOOKING',cam_type:'dome',direction:'down' }, // verify — zone_id not present in Reports/Alerts, inferred from naming convention-checked

  // New cameras
  { camera_id: 'cam_hyd_booking_gate2a', name: 'GATE 2A ENTRANCE', zone_id: 'zone_gate2a_booking', type: 'BOOKING', cam_type: 'ptz', direction: 'up' },

  { camera_id: 'cam_near_gate_2a_fc_swathi_ent', name: 'NEAR GATE 2A FACING SWATHI ENT', zone_id: 'zone_gate2a_booking', type: 'BOOKING', cam_type: 'static', direction: 'up/slant to left' },

  { camera_id: 'cam_gate_5_booking_office', name: 'GATE 5 BOOKING OFFICE', zone_id: 'zone_gate5_booking', type: 'BOOKING', cam_type: 'dome', direction: 'right' },

  { camera_id: 'cam_prs_booking', name: 'PRS BOOKING COUNTER', zone_id: 'zone_hyd_booking', type: 'BOOKING', cam_type: 'static', direction: 'down' },

  // ── Pending — plotted from marked-up reference layout, name/zone not yet assigned ──9
 { camera_id: 'cam_pf1_parking_entr', name: 'PF 1 PARKING ENTRANCE', zone_id: 'zone_hyd_parking', type: 'PLATFORM', cam_type: 'static', direction: 'down' },

  { camera_id: 'cam_gate2a_fc_gate2a_path', name: 'GATE 2A FACING GATE 2 PATHWAY', zone_id: 'zone_gate2a_booking', type: 'BOOKING', cam_type: 'static', direction: 'up' },

  { camera_id: 'cam_rethifile_entr', name: 'RETHIFILE ENTRANCE', zone_id: 'zone_hyd_pf1', type: 'BOOKING', cam_type: 'static', direction: 'down' },

  { camera_id: 'cam_gate2a_towards_avtm', name: 'GATE 2A TOWARDS ATVM', zone_id: 'zone_gate2a_booking', type: 'BOOKING', cam_type: 'dome', direction: 'up' },

  { camera_id: 'cam_pf1_near_gate5_fc_hyd_fob', name: 'PF 1 NEAR GATE 5 FACING HYB FOB', zone_id: 'zone_hyd_pf1', type: 'BOOKING', cam_type: 'static', direction: 'left' },

  { camera_id: 'cam_gate2_fc_ac_wh', name: 'GATE 2 FACING AC WAITING HALL', zone_id: 'zone_gate2a_booking', type: 'BOOKING', cam_type: 'dome', direction: 'right' },

  { camera_id: 'cam_rethifile_bo', name: 'RETHIFILE BO/BUS STOP', zone_id: 'zone_hyd_pf1', type: 'BOOKING', cam_type: 'dome', direction: 'up' },

  { camera_id: 'cam_pf9_fc_hyd', name: 'PF 9 MIDDLE FACING HYB', zone_id: 'zone_hyd_pf9', type: 'PLATFORM', cam_type: 'static', direction: 'left' },

  { camera_id: 'cam_mid_4_5', name: 'PF 4&5 MIDDLE', zone_id: 'zone_hyd_pf4', type: 'PLATFORM', cam_type: 'ptz', direction: 'right' },

  { camera_id: 'cam_pf10_bme_fc_hyd', name: 'PF 10 OPP BASEMENT FACING HYB', zone_id: 'zone_hyd_pf10', type: 'PLATFORM', cam_type: 'static', direction: 'left' },

  { camera_id: 'cam_gate2a_fc_parking', name: 'GATE 2A FACING CAR PARKING', zone_id: 'zone_gate2a_booking', type: 'BOOKING', cam_type: 'static', direction: 'down' },

  { camera_id: 'cam_pf10_vip_saloon', name: 'PF10 VIP SALOON SIDING', zone_id: 'zone_hyd_pf10', type: 'PLATFORM', cam_type: 'static', direction: 'right' },

  { camera_id: 'cam_gate5_pathway', name: 'GATE 5 PATHWAY', zone_id: 'zone_gate5_booking', type: 'BOOKING', cam_type: 'static', direction: 'up' },

  { camera_id: 'cam_north_parking', name: 'NORTH BUILDING PARKING', zone_id: 'zone_hyd_pf1', type: 'PLATFORM',cam_type:'static',direction:'left' },
  { camera_id: 'cam_alpha_exit', name: 'ALPHA EXIT', zone_id: 'zone_hyd_pf1', type: 'PLATFORM',cam_type:'static',direction:'up' },
  { camera_id: 'cam_gate2_wh', name: 'GATE 2 WAITING HALL', zone_id: 'zone_hyd_pf1', type: 'PLATFORM',cam_type:'dome',direction:'up' },
  { camera_id: 'cam_gate8_parking_entr', name: 'GATE 8 PARKING ENTRANCE', zone_id: 'zone_hyd_pf10', type: 'PLATFORM',cam_type:'dome',direction:'down' },
  { camera_id: 'cam_pf5_hyd_end', name: 'PF 5 HYB END', zone_id: 'zone_hyd_pf5', type: 'PLATFORM',cam_type:'static',direction:'left' },
  { camera_id: 'cam_pf1_near_gate4_fc_kzj', name: 'PF 1 NEAR GATE 4 FACING KZJ', zone_id: 'zone_hyd_pf1', type: 'PLATFORM',cam_type:'static',direction:'left' },
  { camera_id: 'cam_pf_6_7_mmts_fc_hyd', name: 'PF 6&7 MMTS BOOKING FACING HYB', zone_id: 'zone_hyd_pf6', type: 'PLATFORM',cam_type:'static',direction:'left' },
  // { camera_id: 'cam_hyd_fob_mid_fc_6_7', name: 'HYB FOB MIDDLE FACING 6&7', zone_id: 'zone_hyd_pf7', type: 'PLATFORM',cam_type:'' },
];

export const CAMERA_BY_ID: Record<string, CameraDefinition> = Object.fromEntries(
  CAMERAS.map((camera) => [camera.camera_id, camera]),
);

// Every camera_id, in the order the dashboard should plot/wire them up.
export const LIVE_CAMERA_IDS: string[] = CAMERAS.map((camera) => camera.camera_id);

// camera_id -> display name, for tooltips/labels. Cameras with no name yet (cam_new_XX)
// are omitted so callers can fall back to the raw camera_id.
export const CAMERA_TITLES: Record<string, string> = Object.fromEntries(
  CAMERAS.filter((camera): camera is CameraDefinition & { name: string } => !!camera.name)
    .map((camera) => [camera.camera_id, camera.name]),
);
