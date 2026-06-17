from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, timedelta, timezone
import jwt

from app.db.database import get_db
from app.db import models, schemas
from app.core.security import pwd_context, SECRET_KEY, ALGORITHM, get_current_user

router = APIRouter()

@router.post("/signup")
async def create_user(request: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    scramble_password = pwd_context.hash(request.password)
    new_user = models.User(username=request.username, hashed_password=scramble_password)
    
    db.add(new_user)
    await db.commit()
    return {"message": f"{request.username} account created successfuly!"}

@router.post("/login")
async def login(request: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    stmt = select(models.User).filter(models.User.username == request.username)
    result = await db.execute(stmt)
    db_user = result.scalars().first()

    if db_user == None:
        raise HTTPException(status_code=404, detail= f"{request.username} not found") 
    is_correct = pwd_context.verify(request.password, db_user.hashed_password)

    if is_correct == False:
       raise HTTPException(status_code=401, detail="Incorrect Password!")
    
    if is_correct == True: 
        expire_time = datetime.now(timezone.utc) + timedelta(minutes=30)
        payload = {"sub": request.username, "exp": expire_time}
        wristband = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

        return {"access_token": wristband, "token_type": "bearer"}

@router.get("/portfolio")
def view_portfolio(current_user: str = Depends(get_current_user)):
    return {"message": f"Welcome to your private portfolio, {current_user}!"}
