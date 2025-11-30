import asyncio
import json
import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

from app.db.session import SessionLocal
from app.models.subscription import Subscription
from app.services.xtream import XtreamClient

async def main():
    db = SessionLocal()
    try:
        # sub = db.query(Subscription).filter(Subscription.is_active == True).first()
        # Search for 'aziza' subscription specifically
        sub = db.query(Subscription).filter(Subscription.name.ilike("%aziza%")).first()
        
        if not sub:
            print("Subscription 'aziza' not found. Falling back to first active.")
            sub = db.query(Subscription).filter(Subscription.is_active == True).first()
            
        if not sub:
            print("No active subscription found.")
            return

        print(f"Using subscription: {sub.name} ({sub.xtream_url})")
        client = XtreamClient(sub.xtream_url, sub.username, sub.password)

        # 1. Fetch Series Info
        print("\n--- Fetching Series Categories ---")
        categories = await client.get_series_categories()
        if categories:
            cat_id = categories[0]['category_id']
            print(f"Using Category ID: {cat_id}")
            
            print(f"Fetching series for category {cat_id}...")
            series_list = await client.get_series(category_id=cat_id)
            
            if series_list:
                series_id = series_list[0]['series_id']
                print(f"Fetching info for Series ID: {series_id}")
                series_info = await client.get_series_info(series_id)
                print(json.dumps(series_info, indent=2))
            else:
                print("No series found in this category.")
        else:
            print("No series categories found.")

        # 2. Fetch Movie Info
        print("\n--- Fetching VOD Info for ID 152579 ---")
        vod_id = "152579"
        try:
            vod_info = await client.get_vod_info(vod_id)
            print(json.dumps(vod_info, indent=2))
        except Exception as e:
            print(f"Error fetching VOD info: {e}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
