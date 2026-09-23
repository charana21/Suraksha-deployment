"""
Unified Station Seed — Zones, Cameras, Dual-Layer Adjacency

Seeds MongoDB with a complete station layout:
- Zones as simple logical groupings (FOB, Platform, Booking)
- Cameras with svg_region_id, adjacent_cameras
- Zone adjacency (macro routing: platform ↔ FOB)
- Camera adjacency (micro flow: platform cam ↔ FOB cam)

Replaces old seed_cameras.py and seed_station_layout.py.

Usage:
    python scripts/seed_platform_zones.py           # first run
    python scripts/seed_platform_zones.py --clear    # wipe and re-seed

Zones: 14 total (3 FOB + 10 platform + 1 booking)
Cameras: 64 total (9 HYB FOB + 6 KZJ FOB + 3 mid FOB + 10 platform legacy + 30 platform (3x10) + 6 booking)
"""
import asyncio
import sys
import argparse
from datetime import UTC, datetime
from pathlib import Path
import logging
logger = logging.getLogger(__name__)
sys.path.insert(0, str(Path(__file__).parent.parent))
from motor.motor_asyncio import AsyncIOMotorClient
from config.config import get_settings

STATION_ID = "HYB"

# ============================================================================
# ZONES — simple logical groupings
# ============================================================================

ZONES = [
    # 3 FOB zones (one per physical bridge)
    {
        "zone_id": "zone_hyb_fob",
        "zone_name": "HYB FOB",
        "zone_type": "FOB",
        "display_order": 1,
        "description": "Hyderabad FOB (main bridge, 9 cameras)",
    },
    {
        "zone_id": "zone_kzj_fob",
        "zone_name": "KZJ FOB",
        "zone_type": "FOB",
        "display_order": 2,
        "description": "Kazipet FOB (second bridge, 6 cameras)",
    },
    {
        "zone_id": "zone_mid_fob",
        "zone_name": "Middle FOB",
        "zone_type": "FOB",
        "display_order": 3,
        "description": "Middle FOB (third bridge between HYB & KZJ, 3 cameras)",
    },
    # 10 Platform zones
    *[
        {
            "zone_id": f"zone_hyb_pf{n}",
            "zone_name": f"Platform {n}",
            "zone_type": "PLATFORM",
            "display_order": 10 + n,
            "description": f"Platform {n}",
        }
        for n in range(1, 11)
    ],
    # 1 Booking zone
            {
                "zone_id": "zone_hyb_booking",
                "zone_name": "Booking Counter",
                "zone_type": "BOOKING",
                "display_order": 30,
                "description": "Main booking/ticketing counter area",
            },
            {
                "zone_id": "zone_gate5_booking",
                "zone_name": "Gate 5 Booking Office",
                "zone_type": "BOOKING",
                "display_order": 31,
                "description": "Gate 5 booking office area",
            },
            {
                "zone_id": "zone_gate4a_booking",
                "zone_name": "Gate 4A Booking Area",
                "zone_type": "BOOKING",
                "display_order": 32,
                "description": "Gate 4A booking area",
            },
            {
                "zone_id": "zone_gate2a_booking",
                "zone_name": "Gate 2A Booking Area",
                "zone_type": "BOOKING",
                "display_order": 33,
                "description": "Gate 2A booking area",
            },
            {
                "zone_id": "zone_gate6_booking",
                "zone_name": "Gate 6 Booking Area",
                "zone_type": "BOOKING",
                "display_order": 34,
                "description": "Gate 6 booking area",
            },
            # --- New zone from Excel camera registry (only genuinely new zone) ---
            {
                "zone_id": "zone_hyb_parking",
                "zone_name": "HYB Parking",
                "zone_type": "PLATFORM",
                "display_order": 36,
                "description": "Hyderabad parking / approach area",
            },
        ]

# Old granular FOB zones to remove (replaced by zone_hyb_fob / zone_kzj_fob)
OLD_HYB_FOB_ZONE_IDS = [
    "zone_pf1_fob_kzj",
    "zone_pf1_hyb_fob_fc_pf10",
    "zone_pf1_fob_hyb_end",
    "zone_middle_fob_4_5",
    "zone_middle_fob_6_7",
    "zone_pf10_hyb_fob_fc_pf1",
    "zone_pf10_fob_steps",
    "zone_pf10_fob_vip",
    "zone_pf1_fob_lift",
]

OLD_KZJ_FOB_ZONE_IDS = [
    "zone_pf1_kzj_fob_fc_kzj",
    "zone_new_kzj_fob_middle_fc_pf10",
    "zone_pf1_kzj_fob_fc_hyb",
    "zone_kzj_fob_middle_fc_4_5",
    "zone_kzj_fob_middle_fc_8_9",
    "zone_kzj_fob_escalator_fc_pf1",
]

# ============================================================================
# CAMERAS — physical sensors
# ============================================================================

