import os
from dotenv import load_dotenv
from pathlib import Path


DB_HOST = os.getenv("DB_HOST","localhost")
DB_PORT = os.getenv("DB_PORT","5432")
DB_NAME = os.getenv("DB_NAME","cartcopilot")
DB_USER = os.getenv("DB_USER","cartcopilot")
DB_PASSWORD = os.getenv("DB_PASSWORD","cartcopilot")

'''
PROJECT_ROOT = os.getenv("PROJECT_ROOT",".")
CSV_PATH = os.getenv("CSV_PATH",f"{PROJECT_ROOT}/Dataset/Swiggy.csv")
SCHEMA_PATH = os.getenv("SCHEMA_PATH",f"{PROJECT_ROOT}/services/catalog-service/src/schema.sql")
'''
#The above won't work if we are calling this from different directory
#Therefore, the correct way is : 
PROJECT_ROOT = Path(__file__).resolve().parents[3]
CSV_PATH = PROJECT_ROOT/"Dataset"/"Swiggy.csv"
SCHEMA_PATH = PROJECT_ROOT/"services"/"catalog-service"/"src"/"schema.sql"

#Already remapped in the dataset itself therefore no need to remap again via below

#City Remap (locked)
CITY_REMAP = {
    "Abohar" : "Delhi",
    "Adoni" : "Mumbai",
    #Bangalore already present in the dataset as it is
}

PHASE1_MODE = os.getenv("PHASE1_MODE","true").lower() == "true"

RESTAURANTS_TABLE = "phase1_restaurants" if PHASE1_MODE else "restaurants"
MENU_ITEMS_TABLE = "phase1_menu_items" if PHASE1_MODE else "menu_items"