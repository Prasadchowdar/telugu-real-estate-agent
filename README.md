# Real-Time Telugu Voice Agent (AI Sales Assistant)

A production-ready conversational AI agent designed for real estate sales. Converses naturally in Telugu with full-duplex audio, interruption handling (barge-in), and context-aware responses using RAG.

## 🚀 Key Features

*   **🎙️ Real-Time Voice Conversation:** Low-latency WebSockets for fluid dialogue.
*   **⚡ Barge-In / Interruption:** Users can speak over the AI to interrupt instantly (handled by backend RMS-based VAD).
*   **🧠 RAG Integration:** Upload property PDFs to give the AI specific knowledge (ChromaDB + SentenceTransformers).
*   **🗣️ Telugu Native:** Powered by Sarvam AI (Saarika v3 STT + Bulbul v3 TTS + Sarvam-M LLM).
*   **🔄 Robust State Machine:** Handles `GREETING`, `LISTENING`, `AI_SPEAKING`, and `PROCESSING` states gracefully with watchdog timers.

## 🛠️ Architecture

*   **Frontend:** React 19, AudioWorklet (for raw PCM streaming), ShadCN UI, TailwindCSS.
*   **Backend:** Python 3.11+, FastAPI (Async), Websockets, HTTPX.
*   **AI Models:** Sarvam-M (LLM), Saarika (STT), Bulbul (TTS).

## 📦 Setup & Run

### Backend

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

# Create .env with SARVAM_API_KEY=...
python -m uvicorn server:app --host 0.0.0.0 --port 8001
```

### Frontend

```bash
cd frontend
npm install
# Create .env with REACT_APP_WS_URL=ws://localhost:8001
npm start
```

## 🔒 Security & Deployment

*   `.env` files are excluded from git to protect API keys.
*   `chroma_db` (local vector store) and `uploads` are excluded to keep the repo clean.
*   `test_reports` and logs are excluded.
