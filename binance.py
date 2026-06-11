import os 
from dotenv import load_dotenv
from binance.client import Client
import binance
from binance.async_client import AsyncClient
from binance.exceptions import BinanceAPIException
from fastapi import FastAPI

load_dotenv()

api_key = os.getenv("BINANCE_TESTNET_API_KEY")
api_secret = os.getenv("BINANCE_TESTNET_SECRET_KEY")

client = Client(api_key, api_secret, testnet=True)

app = FastAPI()

@app.get("/test_trade/{crypto}")
def signal(crypto:str):
    return(client.get_account())



    

