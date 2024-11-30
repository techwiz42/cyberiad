from fastapi import WebSocket, WebSocketDisconnect, HTTPException
from typing import Dict, Set, Optional, List
import json
import asyncio
import logging
from datetime import datetime
from uuid import UUID

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[UUID, Dict[UUID, WebSocket]] = {}
        self.user_threads: Dict[UUID, Set[UUID]] = {}
        self.connection_timestamps: Dict[str, datetime] = {}
        self.typing_status: Dict[UUID, Dict[UUID, datetime]] = {}

    async def connect(self, websocket: WebSocket, thread_id: UUID, user_id: UUID):
        """Connect and initialize a WebSocket connection."""
        try:
            await websocket.accept()
            
            if thread_id not in self.active_connections:
                self.active_connections[thread_id] = {}
            self.active_connections[thread_id][user_id] = websocket
            
            if user_id not in self.user_threads:
                self.user_threads[user_id] = set()
            self.user_threads[user_id].add(thread_id)
            
            connection_key = f"{thread_id}:{user_id}"
            self.connection_timestamps[connection_key] = datetime.utcnow()
            
            # Broadcast user joined message
            await self.broadcast(thread_id, {
                "type": "user_joined",
                "user_id": str(user_id),
                "timestamp": datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error connecting WebSocket: {e}")
            raise

    async def disconnect(self, user_id: UUID, thread_id: UUID):
        """Disconnect a user from a thread."""
        if thread_id in self.active_connections:
            if user_id in self.active_connections[thread_id]:
                del self.active_connections[thread_id][user_id]
            
                # If the thread is empty, remove it
                if not self.active_connections[thread_id]:
                    del self.active_connections[thread_id]


    async def broadcast(self, thread_id: UUID, message: dict, exclude_user: Optional[UUID] = None):
        """Broadcast message to all thread participants."""
        if thread_id in self.active_connections:
            message_json = json.dumps(message)
            failed_connections = []
            
            for user_id, connection in self.active_connections[thread_id].items():
                if user_id != exclude_user:
                    try:
                        await connection.send_text(message_json)
                    except Exception as e:
                        logger.error(f"Error broadcasting to user {user_id}: {e}")
                        failed_connections.append(user_id)
            
            # Clean up failed connections
            for user_id in failed_connections:
                await self.disconnect(thread_id, user_id)

    async def send_personal_message(self, message: dict, thread_id: UUID, user_id: UUID):
        """Send a message to a specific user in a thread."""
        if (thread_id in self.active_connections and 
            user_id in self.active_connections[thread_id]):
            try:
                connection = self.active_connections[thread_id][user_id]
                await connection.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending personal message to user {user_id}: {e}")
                await self.disconnect(thread_id, user_id)

    async def update_typing_status(self, thread_id: UUID, user_id: UUID, is_typing: bool):
        """Update and broadcast typing status."""
        if thread_id not in self.typing_status:
            self.typing_status[thread_id] = {}
            
        current_time = datetime.utcnow()
        
        if is_typing:
            self.typing_status[thread_id][user_id] = current_time
        else:
            self.typing_status[thread_id].pop(user_id, None)
            
        await self.broadcast(
            thread_id,
            {
                "type": "typing_status",
                "user_id": str(user_id),
                "is_typing": is_typing,
                "timestamp": current_time.isoformat()
            },
            exclude_user=user_id
        )

    def get_active_users(self, thread_id: UUID) -> List[UUID]:
        """Get list of active users in a thread."""
        return list(self.active_connections.get(thread_id, {}).keys())

    def is_user_online(self, thread_id: UUID, user_id: UUID) -> bool:
        """Check if a user is currently online in a thread."""
        return (thread_id in self.active_connections and 
                user_id in self.active_connections[thread_id])

    async def handle_client_message(self, websocket: WebSocket, thread_id: UUID, user_id: UUID):
        """Handle incoming messages from clients."""
        try:
            while True:
                message = await websocket.receive_text()
                try:
                    data = json.loads(message)
                    message_type = data.get("type")
                    
                    if message_type == "message":
                        # Regular message
                        await self.broadcast(
                            thread_id,
                            {
                                "type": "message",
                                "user_id": str(user_id),
                                "content": data.get("content"),
                                "timestamp": datetime.utcnow().isoformat()
                            }
                        )
                    elif message_type == "typing":
                        # Typing indicator
                        await self.update_typing_status(
                            thread_id,
                            user_id,
                            data.get("is_typing", False)
                        )
                    elif message_type == "read":
                        # Read receipt
                        await self.broadcast(
                            thread_id,
                            {
                                "type": "read",
                                "user_id": str(user_id),
                                "message_id": data.get("message_id"),
                                "timestamp": datetime.utcnow().isoformat()
                            }
                        )
                except json.JSONDecodeError:
                    logger.error(f"Invalid message format: {message}")
                except KeyError as e:
                    logger.error(f"Missing required field in message: {e}")
                
        except WebSocketDisconnect:
            await self.disconnect(thread_id, user_id)
        except Exception as e:
            logger.error(f"Error handling client message: {e}")
            await self.disconnect(thread_id, user_id)

    async def cleanup_inactive_connections(self, inactive_timeout: int = 3600):
        """Cleanup inactive connections periodically."""
        while True:
            try:
                current_time = datetime.utcnow()
                connections_to_remove = []
                
                for connection_key, timestamp in self.connection_timestamps.items():
                    if (current_time - timestamp).total_seconds() > inactive_timeout:
                        thread_id, user_id = connection_key.split(":")
                        connections_to_remove.append((
                            UUID(thread_id),
                            UUID(user_id)
                        ))
                
                for thread_id, user_id in connections_to_remove:
                    await self.disconnect(thread_id, user_id)
                    
                # Clean up empty typing statuses
                for thread_id in list(self.typing_status.keys()):
                    if not self.typing_status[thread_id]:
                        del self.typing_status[thread_id]
                    
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
            
            await asyncio.sleep(300)  # Run cleanup every 5 minutes


connection_manager = ConnectionManager()

async def initialize_connection_manager():
    await connection_manager.cleanup_inactive_connections()
