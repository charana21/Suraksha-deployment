"""
Standalone script to train models and generate complete 2026 predictions (Jan 1 to Dec 31)
into MongoDB collection `forecasting_data`.
"""
import sys
import os

# Ensure workspace root is on python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("populate_2026_forecast")

from services.forecasting.runner import ForecastingRunner

def main():
    logger.info("=================================================================")
    logger.info("  Starting 2026 UTS & PRS Forecasting Pipeline (Jan 1 - Dec 31) ")
    logger.info("=================================================================")
    
    result = ForecastingRunner.run_pipeline_sync(skip_backtest=True)
    
    logger.info("=================================================================")
    logger.info(f" Pipeline execution completed!")
    logger.info(f" Status: {result.get('status')}")
    logger.info(f" Historical records loaded: {result.get('historical_rows')}")
    logger.info(f" Forecast days generated: {result.get('forecast_days')}")
    logger.info(f" Database save result: {result.get('db_result')}")
    logger.info("=================================================================")
    logger.info(" Now check MongoDB Compass -> forecasting_data collection.")
    logger.info(" You should see 365 documents for all dates from 2026-01-01 to 2026-12-31.")

if __name__ == "__main__":
    main()