# --- HYB FOB cameras (legacy — only those in KEEP_17 will reach ALL_CAMERAS) ---
HYB_FOB_CAMERAS = [
    {"camera_id": "cam_pf1_fob_kzj",       "name": "HYB FOB FACING PF 10",         "rtsp_url": "rtsp://localhost:8554/mystream",    "location": "HYB FOB FACING PF 10"},
    {"camera_id": "cam_pf1_fob_pf10",       "name": "PF 1 HYB FOB FC PF 10",        "rtsp_url": "rtsp://localhost:8554/mystream1",   "location": "PF1 FOB - PF10 Side"},
    {"camera_id": "cam_pf1_hyd_fob_fc_hyd_end", "name": "PF 1 HYD FOB FACING HYD END", "rtsp_url": "rtsp://localhost:8554/mystream",    "location": "PF 1 HYD FOB FACING HYD END"},
    {"camera_id": "cam_middle_fob_4_5",     "name": "HYB FOB MIDDLE FACING PF 4&5", "rtsp_url": "rtsp://localhost:8554/middle_4_5",  "location": "HYB FOB MIDDLE FACING PF 4&5"},
    {"camera_id": "cam_middle_fob_6_7",     "name": "HYB FOB MIDD FC 6&7",          "rtsp_url": "rtsp://localhost:8554/middle_6_7",  "location": "Middle FOB - PF6 & PF7"},
    {"camera_id": "cam_pf10_fob_pf1",       "name": "PF 10 HYB FOB FC PF1",         "rtsp_url": "rtsp://localhost:8554/pf10_pf1",    "location": "PF10 FOB - PF1 Side"},
    {"camera_id": "cam_pf10_fob_steps",     "name": "PF 10 HYB FOB FC HYB STEPS",   "rtsp_url": "rtsp://localhost:8554/pf10_steps",  "location": "PF10 FOB - Steps"},
    {"camera_id": "cam_pf10_fob_vip",       "name": "PF 10 HYB FOB FC VIP ENTRANCE", "rtsp_url": "rtsp://localhost:8554/pf10_vip",    "location": "PF10 FOB - VIP Entry"},
    {"camera_id": "cam_pf1_fob_lift",       "name": "PF 1 HYB FOB LIFT",            "rtsp_url": "rtsp://localhost:8554/pf1_lift",    "location": "PF1 FOB - Lift"},
    # cam_pf1_fob_hyb_end — kept in KEEP_17, referenced in adjacency maps
    {"camera_id": "cam_pf1_fob_hyb_end",    "name": "PF 10 HYB FOB PATHWAY FACING PF 1",  "rtsp_url": "rtsp://localhost:8554/pf1_fob_hyb_end", "location": "PF 10 HYB FOB PATHWAY FACING PF 1"},
]

# --- KZJ FOB cameras (6, new) ---
KZJ_FOB_CAMERAS = [
    {"camera_id": "cam_kzj_pf1_fob_kzj",   "name": "PF 1 KZJ FOB FACING PF 10", "rtsp_url": "rtsp://localhost:8554/kzj_pf1_fob_kzj",  "location": "PF 1 KZJ FOB FACING PF 10"},
    {"camera_id": "cam_kzj_pf1_fob_pf10",  "name": "KZJ FOB ESCALATOR FACING PF 1", "rtsp_url": "rtsp://localhost:8554/kzj_pf1_fob_pf10", "location": "KZJ FOB ESCALATOR FACING PF 1"},
    {"camera_id": "cam_kzj_pf1_fob_hyb",    "name": "PF 1 KZJ FOB FC HYB END",   "rtsp_url": "rtsp://localhost:8554/kzj_pf1_fob_hyb",  "location": "KZJ FOB - PF1 HYB end"},
    {"camera_id": "cam_kzj_fob_mid_4_5",    "name": "KZJ FOB MIDD FC 4&5",       "rtsp_url": "rtsp://localhost:8554/kzj_fob_mid_4_5",  "location": "KZJ FOB - middle 4&5"},
    {"camera_id": "cam_kzj_fob_mid_8_9",    "name": "KZJ FOB MIDD FC 8&9",       "rtsp_url": "rtsp://localhost:8554/kzj_fob_mid_8_9",  "location": "KZJ FOB - middle 8&9"},
    {"camera_id": "cam_kzj_fob_escalator",  "name": "PF 10 KZJ FOB ESCL FC PF1", "rtsp_url": "rtsp://localhost:8554/kzj_fob_escalator", "location": "KZJ FOB - escalator"},
]

# --- Middle FOB cameras (3, new) ---
MID_FOB_CAMERAS = [
    {"camera_id": "cam_mid_fob_pf1",    "name": "NEW KZJ FOB FACING PF 10",        "rtsp_url": "rtsp://localhost:8554/mid_fob_pf1",    "location": "NEW KZJ FOB FACING PF 10"},
    {"camera_id": "cam_mid_fob_center", "name": "NEW KZJ FOB MIDDLE FACING PF 10", "rtsp_url": "rtsp://localhost:8554/mid_fob_center",  "location": "NEW KZJ FOB MIDDLE FACING PF 10"},
    {"camera_id": "cam_mid_fob_pf10",   "name": "Middle FOB PF10 Side",            "rtsp_url": "rtsp://localhost:8554/mid_fob_pf10",    "location": "Middle FOB - PF10 end"},
]

# --- Platform cameras — 1 legacy + 3 new per platform (start/middle/end) ---
CUSTOM_LEGACY_PF_NAMES = {
    "cam_hyb_pf1": "PF 1 NEAR KZJ END FACING GATE 2",
    "cam_hyb_pf2": "PF 2 KZJ FOB FACING RRI",
    "cam_hyb_pf4": "PF 4&5 NEAR KZJ FOB FACING HYB",
    "cam_hyb_pf8": "PF 8 NEAR KZJ FOB FACING HYB",
    "cam_hyb_pf10": "PF 10 OPPOSITE TO GATE 8 FACING KZJ END",
}

PLATFORM_CAMERAS_LEGACY = [
    {
        "camera_id": f"cam_hyb_pf{n}",
        "name": CUSTOM_LEGACY_PF_NAMES.get(f"cam_hyb_pf{n}", f"Platform {n} Camera"),
        "rtsp_url": f"rtsp://localhost:8554/hyb_pf{n}",
        "location": CUSTOM_LEGACY_PF_NAMES.get(f"cam_hyb_pf{n}", f"Platform {n}")
    }
    for n in range(1, 11)
]

CUSTOM_MULTI_PF_NAMES = {
    "cam_hyb_pf1_a": "PF 1 NEAR GATE 4 FACING HYB",
}

