import os
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "cartcopilot")
DB_USER = os.getenv("DB_USER", "cartcopilot")
DB_PASSWORD = os.getenv("DB_PASSWORD", "cartcopilot")

#Phase 1 tables (already verified)
MENU_ITEMS_TABLE = "phase1_menu_items"

#Embedding model
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

#Index output paths
INDEX_DIR = os.getenv("INDEX_DIR", "./indexes")