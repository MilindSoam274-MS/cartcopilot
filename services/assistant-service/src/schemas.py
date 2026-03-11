from pydantic import BaseModel
from typing import Optional,Literal,List,Dict

class ChatRequest(BaseModel):
    message: str
    #Step 4.5C — Update schemas to include session_id
    session_id: str #Required now
    '''
    Why:
    1. Needed for follow-up queries
    2. Simulates real chat sessions
    '''
    city:Optional[str] = None
    veg_flag:Optional[str]=None
    max_price:Optional[float] = None

class ChatResponse(BaseModel):
    reply:str
    items:List[Dict]
    confidence:str