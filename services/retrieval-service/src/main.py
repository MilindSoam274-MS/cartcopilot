#Retrieval logic (FAISS → DB → filters → final)

from fastapi import FastAPI
from typing import List

from .faiss_store import FaissStore
from .schemas import RetrieveRequest, RetrieveResponse, RetrievedItem
from .db import get_conn
from .config import (
    MENU_ITEMS_TABLE, TOP_K, RETURN_K, INDEX_VERSION,
    MIN_TOP1_SCORE, MIN_TOP1_MINUS_TOP2
)

app = FastAPI(title="CartCopilot Retrieval Service", version="0.1")

store = FaissStore()

@app.on_event("startup")
def startup():
    store.load()

def fetch_items(item_ids: List[str]):
    # Pull structured fields for filtering/ranking
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT item_id, item_name, category, price, veg_flag, city, restaurant_id
                FROM {MENU_ITEMS_TABLE}
                WHERE item_id = ANY(%s)
                """,
                (item_ids,)
            )
            return cur.fetchall()

def apply_filters(rows, req: RetrieveRequest):
    out = []
    for r in rows:
        item_id, item_name, category, price, veg_flag, city, restaurant_id = r

        if req.city and city != req.city:
            continue
        if req.veg_flag and (veg_flag is None or str(veg_flag).lower() != req.veg_flag.lower()):
            continue
        if req.max_price is not None and (price is None or float(price) > float(req.max_price)):
            continue
        if req.category and (category is None or req.category.lower() not in str(category).lower()):
            continue

        out.append(r)
    return out

def relax_filters(req: RetrieveRequest) -> RetrieveRequest:
    # Only relax price, keep city/veg strict
    relaxed = req.model_copy(deep=True)
    if relaxed.max_price is not None:
        relaxed.max_price = float(relaxed.max_price) * 1.2  # +20%
    return relaxed

def confidence_label(scores: List[float]) -> str:
    if not scores:
        return "low"
    top1 = scores[0]
    top2 = scores[1] if len(scores) > 1 else 0.0
    if top1 >= MIN_TOP1_SCORE and (top1 - top2) >= MIN_TOP1_MINUS_TOP2:
        return "high"
    if top1 >= MIN_TOP1_SCORE:
        return "medium"
    return "low"

@app.post("/retrieve", response_model=RetrieveResponse)
def retrieve(req: RetrieveRequest):
    # 1) FAISS candidates
    scores, vector_ids = store.search(req.query, TOP_K)
    item_ids = store.vector_ids_to_item_ids(vector_ids)

    # keep aligned tuples (score, item_id)
    pairs = [(scores[i], item_ids[i]) for i in range(len(item_ids)) if item_ids[i] is not None]

    # 2) Fetch rows from DB for candidate ids
    candidate_ids = [p[1] for p in pairs]
    '''
    Visualizing the Extraction
    Think of the list comprehension [p[1] for p in pairs] as a factory line moving from right to left:
    1. for p in pairs: Python looks at the first pair: (0.62, "id_bbb").
    2. p[1]: It grabs the item at index 1 (the string). In Python, counting starts at 0, so 0 is the number and 1 is the ID.
    3. [...]: It "collects" that ID and moves to the next pair until the list is finished.

    Why use p[1]?
    In your data, each "pair" is a tuple. Here is how Python sees the first one:
    Index	Value
    p[0]	0.62 (The Score)
    p[1]	"id_bbb" (The ID)
    By calling p[1], you are telling Python: "Ignore the decimal numbers, I only want the names."
    '''

    #Alternate and better readable approach
    '''
    Using names instead of index numbers makes your code much easier for others (and your future self) to read. This is called Tuple Unpacking.
    Instead of referring to the data as p[1], you can give each part of the pair a specific label.
    The Readable Approach
    Since each pair contains a score and an ID, you can write the list comprehension like this:
    python:
    => candidate_ids = [candidate_id for (score, candidate_id) in pairs]


    Why this is better:
    Self-Explaining: You don't have to remember that [1] means the ID; the word candidate_id tells you exactly what is being extracted.
    Clarity: It explicitly shows the structure of the data you are working with—a number followed by a string.
    How it works step-by-step:
    Deconstruct: For every item in pairs, Python "unpacks" the tuple. It assigns the first value to the variable score and the second value to candidate_id.
    Select: It ignores score and only keeps the candidate_id.
    Result: You get the same list as before: ["id_bbb", "id_aaa", "id_ccc", "id_ddd"].
    A Pro Tip: The "Throwaway" Variable
    If you know you are never going to use the score, Python developers often use an underscore (_) as a placeholder. This signals to anyone reading the code: "I know there is a score here, but I'm intentionally ignoring it."
    python:
    => candidate_ids = [candidate_id for (_, candidate_id) in pairs]
    '''

    rows = fetch_items(candidate_ids)

    # 3) Apply structured filters
    filtered = apply_filters(rows, req)

    fallback_used = False
    relaxed_req = None

    # If too few results, try relaxing only the max_price a bit
    if len(filtered) < min(3, RETURN_K):
        relaxed_req = relax_filters(req)
        filtered = apply_filters(rows, relaxed_req)
        fallback_used = True

    # 4) Keep original FAISS order + attach scores
    score_lookup = {item_id: sc for sc, item_id in pairs}

    results = []
    for r in filtered:
        item_id, item_name, category, price, veg_flag, city, restaurant_id = r
        results.append(
            RetrievedItem(
                item_id=item_id,
                item_name=item_name,
                category=category,
                price=float(price) if price is not None else None,
                veg_flag=veg_flag,
                city=city,
                restaurant_id=int(restaurant_id),
                score=float(score_lookup.get(item_id, 0.0))
            )
        )

    # sort by score desc and return top RETURN_K
    results.sort(key=lambda x: x.score, reverse=True)
    results = results[:RETURN_K]

    conf = confidence_label(scores)

    return RetrieveResponse(
        index_version=INDEX_VERSION,
        top1_score=float(scores[0]) if scores else 0.0,
        confidence=conf,
        results=results,
        debug={
            "requested_filters": req.model_dump(),
            "faiss_top_k": TOP_K,
            "returned_k": len(results),
            "fallback_used": fallback_used,
            "relaxed_filters": relaxed_req.model_dump() if relaxed_req else None,
        }
    )

@app.get("/health")
def health():
    return {"ok": True, "index_version": INDEX_VERSION}

#Why this design works:

# 1. FAISS finds semantic candidates

# 2. DB applies strict constraints (price/city/veg/category)

# 3. Same “Veg burger under 200” query will now actually respect price if 
#    present