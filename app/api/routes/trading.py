import json
import websockets
from fastapi import APIRouter, Depends, HTTPException, WebSocket, Request
from binance.async_client import AsyncClient
from binance.exceptions import BinanceAPIException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from loguru import logger
from google import genai

from app.db.database import get_db
from app.db import models
from app.core.security import get_current_user
from app.core.config import limiter
from app.services.worker import execute_trade_strategy

router = APIRouter()
ai_client = genai.Client()

@router.get("/symbol/{crypto}")
async def crypto_symbol(crypto: str, current_user: str = Depends(get_current_user)):
    client = await AsyncClient.create()
    try: 
        ticker = await client.get_symbol_ticker(symbol=crypto)
        price = ticker['price']
        return {
            "Symbol": crypto,
            "Price": price
        }
    except BinanceAPIException:
        logger.info("Trade triggered", extra={"symbol": crypto, "reason": "Invalid Symbol"})
        raise HTTPException(status_code=404, detail=f"{crypto} doesnt not exist on Binance")
    finally:
        await client.close_connection()

@router.get("/history/{crypto}")
async def get_history(crypto: str, current_user: str = Depends(get_current_user)):
    client = await AsyncClient.create()
    try: 
        lookback = 10
        past_data_1D = await client.get_klines(symbol=crypto, interval=AsyncClient.KLINE_INTERVAL_1DAY, limit=lookback)
        closing_prince_history = [] 

        for daily in (past_data_1D):
            closing_prince_history.append(float(daily[4]))
        
        SMA10 = sum(closing_prince_history)/10
        SMA5 = sum(closing_prince_history[-5:])/5

        if SMA5 > SMA10:
            Signal = "BUY"
        elif SMA5 < SMA10:
            Signal = "SELL"
        else: 
            Signal = None

        return {
            "Symbol": crypto,
            "Closed Daily": closing_prince_history,
            "SMA10": SMA10,
            "SMA5": SMA5,
            "Signal": Signal
        }
    except BinanceAPIException:
        raise HTTPException(status_code=404, detail=f"{crypto} is the wrong symbol, or the history isnt available")
    finally:
        await client.close_connection()

@router.websocket("/ws/live/{crypto}")
async def live(websocket: WebSocket, crypto: str):
    websocket_url = f"wss://stream.binance.com:9443/ws/{crypto}@trade"
    await websocket.accept()
    async with websockets.connect(websocket_url) as tunnel:
        async for message in tunnel: 
            await websocket.send_text(message)

@router.post("/trade/{crypto}")
@limiter.limit("5/minute")
async def trigger_trade(request: Request, crypto: str, current_user: str = Depends(get_current_user)): 
    task = execute_trade_strategy.delay(crypto)
    logger.info("Trade triggered", extra={"crypto_symbol": crypto, "user": current_user, "task_id": task.id})

    return {
        "message": f"Trade strategy for {crypto} has been send to the background worker",
        "task_id": task.id
    }

@router.get("/search")
async def search(q: str, db: AsyncSession = Depends(get_db)):
    embedded_content = ai_client.models.embed_content(model="gemini-embedding-001", contents=q)
    query_vector = embedded_content.embeddings[0].values

    stmt = select(models.TradeAnalysis).order_by(models.TradeAnalysis.embedding.cosine_distance(query_vector)).limit(1)
    result = await db.execute(stmt)
    closest_match = result.scalars().first()

    if closest_match:
        return {
            "query": q,
            "symbol": closest_match.symbol,
            "sentiment": closest_match.sentiment,
            "reasoning": closest_match.reasoning
        }
    else:
        raise HTTPException(status_code=404, detail="404 Result not found!")
