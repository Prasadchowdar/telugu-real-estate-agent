"""
WebSocket handler for real-time voice conversations — PRODUCTION READY.

Manages the full-duplex connection between the browser and the
streaming voice pipeline (STT → RAG → LLM → TTS).

Architecture inspired by ElevenLabs Conversational AI:
- Explicit Finite State Machine (GREETING → LISTENING → USER_SPEAKING → PROCESSING → AI_SPEAKING)
- Mic audio is IGNORED during AI_SPEAKING (eliminates echo-triggered VAD)
- Barge-in with high RMS threshold during AI speech
- Watchdog timer for stuck state recovery
- Post-playback cooldown to avoid echo tail
- Per-stage timing instrumentation
"""

import asyncio
import base64
import enum
import json
import logging
import struct
import time
from typing import Dict, List, Optional

from fastapi import WebSocket, WebSocketDisconnect

from services.rag_service import search_context, get_business_summary
from services.streaming_service import (
    stream_stt,
    stream_llm,
    stream_tts,
    rest_stt,
    rest_tts,
    generate_greeting,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Session State Machine
# ---------------------------------------------------------------------------

class SessionState(enum.Enum):
    """Finite State Machine for voice session."""
    GREETING = "greeting"          # Auto-greeting in progress
    LISTENING = "listening"        # Waiting for user to speak
    USER_SPEAKING = "user_speaking"  # User is speaking, buffering audio
    PROCESSING = "processing"      # Pipeline running (STT → RAG → LLM → TTS)
    AI_SPEAKING = "ai_speaking"    # AI audio playing in browser


class VoiceSession:
    """Manages a single real-time voice conversation session."""

    def __init__(self, websocket: WebSocket, session_id: str):
        self.ws = websocket
        self.session_id = session_id
        self.conversation_history: List[dict] = []
        self.is_active = True

        # ---- State Machine ----
        self._state = SessionState.GREETING
        self._state_entered_at = time.time()

        # ---- Audio buffer ----
        self._audio_buffer = bytearray()
        self._silence_frames = 0
        self._speech_frames = 0
        self._is_speaking = False
        self._last_speech_time = 0.0
        self._chunk_count = 0

        # Background task for the processing pipeline
        self._processing_task: Optional[asyncio.Task] = None

        # ---- VAD parameters ----
        self.SILENCE_THRESHOLD = 80
        self.SPEECH_THRESHOLD = 200
        self.SILENCE_DURATION_MS = 1000
        self.MIN_SPEECH_DURATION_MS = 300
        self.FRAME_DURATION_MS = 256           # 4096 samples at 16kHz
        self.MIN_AUDIO_BYTES = 8192            # ~0.25s — skip noise/clicks

        # Barge-in echo rejection (only during AI_SPEAKING)
        self.BARGE_IN_THRESHOLD = 500
        self.MIN_BARGE_IN_FRAMES = 3           # Require 3 consecutive loud frames
        self._barge_in_frames = 0

        # Post-playback cooldown
        self.PLAYBACK_COOLDOWN_MS = 500        # Ignore audio for 500ms after AI stops
        self._playback_ended_at = 0.0

        # Watchdog
        self.WATCHDOG_TIMEOUT_S = 30           # Auto-reset if stuck in AI_SPEAKING

        # Conversation history cap
        self.MAX_HISTORY_ENTRIES = 10

    # ---- State transitions ----

    def _set_state(self, new_state: SessionState):
        """Transition to a new state."""
        old = self._state
        self._state = new_state
        self._state_entered_at = time.time()
        logger.info(
            f"[{self.session_id}] State: {old.value} → {new_state.value}"
        )

    @property
    def is_ai_speaking(self) -> bool:
        """Compatibility property — True when in AI_SPEAKING or GREETING state."""
        return self._state in (SessionState.AI_SPEAKING, SessionState.GREETING)

    # ---- Network helpers ----

    async def send_event(self, event_type: str, data: dict = None):
        """Send a JSON event to the browser."""
        try:
            msg = {"type": event_type}
            if data:
                msg.update(data)
            await self.ws.send_json(msg)
        except Exception as e:
            logger.error(f"[{self.session_id}] Send error: {e}")

    # ---- Audio analysis ----

    def _calculate_rms(self, audio_bytes: bytes) -> float:
        """Calculate RMS volume of PCM audio (16-bit signed, little-endian)."""
        if len(audio_bytes) < 2:
            return 0.0
        samples = struct.unpack(f"<{len(audio_bytes) // 2}h", audio_bytes)
        if not samples:
            return 0.0
        rms = (sum(s * s for s in samples) / len(samples)) ** 0.5
        return rms

    # ---- VAD ----

    def _detect_speech(self, audio_bytes: bytes) -> str:
        """
        Simple VAD based on RMS energy.
        Returns: 'speech_start', 'speech_continue', 'speech_end', or 'silence'
        """
        rms = self._calculate_rms(audio_bytes)
        self._chunk_count += 1

        # Debug: log RMS every 20 chunks (~5 seconds)
        if self._chunk_count % 20 == 0:
            logger.info(
                f"[{self.session_id}] VAD: chunk={self._chunk_count}, "
                f"rms={rms:.1f}, speaking={self._is_speaking}, "
                f"state={self._state.value}, "
                f"buf={len(self._audio_buffer)} bytes"
            )

        # Above speech threshold → definite speech
        if rms > self.SPEECH_THRESHOLD:
            self._silence_frames = 0
            self._speech_frames += 1

            if not self._is_speaking:
                self._is_speaking = True
                self._last_speech_time = time.time()
                return "speech_start"
            return "speech_continue"

        # Below speech threshold → count toward silence detection
        # This includes the dead zone (80-200) AND below silence (< 80).
        # Once speaking, ANY drop below SPEECH_THRESHOLD accumulates silence.
        self._silence_frames += 1
        silence_ms = self._silence_frames * self.FRAME_DURATION_MS

        if self._is_speaking and silence_ms >= self.SILENCE_DURATION_MS:
            speech_ms = self._speech_frames * self.FRAME_DURATION_MS
            self._is_speaking = False
            self._speech_frames = 0
            self._silence_frames = 0

            if speech_ms >= self.MIN_SPEECH_DURATION_MS:
                return "speech_end"
            else:
                self._audio_buffer.clear()
                return "silence"

        # Not speaking and below threshold → silence (don't start speech)
        if not self._is_speaking:
            return "silence"

        return "speech_continue"

    # ---- Audio chunk handler ----

    async def handle_audio_chunk(self, audio_bytes: bytes):
        """Process an incoming audio chunk from the browser."""

        # ======================================================
        # CRITICAL: State-based audio gating (ElevenLabs pattern)
        # ======================================================

        # During GREETING or AI_SPEAKING: ONLY check for barge-in
        if self._state in (SessionState.AI_SPEAKING, SessionState.GREETING):
            rms = self._calculate_rms(audio_bytes)
            self._chunk_count += 1

            # Debug every 20 chunks
            if self._chunk_count % 20 == 0:
                logger.info(
                    f"[{self.session_id}] VAD: chunk={self._chunk_count}, "
                    f"rms={rms:.1f}, state={self._state.value} (muted)"
                )

            # Check for barge-in: very loud audio for consecutive frames
            if rms > self.BARGE_IN_THRESHOLD:
                self._barge_in_frames += 1
                if self._barge_in_frames >= self.MIN_BARGE_IN_FRAMES:
                    # Real barge-in detected!
                    self._barge_in_frames = 0
                    await self._interrupt_ai()
                    # Start buffering this chunk as new speech
                    self._audio_buffer.clear()
                    self._audio_buffer.extend(audio_bytes)
                    self._is_speaking = True
                    self._speech_frames = 1
                    self._silence_frames = 0
                    self._set_state(SessionState.USER_SPEAKING)
                    await self.send_event("vad", {"speaking": True})
            else:
                self._barge_in_frames = 0
            return  # All other audio ignored during AI speech

        # During PROCESSING: ignore audio (pipeline is running)
        if self._state == SessionState.PROCESSING:
            return

        # Post-playback cooldown: ignore audio briefly after AI stops
        if self._playback_ended_at > 0:
            elapsed = (time.time() - self._playback_ended_at) * 1000
            if elapsed < self.PLAYBACK_COOLDOWN_MS:
                return  # Still in cooldown, ignore audio

        # ======================================================
        # LISTENING or USER_SPEAKING: Normal VAD processing
        # ======================================================

        vad_result = self._detect_speech(audio_bytes)

        if vad_result == "speech_start":
            logger.info(f"[{self.session_id}] Speech detected")
            self._set_state(SessionState.USER_SPEAKING)
            await self.send_event("vad", {"speaking": True})
            self._audio_buffer.clear()
            self._audio_buffer.extend(audio_bytes)

        elif vad_result == "speech_continue":
            if self._is_speaking:
                self._audio_buffer.extend(audio_bytes)

        elif vad_result == "speech_end":
            logger.info(
                f"[{self.session_id}] Speech ended, "
                f"buffer size: {len(self._audio_buffer)} bytes"
            )
            await self.send_event("vad", {"speaking": False})

            # Skip processing if audio is too short (noise/click)
            if len(self._audio_buffer) < self.MIN_AUDIO_BYTES:
                logger.info(
                    f"[{self.session_id}] Audio too short "
                    f"({len(self._audio_buffer)} bytes < {self.MIN_AUDIO_BYTES}), skipping"
                )
                self._audio_buffer.clear()
                self._set_state(SessionState.LISTENING)
                return

            # Process the complete utterance
            self._set_state(SessionState.PROCESSING)
            audio_data = bytes(self._audio_buffer)
            self._audio_buffer.clear()
            self._processing_task = asyncio.create_task(
                self._process_utterance(audio_data)
            )

    # ---- Barge-in ----

    async def _interrupt_ai(self):
        """Stop AI speech/processing when user interrupts (barge-in)."""
        logger.info(f"[{self.session_id}] ⚡ Barge-in: interrupting AI")

        # Cancel the processing pipeline task
        if self._processing_task and not self._processing_task.done():
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
            self._processing_task = None

        # Tell browser to stop playing audio
        await self.send_event("interrupt")
        await self.send_event("status", {"stage": "listening"})

    # ---- Playback done ----

    def handle_playback_done(self):
        """Called when the browser reports audio playback finished."""
        logger.info(f"[{self.session_id}] Browser reported playback done")
        self._playback_ended_at = time.time()
        self._barge_in_frames = 0
        # Reset VAD state to clean slate
        self._is_speaking = False
        self._speech_frames = 0
        self._silence_frames = 0
        self._audio_buffer.clear()
        self._set_state(SessionState.LISTENING)

    def handle_user_interrupt(self):
        """Called when the browser detects user spoke during AI playback."""
        logger.info(f"[{self.session_id}] Browser requested interrupt")

    # ---- Watchdog ----

    async def check_watchdog(self):
        """Reset stuck states. Called periodically from the main loop."""
        if self._state == SessionState.AI_SPEAKING:
            elapsed = time.time() - self._state_entered_at
            if elapsed > self.WATCHDOG_TIMEOUT_S:
                logger.warning(
                    f"[{self.session_id}] WATCHDOG: stuck in AI_SPEAKING "
                    f"for {elapsed:.0f}s, resetting to LISTENING"
                )
                self._playback_ended_at = time.time()
                self._set_state(SessionState.LISTENING)
                await self.send_event("status", {"stage": "listening"})

        elif self._state == SessionState.GREETING:
            elapsed = time.time() - self._state_entered_at
            if elapsed > 120:  # Allow time for first-run model loading (~40s)
                logger.warning(
                    f"[{self.session_id}] WATCHDOG: greeting stuck "
                    f"for {elapsed:.0f}s, resetting to LISTENING"
                )
                self._set_state(SessionState.LISTENING)
                await self.send_event("status", {"stage": "listening"})

    # ---- Pipeline ----

    async def _process_utterance(self, audio_data: bytes):
        """
        Process a complete user utterance through the pipeline:
        STT → RAG → LLM → TTS → stream audio back

        With per-stage timing + timeout protection + timing sent to frontend
        """
        turn_start = time.time()
        perf = {}  # Collect per-stage timings

        try:
            # ---- Step 1: Speech-to-Text ----
            await self.send_event("status", {"stage": "transcribing"})

            t0 = time.time()
            wav_data = self._pcm_to_wav(audio_data, 16000, 1, 16)

            # Timeout protection: 10 seconds max for STT
            try:
                transcript = await asyncio.wait_for(
                    rest_stt(wav_data), timeout=10.0
                )
            except asyncio.TimeoutError:
                logger.error(f"[{self.session_id}] STT timeout (10s)")
                self._set_state(SessionState.LISTENING)
                await self.send_event("status", {"stage": "listening"})
                return

            perf["stt_ms"] = (time.time() - t0) * 1000

            if not transcript or not transcript.strip():
                logger.warning(f"[{self.session_id}] Empty transcript — resetting to LISTENING")
                self._set_state(SessionState.LISTENING)
                await self.send_event("status", {"stage": "listening"})
                return

            logger.info(f"[{self.session_id}] Transcript: {transcript}")
            await self.send_event("transcript", {
                "text": transcript,
                "role": "user",
            })

            # ---- Step 2: RAG Context Search ----
            await self.send_event("status", {"stage": "searching"})

            t1 = time.time()
            try:
                rag_context = await asyncio.wait_for(
                    search_context(transcript), timeout=5.0
                )
            except asyncio.TimeoutError:
                logger.warning(f"[{self.session_id}] RAG timeout (5s), proceeding without context")
                rag_context = None

            perf["rag_ms"] = (time.time() - t1) * 1000

            if rag_context:
                logger.info(f"[{self.session_id}] RAG found context ({len(rag_context)} chars)")

            # ---- Step 3: LLM Streaming ----
            await self.send_event("status", {"stage": "thinking"})

            t2 = time.time()
            full_response = ""

            try:
                async for token in stream_llm(transcript, rag_context, self.conversation_history):
                    # Check for cancellation between tokens
                    if not self.is_active:
                        return
                    full_response += token
                    await self.send_event("token", {"text": token})
            except asyncio.CancelledError:
                raise  # Re-raise for barge-in handler
            except Exception as e:
                logger.error(f"[{self.session_id}] LLM error: {e}")
                full_response = "క్షమించండి, మళ్ళీ చెప్పగలరా?"

            perf["llm_ms"] = (time.time() - t2) * 1000

            logger.info(f"[{self.session_id}] LLM response ({len(full_response)} chars): {full_response[:80]}...")
            await self.send_event("transcript", {
                "text": full_response,
                "role": "assistant",
            })

            # ---- Step 4: TTS ----
            await self.send_event("status", {"stage": "speaking"})

            t3 = time.time()
            audio_bytes = None
            try:
                audio_bytes = await asyncio.wait_for(
                    rest_tts(full_response), timeout=15.0
                )
            except asyncio.TimeoutError:
                logger.error(f"[{self.session_id}] TTS timeout (15s)")

            # TTS retry once on failure
            if not audio_bytes:
                logger.warning(f"[{self.session_id}] TTS failed, retrying once...")
                try:
                    audio_bytes = await asyncio.wait_for(
                        rest_tts(full_response), timeout=15.0
                    )
                except (asyncio.TimeoutError, Exception) as e:
                    logger.error(f"[{self.session_id}] TTS retry failed: {e}")

            perf["tts_ms"] = (time.time() - t3) * 1000

            if audio_bytes:
                # Transition to AI_SPEAKING — mic audio will be ignored
                self._set_state(SessionState.AI_SPEAKING)
                audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                await self.send_event("audio", {
                    "data": audio_b64,
                    "format": "wav",
                })
            else:
                # TTS failed completely — reset to listening
                logger.error(f"[{self.session_id}] TTS failed after retry, resetting")
                self._set_state(SessionState.LISTENING)
                await self.send_event("status", {"stage": "listening"})

            # ---- Update conversation history ----
            self.conversation_history.append({"role": "user", "content": transcript})
            self.conversation_history.append({"role": "assistant", "content": full_response})

            # Cap conversation history
            if len(self.conversation_history) > self.MAX_HISTORY_ENTRIES:
                self.conversation_history = self.conversation_history[-self.MAX_HISTORY_ENTRIES:]

            # ---- Performance report ----
            perf["total_ms"] = (time.time() - turn_start) * 1000
            logger.info(
                f"[{self.session_id}] PERF: "
                f"STT={perf.get('stt_ms', 0):.0f}ms "
                f"RAG={perf.get('rag_ms', 0):.0f}ms "
                f"LLM={perf.get('llm_ms', 0):.0f}ms "
                f"TTS={perf.get('tts_ms', 0):.0f}ms "
                f"TOTAL={perf['total_ms']:.0f}ms"
            )

            # Send timing to frontend for visibility
            await self.send_event("perf", perf)

        except asyncio.CancelledError:
            logger.info(f"[{self.session_id}] Turn cancelled (barge-in)")
            self._set_state(SessionState.LISTENING)
            raise  # Re-raise so asyncio knows the task was cancelled
        except Exception as e:
            logger.error(f"[{self.session_id}] Pipeline error: {e}", exc_info=True)
            self._set_state(SessionState.LISTENING)
            await self.send_event("error", {"message": str(e)})
            await self.send_event("status", {"stage": "listening"})

    # ---- Auto-greeting ----

    async def _auto_greet(self):
        """
        Automatically greet the caller when the call starts.
        Queries RAG for company/business info, generates a dynamic
        greeting via LLM, converts to speech, and sends to browser.

        State is GREETING during this — all mic audio is ignored.
        """
        try:
            t0 = time.time()
            logger.info(f"[{self.session_id}] Generating auto-greeting...")
            await self.send_event("status", {"stage": "thinking"})

            # Get business context from uploaded PDFs
            business_context = await get_business_summary()

            # Generate greeting text via LLM (with timeout)
            try:
                greeting_text = await asyncio.wait_for(
                    generate_greeting(business_context), timeout=8.0
                )
            except asyncio.TimeoutError:
                logger.warning(f"[{self.session_id}] Greeting LLM timeout, using generic")
                greeting_text = "నమస్కారం! నేను ప్రియ, మీకు ఎలా సహాయం చేయగలను?"

            logger.info(f"[{self.session_id}] Greeting: {greeting_text}")

            # Send greeting transcript to frontend
            await self.send_event("transcript", {
                "text": greeting_text,
                "role": "assistant",
            })

            # Convert greeting to speech
            await self.send_event("status", {"stage": "speaking"})
            audio_bytes = await rest_tts(greeting_text)

            if audio_bytes:
                # Stay in GREETING state (which already mutes mic)
                # → will transition to LISTENING on playback_done
                self._set_state(SessionState.AI_SPEAKING)
                audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                await self.send_event("audio", {
                    "data": audio_b64,
                    "format": "wav",
                })
            else:
                self._set_state(SessionState.LISTENING)
                await self.send_event("status", {"stage": "listening"})

            # Add greeting to conversation history
            self.conversation_history.append({
                "role": "user",
                "content": "(కాల్ ప్రారంభమైంది)",
            })
            self.conversation_history.append({
                "role": "assistant",
                "content": greeting_text,
            })

            elapsed = (time.time() - t0) * 1000
            logger.info(f"[{self.session_id}] PERF greeting: {elapsed:.0f}ms")

        except Exception as e:
            logger.error(f"[{self.session_id}] Auto-greet error: {e}", exc_info=True)
            self._set_state(SessionState.LISTENING)
            await self.send_event("status", {"stage": "listening"})

    # ---- PCM to WAV conversion ----

    @staticmethod
    def _pcm_to_wav(pcm_data: bytes, sample_rate: int, channels: int, bits: int) -> bytes:
        """Add WAV header to raw PCM data."""
        data_size = len(pcm_data)
        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",
            36 + data_size,
            b"WAVE",
            b"fmt ",
            16,
            1,  # PCM
            channels,
            sample_rate,
            sample_rate * channels * bits // 8,
            channels * bits // 8,
            bits,
            b"data",
            data_size,
        )
        return header + pcm_data


