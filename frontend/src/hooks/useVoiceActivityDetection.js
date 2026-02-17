import { useRef, useCallback } from "react";

/**
 * Hook for Voice Activity Detection (VAD)
 * Detects silence in audio stream to auto-submit queries
 */
export function useVoiceActivityDetection() {
    const audioContextRef = useRef(null);
    const analyserRef = useRef(null);
    const sourceRef = useRef(null);
    const silenceTimerRef = useRef(null);
    const animationFrameRef = useRef(null);

    /**
     * Start VAD monitoring
     * @param {MediaStream} stream - Microphone stream
     * @param {Function} onSilence - Callback when silence is detected
     * @param {Object} options - { threshold: number, silenceDuration: number }
     */
    const startVAD = useCallback((stream, onSilence, options = {}) => {
        const {
            threshold = -50, // dB
            silenceDuration = 2000 // ms
        } = options;

        if (!stream || !stream.active) return;

        // cleanup previous
        stopVAD();

        // Setup Web Audio API
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        const audioContext = new AudioContext();
        const analyser = audioContext.createAnalyser();
        const source = audioContext.createMediaStreamSource(stream);

        analyser.fftSize = 512;
        analyser.smoothingTimeConstant = 0.1; // Fast response
        source.connect(analyser);

        audioContextRef.current = audioContext;
        analyserRef.current = analyser;
        sourceRef.current = source;

        const bufferLength = analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);

        let isSpeaking = false;
        let silenceStart = null;

        const checkVolume = () => {
            analyser.getByteFrequencyData(dataArray);

            // Calculate average volume
            let sum = 0;
            for (let i = 0; i < bufferLength; i++) {
                sum += dataArray[i];
            }
            const average = sum / bufferLength;
            const volumeDB = 20 * Math.log10(average / 255); // Normalize to 0-1, then dB

            // Check if above threshold
            if (volumeDB > threshold) {
                // Speech detected
                isSpeaking = true;
                silenceStart = null;
                if (silenceTimerRef.current) {
                    clearTimeout(silenceTimerRef.current);
                    silenceTimerRef.current = null;
                }
            } else {
                // Silence
                if (isSpeaking && !silenceStart) {
                    silenceStart = Date.now();
                }

                if (isSpeaking && silenceStart) {
                    const silenceDurationMs = Date.now() - silenceStart;
                    if (silenceDurationMs > silenceDuration) {
                        // Trigger silence callback
                        console.log("VAD: Silence detected, stopping recording...");
                        isSpeaking = false;
                        stopVAD(); // Stop monitoring
                        onSilence();
                    }
                }
            }

            animationFrameRef.current = requestAnimationFrame(checkVolume);
        };

        checkVolume();
    }, []);

    const stopVAD = useCallback(() => {
        if (animationFrameRef.current) {
            cancelAnimationFrame(animationFrameRef.current);
            animationFrameRef.current = null;
        }
        if (silenceTimerRef.current) {
            clearTimeout(silenceTimerRef.current);
            silenceTimerRef.current = null;
        }
        if (sourceRef.current) {
            sourceRef.current.disconnect();
            sourceRef.current = null;
        }
        if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
            audioContextRef.current.close();
            audioContextRef.current = null;
        }
    }, []);

    return { startVAD, stopVAD };
}
