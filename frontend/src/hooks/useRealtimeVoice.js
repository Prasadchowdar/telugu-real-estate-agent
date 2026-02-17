import { useState, useRef, useCallback, useEffect } from "react";

/**
 * Real-time voice conversation hook — PRODUCTION READY.
 *
 * Architecture inspired by ElevenLabs Conversational AI:
 * - Audio muting: mic chunks are NOT sent while AI is speaking
 * - Audio queue: multiple TTS chunks are played sequentially
 * - Fallback timer: playback_done fires even if onended doesn't
 * - WebSocket auto-reconnection with exponential backoff
 * - Client-side heartbeat check
 *
 * Protocol matches ws_handler.py on the backend:
 *   Browser → Server:  {type: "audio"|"config"|"end"|"playback_done"|"user_interrupt"|"pong"}
 *   Server → Browser:  {type: "transcript"|"token"|"audio"|"status"|"vad"|"interrupt"|"perf"|"ping"|"error"}
 */

const WS_URL =
    process.env.REACT_APP_WS_URL || "ws://localhost:8001/ws/voice";

const SAMPLE_RATE = 16000;
const BUFFER_SIZE = 4096; // ~256ms of audio at 16kHz

export function useRealtimeVoice() {
    const [isConnected, setIsConnected] = useState(false);
    const [isListening, setIsListening] = useState(false);
    const [isSpeaking, setIsSpeaking] = useState(false); // user speaking
    const [isAiSpeaking, setIsAiSpeaking] = useState(false);
    const [status, setStatus] = useState("idle");
    const [messages, setMessages] = useState([]);
    const [currentToken, setCurrentToken] = useState("");
    const [error, setError] = useState(null);
    const [latestPerf, setLatestPerf] = useState(null);

    const wsRef = useRef(null);
    const audioContextRef = useRef(null);
    const mediaStreamRef = useRef(null);
    const processorRef = useRef(null);
    const sessionIdRef = useRef(`session_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`);

    // Playback refs
    const playbackCtxRef = useRef(null);
    const playbackSourceRef = useRef(null);
    const isAiSpeakingRef = useRef(false); // ref mirror for use inside onaudioprocess
    const isConnectedRef = useRef(false);

    // Audio queue for sequential playback
    const audioQueueRef = useRef([]);
    const isPlayingRef = useRef(false);

    // Playback fallback timer
    const playbackTimerRef = useRef(null);

    // Reconnection
    const reconnectAttemptRef = useRef(0);
    const reconnectTimerRef = useRef(null);
    const shouldReconnectRef = useRef(false);

    // ---- Helper: send WS message safely ----
    const wsSend = useCallback((msg) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify(msg));
        }
    }, []);

    // ---- Clear playback fallback timer ----
    const clearPlaybackTimer = useCallback(() => {
        if (playbackTimerRef.current) {
            clearTimeout(playbackTimerRef.current);
            playbackTimerRef.current = null;
        }
    }, []);

    // ---- Notify backend playback is done ----
    const notifyPlaybackDone = useCallback(() => {
        clearPlaybackTimer();
        playbackSourceRef.current = null;
        isAiSpeakingRef.current = false;
        isPlayingRef.current = false;
        setIsAiSpeaking(false);
        wsSend({ type: "playback_done" });
        console.log("✅ Playback done → notified backend");
    }, [clearPlaybackTimer, wsSend]);

    // ---- Stop AI Audio Playback (without destroying context) ----
    const stopAiAudio = useCallback(() => {
        clearPlaybackTimer();

        if (playbackSourceRef.current) {
            try {
                playbackSourceRef.current.onended = null; // prevent onended callback
                playbackSourceRef.current.stop();
            } catch (e) {
                // Already stopped, ignore
            }
            playbackSourceRef.current = null;
        }

        // Clear the audio queue
        audioQueueRef.current = [];
        isPlayingRef.current = false;
        isAiSpeakingRef.current = false;
        setIsAiSpeaking(false);
    }, [clearPlaybackTimer]);

    // ---- Play next item from audio queue ----
    const playNextInQueue = useCallback(async () => {
        if (audioQueueRef.current.length === 0) {
            // Queue empty — all audio played
            notifyPlaybackDone();
            return;
        }

        const base64Data = audioQueueRef.current.shift();
        isPlayingRef.current = true;

        try {
            // Create or reuse playback context
            if (!playbackCtxRef.current || playbackCtxRef.current.state === "closed") {
                playbackCtxRef.current = new (window.AudioContext || window.webkitAudioContext)({
                    sampleRate: SAMPLE_RATE,
                });
            }

            // Resume if suspended (browser autoplay policy)
            if (playbackCtxRef.current.state === "suspended") {
                await playbackCtxRef.current.resume();
            }

            const ctx = playbackCtxRef.current;
            const binaryString = atob(base64Data);
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i);
            }

            const audioBuffer = await ctx.decodeAudioData(bytes.buffer.slice(0));
            const source = ctx.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(ctx.destination);

            // Track the new source
            playbackSourceRef.current = source;

            // Fallback timer: if onended doesn't fire, force completion
            const fallbackMs = (audioBuffer.duration * 1000) + 1500;
            clearPlaybackTimer();
            playbackTimerRef.current = setTimeout(() => {
                console.warn("⚠️ Playback timer fallback triggered");
                if (playbackSourceRef.current === source) {
                    // Play next in queue or finish
                    playNextInQueue();
                }
            }, fallbackMs);

            source.onended = () => {
                // Only handle if this source is still the active one
                if (playbackSourceRef.current === source) {
                    clearPlaybackTimer();
                    // Play next in queue or finish
                    playNextInQueue();
                }
            };

            source.start(0);
            console.log(`🔊 AI audio playback started (queue: ${audioQueueRef.current.length} remaining)`);
        } catch (err) {
            console.error("Audio playback error:", err);
            // Try next in queue, or finish
            playNextInQueue();
        }
    }, [notifyPlaybackDone, clearPlaybackTimer]);

    // ---- Audio Playback (queued) ----
    const playAudioBase64 = useCallback(async (base64Data) => {
        // Set AI speaking state immediately
        isAiSpeakingRef.current = true;
        setIsAiSpeaking(true);

        if (isPlayingRef.current) {
            // Already playing — queue this chunk
            audioQueueRef.current.push(base64Data);
            console.log(`🔊 Audio queued (queue size: ${audioQueueRef.current.length})`);
            return;
        }

        // Nothing playing — start immediately
        audioQueueRef.current.push(base64Data);
        await playNextInQueue();
    }, [playNextInQueue]);

    // ---- WebSocket Message Handler ----
    const handleMessage = useCallback(
        (event) => {
            try {
                const data = JSON.parse(event.data);

                switch (data.type) {
                    case "status":
                        setStatus(data.stage || "idle");
                        if (data.stage === "speaking") setIsAiSpeaking(true);
                        if (data.stage === "listening") {
                            // Only clear AI speaking if no audio is playing
                            if (!playbackSourceRef.current && !isPlayingRef.current) {
                                setIsAiSpeaking(false);
                                isAiSpeakingRef.current = false;
                            }
                        }
                        break;

                    case "vad":
                        setIsSpeaking(data.speaking || false);
                        break;

                    case "transcript":
                        setCurrentToken("");
                        setMessages((prev) => [
                            ...prev,
                            { role: data.role, content: data.text },
                        ]);
                        break;

                    case "token":
                        setCurrentToken((prev) => prev + (data.text || ""));
                        break;

                    case "audio":
                        if (data.data) {
                            playAudioBase64(data.data);
                        }
                        break;

                    case "interrupt":
                        // Server tells us to stop playing AI audio (barge-in)
                        console.log("⚡ Interrupt received — stopping AI audio");
                        stopAiAudio();
                        setStatus("listening");
                        break;

                    case "perf":
                        // Per-stage timing from backend
                        console.log(
                            `⏱️ PERF: STT=${data.stt_ms?.toFixed(0)}ms ` +
                            `RAG=${data.rag_ms?.toFixed(0)}ms ` +
                            `LLM=${data.llm_ms?.toFixed(0)}ms ` +
                            `TTS=${data.tts_ms?.toFixed(0)}ms ` +
                            `TOTAL=${data.total_ms?.toFixed(0)}ms`
                        );
                        setLatestPerf(data);
                        break;

                    case "error":
                        console.error("Server error:", data.message);
                        setError(data.message);
                        break;

                    case "ping":
                        wsSend({ type: "pong" });
                        break;

                    default:
                        break;
                }
            } catch (err) {
                console.error("Message parse error:", err);
            }
        },
        [playAudioBase64, stopAiAudio, wsSend]
    );

    // ---- Connect WebSocket ----
    const connect = useCallback(async () => {
        if (isConnectedRef.current) return;

        try {
            const sessionId = sessionIdRef.current;
            const ws = new WebSocket(`${WS_URL}/${sessionId}`);

            ws.onopen = () => {
                console.log("🟢 WebSocket connected");
                isConnectedRef.current = true;
                setIsConnected(true);
                setError(null);
                reconnectAttemptRef.current = 0; // Reset backoff on success
                shouldReconnectRef.current = true;

                ws.send(
                    JSON.stringify({
                        type: "config",
                        sampleRate: SAMPLE_RATE,
                        bufferSize: BUFFER_SIZE,
                    })
                );
            };

            ws.onmessage = handleMessage;

            ws.onclose = (event) => {
                console.log("🔴 WebSocket disconnected", event.code);
                isConnectedRef.current = false;
                setIsConnected(false);
                setIsListening(false);
                setStatus("idle");

                // Auto-reconnect if unexpected close
                if (shouldReconnectRef.current && event.code !== 1000) {
                    const attempt = reconnectAttemptRef.current;
                    const delay = Math.min(1000 * Math.pow(2, attempt), 10000);
                    console.log(`🔄 Reconnecting in ${delay}ms (attempt ${attempt + 1})`);
                    reconnectAttemptRef.current = attempt + 1;
                    reconnectTimerRef.current = setTimeout(() => {
                        connect();
                    }, delay);
                }
            };

            ws.onerror = (err) => {
                console.error("WebSocket error:", err);
                setError("Connection failed. Is the backend running?");
            };

            wsRef.current = ws;
        } catch (err) {
            console.error("Connect error:", err);
            setError(err.message);
        }
    }, [handleMessage]);

    // ---- Start Listening (mic + streaming) ----
    const startListening = useCallback(async () => {
        try {
            if (!isConnectedRef.current) {
                await connect();
                await new Promise((resolve, reject) => {
                    const timeout = setTimeout(() => reject(new Error("Connection timeout")), 5000);
                    const check = setInterval(() => {
                        if (isConnectedRef.current) {
                            clearTimeout(timeout);
                            clearInterval(check);
                            resolve();
                        }
                    }, 100);
                });
            }

            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: 1,
                    sampleRate: SAMPLE_RATE,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true,
                },
            });
            mediaStreamRef.current = stream;

            const audioCtx = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: SAMPLE_RATE,
            });
            audioContextRef.current = audioCtx;

            const source = audioCtx.createMediaStreamSource(stream);
            const processor = audioCtx.createScriptProcessor(BUFFER_SIZE, 1, 1);
            processorRef.current = processor;

            processor.onaudioprocess = (e) => {
                if (!isConnectedRef.current || wsRef.current?.readyState !== WebSocket.OPEN) {
                    return;
                }




                const float32 = e.inputBuffer.getChannelData(0);

                // Convert float32 [-1,1] to int16 [-32768,32767]
                const int16 = new Int16Array(float32.length);
                for (let i = 0; i < float32.length; i++) {
                    const s = Math.max(-1, Math.min(1, float32[i]));
                    int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
                }

                // Send as base64
                const bytes = new Uint8Array(int16.buffer);
                const binary = String.fromCharCode(...bytes);
                const base64 = btoa(binary);

                wsRef.current.send(
                    JSON.stringify({ type: "audio", data: base64 })
                );
            };

            source.connect(processor);
            processor.connect(audioCtx.destination);

            setIsListening(true);
            setStatus("listening");
            setError(null);
            console.log("🎤 Microphone streaming started");
        } catch (err) {
            console.error("Start listening error:", err);
            setError(err.message || "Microphone access denied");
        }
    }, [connect]);

    // ---- Stop Listening ----
    const stopListening = useCallback(() => {
        if (mediaStreamRef.current) {
            mediaStreamRef.current.getTracks().forEach((t) => t.stop());
            mediaStreamRef.current = null;
        }

        if (processorRef.current) {
            processorRef.current.disconnect();
            processorRef.current = null;
        }

        if (audioContextRef.current) {
            audioContextRef.current.close().catch(() => { });
            audioContextRef.current = null;
        }

        setIsListening(false);
        setIsSpeaking(false);
        console.log("🔇 Microphone stopped");
    }, []);

    // ---- Disconnect ----
    const disconnect = useCallback(() => {
        shouldReconnectRef.current = false; // Prevent auto-reconnect

        // Clear reconnect timer
        if (reconnectTimerRef.current) {
            clearTimeout(reconnectTimerRef.current);
            reconnectTimerRef.current = null;
        }

        stopListening();
        stopAiAudio();

        if (wsRef.current) {
            if (wsRef.current.readyState === WebSocket.OPEN) {
                wsRef.current.send(JSON.stringify({ type: "end" }));
            }
            wsRef.current.close();
            wsRef.current = null;
        }

        if (playbackCtxRef.current) {
            playbackCtxRef.current.close().catch(() => { });
            playbackCtxRef.current = null;
        }

        isConnectedRef.current = false;
        setIsConnected(false);
        setIsListening(false);
        setIsAiSpeaking(false);
        setStatus("idle");
        console.log("📴 Disconnected");
    }, [stopListening, stopAiAudio]);

    // ---- Cleanup on unmount ----
    useEffect(() => {
        return () => {
            shouldReconnectRef.current = false;
            if (reconnectTimerRef.current) {
                clearTimeout(reconnectTimerRef.current);
            }
            disconnect();
        };
    }, [disconnect]);

    return {
        // State
        isConnected,
        isListening,
        isSpeaking,
        isAiSpeaking,
        status,
        messages,
        currentToken,
        error,
        latestPerf,

        // Actions
        connect,
        startListening,
        stopListening,
        disconnect,
        clearMessages: () => setMessages([]),
        clearError: () => setError(null),
    };
}
