import os
from dotenv import load_dotenv

load_dotenv()

# If running checkout-service on HOST machine:
# REDIS_URL=redis://localhost:6379/0
#
# If running inside docker-compose:
# REDIS_URL=redis://redis:6379/0
REDIS_URL = os.environ.get("REDIS_URL") or "redis://localhost:6379/0"

#TTLs(tunable)

# TTLs (tunable)
CHECKOUT_TTL_SECONDS = int(os.getenv("CHECKOUT_TTL_SECONDS", str(60 * 60)))  # 1 hour
ORDER_TTL_SECONDS = int(os.getenv("ORDER_TTL_SECONDS", str(60 * 60 * 24 * 7)))  # 7 days (or set to 0 later for no TTL)