PLATFORM_CAMERAS_MULTI = [
    cam
    for n in range(1, 11)
    for cam in [
        {
            "camera_id": f"cam_hyb_pf{n}_a",
            "name": CUSTOM_MULTI_PF_NAMES.get(f"cam_hyb_pf{n}_a", f"Platform {n} Start Camera"),
            "rtsp_url": f"rtsp://localhost:8554/hyb_pf{n}_a",
            "location": CUSTOM_MULTI_PF_NAMES.get(f"cam_hyb_pf{n}_a", f"Platform {n} - Start")
        },
        {"camera_id": f"cam_hyb_pf{n}_b", "name": f"Platform {n} Middle Camera", "rtsp_url": f"rtsp://localhost:8554/hyb_pf{n}_b", "location": f"Platform {n} - Middle"},
        {"camera_id": f"cam_hyb_pf{n}_c", "name": f"Platform {n} End Camera",    "rtsp_url": f"rtsp://localhost:8554/hyb_pf{n}_c", "location": f"Platform {n} - End"},
    ]
]

PLATFORM_CAMERAS = PLATFORM_CAMERAS_LEGACY + PLATFORM_CAMERAS_MULTI

# --- Booking cameras ---
BOOKING_CAMERAS = [
    {"camera_id": "cam_hyb_booking",              "name": "GATE 2A BOOKING COUNTER",        "rtsp_url": "rtsp://localhost:8554/hyb_booking",               "location": "GATE 2A BOOKING COUNTER"},
    {"camera_id": "cam_hyb_booking_gate5_office", "name": "Gate 5 Booking Office Camera",   "rtsp_url": "rtsp://localhost:8554/hyb_booking_gate5_office",  "location": "Gate 5 booking office"},
    {"camera_id": "cam_hyb_booking_gate4a",       "name": "GATE 4 GENERAL WAITING HALL",    "rtsp_url": "rtsp://localhost:8554/hyb_booking_gate4a",        "location": "GATE 4 GENERAL WAITING HALL"},
    {"camera_id": "cam_hyb_booking_gate2a",       "name": "Gate 2A Booking Camera",         "rtsp_url": "rtsp://localhost:8554/hyb_booking_gate2a",        "location": "Gate 2A booking area"},
    {"camera_id": "cam_hyb_booking_gate6",        "name": "GATE 6 BOOKING OFFICE",          "rtsp_url": "rtsp://localhost:8554/hyb_booking_gate6",         "location": "GATE 6 BOOKING OFFICE"},
    {"camera_id": "cam_hyb_booking_gate8",        "name": "GATE 8 OUTSIDE",                 "rtsp_url": "rtsp://localhost:8554/hyb_booking_gate8",         "location": "GATE 8 OUTSIDE"},
]

# Camera → zone mapping (legacy arrays)
CAMERA_ZONE_MAP = {}
for cam in HYB_FOB_CAMERAS:
    CAMERA_ZONE_MAP[cam["camera_id"]] = "zone_hyb_fob"
for cam in KZJ_FOB_CAMERAS:
    CAMERA_ZONE_MAP[cam["camera_id"]] = "zone_kzj_fob"
for cam in MID_FOB_CAMERAS:
    CAMERA_ZONE_MAP[cam["camera_id"]] = "zone_mid_fob"
for cam in PLATFORM_CAMERAS_LEGACY:
    CAMERA_ZONE_MAP[cam["camera_id"]] = cam["camera_id"].replace("cam_", "zone_")
for cam in PLATFORM_CAMERAS_MULTI:
    base = cam["camera_id"].rsplit("_", 1)[0]
    CAMERA_ZONE_MAP[cam["camera_id"]] = base.replace("cam_", "zone_")
BOOKING_CAMERA_ZONE_MAP = {
    "cam_hyb_booking":              "zone_hyb_booking",
    "cam_hyb_booking_gate5_office": "zone_gate5_booking",
    "cam_hyb_booking_gate4a":       "zone_gate4a_booking",
    "cam_hyb_booking_gate2a":       "zone_gate2a_booking",
    "cam_hyb_booking_gate6":        "zone_gate6_booking",
    "cam_hyb_booking_gate8":        "zone_hyb_booking",
}
for cam in BOOKING_CAMERAS:
    CAMERA_ZONE_MAP[cam["camera_id"]] = BOOKING_CAMERA_ZONE_MAP.get(
        cam["camera_id"], "zone_hyb_booking"
    )

# ===========================================================================
# 17 PROTECTED camera_ids — always kept regardless of Excel import
# ===========================================================================
KEEP_17_CAMERA_IDS = {
    "cam_hyb_pf1",
    "cam_hyb_pf2",
    "cam_hyb_pf4",
    "cam_mid_fob_center",
    "cam_middle_fob_4_5",
    "cam_hyb_pf8",
    "cam_hyb_pf10",
    "cam_pf1_fob_kzj",
    "cam_hyb_pf1_a",
    "cam_mid_fob_pf1",
    "cam_pf1_fob_hyb_end",
    "cam_kzj_pf1_fob_kzj",
    "cam_kzj_pf1_fob_pf10",
    "cam_hyb_booking",
    "cam_hyb_booking_gate6",
    "cam_hyb_booking_gate8",
    "cam_hyb_booking_gate4a",
}

