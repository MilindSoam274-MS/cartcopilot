import hashlib
import pandas as pd

from .db import get_conn
from .config import CSV_PATH, SCHEMA_PATH, CITY_REMAP

REQUIRED_COLS = [
    "city", "subcity", "restaurant_code", "restaurant",
    "rating", "rating_count", "cost", "address",
    "cuisine", "menu", "item", "price", "veg_or_non_veg"
]

def normalize_city(city:str)->str:
    if not isinstance(city,str):
        return ""
    city = city.strip()
    return CITY_REMAP.get(city,city)

def make_item_id(restaurant_id:int, item_name:str, category:str, price)-> str:
    base = f"{restaurant_id}|{item_name}|{category}|{price}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()

def make_embedding_text(row:pd.Series)->str:
    # The text we will embed later for semantic search.
    #Keep it compact but information-dense

    parts = [
        str(row.get("item","")).strip(), #row["item"] would also work 
        f"Category: {str(row.get('menu','')).strip()}", #Similarly here and for others
        f"Cuisine: {str(row.get('cuisine','')).strip()}",
        f"Diet: {str(row.get('veg_or_non_veg','')).strip()}",
        f"Restaurant: {str(row.get('restaurant','')).strip()}",
        f"City: {str(row.get('mapped_city','')).strip()}",
    ]
    #However , .get() is intentional defensive coding
    #row["item"]        # ❌ KeyError → crash
    #row.get("item","") # ✅ returns ""


    return " | ".join([p for p in parts if p and p!= "nan"])

def apply_schema(cur):
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        cur.execute(f.read())

def upsert_city(cur):
    for src,mapped in CITY_REMAP.items():
        cur.execute(
            """
            INSERT INTO city_map(source_city,mapped_city, active)
            VALUES (%s,%s,TRUE)
            ON CONFLICT (source_city) DO UPDATE
            SET mapped_city = EXCLUDED.mapped_city, active=TRUE
            """,
            (src,mapped),
        )

def load():
    df= pd.read_csv(CSV_PATH)

    df = df.rename(
        columns={
            'restaurant code':'restaurant_code',
            'rating count':'rating_count',
        }
    )

    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in CSV: {missing}")
    
    # Basic Cleanup
    df['mapped_city'] = df['city'].apply(normalize_city)

    #Convert restaurant_code safely
    df['restaurant_code'] = pd.to_numeric(df['restaurant_code'],errors="coerce")
    df = df.dropna(subset=["restaurant_code"])
    df["restaurant_code"] = df["restaurant_code"].astype(int)

    #Price cleanup
    df["price"] = pd.to_numeric(df['price'],errors="coerce")

    #Create canonical IDs and embedding_text
    df['item_id'] = df.apply(
        lambda r: make_item_id(
            int(r['restaurant_code']),
            str(r['item']),
            str(r['menu']),
            r['price']
        ),
        axis=1
    )
    df["embedding_text"] = df.apply(make_embedding_text,axis=1)

    #Restaurants: one row per restaurant_id
    restaurants= (
        df[['restaurant_code','mapped_city','subcity','restaurant','cuisine',
            'rating','rating_count','cost','address']].drop_duplicates(
                subset=['restaurant_code']
            ).copy()
    )

    with get_conn() as conn:
        conn.autocommit = False
        with conn.cursor() as cur:
            apply_schema(cur)
            upsert_city(cur)

            #Upsert Restaurants
            for _, r in restaurants.iterrows():
                cur.execute(
                    """
                    INSERT INTO restaurants(restaurant_id, city, subcity, name, cuisine, rating, rating_count, cost_for_two, address)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (restaurant_id) DO UPDATE SET
                    city = EXCLUDED.city,
                    subcity = EXCLUDED.subcity,
                    name = EXCLUDED.name,
                    cuisine = EXCLUDED.cuisine,
                    rating = EXCLUDED.rating,
                    rating_count = EXCLUDED.rating_count,
                    cost_for_two = EXCLUDED.cost_for_two,
                    address = EXCLUDED.address
                    """,
                    (
                        int(r['restaurant_code']),
                        str(r["mapped_city"]),
                        None if pd.isna(r["subcity"]) else str(r["subcity"]),
                        str(r["restaurant"]),
                        None if pd.isna(r["cuisine"]) else str(r["cuisine"]),
                        None if pd.isna(r["rating"]) else str(r["rating"]),
                        None if pd.isna(r["rating_count"]) else str(r["rating_count"]),
                        None if pd.isna(r["cost"]) else str(r["cost"]),
                        None if pd.isna(r["address"]) else str(r["address"]),
                    ),
                )
                #When INSERT happens:

                #Conflict on restaurant_id
                #INSERT is blocked
                #Postgres creates a virtual row called EXCLUDED
                
            # Insert menu items (upsert by item_id)
            for _, r in df.iterrows():
                cur.execute(
                    """
                    INSERT INTO menu_items(item_id, restaurant_id, city, category, item_name, price, veg_flag, cuisine, embedding_text)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (item_id) DO UPDATE SET
                      restaurant_id = EXCLUDED.restaurant_id,
                      city = EXCLUDED.city,
                      category = EXCLUDED.category,
                      item_name = EXCLUDED.item_name,
                      price = EXCLUDED.price,
                      veg_flag = EXCLUDED.veg_flag,
                      cuisine = EXCLUDED.cuisine,
                      embedding_text = EXCLUDED.embedding_text
                    """,
                    (
                        str(r["item_id"]),
                        int(r["restaurant_code"]),
                        str(r["mapped_city"]),
                        None if pd.isna(r["menu"]) else str(r["menu"]),
                        str(r["item"]),
                        None if pd.isna(r["price"]) else float(r["price"]),
                        None if pd.isna(r["veg_or_non_veg"]) else str(r["veg_or_non_veg"]),
                        None if pd.isna(r["cuisine"]) else str(r["cuisine"]),
                        str(r["embedding_text"]),
                    ),
                )
            conn.commit()
    
    print("✅ Load complete.")
    print(f"Rows loaded: restaurants={len(restaurants)}, menu_items={len(df)}")
    print("City remap applied: Abohar→Delhi, Adoni→Mumbai (Bangalore unchanged)")

if __name__ == "__main__":
    load()