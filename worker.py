## here's celery (background runner) boilerplate
import os 
from celery import Celery
from binance.client import Client



# 1) connect celery to redis mailbox
# it looks for redis on port 6379, database 0
redis_url= os.getenv("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery(__name__, broker=redis_url, backend=redis_url)

# 2) Define our long-running Background Task
@celery_app.task
def execute_trade_strategy(crypto_symbol: str):
    
    client = Client() ## no Async functionality becaues celery is strictly synchronous
    lookback = 10
        ## klines is where we get our binance past data from
    past_data_1D = client.get_klines(symbol=crypto_symbol, interval=Client.KLINE_INTERVAL_1DAY, limit=lookback)
        
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
    print(f"[{crypto_symbol}] Signal Generated: {Signal}")

    return(f"{crypto_symbol} Successfully executed at trade for {Signal}") 
    

    
    
    