# ===========================================================================
# EXCEL CAMERAS — 44 cameras from New_Cameras_Registry.xlsx
# These REPLACE all non-protected legacy cameras.
# ===========================================================================
EXCEL_CAMERAS = [
    # ── PLATFORM cameras ────────────────────────────────────────────────────
    {"camera_id": "cam_pf2_fc_hyd_side",            "name": "PF 2 FACING HYD SIDE",               "zone_id": "zone_hyb_pf2",        "zone_type": "PLATFORM",  "location": "PF 2 FACING HYD SIDE",               "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_pf6_near_mid_fob",           "name": "PF 6 NEAR MID FOB",                  "zone_id": "zone_hyb_pf6",        "zone_type": "PLATFORM",  "location": "PF 6 NEAR MID FOB",                  "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_pf6_near_kzj_fob_fc_hyd",   "name": "PF 6 NEAR KZJ FOB FACING HYD",       "zone_id": "zone_hyb_pf6",        "zone_type": "PLATFORM",  "location": "PF 6 NEAR KZJ FOB FACING HYD",       "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_pf7_hyd_end",                "name": "PF 7 HYD END",                       "zone_id": "zone_hyb_pf7",        "zone_type": "PLATFORM",  "location": "PF 7 HYD END",                       "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_pf8_mid_fc_kzj",             "name": "PF 8 MID FACING KZJ",                "zone_id": "zone_hyb_pf8",        "zone_type": "PLATFORM",  "location": "PF 8 MID FACING KZJ",                "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_pf8_9_fc_hyd_end",           "name": "PF 8&9 FACING HYD END",              "zone_id": "zone_hyb_pf8",        "zone_type": "PLATFORM",  "location": "PF 8&9 FACING HYD END",              "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_pf10_hyd_end",               "name": "PF 10 HYD END",                      "zone_id": "zone_hyb_pf10",       "zone_type": "PLATFORM",  "location": "PF 10 HYD END",                      "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_pf10_hyd_end_fc_kzj",        "name": "PF 10 HYD END FACING KZJ",           "zone_id": "zone_hyb_pf10",       "zone_type": "PLATFORM",  "location": "PF 10 HYD END FACING KZJ",           "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_outward_parcel_pf1_entr",    "name": "OUTWARD PARCEL PF 1 ENTRANCE",       "zone_id": "zone_hyb_pf1",        "zone_type": "PLATFORM",  "location": "OUTWARD PARCEL PF 1 ENTRANCE",       "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_pf1_parking_entr",           "name": "PF 1 PARKING ENTRANCE",              "zone_id": "zone_hyb_parking",    "zone_type": "PLATFORM",  "location": "PF 1 PARKING ENTRANCE",              "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_pf9_fc_hyd",                 "name": "PF 9 MIDDLE FACING HYB",             "zone_id": "zone_hyb_pf9",        "zone_type": "PLATFORM",  "location": "PF 9 MIDDLE FACING HYB",             "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_mid_4_5",                    "name": "PF 4&5 MIDDLE",                      "zone_id": "zone_hyb_pf4",        "zone_type": "PLATFORM",  "location": "PF 4&5 MIDDLE",                      "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_pf10_bme_fc_hyd",            "name": "PF 10 OPP BASEMENT FACING HYB",      "zone_id": "zone_hyb_pf10",       "zone_type": "PLATFORM",  "location": "PF 10 OPP BASEMENT FACING HYB",      "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_pf10_vip_saloon",            "name": "PF10 VIP SALOON SIDING",             "zone_id": "zone_hyb_pf10",       "zone_type": "PLATFORM",  "location": "PF10 VIP SALOON SIDING",             "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_north_parking",              "name": "NORTH BUILDING PARKING",             "zone_id": "zone_hyb_pf1",        "zone_type": "PLATFORM",  "location": "NORTH BUILDING PARKING",             "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_alpha_exit",                 "name": "ALPHA EXIT",                         "zone_id": "zone_hyb_pf1",        "zone_type": "PLATFORM",  "location": "ALPHA EXIT",                         "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_gate2_wh",                   "name": "GATE 2 WAITING HALL",                "zone_id": "zone_hyb_pf1",        "zone_type": "PLATFORM",  "location": "GATE 2 WAITING HALL",                "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_gate8_parking_entr",         "name": "GATE 8 PARKING ENTRANCE",            "zone_id": "zone_hyb_pf10",       "zone_type": "PLATFORM",  "location": "GATE 8 PARKING ENTRANCE",            "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_pf5_hyd_end",               "name": "PF 5 HYB END",                       "zone_id": "zone_hyb_pf5",        "zone_type": "PLATFORM",  "location": "PF 5 HYB END",                       "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_pf1_near_gate4_fc_kzj",     "name": "PF 1 NEAR GATE 4 FACING KZJ",        "zone_id": "zone_hyb_pf1",        "zone_type": "PLATFORM",  "location": "PF 1 NEAR GATE 4 FACING KZJ",        "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_pf_6_7_mmts_fc_hyd",        "name": "PF 6&7 MMTS BOOKING FACING HYB",     "zone_id": "zone_hyb_pf6",        "zone_type": "PLATFORM",  "location": "PF 6&7 MMTS BOOKING FACING HYB",     "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_hyd_fob_mid_fc_6_7",        "name": "HYB FOB MIDDLE FACING 6&7",          "zone_id": "zone_hyb_pf7",        "zone_type": "PLATFORM",  "location": "HYB FOB MIDDLE FACING 6&7",          "rtsp_url": "rtsp://localhost:8554/mystream"},
    # ── FOB cameras ─────────────────────────────────────────────────────────
    {"camera_id": "cam_pf1_hyd_fob_fc_hyd_end",    "name": "PF 1 HYD FOB FACING HYD END",        "zone_id": "zone_hyb_fob",        "zone_type": "FOB",       "location": "PF 1 HYD FOB FACING HYD END",        "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_pf1_hyd_fob_fc_kzj_end",    "name": "PF 1 HYD FOB FACING KZJ END",        "zone_id": "zone_hyb_fob",        "zone_type": "FOB",       "location": "PF 1 HYD FOB FACING KZJ END",        "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_hyd_fob_fc_6_7",            "name": "HYD FOB MID FACING 6&7",             "zone_id": "zone_hyb_fob",        "zone_type": "FOB",       "location": "HYD FOB MID FACING 6&7",             "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_kzj_fob_pf1_fc_hyd_end",    "name": "PF 1 KZJ FOB FACING HYD END",        "zone_id": "zone_kzj_fob",        "zone_type": "FOB",       "location": "PF 1 KZJ FOB FACING HYD END",        "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_kzj_fob_pf1_fc_kzj_end",    "name": "PF 1 KZJ FOB FACING KZJ END",        "zone_id": "zone_kzj_fob",        "zone_type": "FOB",       "location": "PF 1 KZJ FOB FACING KZJ END",        "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_kzj_fob_mid_4_5",           "name": "KZJ FOB MID FACING 4&5",             "zone_id": "zone_kzj_fob",        "zone_type": "FOB",       "location": "KZJ FOB MID FACING 4&5",             "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_kzj_fob_mid_8_9",           "name": "KZJ FOB MID FACING 8&9",             "zone_id": "zone_kzj_fob",        "zone_type": "FOB",       "location": "KZJ FOB MID FACING 8&9",             "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_pf8_near_kzj_fob_fc_hyd_end","name": "PF 8 NEAR KZJ FOB FACING HYD",      "zone_id": "zone_kzj_fob",        "zone_type": "FOB",       "location": "PF 8 NEAR KZJ FOB FACING HYD",       "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_pf10_fob_steps",             "name": "PF 10 HYD FOB FACING HYD STEPS",    "zone_id": "zone_hyb_fob",        "zone_type": "FOB",       "location": "PF 10 HYD FOB FACING HYD STEPS",    "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_pf10_fob_vip",              "name": "PF 10 HYD FOB FACING VIP ENTRANCE",  "zone_id": "zone_hyb_fob",        "zone_type": "FOB",       "location": "PF 10 HYD FOB FACING VIP ENTRANCE",  "rtsp_url": "rtsp://localhost:8554/mystream"},
    # ── BOOKING cameras ──────────────────────────────────────────────────────
    {"camera_id": "cam_hyd_booking_gate2a",         "name": "GATE 2A ENTRANCE",                   "zone_id": "zone_gate2a_booking",  "zone_type": "BOOKING",   "location": "GATE 2A ENTRANCE",                   "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_near_gate_2a_fc_swathi_ent", "name": "NEAR GATE 2A FACING SWATHI ENT",     "zone_id": "zone_gate2a_booking",  "zone_type": "BOOKING",   "location": "NEAR GATE 2A FACING SWATHI ENT",     "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_gate_5_booking_office",      "name": "GATE 5 BOOKING OFFICE",              "zone_id": "zone_gate5_booking",   "zone_type": "BOOKING",   "location": "GATE 5 BOOKING OFFICE",              "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_prs_booking",                "name": "PRS BOOKING COUNTER",               "zone_id": "zone_hyb_booking",    "zone_type": "BOOKING",   "location": "PRS BOOKING COUNTER",               "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_gate2a_fc_gate2a_path",      "name": "GATE 2A FACING GATE 2 PATHWAY",      "zone_id": "zone_gate2a_booking",  "zone_type": "BOOKING",   "location": "GATE 2A FACING GATE 2 PATHWAY",      "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_rethifile_entr",             "name": "RETHIFILE ENTRANCE",                 "zone_id": "zone_hyb_pf1",        "zone_type": "BOOKING",   "location": "RETHIFILE ENTRANCE",                 "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_gate2a_towards_atvm",        "name": "GATE 2A TOWARDS ATVM",               "zone_id": "zone_gate2a_booking",  "zone_type": "BOOKING",   "location": "GATE 2A TOWARDS ATVM",               "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_pf1_near_gate5_fc_hyd_fob",  "name": "PF 1 NEAR GATE 5 FACING HYB FOB",   "zone_id": "zone_hyb_pf1",        "zone_type": "BOOKING",   "location": "PF 1 NEAR GATE 5 FACING HYB FOB",   "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_gate2_fc_ac_wh",             "name": "GATE 2 FACING AC WAITING HALL",      "zone_id": "zone_gate2a_booking",  "zone_type": "BOOKING",   "location": "GATE 2 FACING AC WAITING HALL",      "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_rethifile_bo",               "name": "RETHIFILE BO/BUS STOP",              "zone_id": "zone_hyb_pf1",        "zone_type": "BOOKING",   "location": "RETHIFILE BO/BUS STOP",              "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_gate2e_fc_parking",          "name": "GATE 2A FACING CAR PARKING",         "zone_id": "zone_gate2a_booking",  "zone_type": "BOOKING",   "location": "GATE 2A FACING CAR PARKING",         "rtsp_url": "rtsp://localhost:8554/mystream"},
    {"camera_id": "cam_gate5_pathway",              "name": "GATE 5 PATHWAY",                     "zone_id": "zone_gate5_booking",   "zone_type": "BOOKING",   "location": "GATE 5 PATHWAY",                     "rtsp_url": "rtsp://localhost:8554/mystream"},
]

