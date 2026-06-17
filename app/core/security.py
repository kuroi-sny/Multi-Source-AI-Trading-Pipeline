import os
from dotenv import load_dotenv
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException
import jwt
from datetime import datetime, timedelta, timezone

load_dotenv()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
ALGORITHM = "HS256"

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
