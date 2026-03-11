import os
import json
import numpy as np
import faiss

from sentence_transformers import SentenceTransformer

from .config import EMBEDDING_MODEL_NAME, INDEX_DIR
from .db import get_conn

# Change this to the version you see in /indexes
#INDEX_VERSION = os.getenv("INDEX_VERSION", "")
INDEX_VERSION = "20260204_0625"

TOP_K = 5

def load_artifacts(index_version: str):
    index_path = os.path.join(INDEX_DIR, f"faiss_{index_version}.index")
    mapping_path = os.path.join(INDEX_DIR, f"mapping_{index_version}.json")
    metadata_path = os.path.join(INDEX_DIR, f"metadata_{index_version}.json")

    if not os.path.exists(index_path):
        raise FileNotFoundError(f"Missing index file: {index_path}")
    if not os.path.exists(mapping_path):
        raise FileNotFoundError(f"Missing mapping file: {mapping_path}")
    if not os.path.exists(metadata_path):
        raise FileNotFoundError(f"Missing metadata file: {metadata_path}")

    index = faiss.read_index(index_path)

    with open(mapping_path, "r", encoding="utf-8") as f:
        vector_map = json.load(f)

    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    return index, vector_map, metadata

def fetch_items_by_ids(item_ids):
    # Fetch a few details to validate mapping
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT item_id, item_name, category, price, veg_flag, city, restaurant_id
                FROM phase1_menu_items
                WHERE item_id = ANY(%s)
                """,
                (item_ids,)
            )
            rows = cur.fetchall()

    # Preserve order of item_ids
    lookup = {r[0]: r for r in rows}
    ordered = [lookup.get(i) for i in item_ids]
    return ordered

def main():
    if not INDEX_VERSION:
        raise ValueError("Set INDEX_VERSION env var. Example: $env:INDEX_VERSION='20240208_2215'")

    print("🔹 Loading artifacts for version:", INDEX_VERSION)
    index, vector_map, metadata = load_artifacts(INDEX_VERSION)
    print("✅ Metadata:", metadata)

    model = SentenceTransformer(EMBEDDING_MODEL_NAME)

    query = "veg burger under 200"
    print("\n🔎 Query:", query)

    q_vec = model.encode([query], normalize_embeddings=True)
    q_vec = np.asarray(q_vec, dtype="float32")

    scores, vector_ids = index.search(q_vec, TOP_K)

    vector_ids = vector_ids[0].tolist() #vector_ids = [[id1,id2,..]]
    scores = scores[0].tolist() #scores = [[s1,s2,..]]

    item_ids = [vector_map.get(str(v_id)) for v_id in vector_ids]

    print("\nTop results (vector_id → score → item_id):")
    for v_id, sc, it in zip(vector_ids, scores, item_ids):
        print(f"  {v_id} → {sc:.4f} → {it}")

    # Optional: fetch details from Postgres
    print("\nFetching item details from Postgres...")
    items = fetch_items_by_ids(item_ids)

    print("\nTop results (details):")
    for row in items:
        if row is None:
            print("  ⚠️ Missing item in DB for one result")
            continue
        item_id, item_name, category, price, veg_flag, city, restaurant_id = row
        print(f"  - {item_name} | {category} | ₹{price} | {veg_flag} | {city} | rest_id={restaurant_id}")

    print("\n✅ Sanity search complete.")

if __name__ == "__main__":
    main()