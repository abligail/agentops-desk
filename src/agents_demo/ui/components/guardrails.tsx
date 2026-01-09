"use client";

import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ShieldCheck, CheckCircle2, XCircle } from "lucide-react";
import { PanelSection } from "./panel-section";
import type { GuardrailCheck } from "@/lib/types";

interface GuardrailsProps {
  guardrails: GuardrailCheck[];
  inputGuardrails: string[];
}

export function Guardrails({ guardrails, inputGuardrails }: GuardrailsProps) {
  const guardrailNameMap: Record<string, string> = {
    relevance_guardrail: "Relevance Guardrail",
    jailbreak_guardrail: "Jailbreak Guardrail",
  };

  const guardrailDescriptionMap: Record<string, string> = {
    "Relevance Guardrail": "Ensure messages are relevant to airline support",
    "Jailbreak Guardrail":
      "Detect and block attempts to bypass or override system instructions",
  };

  const extractGuardrailName = (rawName: string): string =>
    guardrailNameMap[rawName] ?? rawName;

  const guardrailsToShow: GuardrailCheck[] = inputGuardrails.map((rawName) => {
    const existing = guardrails.find((gr) => gr.name === rawName);
    if (existing) {
      return existing;
    }
    return {
      id: rawName,
      name: rawName,
      input: "",
      reasoning: "",
      passed: false,
      timestamp: new Date(),
    };
  });

  return (
    <PanelSection
      title="Guardrails"
      icon={<ShieldCheck className="h-4 w-4 text-[#8FA0A6]" />}
    >
      <div className="grid grid-cols-3 gap-3">
        {guardrailsToShow.map((gr) => (
          <Card
            key={gr.id}
            className={`bg-white border border-[#B7C3C8] transition-all ${
              !gr.input ? "opacity-60" : ""
            }`}
          >
            <CardHeader className="p-3 pb-1">
              <CardTitle className="text-sm flex items-center text-[#0B1517]">
                {extractGuardrailName(gr.name)}
              </CardTitle>
            </CardHeader>
            <CardContent className="p-3 pt-1">
              <p className="text-xs font-light text-[#8C8C8E] mb-1">
                {(() => {
                  const title = extractGuardrailName(gr.name);
                  return guardrailDescriptionMap[title] ?? gr.input;
                })()}
              </p>
              <div className="flex text-xs">
                {!gr.input || gr.passed ? (
                  <Badge className="mt-2 px-2 py-1 bg-[#52B2CD] hover:bg-[#16749D] flex items-center text-[#0B1517] font-semibold">
                    <CheckCircle2 className="h-4 w-4 mr-1 text-[#0B1517]" />
                    Passed
                  </Badge>
                ) : (
                  <Badge className="mt-2 px-2 py-1 bg-rose-500 hover:bg-rose-600 flex items-center text-white">
                    <XCircle className="h-4 w-4 mr-1 text-white" />
                    Failed
                  </Badge>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </PanelSection>
  );
}
