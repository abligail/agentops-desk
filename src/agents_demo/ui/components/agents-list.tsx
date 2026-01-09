"use client";

import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Users2 } from "lucide-react";
import { PanelSection } from "./panel-section";
import type { Agent } from "@/lib/types";

interface AgentsListProps {
  agents: Agent[];
  currentAgent: string;
}

export function AgentsList({ agents, currentAgent }: AgentsListProps) {
  const activeAgent = agents.find((a) => a.name === currentAgent);
  return (
    <PanelSection
      title="Available Agents"
      icon={<Users2 className="h-4 w-4 text-[#8FA0A6]" />}
    >
      <div className="grid grid-cols-3 gap-3">
        {agents.map((agent) => {
          const isActive = agent.name === currentAgent;
          const isAccessible =
            isActive || activeAgent?.handoffs.includes(agent.name);
          return (
            <Card
              key={agent.name}
              className={`transition-all ${
                isAccessible
                  ? "bg-white border border-[#B7C3C8]"
                  : "bg-[#EEF2F3] border border-dashed border-[#AEB7BC] opacity-85 cursor-not-allowed"
              } ${
                isActive ? "ring-2 ring-[#8FA0A6] shadow-md shadow-[#8FA0A6]/25" : ""
              }`}
            >
              <CardHeader className="p-3 pb-1">
                <CardTitle className="text-sm flex items-center text-[#0B1517]">
                  {agent.name}
                </CardTitle>
              </CardHeader>
              <CardContent className="p-3 pt-1 relative min-h-[96px]">
                <p
                  className={`text-xs font-light ${
                    isAccessible ? "text-[#8C8C8E]" : "text-[#0B1517]/70"
                  }`}
                >
                  {agent.description}
                </p>
                <div className="absolute bottom-2 right-2">
                  {isActive ? (
                    <Badge className="bg-[#52B2CD] hover:bg-[#16749D] text-[#0B1517] font-semibold">
                      Active
                    </Badge>
                  ) : isAccessible ? (
                    <Badge className="bg-white text-[#16749D] border border-[#16749D]/50 font-semibold">
                      Available
                    </Badge>
                  ) : (
                    <Badge className="bg-[#8C8C8E] text-[#0B1517] font-semibold">
                      Locked
                    </Badge>
                  )}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </PanelSection>
  );
}