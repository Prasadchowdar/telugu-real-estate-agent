import os
import httpx
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

SARVAM_LLM_URL = "https://api.sarvam.ai/v1/chat/completions"

SYSTEM_PROMPT = """మీరు ప్రియ - Sri Sai Properties యొక్క రియల్ ఎస్టేట్ సహాయకురాలు.

మీ పని:
1. కాలర్కు అందుబాటులో ఉన్న ప్రాపర్టీల గురించి వివరించడం
2. ధరలు, EMI, లొకేషన్ వివరాలు అందించడం
3. సైట్ విజిట్ షెడ్యూల్ చేయడం
4. లీడ్ సమాచారం సేకరించడం

అందుబాటులో ఉన్న ప్రాపర్టీలు:
- కోకాపేట్: 3BHK విల్లా ₹1.8 కోట్లు | 4BHK ₹2.4 కోట్లు
- నర్సింగి: 2BHK ₹75 లక్షలు | 3BHK ₹1.1 కోట్లు
- మాదాపూర్: కమర్షియల్ స్పేస్ ₹8,500/sqft

నియమాలు:
- ఎల్లప్పుడూ తెలుగులో మాట్లాడండి
- చిన్న సమాధానాలు (2-3 వాక్యాలు)
- స్నేహంగా ఉండండి"""

def get_api_key() -> str:
    """Get API key from environment."""
    return os.environ.get("SARVAM_API_KEY", "")

async def get_llm_response(
    user_message: str,
    history: Optional[List[Dict[str, str]]] = None,
    context: Optional[str] = None
) -> str:
    """Get AI response from Sarvam-M LLM."""
    API_KEY = get_api_key()
    if not API_KEY:
        raise Exception("SARVAM_API_KEY not configured")
    
    try:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        if context:
            messages.append({"role": "system", "content": f"అదనపు సమాచారం:\n{context}"})
        
        if history:
            messages.extend(history)
        
        messages.append({"role": "user", "content": user_message})
        
        logger.info(f"LLM request: {len(messages)} messages")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            payload = {
                "model": "sarvam-m",
                "messages": messages,
                "max_tokens": 250,
                "temperature": 0.7
            }
            headers = {
                "api-subscription-key": API_KEY,
                "Content-Type": "application/json"
            }
            
            response = await client.post(
                SARVAM_LLM_URL,
                json=payload,
                headers=headers
            )
        
        logger.info(f"LLM Response: {response.status_code}")
        
        if response.status_code != 200:
            error_text = response.text
            logger.error(f"LLM API error: {error_text}")
            raise Exception(f"LLM API returned {response.status_code}: {error_text}")
        
        result = response.json()
        reply = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        if not reply:
            raise Exception("Empty response from LLM")
        
        return reply
        
    except Exception as e:
        logger.error(f"LLM failed: {str(e)}")
        raise Exception(f"LLM request failed: {str(e)}")
