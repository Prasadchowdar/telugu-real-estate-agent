import { useState, useRef, useCallback } from "react";
import { Mic, Send, Paperclip, Square } from "lucide-react";
import { Button } from "../components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from "../components/ui/tooltip";

export const VoiceControls = ({
  isRecording,
  isProcessing,
  onStartRecording,
  onStopRecording,
  onSendText,
  onOpenPdfUpload,
}) => {
  const [textInput, setTextInput] = useState("");
  const [showTextInput, setShowTextInput] = useState(false);
  const inputRef = useRef(null);

  const handleSendText = useCallback(() => {
    const trimmed = textInput.trim();
    if (!trimmed) return;
    onSendText(trimmed);
    setTextInput("");
  }, [textInput, onSendText]);

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendText();
    }
  };

  return (
    <TooltipProvider delayDuration={300}>
      <div
        data-testid="voice-controls"
        className="fixed bottom-0 inset-x-0 z-50 bg-white/90 backdrop-blur-xl border-t border-slate-200 shadow-[0_-2px_20px_rgba(0,0,0,0.06)]"
      >
        <div className="max-w-2xl mx-auto px-4 py-3">
          {/* Text input row (toggled) */}
          {showTextInput && (
            <div className="flex items-center gap-2 mb-3" data-testid="text-input-row">
              <input
                ref={inputRef}
                data-testid="text-input"
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="తెలుగులో టైప్ చేయండి..."
                className="flex-1 h-10 rounded-full border border-slate-300 px-4 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent placeholder:text-slate-400"
                disabled={isProcessing}
              />
              <Button
                data-testid="send-text-btn"
                size="icon"
                className="h-10 w-10 rounded-full bg-blue-600 hover:bg-blue-700 text-white shadow-md"
                onClick={handleSendText}
                disabled={!textInput.trim() || isProcessing}
              >
                <Send className="h-4 w-4" />
              </Button>
            </div>
          )}

          <div className="flex items-center justify-center gap-4">
            {/* PDF Upload */}
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  data-testid="pdf-upload-btn"
                  variant="ghost"
                  size="icon"
                  className="h-11 w-11 rounded-full text-slate-500 hover:text-blue-600 hover:bg-blue-50"
                  onClick={onOpenPdfUpload}
                  disabled={isProcessing || isRecording}
                >
                  <Paperclip className="h-5 w-5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>PDF upload</TooltipContent>
            </Tooltip>

            {/* Mic button */}
            <button
              data-testid="mic-button"
              aria-label={isRecording ? "Stop recording" : "Start recording"}
              onClick={isRecording ? onStopRecording : onStartRecording}
              disabled={isProcessing}
              className={`
                h-16 w-16 rounded-full flex items-center justify-center
                focus:outline-none focus:ring-4 focus:ring-blue-200
                disabled:opacity-50 disabled:cursor-not-allowed
                ${isRecording
                  ? "bg-red-500 mic-recording text-white"
                  : "bg-blue-600 text-white shadow-xl hover:bg-blue-700 hover:scale-105"
                }
              `}
              style={{ transition: "background-color 0.2s, transform 0.2s" }}
            >
              {isRecording ? (
                <Square className="h-6 w-6 fill-current" />
              ) : isProcessing ? (
                <div className="flex items-center gap-[3px] h-6">
                  <span className="audio-bar" style={{ animationDelay: "0s" }} />
                  <span className="audio-bar" style={{ animationDelay: "0.1s" }} />
                  <span className="audio-bar" style={{ animationDelay: "0.2s" }} />
                  <span className="audio-bar" style={{ animationDelay: "0.3s" }} />
                  <span className="audio-bar" style={{ animationDelay: "0.15s" }} />
                </div>
              ) : (
                <Mic className="h-7 w-7" />
              )}
            </button>

            {/* Toggle text input */}
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  data-testid="toggle-text-btn"
                  variant="ghost"
                  size="icon"
                  className={`h-11 w-11 rounded-full ${showTextInput
                    ? "text-blue-600 bg-blue-50"
                    : "text-slate-500 hover:text-blue-600 hover:bg-blue-50"
                    }`}
                  onClick={() => {
                    setShowTextInput((v) => !v);
                    setTimeout(() => inputRef.current?.focus(), 100);
                  }}
                  disabled={isProcessing || isRecording}
                >
                  <Send className="h-5 w-5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Type message</TooltipContent>
            </Tooltip>
          </div>

          {/* Recording indicator */}
          {isRecording && (
            <p className="text-center text-xs text-red-500 font-medium mt-2 animate-pulse">
              Recording... tap to stop
            </p>
          )}
          {isProcessing && (
            <p className="text-center text-xs text-blue-500 font-medium mt-2">
              Processing...
            </p>
          )}
        </div>
      </div>
    </TooltipProvider>
  );
};