# Add Excel cameras to CAMERA_ZONE_MAP
for cam in EXCEL_CAMERAS:
    CAMERA_ZONE_MAP[cam["camera_id"]] = cam["zone_id"]

# ===========================================================================
# ALL_CAMERAS = 17 protected legacy cameras + 44 Excel cameras
# ===========================================================================
LEGACY_ALL = HYB_FOB_CAMERAS + KZJ_FOB_CAMERAS + MID_FOB_CAMERAS + PLATFORM_CAMERAS + BOOKING_CAMERAS
ALL_CAMERAS = (
    [cam for cam in LEGACY_ALL if cam["camera_id"] in KEEP_17_CAMERA_IDS]
    + EXCEL_CAMERAS
)


# ============================================================================
# ZONE ADJACENCY (macro — routing)
# ============================================================================

def build_zone_adjacency():
    """Every platform ↔ all 3 FOBs, FOBs ↔ each other."""
    adj = {}

    def add_edge(a, b):
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)

    fob_zones = ["zone_hyb_fob", "zone_kzj_fob", "zone_mid_fob"]

    # Each platform ↔ all 3 FOBs
    for n in range(1, 11):
        for fob in fob_zones:
            add_edge(f"zone_hyb_pf{n}", fob)

    # FOBs adjacent to each other (reachable via platform stairs)
    add_edge("zone_hyb_fob", "zone_kzj_fob")
    add_edge("zone_hyb_fob", "zone_mid_fob")
    add_edge("zone_kzj_fob", "zone_mid_fob")

    return {k: sorted(v) for k, v in adj.items()}


