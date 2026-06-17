## here's celery (background runner) boilerplate
import os 
import asyncio
from dotenv import load_dotenv
from celery import Celery
from binance.client import Client
from google import genai
from app.db.database import SessionLocal
from app.db import models
from google.genai import types
import json
import requests

load_dotenv()

ai_client = genai.Client()

## import keys from .env
api_key = os.getenv("BINANCE_TESTNET_API_KEY")
api_secret = os.getenv("BINANCE_TESTNET_SECRET_KEY")


# 1) connect celery to redis mailbox
# it looks for redis on port 6379, database 0
redis_url= os.getenv("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery(__name__, broker=redis_url, backend=redis_url)

# 2) Define our long-running Background Task
@celery_app.task
def execute_trade_strategy(crypto_symbol: str):
    
    binance_client = Client(api_key, api_secret, testnet=True) ## no Async functionality becaues celery is strictly synchronous

    lookback = 10
        ## klines is where we get our binance past data from
    past_data_1D = binance_client.get_klines(symbol=crypto_symbol, interval=Client.KLINE_INTERVAL_1DAY, limit=lookback)
        
    closing_prince_history = [] 

        ## in binance index = 4 (DAY[4]) is always the closing price
    for daily in (past_data_1D):
            closing_prince_history.append(float(daily[4]))    
        
     ## SMA's based on Daily 
    SMA10 = sum(closing_prince_history)/10
    SMA5 = sum(closing_prince_history[-5:])/5

    ## Fetch secondary data source (Crypto Fear & Greed Index)
    try:
        fng_response = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5)
        fng_data = fng_response.json()
        current_fng = fng_data['data'][0]['value']
        fng_classification = fng_data['data'][0]['value_classification']
    except Exception:
        current_fng = "Unknown"
        fng_classification = "Unknown"

    prompt = f"""
Analyze this cryptocurrency ({crypto_symbol}). 
The recent 10-day closing prices are: {closing_prince_history}. 
The 5-day SMA is {SMA5} and the 10-day SMA is {SMA10}. 
The current Global Crypto Fear & Greed Index is {current_fng} ({fng_classification}).
Given these quantitative indicators and global sentiment, output a strict trading sentiment (BULLISH, BEARISH, or NEUTRAL) followed by a one-sentence reasoning.
You must return the result as a strict JSON object with exactly two keys: "sentiment" and "reasoning"."""
    
    ai_response = ai_client.models.generate_content(model="gemini-2.5-flash", contents=prompt, config=types.GenerateContentConfig(response_mime_type="application/json"))

    ## convert ai_response into text
    ai_text = ai_response.text 

    ai_dict = json.loads(ai_text) ## converting ai_text into dictionary JSON for main.py to give out to /search
    ## embedding content
    embedding_response = ai_client.models.embed_content(model="gemini-embedding-001", contents=ai_text)

    # We access index [0] because we only sent one piece of text to be embedded
    vector = embedding_response.embeddings[0].values
 


 ###---------------------------------####

    async def save_to_db():
        async with SessionLocal() as db:
            new_analysis = models.TradeAnalysis(
                user_id=1,
                symbol=crypto_symbol,
                sentiment=ai_dict["sentiment"],
                reasoning=ai_dict["reasoning"],
                embedding=vector
            )
            db.add(new_analysis)
            await db.commit()

    asyncio.run(save_to_db())


    

    
    
    



