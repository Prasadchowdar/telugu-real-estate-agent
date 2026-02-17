"""
Real-time voice streaming service — PERFORMANCE OPTIMIZED.
Handles the WebSocket pipeline: Browser ↔ Server ↔ Sarvam APIs

Flow per conversation turn:
1. Browser streams PCM audio chunks via WebSocket
2. Server forwards chunks to Sarvam Streaming STT (WebSocket)
3. On final transcript → RAG search for context
4. Context + transcript → Sarvam LLM (SSE streaming)
5. LLM text tokens → Sarvam Streaming TTS (WebSocket)
6. TTS audio chunks → streamed back to browser

Performance optimizations:
- Shared httpx.AsyncClient (connection pooling, skip TCP/TLS per request)
- Reduced max_tokens (100) for shorter TTS input
- Limited conversation history (4 turns instead of 10)
- Compact system prompt
- Response truncation for TTS (max 2 sentences)
- Per-stage timing instrumentation
"""

import asyncio
import base64
import json
import logging
import os
import struct
import time
from typing import Optional

import httpx
import websockets

logger = logging.getLogger(__name__)

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
SARVAM_STT_WS_URL = "wss://api.sarvam.ai/speech-to-text-translate/streaming"
SARVAM_TTS_WS_URL = "wss://api.sarvam.ai/text-to-speech/streaming"
SARVAM_LLM_URL = "https://api.sarvam.ai/v1/chat/completions"


# ---------------------------------------------------------------------------
# Shared HTTP client — connection pooling for Sarvam REST APIs
# ---------------------------------------------------------------------------
# Creating a new httpx.AsyncClient per request wastes ~100-200ms on TCP/TLS.
# A shared client reuses connections across requests.

_http_client: Optional[httpx.AsyncClient] = None


def get_http_client() -> httpx.AsyncClient:
    """Get or create the shared async HTTP client."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=25.0, write=10.0, pool=5.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
    return _http_client


async def cleanup_http_client():
    """Close the shared client (call on shutdown)."""
    global _http_client
    if _http_client and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None


# ---------------------------------------------------------------------------
# Streaming STT  (Browser audio → Sarvam WebSocket → Transcript)
# ---------------------------------------------------------------------------

async def stream_stt(audio_chunks: asyncio.Queue, on_partial=None) -> str:
    """
    Stream audio chunks to Sarvam Streaming STT and return final transcript.

    Args:
        audio_chunks: Queue of raw PCM audio bytes (16kHz, 16-bit, mono)
        on_partial: Optional callback for partial transcripts

    Returns:
        Final transcript string
    """
    final_transcript = ""

    headers = {
        "api-subscription-key": SARVAM_API_KEY,
    }

    config = {
        "language_code": "te-IN",
        "model": "saaras:v3",
        "audio_format": "pcm_s16le",
        "sample_rate": 16000,
        "mode": "transcribe",
        "with_timestamps": False,
    }

    try:
        async with websockets.connect(
            SARVAM_STT_WS_URL,
            additional_headers=headers,
            ping_interval=20,
            ping_timeout=10,
        ) as ws:
            # Send initial config
            await ws.send(json.dumps({"config": config}))
            logger.info("STT WebSocket connected, config sent")

            # Task to send audio chunks
            async def send_audio():
                while True:
                    chunk = await audio_chunks.get()
                    if chunk is None:  # Sentinel: end of audio
                        # Send end-of-stream signal
                        await ws.send(json.dumps({"eof": True}))
                        logger.info("STT: Sent EOF signal")
                        break
                    await ws.send(chunk)

            # Task to receive transcript
            async def receive_transcript():
                nonlocal final_transcript
                async for message in ws:
                    try:
                        data = json.loads(message)
                        transcript = data.get("transcript", "")
                        is_final = data.get("is_final", False)
                        event_type = data.get("type", "")

                        if transcript:
                            if is_final or event_type == "final":
                                final_transcript = transcript
                                logger.info(f"STT final: {transcript}")
                                return
                            elif on_partial:
                                on_partial(transcript)
                                logger.debug(f"STT partial: {transcript}")
                    except json.JSONDecodeError:
                        continue

            # Run both tasks concurrently
            send_task = asyncio.create_task(send_audio())
            recv_task = asyncio.create_task(receive_transcript())

            # Wait for both to complete
            done, pending = await asyncio.wait(
                [send_task, recv_task],
                return_when=asyncio.FIRST_EXCEPTION,
            )

            # Cancel any remaining tasks
            for task in pending:
                task.cancel()

            # Re-raise any exceptions
            for task in done:
                if task.exception():
                    raise task.exception()

    except websockets.exceptions.ConnectionClosed as e:
        logger.warning(f"STT WebSocket closed: {e}")
    except Exception as e:
        logger.error(f"STT streaming error: {e}", exc_info=True)

    return final_transcript


# ---------------------------------------------------------------------------
# Streaming LLM  (Transcript + RAG context → Sarvam LLM → Text tokens)
# ---------------------------------------------------------------------------

# OPTIMIZED: Compact system prompt — every token counts for latency
SYSTEM_PROMPT = """You are Priya, a Telugu real estate calling agent. Rules:
- Always respond in Telugu only
- Answer ONLY from provided context. If not available say "ఆ సమాచారం నా దగ్గర లేదు"
- Respond naturally — give short answers for simple questions, detailed answers when user asks for full details
- Mention prices, locations, sizes when relevant
- Suggest site visit for availability queries"""


GREETING_PROMPT = """Based on the business info below, generate a short Telugu greeting.
You are Priya, calling a potential customer. Mention company name. Keep to 2 sentences max.