# ============================================================================
# CAMERA ADJACENCY (micro — flow detection)
# ============================================================================

# Platform camera → nearest FOB camera on each bridge
# Covers both legacy (cam_hyb_pf{n}) and multi-cam (_a/_b/_c) variants.
# _a = start (near HYB stairs), _b = middle, _c = far end
PLATFORM_CAM_TO_FOB_CAM = {
    # --- PF1 ---
    "cam_hyb_pf1":   ["cam_pf1_fob_kzj",     "cam_kzj_pf1_fob_kzj",  "cam_mid_fob_pf1"],
    "cam_hyb_pf1_a": ["cam_pf1_fob_kzj",     "cam_kzj_pf1_fob_kzj",  "cam_mid_fob_pf1"],
    "cam_hyb_pf1_b": ["cam_pf1_fob_kzj",     "cam_kzj_pf1_fob_kzj",  "cam_mid_fob_pf1"],
    "cam_hyb_pf1_c": ["cam_pf1_fob_kzj",     "cam_kzj_pf1_fob_kzj",  "cam_mid_fob_pf1"],
    # --- PF2 ---
    "cam_hyb_pf2":   ["cam_pf1_fob_pf10",    "cam_kzj_pf1_fob_pf10", "cam_mid_fob_pf1"],
    "cam_hyb_pf2_a": ["cam_pf1_fob_pf10",    "cam_kzj_pf1_fob_pf10", "cam_mid_fob_pf1"],
    "cam_hyb_pf2_b": ["cam_pf1_fob_pf10",    "cam_kzj_pf1_fob_pf10", "cam_mid_fob_pf1"],
    "cam_hyb_pf2_c": ["cam_pf1_fob_pf10",    "cam_kzj_pf1_fob_pf10", "cam_mid_fob_pf1"],
    # --- PF3 ---
    "cam_hyb_pf3":   ["cam_pf1_fob_hyb_end", "cam_kzj_pf1_fob_hyb",  "cam_mid_fob_pf1"],
    "cam_hyb_pf3_a": ["cam_pf1_fob_hyb_end", "cam_kzj_pf1_fob_hyb",  "cam_mid_fob_pf1"],
    "cam_pf1_hyd_fob_fc_hyd_end": ["cam_pf1_fob_hyb_end", "cam_kzj_pf1_fob_hyb",  "cam_mid_fob_pf1"],
    "cam_hyb_pf3_c": ["cam_pf1_fob_hyb_end", "cam_kzj_pf1_fob_hyb",  "cam_mid_fob_pf1"],
    # --- PF4 ---
    "cam_hyb_pf4":   ["cam_middle_fob_4_5",  "cam_kzj_fob_mid_4_5",  "cam_mid_fob_center"],
    "cam_hyb_pf4_a": ["cam_middle_fob_4_5",  "cam_kzj_fob_mid_4_5",  "cam_mid_fob_center"],
    "cam_hyb_pf4_b": ["cam_middle_fob_4_5",  "cam_kzj_fob_mid_4_5",  "cam_mid_fob_center"],
    "cam_hyb_pf4_c": ["cam_middle_fob_4_5",  "cam_kzj_fob_mid_4_5",  "cam_mid_fob_center"],
    # --- PF5 ---
    "cam_hyb_pf5":   ["cam_middle_fob_4_5",  "cam_kzj_fob_mid_4_5",  "cam_mid_fob_center"],
    "cam_hyb_pf5_a": ["cam_middle_fob_4_5",  "cam_kzj_fob_mid_4_5",  "cam_mid_fob_center"],
    "cam_hyb_pf5_b": ["cam_middle_fob_4_5",  "cam_kzj_fob_mid_4_5",  "cam_mid_fob_center"],
    "cam_hyb_pf5_c": ["cam_middle_fob_4_5",  "cam_kzj_fob_mid_4_5",  "cam_mid_fob_center"],
    # --- PF6 ---
    "cam_hyb_pf6":   ["cam_middle_fob_6_7",  "cam_kzj_fob_mid_8_9",  "cam_mid_fob_center"],
    "cam_hyb_pf6_a": ["cam_middle_fob_6_7",  "cam_kzj_fob_mid_8_9",  "cam_mid_fob_center"],
    "cam_hyb_pf6_b": ["cam_middle_fob_6_7",  "cam_kzj_fob_mid_8_9",  "cam_mid_fob_center"],
    "cam_hyb_pf6_c": ["cam_middle_fob_6_7",  "cam_kzj_fob_mid_8_9",  "cam_mid_fob_center"],
    # --- PF7 ---
    "cam_hyb_pf7":   ["cam_middle_fob_6_7",  "cam_kzj_fob_mid_8_9",  "cam_mid_fob_center"],
    "cam_hyb_pf7_a": ["cam_middle_fob_6_7",  "cam_kzj_fob_mid_8_9",  "cam_mid_fob_center"],
    "cam_hyb_pf7_b": ["cam_middle_fob_6_7",  "cam_kzj_fob_mid_8_9",  "cam_mid_fob_center"],
    "cam_hyb_pf7_c": ["cam_middle_fob_6_7",  "cam_kzj_fob_mid_8_9",  "cam_mid_fob_center"],
    # --- PF8 ---
    "cam_hyb_pf8":   ["cam_pf10_fob_pf1",    "cam_kzj_fob_escalator", "cam_mid_fob_pf10"],
    "cam_hyb_pf8_a": ["cam_pf10_fob_pf1",    "cam_kzj_fob_escalator", "cam_mid_fob_pf10"],
    "cam_hyb_pf8_b": ["cam_pf10_fob_pf1",    "cam_kzj_fob_escalator", "cam_mid_fob_pf10"],
    "cam_hyb_pf8_c": ["cam_pf10_fob_pf1",    "cam_kzj_fob_escalator", "cam_mid_fob_pf10"],
    # --- PF9 ---
    "cam_hyb_pf9":   ["cam_pf10_fob_pf1",    "cam_kzj_fob_escalator", "cam_mid_fob_pf10"],
    "cam_hyb_pf9_a": ["cam_pf10_fob_pf1",    "cam_kzj_fob_escalator", "cam_mid_fob_pf10"],
    "cam_hyb_pf9_b": ["cam_pf10_fob_pf1",    "cam_kzj_fob_escalator", "cam_mid_fob_pf10"],
    "cam_hyb_pf9_c": ["cam_pf10_fob_pf1",    "cam_kzj_fob_escalator", "cam_mid_fob_pf10"],
    # --- PF10 ---
    "cam_hyb_pf10":   ["cam_pf10_fob_steps",  "cam_kzj_fob_escalator", "cam_mid_fob_pf10"],
    "cam_hyb_pf10_a": ["cam_pf10_fob_steps",  "cam_kzj_fob_escalator", "cam_mid_fob_pf10"],
    "cam_hyb_pf10_b": ["cam_pf10_fob_steps",  "cam_kzj_fob_escalator", "cam_mid_fob_pf10"],
    "cam_hyb_pf10_c": ["cam_pf10_fob_steps",  "cam_kzj_fob_escalator", "cam_mid_fob_pf10"],
}

