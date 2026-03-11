#Why: One place to control “which index”, “how many results”, and confidence logic.

import os
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "cartcopilot")
DB_USER = os.getenv("DB_USER", "cartcopilot")
DB_PASSWORD = os.getenv("DB_PASSWORD", "cartcopilot")

# Always use Phase 1 view in Phase 1
MENU_ITEMS_TABLE = os.getenv("MENU_ITEMS_TABLE", "phase1_menu_items")

# Embeddings
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")

# FAISS artifacts
INDEX_DIR = os.getenv("INDEX_DIR", "../index-service/indexes")

# IMPORTANT: set this to your built version
INDEX_VERSION = os.getenv("INDEX_VERSION", "20260204_0625")

# Retrieval knobs
TOP_K = int(os.getenv("TOP_K", "80"))  # how many candidates from FAISS before filters
RETURN_K = int(os.getenv("RETURN_K", "5"))  # final results returned to client

# Confidence thresholds (simple, works well)
MIN_TOP1_SCORE = float(os.getenv("MIN_TOP1_SCORE", "0.45"))
MIN_TOP1_MINUS_TOP2 = float(os.getenv("MIN_TOP1_MINUS_TOP2", "0.02"))