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

# Use absolute paths rooted at the backend directory
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
CHAT_HISTORY_FILE = BACKEND_DIR / "documents" / "chat_history.json"
CURRENT_PROFILE_FILE = BACKEND_DIR / "documents" / "current_profile.json"


def get_llm_client():
    """Get or create LLM client instance"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


def migrate_chat_history_profiles(active_profile: str):
    """Annotate history messages with the active profile if missing and persist."""
    try:
        if CHAT_HISTORY_FILE.exists():
            data = []
            with open(CHAT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                except Exception:
                    data = []

            changed = False
            for msg in data:
                if isinstance(msg, dict):
                    if 'profile' not in msg or not msg.get('profile'):
                        msg['profile'] = active_profile or 'general_chat'
                        changed = True
            if changed:
                save_chat_history(data)
    except Exception as e:
        print(f"Warning: chat history migration failed: {e}")


def read_persisted_profile() -> str:
    """Read current profile from persisted file, fallback to 'general_chat'."""
    try:
        if CURRENT_PROFILE_FILE.exists():
            data = json.loads(CURRENT_PROFILE_FILE.read_text(encoding="utf-8"))
            p = data.get("profile")
            if isinstance(p, str) and p:
                return p
    except Exception:
        pass
    return "general_chat"


def get_agent():
    """Get or create agent instance"""
    global _agent
    if _agent is None:
        from backend.core.provider_manager import get_provider_manager
        provider_manager = get_provider_manager()
        _agent = ProfileAgent(llm_client=None, provider_manager=provider_manager)
        # Initialize from persisted profile if available
        try:
            if CURRENT_PROFILE_FILE.exists():
                data = json.loads(CURRENT_PROFILE_FILE.read_text(encoding="utf-8"))
                profile_name = data.get("profile")
                if profile_name:
                    _agent.set_profile(profile_name)
        except Exception as e:
            print(f"Warning: could not load current profile: {e}")
        # Ensure history messages include a profile for UI rendering
        try:
            migrate_chat_history_profiles(_agent.get_current_profile())
        except Exception as e:
            print(f"Warning: could not migrate history profiles: {e}")
    return _agent


@router.post("/profile/{profile_name}")
async def set_profile(profile_name: str):
    """Set active agent profile (used by frontend profile switch)"""
    agent = get_agent()
    if agent.set_profile(profile_name):
        try:
            CURRENT_PROFILE_FILE.parent.mkdir(parents=True, exist_ok=True)
            CURRENT_PROFILE_FILE.write_text(json.dumps({"profile": profile_name}), encoding="utf-8")
        except Exception as e:
            print(f"Warning: could not persist profile: {e}")
        # After changing profile, also migrate existing history entries lacking profile
        try:
            migrate_chat_history_profiles(agent.get_current_profile())
        except Exception as e:
            print(f"Warning: could not migrate history after profile set: {e}")
        return {"message": f"Profile set to {profile_name}", "profile": profile_name}
    raise HTTPException(status_code=404, detail=f"Profile not found: {profile_name}")


@router.post("/history/migrate_profile")
async def migrate_history_profile():
    """Manually trigger migration to annotate messages with current profile."""
    agent = get_agent()
    migrate_chat_history_profiles(agent.get_current_profile())
    return {"message": "History migration completed", "profile": agent.get_current_profile()}


@router.get("/profile/current")
async def get_current_profile():
    """Return current profile and model configured for that profile"""
    agent = get_agent()
    current_prof = agent.get_current_profile()
    
    # Get current provider
    from backend.core.provider_manager import get_provider_manager
    provider_manager = get_provider_manager()
    current_provider = provider_manager.get_current_provider_name()
    
    # Get default model for current profile + provider
    model_for_profile = agent.get_default_model_for_profile(current_prof, current_provider)
    
    if not model_for_profile:
        # Fallback to first supported model
        supported_models = agent.get_models_for_profile(current_prof, current_provider)
        model_for_profile = supported_models[0] if supported_models else "unknown"
    
    return {
        "profile": current_prof,
        "model": model_for_profile,
        "provider": current_provider
    }


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
            "timestamp": datetime.utcnow().isoformat(),
            # Persist current profile context with the user prompt for clarity
            "profile": agent.get_current_profile()
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

            # Resolve target model (override > profile > default)
            # Resolve active profile preferring request > persisted > agent state
            active_profile = request.profile or read_persisted_profile() or agent.get_current_profile()
            
            # Read persisted model if not specified in request
            model_to_use = request.model
            if not model_to_use:
                # Check for persisted model
                model_file = BACKEND_DIR / "documents" / "current_model.json"
                if model_file.exists():
                    try:
                        model_data = json.loads(model_file.read_text(encoding="utf-8"))
                        model_to_use = model_data.get("model")
                    except Exception:
                        pass

            response_text = await agent.run(
                enriched_message,
                profile_name=active_profile,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                model=model_to_use,
            )
            # Model und Provider-Ermittlung nach agent.run() - wurde im run() gesetzt
            model_used = agent.last_model_used or "unknown"
            provider_used = agent.last_provider_used or "lokal"
        except Exception as e:
            print(f"Error in agent.run: {e}")
            import traceback
            traceback.print_exc()
            # Return error message
            response_text = f"⚠️ Fehler bei der Anfrage: {str(e)}"
            active_profile = request.profile or read_persisted_profile() or agent.get_current_profile()
            model_used = "error"
            provider_used = "error"
        
        # Add assistant message to history
        assistant_message = {
            "role": "assistant",
            "content": response_text,
            "timestamp": datetime.utcnow().isoformat(),
            "profile": active_profile,
            "model": model_used,
            "provider": provider_used
        }
        chat_history.append(assistant_message)
        
        # Save updated history
        save_chat_history(chat_history)
        
        # Get rate limits from provider if available
        rate_limits_data = {}
        if hasattr(agent, 'last_response_metadata') and agent.last_response_metadata:
            rate_limits_data = agent.last_response_metadata.get('rate_limits', {})
        
        return ChatResponse(
            response=response_text,
            session_id=session_id,
            model=model_used,
            profile=active_profile or "default",
            timestamp=datetime.utcnow().isoformat(),
            metadata={
                "message_count": len(chat_history),
                "provider": provider_used,
                "rate_limits": rate_limits_data
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


@router.delete("/history/{provider}/{profile}")
async def clear_history_for_context(provider: str, profile: str):
    """
    Delete chat history entries for a specific provider + profile combination.
    Keeps other conversations intact.
    """
    try:
        history = load_chat_history()
        before = len(history)
        filtered = [
            msg for msg in history
            if not (
                msg.get("profile") == profile and
                (msg.get("provider") == provider or not msg.get("provider"))
            )
        ]
        removed = before - len(filtered)
        save_chat_history(filtered)

        # Reset agent conversation history (but keep MCP context)
        try:
            agent = get_agent()
            if hasattr(agent, 'conversation_history'):
                agent.conversation_history = []
        except Exception as e:
            print(f"Warning: Could not reset agent history after context clear: {e}")

        return {
            "message": "Chat history cleared for context",
            "provider": provider,
            "profile": profile,
            "removed": removed
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing context history: {str(e)}")


# Convenience alias for frontend
@router.post("/chat", response_model=ChatResponse)
async def send_message_alias(request: ChatRequest):
    """Send a message (alias for /chat/messages)"""
    return await send_message(request)
