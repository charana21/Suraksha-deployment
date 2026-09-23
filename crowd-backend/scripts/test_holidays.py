"""Test script to check what holidays the library returns for India 2026."""
import sys

try:
    import holidays
    print(f"holidays version: {holidays.__version__}")
    
    # National holidays
    h_national = holidays.country_holidays('IN', years=[2026])
    print(f"\nNational holidays count: {len(h_national)}")
    for d, n in sorted(h_national.items()):
        print(f"  {d}: {n}")
    
    # TG (Telangana) state - correct subdivision code
    print("\n--- TG (Telangana) subdivisions ---")
    try:
        h_ts = holidays.country_holidays('IN', subdiv='TG', years=[2026])
        print(f"TG holidays count: {len(h_ts)}")
        for d, n in sorted(h_ts.items()):
            print(f"  {d}: {n}")
    except Exception as e:
        print(f"TG error: {e}")
    
    # AP (Andhra Pradesh) state
    print("\n--- AP (Andhra Pradesh) subdivisions ---")
    try:
        h_ap = holidays.country_holidays('IN', subdiv='AP', years=[2026])
        print(f"AP holidays count: {len(h_ap)}")
        for d, n in sorted(h_ap.items()):
            print(f"  {d}: {n}")
    except Exception as e:
        print(f"AP error: {e}")

    # Check available subdivisions
    print("\n--- Available IN subdivisions ---")
    try:
        subdivs = holidays.country_holidays('IN').subdivisions
        print(subdivs)
    except Exception as e:
        print(f"Error getting subdivisions: {e}")

except ImportError as e:
    print(f"holidays not installed: {e}")
    sys.exit(1)
