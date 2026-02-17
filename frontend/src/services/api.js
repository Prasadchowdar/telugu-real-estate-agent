import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "http://localhost:8001";
const API_BASE = `${BACKEND_URL}/api`;

const client = axios.create({
  baseURL: API_BASE,
  timeout: 60000, // 60s — voice processing takes time
});

/**
 * Send recorded audio for voice chat.
 * @param {Blob} audioBlob  – WebM audio blob from MediaRecorder
 * @param {string} sessionId – Conversation session ID
 * @returns {Promise<{session_id, user_transcript, agent_response, agent_audio_base64, timestamp}>}
 */
export async function sendVoiceMessage(audioBlob, sessionId) {
  const form = new FormData();
  form.append("audio", audioBlob, "recording.webm");
  form.append("session_id", sessionId);

  const { data } = await client.post("/chat/voice", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

/**
 * Send a text message for text-based chat.
 * @param {string} message   – User's text message
 * @param {string} sessionId – Conversation session ID
 * @returns {Promise<{session_id, agent_response, agent_audio_base64, timestamp}>}
 */
export async function sendTextMessage(message, sessionId) {
  const { data } = await client.post("/chat/text", {
    session_id: sessionId,
    message,
  });
  return data;
}

/**
 * Upload a PDF for RAG knowledge base.
 * @param {File} file – PDF file (max 10 MB)
 * @returns {Promise<{doc_id, filename, num_chunks, preview}>}
 */
export async function uploadPdf(file) {
  const form = new FormData();
  form.append("file", file);

  const { data } = await client.post("/upload/pdf", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

/**
 * Fetch conversation history for a session.
 * @param {string} sessionId
 * @returns {Promise<{session_id, turns: Array}>}
 */
export async function getHistory(sessionId) {
  const { data } = await client.get(`/history/${sessionId}`);
  return data;
}

/**
 * List all uploaded documents.
 * @returns {Promise<Array<{doc_id, filename, num_chunks, preview}>>}
 */
export async function getDocuments() {
  const { data } = await client.get("/documents");
  return data;
}

/**
 * Delete an uploaded document.
 * @param {string} docId
 * @returns {Promise<{status: string}>}
 */
export async function deleteDocument(docId) {
  const { data } = await client.delete(`/documents/${docId}`);
  return data;
}

/**
 * Health check.
 * @returns {Promise<{status, sarvam_key_set}>}
 */
export async function healthCheck() {
  const { data } = await client.get("/health");
  return data;
}
