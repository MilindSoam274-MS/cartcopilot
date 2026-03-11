from .db import get_conn
from .config import PHASE1_MODE,RESTAURANTS_TABLE,MENU_ITEMS_TABLE

def main():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) from {RESTAURANTS_TABLE};")
            cur.execute(f"select count(*) from {MENU_ITEMS_TABLE};")
            restaurants_count = cur.fetchone()[0]

            cur.execute(f"select city,count(*) from {MENU_ITEMS_TABLE} Group by city order by count(*) DESC;")
            city_counts = cur.fetchall()

    print("PHASE1_MODE = ", PHASE1_MODE)
    print("RESTAURANTS_TABLE = ",RESTAURANTS_TABLE, "count = ",restaurants_count)
    print("MENU_ITEMS_TABLE = ",MENU_ITEMS_TABLE)
    print("City counts: ")
    for city,cnt in city_counts:
        print(f" - {city} : {cnt}")

if __name__ == "__main__":
    main()