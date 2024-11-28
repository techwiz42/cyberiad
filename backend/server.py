import os
import asyncio
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from routes import auth_router, thread_router, message_router, agent_router
from database import db_manager
from websocket_manager import connection_manager
from config import CORS_ORIGINS

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
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(thread_router)
app.include_router(message_router)
app.include_router(agent_router)

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    try:
        await connection_manager.connect(websocket, client_id)
        while True:
            data = await websocket.receive_text()
            await connection_manager.broadcast(f"Client {client_id}: {data}")
    except WebSocketDisconnect:
        await connection_manager.disconnect(websocket, client_id)
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}", exc_info=True)
        await connection_manager.disconnect(websocket, client_id)

async def startup():
    """Initialize application on startup."""
    try:
        await db_manager.create_tables()
        asyncio.create_task(connection_manager.cleanup_inactive_connections())
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
