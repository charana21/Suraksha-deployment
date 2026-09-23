import asyncio
from db.mongodb import connect_to_mongo, close_mongo_connection, MongoDB
from config.config import get_settings

async def main():
    settings = get_settings()
    await connect_to_mongo(settings)
    
    # Check 2026-09-14
    doc = await MongoDB.database.forecasting_data.find_one({"date": "2026-09-14"})
    print("2026-09-14 doc:", doc)
    
    # Find all docs with occasion_or_holiday in forecasting_data
    docs = await MongoDB.database.forecasting_data.find(
        {"date": {"$regex": "^2026-"}, "occasion_or_holiday": {"$ne": None, "$ne": ""}},
        {"date": 1, "occasion_or_holiday": 1, "_id": 0}
    ).sort("date", 1).to_list(length=None)
    
    print(f"Total holidays/festivals found in forecasting_data for 2026: {len(docs)}")
    for d in docs:
        print(f"  {d['date']}: {d['occasion_or_holiday']}")
        
    await close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(main())
