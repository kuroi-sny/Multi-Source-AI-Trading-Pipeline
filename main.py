from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
import models, schemas, database
from database import get_db
from binance.async_client import AsyncClient
from binance.exceptions import BinanceAPIException
from sqlalchemy.future import select
from fastapi import WebSocket
import websockets 
import json
import os
from worker import execute_trade_strategy
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from passlib.context import CryptContext
import jwt
from datetime import datetime, timedelta, timezone
import sys
from loguru import logger
from google.genai import types
from google import genai

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256" 


app = FastAPI()
ai_client = genai.Client()
## initializing Rate-limiter 
## STRICTLY BELOW APP
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter ## attach it to the app 
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

## remove the default messy test logger
logger.remove()

## add a clean production grade JSON logger that outputs to the console
logger.add(sys.stdout, serialize=True)

@app.post("/signup")
async def create_user(request:schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    
    scramble_password = pwd_context.hash(request.password)
    
    new_user = models.User(username=request.username, hashed_password = scramble_password)
    
    db.add(new_user)
    await db.commit()
    return{"message":f"{request.username} account created successfuly!"}


@app.post("/login")
async def login(request: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    
    #db_user = await db.query(models.User).filter(models.User.username == request.username).first ## outdated version without async

    stmt = select(models.User).filter(models.User.username == request.username)
    result = await db.execute(stmt)
    db_user = result.scalars().first()

    if db_user == None:
        raise HTTPException(status_code=404, detail= f"{request.username} not found") 
    is_correct = pwd_context.verify(request.password, db_user.hashed_password)

    if is_correct == False:
       raise HTTPException(status_code=401, detail = "Incorrect Passowrd!")
    
    if is_correct == True: 
        expire_time = datetime.now(timezone.utc) + timedelta(minutes=30)
        payload = {"sub": request.username, "exp":expire_time }
        wristband = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

        return{"access_token": wristband, "token_type": "bearer"}
    


## ----------------------------------------------##




# 2. This tells the Bouncer where users go to get their wristbands
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# 3. The Bouncer Function
def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        # The Bouncer checks the secret signature on the wristband
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # He reads the username written on it
        username: str = payload.get("sub")
        
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid wristband!")
            
        return username
        
    except jwt.PyJWTError:
        # If the signature is fake or expired, kick them out
        raise HTTPException(status_code=401, detail="Fake or expired wristband!")
    


## ----------------------------------------------##


 
@app.get("/portfolio")
def view_portfolio(current_user: str = Depends(get_current_user)):
    
    # If the code reaches this line, it means the Bouncer checked the wristband 
    # and it was 100% valid. The Bouncer also extracted the username for us!
    
    return {"message": f"Welcome to your private portfolio, {current_user}!"}


## ----------------------------------------------##


## Using Binance Lib to get data
@app.get("/symbol/{crypto}")
async def crypto_symbol(crypto: str, current_user: str = Depends(get_current_user)):

    client = await AsyncClient.create() ## Async Connection in each endpoint
   
    try: 
        ticker = await client.get_symbol_ticker(symbol = crypto)
        
        price = ticker['price']

        return {
            "Symbol": crypto,
            "Price": price
        }
    
    except BinanceAPIException:
        logger.info("Trade triggered", extra={"symbol": crypto, "reason": "Invalid Symbol"})
        raise HTTPException(status_code=404, detail=f"{crypto} doesnt not exist on Binance")
    
    finally: await client.close_connection()  ## await Async connection close


## ----------------------------------------------##


## Getting historical data out of binance 
## CURRENTLY also in worker.py for CELERY to run it in background

@app.get("/history/{crypto}")
async def get_history(crypto:str, current_user:str = Depends(get_current_user)):
    
    client = await AsyncClient.create()
    try: 

        lookback = 10
        ## klines is where we get our binance past data from
        past_data_1D = await client.get_klines(symbol=crypto, interval=AsyncClient.KLINE_INTERVAL_1DAY, limit=lookback)
        
        closing_prince_history = [] 

        ## in binance index = 4 (DAY[4]) is always the closing price
        for daily in (past_data_1D):
            closing_prince_history.append(float(daily[4]))
        
        ## SMA's based on Daily close
        SMA10 = sum(closing_prince_history)/10
        SMA5 = sum(closing_prince_history[-5:])/5


        ## SMA trade signals
        if SMA5 > SMA10:
            Signal = "BUY"
        elif SMA5 < SMA10:
            Signal = "SELL"
        else: 
            Signal = None

        return{
            "Symbol": crypto,
            "Closed Daily": closing_prince_history,
            "SMA10": SMA10,
            "SMA5": SMA5,
            "Signal": Signal
        }


    except BinanceAPIException:
        raise HTTPException(status_code=404, detail = f"{crypto} is the wrong symbol, or the history isnt available")
    
    finally: await client.close_connection()  ## await Async connection close '''





## Websocket Part of it, starts from here :
@app.websocket("/ws/live/{crypto}")
async def live(websocket: WebSocket, crypto:str):

    websocket_url = f"wss://stream.binance.com:9443/ws/{crypto}@trade"

    await websocket.accept()
    async with websockets.connect(websocket_url) as tunnel:
        
        ## logger.info("Tunnel for symbol's LIVE price triggered", extra={"crypto_symbol": crypto, "user": current_user})


        async for message in tunnel: 
            await websocket.send_text(message)


## ----------------------------------------- ##



## Rate limiter 
@app.post("/trade/{crypto}")
@limiter.limit("5/minute") ## Rate limiting decorator
async def trigger_trade(request: Request, crypto: str, current_user: str = Depends(get_current_user)): 
## request: Requests because slowapi needs needs the object to look at IP add fo the usr calling the api
    # 1) send ticket to redis mailbox using .delay
    ## .delay tells it to run in the backrgound (celery)
    task = execute_trade_strategy.delay(crypto)

    logger.info("Trade triggered", extra={"crypto_symbol": crypto, "user": current_user, "task_id":task.id})

    return{
        "message": f"Trade strategy for {crypto} has been send to the background worker",
        "task_id": task.id
    }
    
  

## ----------------------------------------- ## 

## converting user query into AI embedding and get vectordb
@app.get("/search")
async def search(q: str, db: AsyncSession=Depends(get_db)):

    embedded_content = ai_client.models.embed_content(model="gemini-embedding-001", contents=q)
    query_vector = embedded_content.embeddings[0].values

    stmt = select(models.TradeAnalysis).order_by(models.TradeAnalysis.embedding.cosine_distance(query_vector)).limit(1)

    result = (await db.execute(stmt)).scalars().first()

    if result is not None:
        return{
            "symbol": result.symbol,
            "sentiment":result.sentiment,
            "reasoning":result.reasoning
        }

    else: 
        raise HTTPException(status_code=404, detail="404 Result not found!")

