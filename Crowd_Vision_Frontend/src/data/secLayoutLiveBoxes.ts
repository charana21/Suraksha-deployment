export type CameraBox = {
  id: string;
  label: string;
  x: number;
  y: number;
  w: number;
  h: number;
};

export const VIEWBOX_WIDTH = 2100;
export const LIVE_VIEWBOX_HEIGHT = 1856;
export const LIVE_BOX_SCALE = 1.55;
export const PRS_BOOKING_CAMERA_ID = 'prs-booking-office';

export const INLINE_OFFICE_LIVE_IDS = new Set<string>();

export const FIXED_SCALE_CAMERA_IDS = new Set<string>([
  'hyd-fob-top',
  'hyd-fob-mid-fc-4-5',
  'hyd-fob-pf10',
  'kzj-fob-top',
  'kzj-fob-pf10',
  PRS_BOOKING_CAMERA_ID,
]);

export const CAMERA_BOXES: CameraBox[] = [
  { id: 'hyd-fob-top', label: 'HYD FOB TOP', x: 300, y: 398, w: 110, h: 84 },
  { id: 'kzj-fob-top', label: 'KZJ FOB TOP', x: 1600, y: 398, w: 110, h: 84 },
  { id: 'pf1-near-kzj-fob-fc-gate2', label: 'PF-1 NEAR KZJ FOB FC GATE 2', x: 760, y: 330, w: 110, h: 58 },
  { id: 'pf2-kzj-fob-fc-rri', label: 'PF 2 KZJ FOB FC RRI', x: 1420, y: 546, w: 110, h: 58 },
  { id: 'pf4-5-middle-ptz', label: 'PF.NO.4&5 MIDDLE PTZ', x: 760, y: 711, w: 110, h: 58 },
  { id: 'pf6-near-mid-fob', label: 'PF 6 NEAR MID FOB', x: 760, y: 891, w: 110, h: 58 },
  { id: 'pf6-7-kzj-fob-fc-rri', label: 'PF 6&7 KZJ FOB FC RRI', x: 1420, y: 891, w: 110, h: 58 },
  { id: 'hyd-fob-mid-fc-4-5', label: 'HYD FOB MID FC 4&5', x: 300, y: 711, w: 110, h: 84 },
  { id: 'gate-2-booking-office', label: 'GATE 2 BOOKING OFFICE', x: 886, y: 190, w: 58, h: 110 },
  { id: 'hyd-fob-pf10', label: 'HYD FOB PF10', x: 300, y: 1196, w: 110, h: 84 },
  { id: 'pf10-opp-gate8-fc-kzj-fob', label: 'PF 10(OPP GATE-8) FC KZJ FOB', x: 1420, y: 1236, w: 110, h: 58 },
  { id: 'pf8-middle-fc-kzj', label: 'PF 8 MIDDLE FC KZJ', x: 760, y: 1071, w: 110, h: 58 },
  { id: 'kzj-fob-pf10', label: 'KZJ FOB PF10', x: 1600, y: 1196, w: 110, h: 84 },
  { id: 'prs-booking-office', label: 'PRS BOOKING OFFICE', x: 1535, y: 165, w: 260, h: 95 },
  { id: 'gate-6-booking-office', label: 'GATE 6 BOOKING OFFICE', x: 786, y: 1368, w: 58, h: 110 },
];
