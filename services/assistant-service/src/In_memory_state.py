# Very simple in-memory state (Phase 1 only)
# Later this moves to Redis
#Renamed from state.py to In_memory_state.py
#Now we have moved to Redis , not to be used. 

SESSION_STATE = {}

def get_state(session_id: str) -> dict:
    # setdefault is built-in Python dict method
    return SESSION_STATE.setdefault(session_id, {})

def update_state(session_id: str, updates: dict):
    state = get_state(session_id)
    state.update(updates)