Business Info:
{business_context}

Generate ONLY the Telugu greeting, nothing else."""


GENERIC_GREETING = "నమస్కారం! నేను ప్రియ, మీకు ఎలా సహాయం చేయగలను?"


async def generate_greeting(business_context: Optional[str]) -> str:
    """
    Generate a dynamic greeting using LLM based on business context.
    Falls back to GENERIC_GREETING if no context or if LLM fails.
    """
    if not business_context:
        return GENERIC_GREETING

    prompt = GREETING_PROMPT.format(business_context=business_context)

    headers = {
        "Content-Type": "application/json",
        "api-subscription-key": SARVAM_API_KEY,
    }

    payload = {
        "model": "sarvam-m",
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Generate the greeting now."},
        ],
        "stream": False,
        "max_tokens": 100,
        "temperature": 0.7,
    }

    try:
        t0 = time.time()
        client = get_http_client()
        response = await client.post(
            SARVAM_LLM_URL,
            headers=headers,
            json=payload,
        )
        elapsed = (time.time() - t0) * 1000
        logger.info(f"PERF greeting LLM: {elapsed:.0f}ms")

        response.raise_for_status()
        data = response.json()
        greeting = data["choices"][0]["message"]["content"].strip()
        logger.info(f"Generated greeting: {greeting[:80]}...")
        return greeting
    except Exception as e:
        logger.error(f"Greeting generation error: {e}")
        return GENERIC_GREETING


async def stream_llm(
    transcript: str,
    rag_context: Optional[str],
    conversation_history: list,
):
    """
    Stream LLM response tokens.
    Yields text chunks as they arrive.

    OPTIMIZED:
    - Single system message (merged RAG context)
    - Limited to 4 conversation history turns (was 10)
    - max_tokens=100 (was 200) — forces concise responses
    - Shared HTTP client for connection pooling
    """
    messages = []

    # Build single system prompt (Sarvam API requires exactly one system message)
    system_content = SYSTEM_PROMPT
    if rag_context:
        system_content += f"\n\nProperty information:\n{rag_context}"

    messages.append({"role": "system", "content": system_content})

    # OPTIMIZED: Only last 4 turns (was 10) — reduces prompt size significantly
    for msg in conversation_history[-4:]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    # Add current user message
    messages.append({"role": "user", "content": transcript})

    # Debug: log message roles and total size
    roles = [m["role"] for m in messages]
    total_chars = sum(len(m["content"]) for m in messages)
    logger.info(f"LLM messages: {roles}, total_chars={total_chars}")

    headers = {
        "Content-Type": "application/json",
        "api-subscription-key": SARVAM_API_KEY,
    }

    payload = {
        "model": "sarvam-m",
        "messages": messages,
        "stream": True,
        "max_tokens": 128,      # Reduced to ~400 chars to match TTS limit (500)
        "temperature": 0.7,
    }

    try:
        client = get_http_client()
        async with client.stream(
            "POST",
            SARVAM_LLM_URL,
            headers=headers,
            json=payload,
        ) as response:
            if response.status_code != 200:
                error_body = await response.aread()
                error_text = error_body.decode()
                logger.error(f"LLM error {response.status_code}: {error_text}")

                # If streaming fails with 400, try non-streaming fallback
                if response.status_code == 400:
                    logger.info("LLM: Trying non-streaming fallback...")
                    fallback = await _llm_fallback(messages)
                    if fallback:
                        yield fallback
                    else:
                        yield "క్షమించండి, మళ్ళీ చెప్పగలరా?"
                    return

            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue
    except httpx.ReadTimeout:
        logger.error("LLM: Read timeout")
        yield "క్షమించండి, ఆలస్యం అవుతోంది. మళ్ళీ చెప్పండి."
    except Exception as e:
        logger.error(f"LLM streaming error: {e}", exc_info=True)
        yield "క్షమించండి, మళ్ళీ చెప్పగలరా?"


async def _llm_fallback(messages: list) -> Optional[str]:
    """Non-streaming LLM call as fallback when streaming returns 400."""
    headers = {
        "Content-Type": "application/json",
        "api-subscription-key": SARVAM_API_KEY,
    }

    payload = {
        "model": "sarvam-m",
        "messages": messages,
        "stream": False,
        "max_tokens": 100,
        "temperature": 0.7,
    }

    try:
        client = get_http_client()
        response = await client.post(
            SARVAM_LLM_URL,
            headers=headers,
            json=payload,
        )
        if response.status_code != 200:
            logger.error(f"LLM fallback error {response.status_code}: {response.text}")
            return None
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"LLM fallback error: {e}")
        return None


# ---------------------------------------------------------------------------
# Streaming TTS  (Text tokens → Sarvam WebSocket → Audio chunks)
# ---------------------------------------------------------------------------

async def stream_tts(text_queue: asyncio.Queue, on_audio_chunk=None):
    """
    Stream text to Sarvam TTS WebSocket and yield audio chunks.

    Args:
        text_queue: Queue of text strings. None = end of text.
        on_audio_chunk: Callback called with each audio chunk (bytes)
    """
    headers = {
        "api-subscription-key": SARVAM_API_KEY,
    }

    config = {
        "speaker": "anushka",
        "model": "bulbul:v2",
        "language_code": "te-IN",
        "audio_format": "pcm_s16le",
        "sample_rate": 16000,
        "enable_preprocessing": True,
    }

    try:
        async with websockets.connect(
            SARVAM_TTS_WS_URL,
            additional_headers=headers,
            ping_interval=20,
            ping_timeout=10,
        ) as ws:
            # Send initial config
            await ws.send(json.dumps({"config": config}))
            logger.info("TTS WebSocket connected, config sent")

            # Task to send text chunks
            async def send_text():
                accumulated = ""
                while True:
                    text = await text_queue.get()
                    if text is None:
                        # Send remaining text
                        if accumulated.strip():
                            await ws.send(json.dumps({"text": accumulated}))
                        await ws.send(json.dumps({"eof": True}))
                        logger.info("TTS: Sent EOF signal")
                        break

                    accumulated += text
                    # Send in sentence-sized chunks for natural TTS
                    while any(sep in accumulated for sep in [".", "।", "!", "?", ","]):
                        # Find the first sentence boundary
                        idx = -1
                        for sep in [".", "।", "!", "?", ","]:
                            pos = accumulated.find(sep)
                            if pos != -1 and (idx == -1 or pos < idx):
                                idx = pos

                        if idx != -1:
                            sentence = accumulated[: idx + 1].strip()
                            accumulated = accumulated[idx + 1:]
                            if sentence:
                                await ws.send(json.dumps({"text": sentence}))
                                logger.debug(f"TTS sent: {sentence}")

            # Task to receive audio
            async def receive_audio():
                async for message in ws:
                    if isinstance(message, bytes):
                        if on_audio_chunk:
                            on_audio_chunk(message)
                    else:
                        try:
                            data = json.loads(message)
                            if data.get("type") == "audio":
                                audio_b64 = data.get("audio", "")
                                if audio_b64:
                                    audio_bytes = base64.b64decode(audio_b64)
                                    if on_audio_chunk:
                                        on_audio_chunk(audio_bytes)
                            elif data.get("eof"):
                                logger.info("TTS: Received EOF")
                                return
                        except json.JSONDecodeError:
                            continue

            send_task = asyncio.create_task(send_text())
            recv_task = asyncio.create_task(receive_audio())

            done, pending = await asyncio.wait(
                [send_task, recv_task],
                return_when=asyncio.FIRST_EXCEPTION,
            )

            for task in pending:
                task.cancel()

            for task in done:
                if task.exception():
                    raise task.exception()

    except websockets.exceptions.ConnectionClosed as e:
        logger.warning(f"TTS WebSocket closed: {e}")
    except Exception as e:
        logger.error(f"TTS streaming error: {e}", exc_info=True)


# ---------------------------------------------------------------------------
# Fallback: REST-based STT + TTS (if WebSocket streaming isn't available)
# ---------------------------------------------------------------------------

async def rest_stt(audio_data: bytes) -> str:
    """Send complete audio via REST API for transcription.
    Uses shared HTTP client for connection pooling.
    """
    try:
        t0 = time.time()
        client = get_http_client()
        response = await client.post(
            "https://api.sarvam.ai/speech-to-text",
            headers={"api-subscription-key": SARVAM_API_KEY},
            files={"file": ("audio.wav", audio_data, "audio/wav")},
            data={
                "language_code": "te-IN",
                "model": "saarika:v2.5",
            },
        )
        elapsed = (time.time() - t0) * 1000
        logger.info(f"PERF STT: {elapsed:.0f}ms")

        if response.status_code != 200:
            logger.error(f"REST STT error {response.status_code}: {response.text}")
            return ""
        result = response.json()
        transcript = result.get("transcript", "")
        logger.info(f"REST STT transcript: {transcript}")
        return transcript
    except httpx.ReadTimeout:
        logger.error("REST STT: Read timeout")
        return ""
    except Exception as e:
        logger.error(f"REST STT error: {e}")
        return ""




def _smart_truncate(text: str, limit: int = 490) -> str:
    """Truncate text to fit within API limits (500 chars), preserving sentences."""
    if len(text) <= limit:
        return text

    # Try to cut at the last sentence boundary before the limit
    truncated = text[:limit]
    last_period = max(
        truncated.rfind('.'),
        truncated.rfind('!'),
        truncated.rfind('?'),
        truncated.rfind('।')
    )

    if last_period > limit // 2:  # If we found a boundary reasonably late
        return truncated[:last_period + 1]
    
    # Fallback: just cut at space
    last_space = truncated.rfind(' ')
    if last_space > limit // 2:
        return truncated[:last_space] + "..."
        
    return truncated + "..."


async def rest_tts(text: str) -> Optional[bytes]:
    """Generate complete audio via REST API.

    OPTIMIZED:
    - Uses shared HTTP client (connection pooling)
    - Truncates text to <500 chars to avoid API errors
    - pace=1.15 for slightly faster speech
    """
    # Enforce character limit to prevent 400 errors
    tts_text = _smart_truncate(text)

    if len(text) > len(tts_text):
        logger.warning(
            f"TTS Truncated: {len(text)} → {len(tts_text)} chars "
            f"to meet API limit"
        )

    try:
        t0 = time.time()
        client = get_http_client()
        response = await client.post(
            "https://api.sarvam.ai/text-to-speech",
            headers={
                "api-subscription-key": SARVAM_API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "inputs": [tts_text],
                "target_language_code": "te-IN",
                "speaker": "vidya",
                "model": "bulbul:v2",
                "pace": 1.15,               # OPTIMIZED: slightly faster speech
                "loudness": 1.5,
                "enable_preprocessing": True,
                "audio_format": "wav",
            },
        )
        elapsed = (time.time() - t0) * 1000
        logger.info(f"PERF TTS: {elapsed:.0f}ms (text={len(tts_text)} chars)")

        if response.status_code != 200:
            logger.error(f"REST TTS error {response.status_code}: {response.text}")
            return None
        data = response.json()
        audios = data.get("audios", [])
        if audios:
            return base64.b64decode(audios[0])
        logger.warning("REST TTS: No audio in response")
    except httpx.ReadTimeout:
        logger.error("REST TTS: Read timeout")
    except Exception as e:
        logger.error(f"REST TTS error: {e}")
    return None
