# message_persistence.py
from sqlalchemy import select, and_, desc, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID
import logging
from fastapi import HTTPException

from models import Message, MessageReadReceipt, User, Base

logger = logging.getLogger(__name__)

class MessagePersistenceManager:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def save_message(self, message_data: Dict[str, Any]) -> Message:
        """
        Save a message to the database with all associated metadata.
        """
        try:
            message = Message(
                thread_id=message_data['thread_id'],
                user_id=message_data.get('user_id'),
                agent_id=message_data.get('agent_id'),
                content=message_data['content'],
                message_metadata=message_data.get('metadata', {}),
                parent_id=message_data.get('parent_id'),
                edited=False,
                deleted=False,
                created_at=datetime.utcnow(),
                client_generated_id=message_data.get('client_generated_id')
            )
            
            self.db.add(message)
            await self.db.commit()
            await self.db.refresh(message)
            
            # Create message read receipt for sender
            if message.user_id:
                await self.create_read_receipt(
                    message.id,
                    message.user_id,
                    datetime.utcnow()
                )
            
            return message
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error saving message: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Error saving message: {str(e)}"
            )

    async def get_thread_messages(
        self,
        thread_id: UUID,
        limit: int = 50,
        before_id: Optional[UUID] = None,
        include_deleted: bool = False
    ) -> List[Message]:
        """
        Retrieve messages from a thread with pagination.
        """
        try:
            query = (
                select(Message)
                .where(Message.thread_id == thread_id)
                .options(
                    joinedload(Message.user),
                    joinedload(Message.agent),
                    joinedload(Message.read_receipts)
                )
                .order_by(desc(Message.created_at))
            )

            if not include_deleted:
                query = query.where(Message.deleted == False)

            if before_id:
                before_message = await self.get_message_by_id(before_id)
                if before_message:
                    query = query.where(Message.created_at < before_message.created_at)

            query = query.limit(limit)
            result = await self.db.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error retrieving thread messages: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Error retrieving messages: {str(e)}"
            )

    async def create_message(
        self,
        content: str,
        user_id: UUID,
        thread_id: UUID,
        message_metadata: dict = None,
    ) -> Message:
        """
        Create a new message and save it to the database.
        """
        try:
            if message_metadata is None:
                message_metadata = {}

            new_message = Message(
                content=content,
                user_id=user_id,
                thread_id=thread_id,
                created_at=datetime.now(timezone.utc),
                message_metadata=message_metadata,
            )

            self.db.add(new_message)
            await self.db.commit()
            await self.db.refresh(new_message)
            return new_message
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating message: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Error creating message: {str(e)}"
            )

    async def update_message(
        self,
        message_id: UUID,
        new_content: str,
        editor_id: UUID
    ) -> Message:
        """
        Update a message's content and mark it as edited.
        """
        try:
            message = await self.get_message_by_id(message_id)
            if not message:
                raise HTTPException(status_code=404, detail="Message not found")

            if message.user_id != editor_id:
                raise HTTPException(status_code=403, detail="Not authorized to edit this message")

            # Store original content in metadata
            if not message.message_metadata.get('edit_history'):
                message.message_metadata['edit_history'] = []
            
            message.message_metadata['edit_history'].append({
                'content': message.content,
                'edited_at': datetime.utcnow().isoformat(),
                'edited_by': str(editor_id)
            })

            message.content = new_content
            message.edited = True
            message.edited_at = datetime.utcnow()

            await self.db.commit()
            await self.db.refresh(message)
            return message
        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating message: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Error updating message: {str(e)}"
            )

    async def soft_delete_message(self, message_id: UUID, deleter_id: UUID) -> Message:
        """
        Soft delete a message (mark as deleted but keep in database).
        """
        try:
            message = await self.get_message_by_id(message_id)
            if not message:
                raise HTTPException(status_code=404, detail="Message not found")

            if message.user_id != deleter_id:
                raise HTTPException(status_code=403, detail="Not authorized to delete this message")

            message.deleted = True
            message.deleted_at = datetime.utcnow()
            message.message_metadata['deleted_by'] = str(deleter_id)

            await self.db.commit()
            await self.db.refresh(message)
            return message
        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error deleting message: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Error deleting message: {str(e)}"
            )

    async def create_read_receipt(
        self,
        message_id: UUID,
        user_id: UUID,
        timestamp: datetime
    ) -> MessageReadReceipt:
        """
        Create or update a read receipt for a message.
        """
        try:
            # Check for existing receipt
            existing_receipt = await self.db.execute(
                select(MessageReadReceipt).where(
                    and_(
                        MessageReadReceipt.message_id == message_id,
                        MessageReadReceipt.user_id == user_id
                    )
                )
            )
            receipt = existing_receipt.scalars().first()

            if receipt:
                receipt.read_at = timestamp
            else:
                receipt = MessageReadReceipt(
                    message_id=message_id,
                    user_id=user_id,
                    read_at=timestamp
                )
                self.db.add(receipt)

            await self.db.commit()
            await self.db.refresh(receipt)
            return receipt
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating read receipt: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Error creating read receipt: {str(e)}"
            )

    async def get_message_by_id(self, message_id: UUID) -> Optional[Message]:
        """
        Get a specific message by ID.
        """
        try:
            result = await self.db.execute(
                select(Message)
                .where(Message.id == message_id)
                .options(
                    joinedload(Message.user),
                    joinedload(Message.agent),
                    joinedload(Message.read_receipts)
                )
            )
            return result.scalars().first()
        except Exception as e:
            logger.error(f"Error retrieving message: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Error retrieving message: {str(e)}"
            )


    async def get_unread_count(self, thread_id: UUID, user_id: UUID) -> int:
        """
        Get count of unread messages in a thread for a user.
        """
        try:
            # Get the timestamp of the user's last read message in the thread
            last_read = await self.db.execute(
                select(func.max(MessageReadReceipt.read_at))
                .join(Message, Message.id == MessageReadReceipt.message_id)
                .where(
                    and_(
                        Message.thread_id == thread_id,
                        MessageReadReceipt.user_id == user_id
                    )
                )
            )
            last_read_time = last_read.scalar()

            # Count messages after the last read timestamp
            query = select(func.count(Message.id)).where(
                and_(
                    Message.thread_id == thread_id,
                    Message.user_id != user_id,
                    Message.deleted == False
                )
            )

            if last_read_time:
                query = query.where(Message.created_at > last_read_time)

            result = await self.db.execute(query)
            return result.scalar()
        except Exception as e:
            logger.error(f"Error getting unread count: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Error getting unread count: {str(e)}"
            )

    async def mark_thread_read(self, thread_id: UUID, user_id: UUID):
        """
        Mark all messages in a thread as read for a user.
        """
        try:
            # Get all unread messages
            messages = await self.db.execute(
                select(Message)
                .where(
                    and_(
                        Message.thread_id == thread_id,
                        Message.user_id != user_id,
                        Message.deleted == False
                    )
                )
                .outerjoin(
                    MessageReadReceipt,
                    and_(
                        MessageReadReceipt.message_id == Message.id,
                        MessageReadReceipt.user_id == user_id
                    )
                )
                .where(MessageReadReceipt.id == None)
            )

            # Create read receipts
            now = datetime.utcnow()
            for message in messages.scalars():
                receipt = MessageReadReceipt(
                    message_id=message.id,
                    user_id=user_id,
                    read_at=now
                )
                self.db.add(receipt)

            await self.db.commit()
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error marking thread read: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Error marking thread read: {str(e)}"
            )
