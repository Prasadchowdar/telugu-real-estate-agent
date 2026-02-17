import os
import httpx
import logging

logger = logging.getLogger(__name__)

SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"

def get_api_key() -> str:
    """Get API key from environment."""
    return os.environ.get("SARVAM_API_KEY", "")

async def synthesize_speech(text: str) -> str:
    """
    Convert Telugu text to speech using Sarvam.ai TTS API.
    Returns base64 encoded audio.
    """
    API_KEY = get_api_key()
    if not API_KEY:
        raise Exception("SARVAM_API_KEY not configured")
    
    if not text or not text.strip():
        raise Exception("No text provided for TTS")
    
    try:
        logger.info(f"Synthesizing: {text[:50]}...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            payload = {
                "inputs": [text],
                "target_language_code": "te-IN",
                "speaker": "vidya",
                "model": "bulbul:v2",
                "pace": 1.0,
                "loudness": 1.5,
                "enable_preprocessing": True,
                "audio_format": "wav"
            }
            headers = {
                "api-subscription-key": API_KEY,
                "Content-Type": "application/json"
            }
            
            logger.info(f"POST {SARVAM_TTS_URL}")
            
            response = await client.post(
                SARVAM_TTS_URL,
                json=payload,
                headers=headers
            )
        
        logger.info(f"TTS Response: {response.status_code}")
        
        if response.status_code != 200:
            error_text = response.text
            logger.error(f"TTS API error: {error_text}")
            raise Exception(f"TTS API returned {response.status_code}: {error_text}")
        
        result = response.json()
        audio_base64 = result.get("audios", [None])[0]
        
        if not audio_base64:
            raise Exception("No audio in TTS response")
        
        return audio_base64
        
    except Exception as e:
        logger.error(f"TTS failed: {str(e)}")
        raise Exception(f"Text-to-speech failed: {str(e)}")
