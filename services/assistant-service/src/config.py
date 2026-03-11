import os
from dotenv import load_dotenv

load_dotenv()

#Retrieval service
RETRIEVAL_BASE_URL = os.getenv("RETRIEVAL_BASE_URL","http://127.0.0.1:8001")

#LLM Provider (placeholder for now)
LLM_PROVIDER = os.getenv("LLM_PROVIDER","grok") #grok / openai /local

#Phase control
PHASE = "phase1"