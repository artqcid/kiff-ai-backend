"""
chat.py

Chat and conversation endpoints
"""

from fastapi import APIRouter, HTTPException
from typing import List
import sys
import json
import uuid
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from backend.api.v1.models import (
    ChatRequest, ChatResponse, ChatSession, ChatSessionList, ChatMessage
)
from src.llm.llama_client_kiff import LlamaClientKiff
from src.agents.profile_agent_kiff import ProfileAgentKiff

router = APIRouter()

# Global instances
_llm_client = None
_agent = None
CHAT_HISTORY_FILE = Path("./documents/chat_history.json")


def get_llm_client():
    """Get or create LLM client instance"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LlamaClientKiff()
    return _llm_client


def get_agent():
    """Get or create agent instance"""
    global _agent
    if _agent is None:
        llm_client = get_llm_client()
        _agent = ProfileAgentKiff(llm=llm_client)
    return _agent


def load_chat_history() -> List[dict]:
    """Load chat history from file"""
    if CHAT_HISTORY_FILE.exists():
        try:
            with open(CHAT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_chat_history(chat_history: List[dict]):
    """Save chat history to file"""
    try:
        CHAT_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CHAT_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(chat_history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving chat history: {e}")


@router.post("/chat/messages", response_model=ChatResponse)
async def send_message(request: ChatRequest):
    """
    Send a message and get AI response
    """
    try:
        agent = get_agent()
        
        # Generate session ID if not provided
        session_id = request.session_id or str(uuid.uuid4())
        
        # Load chat history
        chat_history = load_chat_history()
        
        # Add user message to history
        user_message = {
            "role": "user",
            "content": request.message,
            "timestamp": datetime.utcnow().isoformat()
        }
        chat_history.append(user_message)
        
        # Get AI response
        # TODO: Implement proper profile selection and agent invocation
        try:
            response_text = agent.chat(request.message)
        except Exception as e:
            # Fallback to simple completion if agent fails
            llm_client = get_llm_client()
            result = llm_client._generate([request.message])
            response_text = result.generations[0][0].text if result.generations else "Error generating response"
        
        # Add assistant message to history
        assistant_message = {
            "role": "assistant",
            "content": response_text,
            "timestamp": datetime.utcnow().isoformat()
        }
        chat_history.append(assistant_message)
        
        # Save updated history
        save_chat_history(chat_history)
        
        return ChatResponse(
            message=response_text,
            session_id=session_id,
            model=request.model or "default",
            profile=request.profile or "default",
            timestamp=datetime.utcnow().isoformat(),
            metadata={
                "message_count": len(chat_history)
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")


@router.get("/chat/sessions", response_model=ChatSessionList)
async def get_sessions():
    """
    Get list of chat sessions
    For now, returns a single session with full history
    """
    chat_history = load_chat_history()
    
    if not chat_history:
        return ChatSessionList(sessions=[], total=0)
    
    messages = [
        ChatMessage(
            role=msg["role"],
            content=msg["content"],
            timestamp=msg.get("timestamp")
        )
        for msg in chat_history
    ]
    
    session = ChatSession(
        session_id="default",
        messages=messages,
        created_at=messages[0].timestamp if messages else datetime.utcnow().isoformat(),
        updated_at=messages[-1].timestamp if messages else datetime.utcnow().isoformat()
    )
    
    return ChatSessionList(sessions=[session], total=1)


@router.delete("/chat/sessions/{session_id}")
async def delete_session(session_id: str):
    """
    Delete a chat session
    For now, clears all history
    """
    try:
        save_chat_history([])
        return {"message": "Chat history cleared", "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting session: {str(e)}")


@router.delete("/chat/sessions")
async def clear_all_sessions():
    """
    Clear all chat sessions
    """
    try:
        save_chat_history([])
        return {"message": "All chat history cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing sessions: {str(e)}")
