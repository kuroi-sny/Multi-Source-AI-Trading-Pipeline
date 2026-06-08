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



## client = Client() ## Async needs this inside the functions its being used it

## AUTH tools for jwt 
from passlib.context import CryptContext
import jwt
from datetime import datetime, timedelta, timezone


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = "Super_super_secret_key"
ALGORITHM = "HS256" 


app = FastAPI()

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
        raise HTTPException(status_code=404, detail=f"{crypto} doesnt not exist on Binance")
    
    finally: await client.close_connection()  ## await Async connection close


## ----------------------------------------------##


## Getting historical data out of binance
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
    
    finally: await client.close_connection()  ## await Async connection close





## Websocket Part of it, starts from here :
@app.websocket("/ws/live/{crypto}")
async def live(websocket: WebSocket, crypto:str ):

    websocket_url = f"wss://stream.binance.com:9443/ws/{crypto}@trade"

    await websocket.accept()
    async with websockets.connect(websocket_url) as tunnel:
        print("Tunnel opened, waiting for live trades: ")


        async for message in tunnel: 
            await websocket.send_text(message)
  







