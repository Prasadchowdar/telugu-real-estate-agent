import { Building2 } from "lucide-react";
import { Avatar, AvatarImage, AvatarFallback } from "../components/ui/avatar";

const AGENT_AVATAR =
  "https://images.unsplash.com/photo-1669829528850-959d7b08278b?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxODl8MHwxfHNlYXJjaHwxfHxpbmRpYW4lMjBidXNpbmVzcyUyMHdvbWFuJTIwcHJvZmVzc2lvbmFsJTIwcG9ydHJhaXQlMjBzbWlsaW5nfGVufDB8fHx8MTc3MTAwMzkxOXww&ixlib=rb-4.1.0&q=85&w=120";

export const Header = () => {
  return (
    <header
      data-testid="app-header"
      className="sticky top-0 z-50 h-16 bg-white/80 backdrop-blur-md border-b border-slate-200 flex items-center justify-between px-4 md:px-6"
    >
      {/* Left: Brand */}
      <div className="flex items-center gap-2.5">
        <div className="h-9 w-9 rounded-lg bg-blue-600 flex items-center justify-center shadow-sm">
          <Building2 className="h-5 w-5 text-white" />
        </div>
        <div className="leading-tight">
          <p className="text-sm font-bold text-slate-900 tracking-tight">
            Sri Sai Properties
          </p>
          <p className="text-[11px] text-slate-500">Hyderabad</p>
        </div>
      </div>

      {/* Right: Agent avatar */}
      <div className="flex items-center gap-2">
        <div className="text-right leading-tight hidden sm:block">
          <p className="text-xs font-semibold text-slate-700">
            ప్రియ
          </p>
          <p className="text-[10px] text-emerald-600 font-medium">Online</p>
        </div>
        <div className="relative">
          <Avatar className="h-9 w-9 border-2 border-white shadow-sm">
            <AvatarImage src={AGENT_AVATAR} alt="Priya" />
            <AvatarFallback className="bg-blue-100 text-blue-700 text-xs font-bold">
              P
            </AvatarFallback>
          </Avatar>
          <span className="absolute bottom-0 right-0 h-2.5 w-2.5 rounded-full bg-emerald-500 border-2 border-white" />
        </div>
      </div>
    </header>
  );
};
