import { useRef, useEffect } from "react";
import { Volume2, User } from "lucide-react";
import { Avatar, AvatarImage, AvatarFallback } from "../components/ui/avatar";
import { Button } from "../components/ui/button";
import { ScrollArea } from "../components/ui/scroll-area";

const AGENT_AVATAR =
  "https://images.unsplash.com/photo-1669829528850-959d7b08278b?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxODl8MHwxfHNlYXJjaHwxfHxpbmRpYW4lMjBidXNpbmVzcyUyMHdvbWFuJTIwcHJvZmVzc2lvbmFsJTIwcG9ydHJhaXQlMjBzbWlsaW5nfGVufDB8fHx8MTc3MTAwMzkxOXww&ixlib=rb-4.1.0&q=85&w=120";

const TypingIndicator = () => (
  <div className="flex items-end gap-2 chat-message-enter">
    <Avatar className="h-7 w-7 border border-slate-200 shrink-0">
      <AvatarImage src={AGENT_AVATAR} alt="Priya" />
      <AvatarFallback className="bg-blue-50 text-blue-700 text-[10px]">P</AvatarFallback>
    </Avatar>
    <div className="bg-white border border-slate-200 rounded-2xl rounded-tl-none px-4 py-3 shadow-sm">
      <div className="flex items-center gap-1">
        <span className="typing-dot" />
        <span className="typing-dot" />
        <span className="typing-dot" />
      </div>
    </div>
  </div>
);

const WelcomeMessage = () => (
  <div className="flex items-end gap-2 chat-message-enter" data-testid="welcome-message">
    <Avatar className="h-7 w-7 border border-slate-200 shrink-0">
      <AvatarImage src={AGENT_AVATAR} alt="Priya" />
      <AvatarFallback className="bg-blue-50 text-blue-700 text-[10px]">P</AvatarFallback>
    </Avatar>
    <div className="bg-white border border-slate-200 rounded-2xl rounded-tl-none p-4 max-w-[90%] shadow-sm">
      <p className="text-slate-800 text-sm leading-relaxed">
        నమస్కారం! నేను ప్రియ, శ్రీ సాయి ప్రాపర్టీస్ నుండి మీ రియల్ ఎస్టేట్ అసిస్టెంట్.
        హైదరాబాద్‌లో ప్రాపర్టీల గురించి మీకు సహాయం చేయడానికి నేను ఇక్కడ ఉన్నాను.
      </p>
      <p className="text-slate-500 text-xs mt-2">
        మైక్రోఫోన్ బటన్ నొక్కి తెలుగులో మాట్లాడండి
      </p>
    </div>
  </div>
);

const AudioPlayButton = ({ audioBase64, isPlaying, onPlay }) => {
  if (!audioBase64) return null;
  return (
    <Button
      variant="ghost"
      size="sm"
      data-testid="play-audio-btn"
      className="mt-1 h-7 px-2 text-blue-600 hover:text-blue-700 hover:bg-blue-50 gap-1 text-xs"
      onClick={() => onPlay(audioBase64)}
    >
      <Volume2 className="h-3.5 w-3.5" />
      {isPlaying ? "Playing..." : "Play audio"}
    </Button>
  );
};

export const ChatArea = ({
  messages,
  isProcessing,
  playingAudioId,
  onPlayAudio,
}) => {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isProcessing]);

  return (
    <ScrollArea className="flex-1 custom-scrollbar" data-testid="chat-area">
      <div className="px-4 py-6 space-y-5 pb-36 max-w-2xl mx-auto">
        <WelcomeMessage />

        {messages.map((msg, idx) => {
          const isUser = msg.role === "user";
          return (
            <div
              key={idx}
              data-testid={`chat-message-${idx}`}
              className={`flex items-end gap-2 chat-message-enter ${
                isUser ? "flex-row-reverse" : ""
              }`}
            >
              {/* Avatar */}
              {isUser ? (
                <div className="h-7 w-7 rounded-full bg-blue-600 flex items-center justify-center shrink-0">
                  <User className="h-3.5 w-3.5 text-white" />
                </div>
              ) : (
                <Avatar className="h-7 w-7 border border-slate-200 shrink-0">
                  <AvatarImage src={AGENT_AVATAR} alt="Priya" />
                  <AvatarFallback className="bg-blue-50 text-blue-700 text-[10px]">
                    P
                  </AvatarFallback>
                </Avatar>
              )}

              {/* Bubble */}
              <div
                className={
                  isUser
                    ? "bg-blue-600 text-white rounded-2xl rounded-tr-none px-4 py-2.5 max-w-[85%] shadow-sm"
                    : "bg-white border border-slate-200 text-slate-800 rounded-2xl rounded-tl-none px-4 py-3 max-w-[90%] shadow-sm"
                }
              >
                <p className="text-sm leading-relaxed whitespace-pre-wrap">
                  {msg.content}
                </p>
                {!isUser && msg.audio_base64 && (
                  <AudioPlayButton
                    audioBase64={msg.audio_base64}
                    isPlaying={playingAudioId === idx}
                    onPlay={() => onPlayAudio(idx, msg.audio_base64)}
                  />
                )}
              </div>
            </div>
          );
        })}

        {isProcessing && <TypingIndicator />}
        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  );
};
