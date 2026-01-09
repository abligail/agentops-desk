"use client";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { AgentEvent } from "@/lib/types";
import {
  ArrowRightLeft,
  Wrench,
  WrenchIcon,
  RefreshCw,
  MessageSquareMore,
} from "lucide-react";
import { PanelSection } from "./panel-section";

interface RunnerOutputProps {
  runnerEvents: AgentEvent[];
}

function formatEventName(type: string) {
  return (type.charAt(0).toUpperCase() + type.slice(1)).replace("_", " ");
}

function EventIcon({ type }: { type: string }) {
  const className = "h-4 w-4 text-[#CDDCDE]";
  switch (type) {
    case "handoff":
      return <ArrowRightLeft className={className} />;
    case "tool_call":
      return <Wrench className={className} />;
    case "tool_output":
      return <WrenchIcon className={className} />;
    case "context_update":
      return <RefreshCw className={className} />;
    default:
      return null;
  }
}

function EventDetails({ event }: { event: AgentEvent }) {
  let details = null;
  const boxClass =
    "border border-[#16749D]/30 bg-[#F6FAFB] text-xs p-3 rounded-md flex flex-col gap-1.5 whitespace-pre-wrap break-words leading-relaxed text-[#0B1517] max-w-full min-w-0";
  switch (event.type) {
    case "handoff":
      details = event.metadata && (
        <div className={`${boxClass} w-full min-w-0 overflow-x-auto`}>
          <div>
            <span className="font-medium">From:</span>{" "}
            {event.metadata.source_agent}
          </div>
          <div>
            <span className="font-medium">To:</span>{" "}
            {event.metadata.target_agent}
          </div>
        </div>
      );
      break;
    case "tool_call":
      details = event.metadata && event.metadata.tool_args && (
        <div className={`${boxClass} w-full min-w-0 overflow-x-auto`}>
          <div className="text-xs font-medium text-[#0B1517] mb-1">Arguments</div>
          <pre className="text-[11px] text-[#0B1517] bg-white border border-[#16749D]/20 p-2 rounded overflow-x-auto whitespace-pre-wrap break-words w-full min-w-0 max-w-full">
            {JSON.stringify(event.metadata.tool_args, null, 2)}
          </pre>
        </div>
      );
      break;
    case "tool_output":
      details = event.metadata && event.metadata.tool_result && (
        <div className={`${boxClass} w-full min-w-0 overflow-x-auto`}>
          <div className="text-xs font-medium text-[#0B1517] mb-1">Result</div>
          <pre className="text-[11px] text-[#0B1517] bg-white border border-[#16749D]/20 p-2 rounded overflow-x-auto whitespace-pre-wrap break-words w-full min-w-0 max-w-full">
            {JSON.stringify(event.metadata.tool_result, null, 2)}
          </pre>
        </div>
      );
      break;
    case "context_update":
      details = event.metadata?.changes && (
        <div className={`${boxClass} w-full min-w-0 overflow-x-auto`}>
          {Object.entries(event.metadata.changes).map(([key, value]) => (
            <div key={key} className="text-xs">
              <span className="font-medium">{key}:</span>{" "}
              <span className="text-[#0B1517]/80">{value ?? "null"}</span>
            </div>
          ))}
        </div>
      );
      break;
    default:
      return null;
  }

  return (
    <div className="mt-1 text-sm space-y-2 w-full max-w-full min-w-0">
      {event.content && (
        <div className="bg-white border border-[#16749D]/20 rounded-lg px-3 py-2 font-mono text-[12px] text-[#0B1517] whitespace-pre-wrap break-words leading-relaxed shadow-sm overflow-x-auto w-full min-w-0 max-w-full">
          {event.content}
        </div>
      )}
      {details}
    </div>
  );
}

function TimeBadge({ timestamp }: { timestamp: Date }) {
  const date =
    timestamp && typeof (timestamp as any)?.toDate === "function"
      ? (timestamp as any).toDate()
      : timestamp;
  const formattedDate = new Date(date).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  return (
    <Badge
      variant="outline"
      className="text-[10px] h-5 bg-white text-zinc-500 border-gray-200"
    >
      {formattedDate}
    </Badge>
  );
}

export function RunnerOutput({ runnerEvents }: RunnerOutputProps) {
  return (
    <div className="flex-1 overflow-hidden">
      <PanelSection title="Runner Output" icon={<MessageSquareMore className="h-4 w-4 text-[#52B2CD]" />}>
        <ScrollArea className="h-[calc(100%-2rem)] rounded-md border border-[#16749D]/40 bg-[#CDDCDE] shadow-sm">
          <div className="p-4 space-y-3 w-full">
            {runnerEvents.length === 0 ? (
              <p className="text-center text-[#0B1517] p-4">
                No runner events yet
              </p>
            ) : (
              runnerEvents.map((event) => (
                <div key={event.id} className="w-full">
                  <Card className="w-full border border-[#16749D]/40 bg-white shadow-sm rounded-lg overflow-hidden">
                    <CardHeader className="flex flex-row justify-between items-center p-4">
                      <span className="font-medium text-[#0B1517] text-sm">
                        {event.agent}
                      </span>
                      <TimeBadge timestamp={event.timestamp} />
                    </CardHeader>

                    <CardContent className="flex items-start gap-3 p-4">
                      <div className="h-8 pl-0 pr-4 rounded-full bg-[#CDDCDE] flex items-center justify-center gap-1.5 border border-[#16749D]/40 flex-shrink-0">
                        <div className="flex-shrink-0 flex items-center justify-center">
                          <EventIcon type={event.type} />
                        </div>
                        <span className="text-xs font-medium text-[#0B1517] leading-none pt-[1px] whitespace-nowrap">
                          {formatEventName(event.type)}
                        </span>
                      </div>

                      <div className="flex-1 min-w-0 space-y-2 overflow-x-auto">
                        <EventDetails event={event} />
                      </div>
                    </CardContent>
                  </Card>
                </div>
              ))
            )}
          </div>
        </ScrollArea>
      </PanelSection>
    </div>
  );
}
