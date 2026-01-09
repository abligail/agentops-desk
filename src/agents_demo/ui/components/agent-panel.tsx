"use client";

import { Sparkles } from "lucide-react";
import type { Agent, AgentEvent, GuardrailCheck } from "@/lib/types";
import { AgentsList } from "./agents-list";
import { Guardrails } from "./guardrails";
import { ConversationContext } from "./conversation-context";
import { RunnerOutput } from "./runner-output";

interface AgentPanelProps {
  agents: Agent[];
  currentAgent: string;
  events: AgentEvent[];
  guardrails: GuardrailCheck[];
  context: {
    passenger_name?: string;
    confirmation_number?: string;
    seat_number?: string;
    flight_number?: string;
    account_number?: string;
  };
}

export function AgentPanel({
  agents,
  currentAgent,
  events,
  guardrails,
  context,
}: AgentPanelProps) {
  const activeAgent = agents.find((a) => a.name === currentAgent);
  const runnerEvents = events.filter((e) => e.type !== "message");

  return (
    <div className="flex-[0.62] min-w-0 h-full flex flex-col bg-[#EFF2F3] border border-[#B7C3C8] rounded-2xl shadow-xl overflow-hidden">
      <div className="bg-[#52B2CD] text-white h-12 px-4 flex items-center gap-3 shadow-md">
        <div className="flex items-center justify-center h-8 w-8 rounded-full bg-white/75">
          <Sparkles className="h-5 w-5 text-[#0B1517]" />
        </div>
        <h1 className="font-semibold text-sm sm:text-base lg:text-lg text-white">Agent View</h1>
        <span className="ml-auto text-xs font-medium tracking-wide text-white/80">
          Airline • Orchestrator
        </span>
      </div>

      <div className="flex-1 overflow-y-auto p-6 bg-[#EFF2F3]">
        <AgentsList agents={agents} currentAgent={currentAgent} />
        <Guardrails
          guardrails={guardrails}
          inputGuardrails={activeAgent?.input_guardrails ?? []}
        />
        <ConversationContext context={context} />
        <RunnerOutput runnerEvents={runnerEvents} />
      </div>
    </div>
  );
}