"use client";

import { useEffect, useRef, useState } from "react";
import { PanelSection } from "./panel-section";
import { Card, CardContent } from "@/components/ui/card";
import { NotebookPen } from "lucide-react";

interface ConversationContextProps {
  context: {
    passenger_name?: string;
    confirmation_number?: string;
    seat_number?: string;
    flight_number?: string;
    account_number?: string;
  };
}

export function ConversationContext({ context }: ConversationContextProps) {
  const [highlighted, setHighlighted] = useState<Set<string>>(new Set());
  const prevRef = useRef<typeof context | null>(null);

  useEffect(() => {
    const prev = prevRef.current || {};
    const keys = new Set([
      ...Object.keys(prev || {}),
      ...Object.keys(context || {}),
    ]);
    const changed = new Set<string>();
    keys.forEach((key) => {
      if ((prev as any)[key] !== (context as any)[key]) {
        changed.add(key);
      }
    });
    setHighlighted(changed);
    prevRef.current = context;
    if (changed.size === 0) return;
    const timer = setTimeout(() => setHighlighted(new Set()), 1200);
    return () => clearTimeout(timer);
  }, [context]);

  return (
    <PanelSection
      title="Conversation Context"
      icon={<NotebookPen className="h-4 w-4 text-[#8FA0A6]" />}
    >
      <Card className="bg-white border border-[#B7C3C8] shadow-sm">
        <CardContent className="p-3">
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(context).map(([key, value]) => {
              const isHighlight = highlighted.has(key);
              return (
                <div
                  key={key}
                  className={`flex items-center gap-2 p-2 rounded-md border shadow-sm transition-all ${
                    isHighlight
                      ? "bg-[#F6FAFB] border-[#8FA0A6] ring-1 ring-[#8FA0A6]/60"
                      : "bg-[#EEF2F3] border-[#B7C3C8]"
                  }`}
                >
                  <div
                    className={`w-2 h-2 rounded-full ${
                      isHighlight ? "bg-[#8FA0A6]" : "bg-[#8FA0A6]/70"
                    }`}
                  ></div>
                  <div className="text-xs text-[#0B1517]">
                    <span className="text-[#8C8C8E] font-light">{key}:</span>{" "}
                    <span
                      className={
                        value
                          ? "text-[#0B1517] font-light"
                          : "text-[#8C8C8E] italic"
                      }
                    >
                      {value || "null"}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </PanelSection>
  );
}