# FOB internal camera adjacency (linear walkway chain)
HYB_FOB_CAM_LINEAR = [
    "cam_pf1_fob_kzj", "cam_pf1_fob_pf10", "cam_pf1_fob_hyb_end",
    "cam_middle_fob_4_5", "cam_middle_fob_6_7",
    "cam_pf10_fob_pf1", "cam_pf10_fob_steps",
]
KZJ_FOB_CAM_LINEAR = [
    "cam_kzj_pf1_fob_kzj", "cam_kzj_pf1_fob_pf10", "cam_kzj_pf1_fob_hyb",
    "cam_kzj_fob_mid_4_5", "cam_kzj_fob_mid_8_9", "cam_kzj_fob_escalator",
]
MID_FOB_CAM_LINEAR = [
    "cam_mid_fob_pf1", "cam_mid_fob_center", "cam_mid_fob_pf10",
]


def build_camera_adjacency():
    """Platform cam ↔ FOB cam + FOB internal linear."""
    adj = {}

    def add_edge(a, b):
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)

    # Platform cam ↔ FOB cam
    for pf_cam, fob_cams in PLATFORM_CAM_TO_FOB_CAM.items():
        for fob_cam in fob_cams:
            add_edge(pf_cam, fob_cam)

    # FOB internal linear
    for linear in [HYB_FOB_CAM_LINEAR, KZJ_FOB_CAM_LINEAR, MID_FOB_CAM_LINEAR]:
        for i in range(len(linear) - 1):
            add_edge(linear[i], linear[i + 1])

    return {k: sorted(v) for k, v in adj.items()}


# ============================================================================
# SEEDING FUNCTIONS
# ============================================================================

async def remove_old_zones(db):
    """Remove old granular FOB zones (replaced by consolidated FOB zones)."""
    old_ids = OLD_HYB_FOB_ZONE_IDS + OLD_KZJ_FOB_ZONE_IDS
    result = await db.zones.delete_many({"zone_id": {"$in": old_ids}})
    logger.info(f"  Removed {result.deleted_count} old granular FOB zones")
    return result.deleted_count


