import { ZoneAnalytics } from "@/types/zone";

function base(
  partial: Pick<ZoneAnalytics, "zone_id" | "zone_name" | "svg_region_id" | "display_order" | "zone_type">,
  riskOverride: Partial<ZoneAnalytics> = {}
): ZoneAnalytics {
  return {
    ...partial,
    people_count: 0,
    density_avg: 0,
    density_level: "LOW",
    motion_intensity: 0,
    risk_score: 0,
    risk_level: "LOW",
    camera_count: 1,
    cameras: [],
    ...riskOverride
  };
}

export function getDefaultZoneAnalytics(stationId: string): ZoneAnalytics[] {
  const id = stationId.toUpperCase();

  if (id === "HYB" || id === "HYD") {
    return [
      base({
        zone_id: "zone_pf10_fob_vip",
        zone_name: "VIP Entry",
        svg_region_id: "zone_pf10_fob_vip",
        display_order: 1,
        zone_type: "ENTRY",
      }),
      base({
        zone_id: "zone_kzj_e_sel", // Corrected from zone_pf1_fob_lift
        zone_name: "PF-1 Lift",
        svg_region_id: "zone_kzj_e_sel",
        display_order: 2,
        zone_type: "LIFT",
      }),
      base({
        zone_id: "zone_pf1_fob_kzj",
        zone_name: "KZJ Side Zone",
        svg_region_id: "zone_pf1_fob_kzj",
        display_order: 3,
        zone_type: "FOB",
      }),
      base({
        zone_id: "zone_pf1_fob_hyb_end",
        zone_name: "HYB Side Zone",
        svg_region_id: "zone_pf1_fob_hyb_end",
        display_order: 4,
        zone_type: "FOB",
      }),
      base({
        zone_id: "zone_middle_fob_4_5",
        zone_name: "Middle 4&5 Zone",
        svg_region_id: "zone_middle_fob_4_5",
        display_order: 5,
        zone_type: "FOB",
      }),
      base({
        zone_id: "zone_middle_fob_6_7",
        zone_name: "Middle 6&7 Zone",
        svg_region_id: "zone_middle_fob_6_7",
        display_order: 6,
        zone_type: "FOB",
      }),
      base({
        zone_id: "zone_pf10_fob_steps",
        zone_name: "Steps to PF-10",
        svg_region_id: "zone_pf10_fob_steps",
        display_order: 7,
        zone_type: "STAIRS",
      })
    ];
  }

  // KZJ fallback - Exact Match to fob_zones.json
  return [
    base({ zone_id: "zone_pf1_kzj_fob_fc_kzj", zone_name: "PF 1 KZJ FC KZJ", svg_region_id: "zone_pf1_kzj_fob_fc_kzj", display_order: 1, zone_type: "FOB" }),
    base({ zone_id: "zone_pf1_kzj_fob_fc_hyb", zone_name: "PF 1 KZJ FC HYB", svg_region_id: "zone_pf1_kzj_fob_fc_hyb", display_order: 2, zone_type: "FOB" }),
    base({ zone_id: "zone_new_kzj_fob_middle_fc_pf10", zone_name: "PF 1 KZJ FC PF 10", svg_region_id: "zone_new_kzj_fob_middle_fc_pf10", display_order: 3, zone_type: "FOB" }),
    base({ zone_id: "zone_kzj_fob_escalator_fc_pf1", zone_name: "KZJ PF1 ESCL", svg_region_id: "zone_kzj_fob_escalator_fc_pf1", display_order: 4, zone_type: "ESCALATOR" }),
    base({ zone_id: "zone_new_kzj_fob_near_pf01", zone_name: "NEW KZJ NEAR PF-01", svg_region_id: "zone_new_kzj_fob_near_pf01", display_order: 5, zone_type: "FOB" }),
    base({ zone_id: "zone_new_kzj_fob_fc_pf01", zone_name: "NEW KZJ FC PF-01", svg_region_id: "zone_new_kzj_fob_fc_pf01", display_order: 6, zone_type: "FOB" }),
    base({ zone_id: "zone_kzj_fob_middle_fc_4_5", zone_name: "KZJ FOB MIDDLE FC 4&5", svg_region_id: "zone_kzj_fob_middle_fc_4_5", display_order: 7, zone_type: "FOB" }),
    base({ zone_id: "zone_kzj_fob_middle_fc_8_9", zone_name: "KZJ FOB MIDDLE FC 8&9", svg_region_id: "zone_kzj_fob_middle_fc_8_9", display_order: 8, zone_type: "FOB" }),
    base({ zone_id: "zone_new_kzj_fob_fc_pf10_bottom", zone_name: "NEW KZJ FOB FC PF-10", svg_region_id: "zone_new_kzj_fob_fc_pf10_bottom", display_order: 9, zone_type: "FOB" }),
    base({ zone_id: "zone_new_kzj_mid_fc_pf10", zone_name: "NEW KZJ MID FC-PF-10", svg_region_id: "zone_new_kzj_mid_fc_pf10", display_order: 10, zone_type: "FOB" }),
  ];
}

