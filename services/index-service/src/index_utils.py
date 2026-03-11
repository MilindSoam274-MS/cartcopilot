import os
import json
from datetime import datetime

def generate_index_version():
    return datetime.utcnow().strftime("%Y%m%d_%H%M")

#Creates a directory if it doesn’t already exist.
def ensure_dir(path:str):
    os.makedirs(path, exist_ok=True)
    #Why exist_ok=True? 
    #Prevents -> FileExistsError
    #So you can safely call it every time.

#Writes a Python dictionary to a JSON file.
def save_json(path:str,data:dict):
    with open(path,"w",encoding="utf-8") as f:
        #json.dumps(data,f,indent=2) #dumps returns string
        json.dump(data,f,indent=2)  #dump writes to file
