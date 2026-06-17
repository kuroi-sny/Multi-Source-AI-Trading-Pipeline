import sys
from fastapi import FastAPI
from loguru import logger
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from app.core.config import limiter
from app.api.routes import auth, trading

# Remove the default messy test logger
logger.remove()

# Add a clean production-grade JSON logger that outputs to the console
logger.add(sys.stdout, serialize=True)

# 1. Create the App
app = FastAPI(title="Multi-Source AI Trading API")

# 2. Attach Rate Limiter
app.state.limiter = limiter 
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 3. Include API Routers
app.include_router(auth.router, tags=["Authentication"])
app.include_router(trading.router, tags=["Trading"])
