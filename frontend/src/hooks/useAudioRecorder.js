import { useState, useRef, useCallback } from "react";

/**
 * Custom hook for recording audio from the microphone.
 *
 * Uses MediaRecorder API to capture audio as a WebM blob.
 * Handles permission prompts and error states.
 *
 * @returns {{ isRecording: boolean, startRecording: () => Promise<void>, stopRecording: () => Promise<Blob|null>, error: string|null }}
 */
export function useAudioRecorder() {
    const [isRecording, setIsRecording] = useState(false);
    const [stream, setStream] = useState(null);
    const [error, setError] = useState(null);
    const mediaRecorderRef = useRef(null);
    const chunksRef = useRef([]);
    const resolveRef = useRef(null);

    const startRecording = useCallback(async () => {
        setError(null);
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: 1,
                    sampleRate: 16000,
                    echoCancellation: true,
                    noiseSuppression: true,
                },
            });
            setStream(stream);

            chunksRef.current = [];

            // Prefer webm/opus, fall back to whatever is available
            const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
                ? "audio/webm;codecs=opus"
                : MediaRecorder.isTypeSupported("audio/webm")
                    ? "audio/webm"
                    : "";

            const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : {});

            recorder.ondataavailable = (e) => {
                if (e.data.size > 0) {
                    chunksRef.current.push(e.data);
                }
            };

            recorder.onstop = () => {
                // Stop all tracks so the browser mic indicator goes away
                stream.getTracks().forEach((t) => t.stop());

                const blob = new Blob(chunksRef.current, {
                    type: mimeType || "audio/webm",
                });
                chunksRef.current = [];

                if (resolveRef.current) {
                    resolveRef.current(blob);
                    resolveRef.current = null;
                }
            };

            mediaRecorderRef.current = recorder;
            recorder.start(250); // collect data every 250ms
            setIsRecording(true);
        } catch (err) {
            const msg =
                err.name === "NotAllowedError"
                    ? "Microphone permission denied. Please allow microphone access."
                    : err.name === "NotFoundError"
                        ? "No microphone found. Please connect a microphone."
                        : `Microphone error: ${err.message}`;
            setError(msg);
            throw new Error(msg);
        }
    }, []);

    const stopRecording = useCallback(() => {
        return new Promise((resolve) => {
            const recorder = mediaRecorderRef.current;
            if (!recorder || recorder.state === "inactive") {
                setIsRecording(false);
                resolve(null);
                return;
            }
            resolveRef.current = resolve;
            recorder.stop();
            setIsRecording(false);
            setStream(null);
        });
    }, []);

    return { isRecording, startRecording, stopRecording, error, stream };
}