async def seed_zones(db):
    """Create all zones."""
    now = datetime.now(UTC)
    created = 0
    skipped = 0

    for zone in ZONES:
        existing = await db.zones.find_one({"zone_id": zone["zone_id"]})
        if existing:
            logger.info(f"  [SKIP] {zone['zone_id']} already exists")
            skipped += 1
            continue

        zone_doc = {
            **zone,
            "station_id": STATION_ID,
            "svg_region_id": zone["zone_id"],  # backward compat
            "adjacent_zones": [],
            "area_m2": None,
            "capacity": None,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        await db.zones.insert_one(zone_doc)
        logger.info(f"  [OK] {zone['zone_id']} ({zone['zone_name']})")
        created += 1

    logger.info(f"\n  Zones: {created} created, {skipped} skipped")
    return created


async def seed_cameras(db):
    """Create or update all cameras."""
    now = datetime.now(UTC)
    created = 0
    updated = 0
    skipped = 0

    for cam in ALL_CAMERAS:
        zone_id = CAMERA_ZONE_MAP[cam["camera_id"]]
        existing = await db.cameras.find_one({"camera_id": cam["camera_id"]})

        if existing:
            # Update existing camera: reassign zone_id + set svg_region_id
            update_fields = {
                "zone_id": zone_id,
                "svg_region_id": cam["camera_id"],
                "name": cam["name"],
                "updated_at": now,
            }
            # Don't overwrite real RTSP URLs with placeholders
            if not existing.get("rtsp_url") or existing["rtsp_url"].startswith("rtsp://localhost"):
                update_fields["rtsp_url"] = cam["rtsp_url"]

            await db.cameras.update_one(
                {"camera_id": cam["camera_id"]},
                {"$set": update_fields}
            )
            logger.info(f"  [UPD] {cam['camera_id']} → {zone_id}")
            updated += 1
            continue

        cam_doc = {
            "camera_id": cam["camera_id"],
            "name": cam["name"],
            "rtsp_url": cam["rtsp_url"],
            "location": cam.get("location"),
            "zone_id": zone_id,
            "adjacent_cameras": [],
            "svg_region_id": cam["camera_id"],
            "status": "active",
            "is_active": True,
            "settings": {
                "target_fps": 1,
                "enable_analytics": True,
                "enable_alerts": True,
                "enable_heatmaps": False,
            },
            "created_at": now,
            "updated_at": now,
        }
        await db.cameras.insert_one(cam_doc)
        logger.info(f"  [OK] {cam['camera_id']} → {zone_id}")
        created += 1

    logger.info(f"\n  Cameras: {created} created, {updated} updated")
    return created + updated


async def update_zone_adjacency(db):
    """Set adjacent_zones on all affected zones."""
    adjacency = build_zone_adjacency()
    now = datetime.now(UTC)
    updated = 0

    for zone_id, adj_list in adjacency.items():
        result = await db.zones.update_one(
            {"zone_id": zone_id},
            {"$set": {"adjacent_zones": adj_list, "updated_at": now}}
        )
        if result.matched_count > 0:
            logger.info(f"  [OK] {zone_id} → {len(adj_list)} adjacent")
            updated += 1
        else:
            logger.info(f"  [WARN] {zone_id} not found in DB")

    logger.info(f"\n  Zone adjacency: {updated} zones updated")
    return updated


async def update_camera_adjacency(db):
    """Set adjacent_cameras on all affected cameras."""
    adjacency = build_camera_adjacency()
    now = datetime.now(UTC)
    updated = 0

    for camera_id, adj_list in adjacency.items():
        result = await db.cameras.update_one(
            {"camera_id": camera_id},
            {"$set": {"adjacent_cameras": adj_list, "updated_at": now}}
        )
        if result.matched_count > 0:
            logger.info(f"  [OK] {camera_id} → {len(adj_list)} adjacent")
            updated += 1
        else:
            logger.info(f"  [WARN] {camera_id} not found in DB")

    logger.info(f"\n  Camera adjacency: {updated} cameras updated")
    return updated


# ============================================================================
# MAIN
# ============================================================================

async def main():
    parser = argparse.ArgumentParser(description="Unified station seed: zones + cameras + adjacency")
    parser.add_argument("--clear", action="store_true", help="Wipe ALL zones and cameras, re-seed from scratch")
    args = parser.parse_args()

    settings = get_settings()

    logger.info(f"[INFO] MongoDB: {settings.mongodb_uri}")
    logger.info(f"[INFO] Database: {settings.mongodb_database}")
    logger.info(f"[INFO] Station: {STATION_ID}")
    logger.info("")

    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_database]

    try:
        await client.admin.command("ping")
        logger.info("[OK] MongoDB connected\n")

        if args.clear:
            logger.info("=" * 50)
            logger.info("CLEARING ALL DATA")
            logger.info("=" * 50)
            r1 = await db.zones.delete_many({"station_id": STATION_ID})
            r2 = await db.cameras.delete_many({})
            logger.info(f"  Removed {r1.deleted_count} zones, {r2.deleted_count} cameras\n")
        else:
            # Remove old granular FOB zones (migration)
            logger.info("=" * 50)
            logger.info("REMOVING OLD GRANULAR FOB ZONES")
            logger.info("=" * 50)
            await remove_old_zones(db)
            logger.info("")

        # 1. Seed zones
        logger.info("=" * 50)
        logger.info(f"SEEDING ZONES ({len(ZONES)})")
        logger.info("=" * 50)
        await seed_zones(db)

        # 2. Seed cameras
        logger.info("")
        logger.info("=" * 50)
        logger.info(f"SEEDING CAMERAS ({len(ALL_CAMERAS)})")
        logger.info("=" * 50)
        await seed_cameras(db)

        # 3. Zone adjacency
        logger.info("")
        logger.info("=" * 50)
        logger.info("ZONE ADJACENCY (macro — routing)")
        logger.info("=" * 50)
        await update_zone_adjacency(db)

        # 4. Camera adjacency
        logger.info("")
        logger.info("=" * 50)
        logger.info("CAMERA ADJACENCY (micro — flow)")
        logger.info("=" * 50)
        await update_camera_adjacency(db)

        # 5. Summary
        logger.info("")
        logger.info("=" * 50)
        logger.info("SUMMARY")
        logger.info("=" * 50)
        total_zones = await db.zones.count_documents({"station_id": STATION_ID})
        total_cameras = await db.cameras.count_documents({})
        zones_adj = await db.zones.count_documents({"adjacent_zones": {"$ne": []}})
        cams_adj = await db.cameras.count_documents({"adjacent_cameras": {"$ne": []}})
        logger.info(f"  Total zones:               {total_zones}")
        logger.info(f"  Total cameras:             {total_cameras}")
        logger.info(f"  Zones with adjacency:      {zones_adj}")
        logger.info(f"  Cameras with adjacency:    {cams_adj}")
        logger.info("")
        logger.info("[DONE] Seeding complete!")
        return 0

    except Exception as e:
        logger.error(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        client.close()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
