import os
import asyncio
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from routes import auth_router, thread_router, message_router, agent_router
from database import db_manager
from websocket_manager import connection_manager, initialize_connection_manager
#from config import CORS_ORIGINS

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://cyberiad.ai:3000",
        "http://cyberiad.ai:3001"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(thread_router)
app.include_router(message_router)
app.include_router(agent_router)

@app.websocket("/ws/{thread_id}/{user_id}")
async def websocket_endpoint(websocket: WebSocket, thread_id: str, user_id: str):
    try:
        await connection_manager.connect(websocket, thread_id, user_id)
        await connection_manager.handle_client_message(websocket, thread_id, user_id)
    except WebSocketDisconnect:
        await connection_manager.disconnect(thread_id, user_id)
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id} in thread {thread_id}: {str(e)}", exc_info=True)
        await connection_manager.disconnect(thread_id, user_id)

async def startup():
    """Initialize application on startup."""
    try:
        #await db_manager.create_tables()
        # Start cleanup task as a background process
        asyncio.create_task(initialize_connection_manager())
        logger.info("Application startup complete")
    except Exception as e:
        logger.error(f"Startup error: {str(e)}", exc_info=True)
        raise

async def shutdown():
    """Cleanup on application shutdown."""
    try:
        await connection_manager.close_all_connections()
        logger.info("Application shutdown complete")
    except Exception as e:
        logger.error(f"Shutdown error: {str(e)}", exc_info=True)

# Add event handlers for startup and shutdown
app.add_event_handler("startup", startup)
app.add_event_handler("shutdown", shutdown)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )

