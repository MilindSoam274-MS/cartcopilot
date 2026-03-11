#Step 4.5D — Handlers for each intent
import re

def handle_search(items):
    return items

def handle_refine_cheapest(items):
    return sorted(items,key=lambda x: x.get("price") or 1e18)

def handle_refine_best(items):
    # proxy: higher semantic score = tastier
    return sorted(items,key=lambda x : x.score,reverse=True)

def handle_compare(items,message:str):
    # compare option numbers mentioned by user
    #nums = [int(s) for s in message.split() if s.isdigit()]
    nums = [int(n) for n in re.findall(r"\b\d+\b", message)]
    selected=[]
    for n in nums:
        if 1<=n<=len(items):
            selected.append(items[n-1])
    
    return selected

def handle_addons(items):
    # Phase 1: just reuse similar items
    return items[:3]