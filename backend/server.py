from pathlib import Path
from dotenv import load_dotenv
import os

# ⚠️ CRITICAL: Load .env BEFORE any other imports
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# Verify API key is loaded
if not os.environ.get("SARVAM_API_KEY"):
    print("⚠️ WARNING: SARVAM_API_KEY not found in environment!")
else:
    print(f"✓ SARVAM_API_KEY loaded (length: {len(os.environ.get('SARVAM_API_KEY'))})")

# Now import everything else
from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from services.stt_service import transcribe_audio
from services.tts_service import synthesize_speech
from services.llm_service import get_llm_response
from services.rag_service import search_context
from ws_handler import handle_voice_websocket
from services.streaming_service import cleanup_http_client
import logging
import uuid
from typing import Dict, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Telugu Real Estate Voice Assistant")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up shared HTTP client on server shutdown."""
    await cleanup_http_client()
    logger.info("Shared HTTP client closed")

# CORS configuration
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session storage
conversation_sessions: Dict[str, List[Dict[str, str]]] = {}

@app.get("/")
async def root():
    return {
        "status": "running",
        "service": "Telugu Real Estate Voice Assistant",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    api_key_present = bool(os.environ.get("SARVAM_API_KEY"))
    return {
        "status": "healthy",
        "api_key_configured": api_key_present
    }

@app.post("/api/chat/voice")
async def voice_chat(
    audio: UploadFile = File(...),
    session_id: str = None
):
    """
    Handle voice chat: STT → LLM → TTS
    """
    # Generate session ID if not provided
    if not session_id:
        session_id = str(uuid.uuid4())
    
    logger.info(f"Voice chat – session={session_id}, file={audio.filename}")
    
    try:
        # Step 1: Speech to Text
        logger.info(f"[{session_id}] Starting STT...")
        transcript = await transcribe_audio(audio)
        logger.info(f"[{session_id}] Transcript: {transcript}")
        
        # Step 2: Get conversation history
        history = conversation_sessions.get(session_id, [])
        
        # Step 3: Search RAG context (if available)
        context = None
        try:
            context = await search_context(transcript)
            if context:
                logger.info(f"[{session_id}] Found RAG context: {len(context)} chars")
        except Exception as e:
            logger.warning(f"[{session_id}] RAG search failed: {e}")
        
        # Step 4: Get LLM response
        logger.info(f"[{session_id}] Getting LLM response...")
        ai_reply = await get_llm_response(transcript, history, context)
        logger.info(f"[{session_id}] AI reply: {ai_reply}")
        
        # Step 5: Text to Speech
        logger.info(f"[{session_id}] Starting TTS...")
        audio_base64 = await synthesize_speech(ai_reply)
        logger.info(f"[{session_id}] TTS complete: {len(audio_base64)} chars")
        
        # Step 6: Update conversation history
        history.append({"role": "user", "content": transcript})
        history.append({"role": "assistant", "content": ai_reply})
        conversation_sessions[session_id] = history[-10:]  # Keep last 10 messages
        
        return {
            "session_id": session_id,
            "user_transcript": transcript,
            "agent_response": ai_reply,
            "agent_audio_base64": audio_base64
        }
        
    except Exception as e:
        logger.error(f"[{session_id}] Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload/pdf")
async def upload_pdf(file: UploadFile = File(...)):
    """
    Upload and process PDF for RAG
    """
    logger.info(f"PDF upload: {file.filename}")
    
    try:
        from services.rag_service import ingest_pdf
        result = await ingest_pdf(file)
        return result
    except Exception as e:
        logger.error(f"PDF upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/history/{session_id}")
async def get_history(session_id: str):
    """
    Get conversation history for a session
    """
    history = conversation_sessions.get(session_id, [])
    return {"session_id": session_id, "history": history}

@app.websocket("/ws/voice/{session_id}")
async def voice_ws_endpoint(websocket: WebSocket, session_id: str):
    """
    Real-time voice conversation via WebSocket.
    Full-duplex: browser streams mic audio, server streams AI audio back.
    """
    await handle_voice_websocket(websocket, session_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
