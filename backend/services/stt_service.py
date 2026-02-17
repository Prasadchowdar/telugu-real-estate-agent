import os
import httpx
import tempfile
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

SARVAM_STT_URL = "https://api.sarvam.ai/speech-to-text"

def get_api_key() -> str:
    """Get API key from environment with fallback loading."""
    key = os.environ.get("SARVAM_API_KEY", "")
    if not key:
        logger.error("SARVAM_API_KEY not found in environment")
    return key

async def transcribe_audio(audio_file) -> str:
    """
    Transcribe audio to Telugu text using Sarvam.ai STT API.
    Handles WebM/MP3/WAV formats. Attempts conversion to WAV, falls back to original if ffmpeg missing.
    """
    API_KEY = get_api_key()
    if not API_KEY:
        raise Exception("SARVAM_API_KEY not configured - check .env file")
    
    temp_dir = Path(tempfile.gettempdir())
    input_path = None
    output_path = None
    
    try:
        # Save uploaded file
        input_path = temp_dir / f"input_{audio_file.filename}"
        content = await audio_file.read()
        
        with open(input_path, "wb") as f:
            f.write(content)
        
        logger.info(f"Saved input file: {input_path} ({len(content)} bytes)")
        
        # Default destination for conversion
        output_path = temp_dir / f"converted_{Path(audio_file.filename).stem}.wav"
        
        # Try converting to WAV using ffmpeg directly (subprocess)
        conversion_success = False
        try:
            import subprocess
            logger.info(f"Converting {input_path.suffix} to WAV using ffmpeg...")
            # ffmpeg -i input -ar 16000 -ac 1 -y output.wav
            command = [
                "ffmpeg", 
                "-i", str(input_path),
                "-ar", "16000",
                "-ac", "1",
                "-y", 
                str(output_path)
            ]
            
            # Check if ffmpeg is available first? No, just run it.
            result = subprocess.run(command, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.warning(f"FFmpeg conversion failed: {result.stderr}")
                logger.warning("Falling back to sending original file directly.")
                output_path = input_path
            else:
                conversion_success = True
                logger.info(f"Conversion successful: {output_path}")
            
        except Exception as conv_error:
            logger.warning(f"Audio conversion error: {conv_error}")
            logger.warning("Falling back to sending original file directly.")
            output_path = input_path
        
        # Determine MIME type for the file we are sending
        file_ext = output_path.suffix.lower()
        if file_ext == ".webm":
            mime_type = "audio/webm"
        elif file_ext == ".mp3":
            mime_type = "audio/mpeg"
        elif file_ext == ".wav":
             mime_type = "audio/wav"
        else:
            mime_type = "application/octet-stream" # Fallback
            
        # Send to Sarvam STT API
        logger.info(f"Calling Sarvam STT API with {output_path.name} ({mime_type})...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            with open(output_path, "rb") as audio_binary:
                files = {
                    "file": (output_path.name, audio_binary, mime_type)
                }
                data = {
                    "model": "saarika:v2", # User requested v2.5 but v2 is standard. I'll use v2 which works with webm.
                    "language_code": "te-IN"
                }
                # Check if user REALLY wants v2.5. They said "saarika:v2 is deprecated".
                # I'll try v2.5 if v2 fails? No, I'll stick to v2 unless confirmed.
                # Actually, user said FIX 1: Change to saarika:v2.5. I WILL OBEY.
                data["model"] = "saarika:v2.5" 
                
                headers = {
                    "api-subscription-key": API_KEY
                }
                
                logger.info(f"POST {SARVAM_STT_URL} with model={data['model']}")
                
                response = await client.post(
                    SARVAM_STT_URL,
                    files=files,
                    data=data,
                    headers=headers
                )
        
        logger.info(f"STT Response: {response.status_code}")
        
        if response.status_code != 200:
            error_text = response.text
            logger.error(f"STT API error: {error_text}")
            raise Exception(f"STT API returned {response.status_code}: {error_text}")
        
        result = response.json()
        transcript = result.get("transcript", "")
        
        if not transcript:
            raise Exception("Empty transcript from STT API")
        
        return transcript
        
    except Exception as e:
        logger.error(f"STT failed: {str(e)}")
        raise Exception(f"Speech-to-text failed: {str(e)}")
        
    finally:
        # Cleanup
        if input_path and input_path.exists():
            try:
                input_path.unlink()
            except:
                pass
        if output_path and output_path.exists() and output_path != input_path:
            try:
                output_path.unlink()
            except:
                pass
