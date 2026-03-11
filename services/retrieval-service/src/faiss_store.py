#Why: FastAPI should load FAISS once on startup, not every request.

import os
import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

from .config import INDEX_DIR, INDEX_VERSION, EMBEDDING_MODEL_NAME

class FaissStore:
    def __init__(self):
        self.index = None
        self.vector_map = None
        self.model = None
        self.metadata = None

    def load(self):
        index_path = os.path.join(INDEX_DIR, f"faiss_{INDEX_VERSION}.index")
        mapping_path = os.path.join(INDEX_DIR, f"mapping_{INDEX_VERSION}.json")
        metadata_path = os.path.join(INDEX_DIR, f"metadata_{INDEX_VERSION}.json")

        if not os.path.exists(index_path):
            raise FileNotFoundError(f"Missing FAISS index: {index_path}")
        if not os.path.exists(mapping_path):
            raise FileNotFoundError(f"Missing mapping: {mapping_path}")
        if not os.path.exists(metadata_path):
            raise FileNotFoundError(f"Missing metadata: {metadata_path}")

        self.index = faiss.read_index(index_path)

        with open(mapping_path, "r", encoding="utf-8") as f:
            self.vector_map = json.load(f)

        with open(metadata_path, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)

        self.model = SentenceTransformer(EMBEDDING_MODEL_NAME)

    def search(self, query: str, top_k: int):
        q_vec = self.model.encode([query], normalize_embeddings=True)
        q_vec = np.asarray(q_vec, dtype="float32")
        scores, vector_ids = self.index.search(q_vec, top_k)
        return scores[0].tolist(), vector_ids[0].tolist()

    def vector_ids_to_item_ids(self, vector_ids):
        return [self.vector_map.get(str(v)) for v in vector_ids]
        #vector_ids = [1, 0] scores = [0.88, 0.82] 
        # item_ids = ["id_bbb", "id_aaa"]
        #Basically this funciton is returning the item_ids
        #["id_bbb", "id_aaa"]