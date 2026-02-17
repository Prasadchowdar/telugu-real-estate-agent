import { useState, useRef, useCallback } from "react";

/**
 * Custom hook for playing base64-encoded audio.
 *
 * Creates an Audio object from base64 WAV data and manages playback state.
 *
 * @returns {{ playingId: number|null, playAudio: (id: number, base64: string) => void, stopAudio: () => void }}
 */
export function useAudioPlayer() {
    const [playingId, setPlayingId] = useState(null);
    const audioRef = useRef(null);

    const stopAudio = useCallback(() => {
        if (audioRef.current) {
            audioRef.current.pause();
            audioRef.current.currentTime = 0;
            audioRef.current = null;
        }
        setPlayingId(null);
    }, []);

    const playAudio = useCallback(
        (id, base64, onEnded) => {
            // Stop any currently playing audio
            stopAudio();

            if (!base64) return;

            try {
                // Sarvam TTS returns base64 WAV — build a data URI
                const dataUri = base64.startsWith("data:")
                    ? base64
                    : `data:audio/wav;base64,${base64}`;

                const audio = new Audio(dataUri);

                audio.onended = () => {
                    setPlayingId(null);
                    audioRef.current = null;
                    if (onEnded) onEnded();
                };

                audio.onerror = () => {
                    console.error("Audio playback error");
                    setPlayingId(null);
                    audioRef.current = null;
                };

                audioRef.current = audio;
                setPlayingId(id);
                audio.play().catch((err) => {
                    console.error("Audio play failed:", err);
                    setPlayingId(null);
                });
            } catch (err) {
                console.error("Audio creation error:", err);
            }
        },
        [stopAudio]
    );

    return { playingId, playAudio, stopAudio };
}
