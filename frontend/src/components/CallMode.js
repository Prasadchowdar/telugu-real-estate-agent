import React, { useState, useRef, useEffect } from "react";
import { useRealtimeVoice } from "../hooks/useRealtimeVoice";
import { toast } from "react-toastify";

/**
 * Real-time call mode UI component.
 * Provides a phone-call-like experience with live transcription.
 */
export default function CallMode() {
    const {
        isConnected,
        isListening,
        isSpeaking,
        isAiSpeaking,
        status,
        messages,
        currentToken,
        error,
        latestPerf,
        startListening,
        stopListening,
        disconnect,
        clearMessages,
        clearError,
    } = useRealtimeVoice();

    const messagesEndRef = useRef(null);
    const [showUpload, setShowUpload] = useState(false);
    const [uploadStatus, setUploadStatus] = useState(null);

    // Auto-scroll to latest message
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages, currentToken]);

    // Show errors as toasts
    useEffect(() => {
        if (error) {
            toast.error(error);
            clearError();
        }
    }, [error, clearError]);

    // Handle call button click
    const handleCallToggle = async () => {
        if (isListening) {
            stopListening();
            disconnect();
        } else {
            try {
                await startListening();
            } catch (err) {
                toast.error("Failed to start: " + err.message);
            }
        }
    };

    // Handle PDF upload
    const handlePdfUpload = async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        if (!file.name.toLowerCase().endsWith(".pdf")) {
            toast.error("Please upload a PDF file");
            return;
        }

        setUploadStatus("uploading");
        try {
            const formData = new FormData();
            formData.append("file", file);

            const res = await fetch(
                `${process.env.REACT_APP_API_URL || "http://localhost:8001"}/api/upload/pdf`,
                { method: "POST", body: formData }
            );

            const data = await res.json();
            if (data.status === "success") {
                toast.success(`📄 ${data.message}`);
                setUploadStatus("success");
            } else {
                toast.error(data.message || "Upload failed");
                setUploadStatus("error");
            }
        } catch (err) {
            toast.error("Upload failed: " + err.message);
            setUploadStatus("error");
        }

        setTimeout(() => setUploadStatus(null), 3000);
    };

    // Status label
    const getStatusLabel = () => {
        if (isSpeaking && isAiSpeaking) return "⚡ Interrupting...";
        switch (status) {
            case "listening":
                return isSpeaking ? "Listening..." : "Speak now...";
            case "transcribing":
                return "Transcribing...";
            case "searching":
                return "Searching knowledge...";
            case "thinking":
                return "Thinking...";
            case "speaking":
                return isAiSpeaking ? "Speaking..." : "Speak now...";
            default:
                return isListening ? "Ready" : "Tap to start";
        }
    };

    // Status color
    const getStatusColor = () => {
        if (!isListening) return "#6b7280";
        if (isSpeaking) return "#10b981";
        if (isAiSpeaking || status === "speaking") return "#8b5cf6";
        if (status === "thinking" || status === "transcribing") return "#f59e0b";
        return "#3b82f6";
    };

    return (
        <div className="call-mode">
            {/* Header */}
            <div className="call-header">
                <h1 className="call-title">
                    <span className="call-logo">🏠</span>
                    Sri Sai Properties
                </h1>
                <p className="call-subtitle">Telugu Voice Assistant</p>

                {/* PDF Upload */}
                <div className="upload-section">
                    <button
                        className={`upload-btn ${uploadStatus || ""}`}
                        onClick={() => setShowUpload(!showUpload)}
                    >
                        📄 {uploadStatus === "uploading" ? "Uploading..." : "Upload PDF"}
                    </button>
                    {showUpload && (
                        <input
                            type="file"
                            accept=".pdf"
                            onChange={handlePdfUpload}
                            className="upload-input"
                        />
                    )}
                </div>
            </div>

            {/* Conversation Messages */}
            <div className="call-messages">
                {messages.length === 0 && !currentToken && (
                    <div className="call-empty">
                        <div className="empty-icon">🎙️</div>
                        <p>Start a call to chat with our AI assistant</p>
                        <p className="empty-hint">
                            Upload a PDF first to give the assistant knowledge about your properties
                        </p>
                    </div>
                )}

                {messages.map((msg, idx) => (
                    <div key={idx} className={`call-msg ${msg.role}`}>
                        <div className="msg-avatar">
                            {msg.role === "user" ? "👤" : "🤖"}
                        </div>
                        <div className="msg-content">
                            <div className="msg-role">
                                {msg.role === "user" ? "You" : "Priya (AI)"}
                            </div>
                            <div className="msg-text">{msg.content}</div>
                        </div>
                    </div>
                ))}

                {/* Streaming token display */}
                {currentToken && (
                    <div className="call-msg assistant streaming">
                        <div className="msg-avatar">🤖</div>
                        <div className="msg-content">
                            <div className="msg-role">Priya (AI)</div>
                            <div className="msg-text">
                                {currentToken}
                                <span className="cursor-blink">▊</span>
                            </div>
                        </div>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* Call Controls */}
            <div className="call-controls">
                {/* Status indicator */}
                <div className="call-status" style={{ color: getStatusColor() }}>
                    <span
                        className={`status-dot ${isListening ? "active" : ""} ${isSpeaking ? "speaking" : ""
                            } ${isAiSpeaking ? "ai-speaking" : ""}`}
                        style={{ backgroundColor: getStatusColor() }}
                    />
                    {getStatusLabel()}
                </div>

                {/* Performance metrics (dev overlay) */}
                {latestPerf && (
                    <div className="perf-bar">
                        <span>STT:{Math.round(latestPerf.stt_ms || 0)}</span>
                        <span>RAG:{Math.round(latestPerf.rag_ms || 0)}</span>
                        <span>LLM:{Math.round(latestPerf.llm_ms || 0)}</span>
                        <span>TTS:{Math.round(latestPerf.tts_ms || 0)}</span>
                        <span className="perf-total">={Math.round(latestPerf.total_ms || 0)}ms</span>
                    </div>
                )}

                {/* Waveform visualization */}
                {isListening && (
                    <div className={`waveform ${isSpeaking ? "active" : ""} ${isAiSpeaking ? "ai" : ""}`}>
                        {[...Array(12)].map((_, i) => (
                            <div
                                key={i}
                                className="wave-bar"
                                style={{
                                    animationDelay: `${i * 0.08}s`,
                                    height: isSpeaking || isAiSpeaking ? undefined : "4px",
                                }}
                            />
                        ))}
                    </div>
                )}

                {/* Call button */}
                <button
                    className={`call-button ${isListening ? "active" : ""}`}
                    onClick={handleCallToggle}
                    aria-label={isListening ? "End call" : "Start call"}
                >
                    {isListening ? (
                        <span className="call-icon end">✕</span>
                    ) : (
                        <span className="call-icon start">📞</span>
                    )}
                </button>

                {/* Clear button */}
                {messages.length > 0 && (
                    <button className="clear-btn" onClick={clearMessages}>
                        Clear Chat
                    </button>
                )}
            </div>
        </div>
    );
}