# ---------------------------------------------------------------------------
# Active sessions registry
# ---------------------------------------------------------------------------

active_sessions: Dict[str, VoiceSession] = {}


async def handle_voice_websocket(websocket: WebSocket, session_id: str):
    """
    Main WebSocket handler for real-time voice conversations.

    Protocol (JSON messages from browser):
        {"type": "audio", "data": "<base64 PCM>"}     — audio chunk
        {"type": "config", "sampleRate": 16000, ...}   — initial config
        {"type": "end"}                                 — end session
        {"type": "playback_done"}                       — browser finished playing AI audio
        {"type": "user_interrupt"}                      — browser detected user speech during AI audio
        {"type": "pong"}                                — heartbeat response

    Protocol (JSON messages to browser):
        {"type": "vad", "speaking": true/false}         — VAD state
        {"type": "transcript", "text": "...", "role": "user"|"assistant"}
        {"type": "token", "text": "..."}                — LLM streaming token
        {"type": "audio", "data": "<base64 WAV>"}       — TTS audio
        {"type": "status", "stage": "listening"|"transcribing"|"thinking"|"speaking"}
        {"type": "interrupt"}                            — AI interrupted
        {"type": "perf", ...}                            — Per-stage timing
        {"type": "ping"}                                 — heartbeat request
        {"type": "error", "message": "..."}             — error
    """
    await websocket.accept()
    logger.info(f"[{session_id}] WebSocket connected")

    session = VoiceSession(websocket, session_id)
    active_sessions[session_id] = session

    # Auto-greet the caller (state starts as GREETING — mic is muted)
    session._processing_task = asyncio.create_task(session._auto_greet())

    try:
        while session.is_active:
            try:
                message = await asyncio.wait_for(
                    websocket.receive(), timeout=30.0
                )
            except asyncio.TimeoutError:
                # Heartbeat ping
                await session.send_event("ping")
                # Check watchdog for stuck states
                await session.check_watchdog()
                continue

            # Check watchdog on every message cycle
            await session.check_watchdog()

            if "text" in message:
                data = json.loads(message["text"])
                msg_type = data.get("type", "")

                if msg_type == "audio":
                    audio_b64 = data.get("data", "")
                    if audio_b64:
                        audio_bytes = base64.b64decode(audio_b64)
                        await session.handle_audio_chunk(audio_bytes)

                elif msg_type == "config":
                    logger.info(f"[{session_id}] Config: {data}")

                elif msg_type == "playback_done":
                    session.handle_playback_done()
                    await session.send_event("status", {"stage": "listening"})

                elif msg_type == "user_interrupt":
                    session.handle_user_interrupt()

                elif msg_type == "pong":
                    pass  # Heartbeat response, nothing to do

                elif msg_type == "end":
                    logger.info(f"[{session_id}] Session ended by client")
                    break

            elif "bytes" in message:
                await session.handle_audio_chunk(message["bytes"])

    except WebSocketDisconnect:
        logger.info(f"[{session_id}] WebSocket disconnected")
    except Exception as e:
        logger.error(f"[{session_id}] WebSocket error: {e}", exc_info=True)
    finally:
        session.is_active = False
        # Cancel any running processing task
        if session._processing_task and not session._processing_task.done():
            session._processing_task.cancel()
        active_sessions.pop(session_id, None)
        logger.info(f"[{session_id}] Session cleaned up")
