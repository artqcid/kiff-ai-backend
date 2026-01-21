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
from backend.core.llm_client import LLMClient
from backend.core.profile_agent import ProfileAgent

router = APIRouter()

# Global instances
_llm_client = None
_agent = None
CHAT_HISTORY_FILE = Path("./documents/chat_history.json")


def get_llm_client():
    """Get or create LLM client instance"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


def get_agent():
    """Get or create agent instance"""
    global _agent
    if _agent is None:
        llm_client = get_llm_client()
        _agent = ProfileAgent(llm_client)
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
    Send a message and get AI response with optional web context via @tags
    """
    try:
        agent = get_agent()
        
        # Generate session ID if not provided
        session_id = request.session_id or str(uuid.uuid4())
        
        # Extract message from either format
        if request.messages and len(request.messages) > 0:
            # Use last message from messages array
            user_message_text = request.messages[-1].content
        elif request.message:
            # Use deprecated message field
            user_message_text = request.message
        else:
            raise HTTPException(status_code=400, detail="No message provided")
        
        # Load chat history
        chat_history = load_chat_history()
        
        # Add user message to history
        user_message = {
            "role": "user",
            "content": user_message_text,
            "timestamp": datetime.utcnow().isoformat()
        }
        chat_history.append(user_message)
        
        # Fetch web contexts if @tags are present
        contexts = {}
        try:
            contexts = await agent.get_contexts_for_prompt(user_message_text)
            if contexts:
                print(f"Fetched {len(contexts)} web contexts for message")
        except Exception as e:
            print(f"Error fetching web contexts: {e}")
            # Continue without contexts
        
        # Get AI response
        try:
            # If we have contexts, enrich the message
            enriched_message = user_message_text
            if contexts:
                context_text = "\n\n## Business Context\n"
                for url, content in contexts.items():
                    context_text += f"\n### Quelle: {url}\n{content[:2000]}...\n"
                enriched_message = context_text + "\n\n" + user_message_text
            
            # Use agent.run() with profile from request
            response_text = agent.run(
                enriched_message, 
                profile_name=request.profile,
                temperature=request.temperature,
                max_tokens=request.max_tokens
            )
        except Exception as e:
            print(f"Error in agent.run: {e}")
            # Fallback to simple completion if agent fails
            llm_client = get_llm_client()
            response_text = llm_client.complete(user_message_text)
        
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
            response=response_text,
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


@router.get("/history")
async def get_history():
    """
    Get chat history (simplified endpoint for frontend)
    """
    chat_history = load_chat_history()
    return {"history": chat_history}


@router.delete("/history")
async def clear_history():
    """
    Clear chat history (simplified endpoint for frontend)
    """
    try:
        save_chat_history([])
        
        # Reset agent conversation history (but keep MCP context)
        try:
            agent = get_agent()
            if hasattr(agent, 'conversation_history'):
                agent.conversation_history = []
        except Exception as e:
            print(f"Warning: Could not reset agent history: {e}")
        
        return {"message": "Chat history cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing history: {str(e)}")


# Convenience alias for frontend
@router.post("/chat", response_model=ChatResponse)
async def send_message_alias(request: ChatRequest):
    """Send a message (alias for /chat/messages)"""
    return await send_message(request)
