#Build the FAISS index (core logic)

import os
import numpy as np
import faiss
import psycopg2

from sentence_transformers import SentenceTransformer
from .db import get_conn
from .config import MENU_ITEMS_TABLE,EMBEDDING_MODEL_NAME,INDEX_DIR
from .index_utils import generate_index_version,ensure_dir,save_json

BATCH_SIZE = 1024 #Safe For CPU

def fetch_menu_items():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                select item_id,embedding_text
                from {MENU_ITEMS_TABLE} 
                order by item_id
                """
            )
            return cur.fetchall()

def main():
    print("🔹 Starting FAISS index build")

    index_version = generate_index_version()
    index_path = os.path.join(INDEX_DIR, f"faiss_{index_version}.index")
    mapping_path = os.path.join(INDEX_DIR,f"mapping_{index_version}.json")
    metadata_path = os.path.join(INDEX_DIR,f"metadata_{index_version}.json")

    ensure_dir(INDEX_DIR)

    print("🔹 Loading embedding model:", EMBEDDING_MODEL_NAME)
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)

    rows = fetch_menu_items()
    print(f"🔹 Fetched {len(rows)} menu items")

    texts = [r[1] for r in rows]
    item_ids = [r[0] for r in rows]

    print("🔹 Generating embeddings (this may take time)...")
    embeddings = model.encode(
        texts,
        batch_size = BATCH_SIZE,
        show_progress_bar=True,
        normalize_embeddings=True
    )

    embeddings = np.asarray(embeddings,dtype="float32")
    dim = embeddings.shape[1]

    print(f"🔹 Embedding dimension: {dim}")

    print("🔹 Creating FAISS index")
    index = faiss.IndexFlatIP(dim) #cosine similarity via inner product
    index.add(embeddings)

    print("🔹 Saving FAISS index")
    faiss.write_index(index,index_path)

    print("🔹 Saving vector_id → item_id mapping")
    vector_map = {str(i): item_ids[i] for i in range(len(item_ids))}
    save_json(mapping_path,vector_map)

    print("🔹 Saving index metadata")
    metadata = {
        "index_version": index_version,
        "embedding_model": EMBEDDING_MODEL_NAME,
        "item_count": len(item_ids),
        "dimension": dim,
        "phase": "phase1",
        "similarity": "cosine",
    }

    save_json(metadata_path,metadata)

    print("✅ FAISS index build complete")
    print("Index version:", index_version)

if __name__ == "__main__":
    main()