"use client";

import { useEffect, useState } from "react";
import { AgentPanel } from "@/components/agent-panel";
import { Chat } from "@/components/Chat";
import type { Agent, AgentEvent, GuardrailCheck, Message } from "@/lib/types";
import { callChatAPI, sendFeedback } from "@/lib/api";

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [currentAgent, setCurrentAgent] = useState<string>("");
  const [guardrails, setGuardrails] = useState<GuardrailCheck[]>([]);
  const [context, setContext] = useState<Record<string, any>>({});
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [lastTraceId, setLastTraceId] = useState<string | null>(null);
  // Loading state while awaiting assistant response
  const [isLoading, setIsLoading] = useState(false);

  // Boot the conversation
  useEffect(() => {
    (async () => {
      const data = await callChatAPI("", conversationId ?? "");
      if (!data) return;
      setConversationId(data.conversation_id);
      setCurrentAgent(data.current_agent);
      setContext(data.context);
      const initialEvents = (data.events || []).map((e: any) => ({
        ...e,
        timestamp: new Date(e.timestamp ?? Date.now()),
      }));
      setEvents(initialEvents);
      setAgents(data.agents || []);
      if (data.guardrails) {
        setGuardrails(
          data.guardrails.map((g: any) => ({
            ...g,
            timestamp: new Date(g.timestamp ?? Date.now()),
          }))
        );
      }
      if (Array.isArray(data.messages)) {
        setMessages(
          data.messages.map((m: any) => ({
            id: m.id ?? Date.now().toString() + Math.random().toString(),
            content: m.content,
            role: "assistant",
            agent: m.agent,
            traceId: m.trace_id,
            timestamp: new Date(m.timestamp ?? Date.now()),
            feedback: m.feedback ?? null,
          }))
        );
      }
      if (data.trace_id) {
        setLastTraceId(data.trace_id);
      }
    })();
  }, []);

  // Send a user message
  const handleSendMessage = async (content: string) => {
    const userMsg: Message = {
      id: Date.now().toString(),
      content,
      role: "user",
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    const data = await callChatAPI(content, conversationId ?? "");
    if (!data) {
      setIsLoading(false);
      return;
    }

    if (!conversationId) setConversationId(data.conversation_id);
    setCurrentAgent(data.current_agent);
    setContext(data.context);
    if (data.trace_id) {
      setLastTraceId(data.trace_id);
    }
    if (data.events) {
      const stamped = data.events.map((e: any) => ({
        ...e,
        timestamp: new Date(e.timestamp ?? Date.now()),
      }));
      setEvents((prev) => [...prev, ...stamped]);
    }
    if (data.agents) setAgents(data.agents);
    // Update guardrails state
    if (data.guardrails) {
      setGuardrails(
        data.guardrails.map((g: any) => ({
          ...g,
          timestamp: new Date(g.timestamp ?? Date.now()),
        }))
      );
    }

    if (data.messages) {
      const responses: Message[] = data.messages.map((m: any) => ({
        id: m.id ?? Date.now().toString() + Math.random().toString(),
        content: m.content,
        role: "assistant",
        agent: m.agent,
        traceId: m.trace_id ?? data.trace_id,
        timestamp: new Date(m.timestamp ?? Date.now()),
        feedback: m.feedback ?? null,
      }));
      setMessages((prev) => [...prev, ...responses]);
    }

    setIsLoading(false);
  };

  const handleFeedback = async (
    messageId: string,
    traceId: string | undefined,
    positive: boolean
  ) => {
    if (!conversationId || !traceId) return;
    await sendFeedback({
      conversation_id: conversationId,
      message_id: messageId,
      trace_id: traceId,
      score: positive ? 1 : 0,
    });
    setMessages((prev) =>
      prev.map((m) =>
        m.id === messageId
          ? { ...m, feedback: positive ? "positive" : "negative" }
          : m
      )
    );
  };

  const MetaCard = ({ label, value }: { label: string; value: string }) => (
    <div className="rounded-xl border border-white/10 bg-white/10 px-4 py-3 shadow-lg backdrop-blur">
      <p className="text-[11px] uppercase tracking-[0.25em] text-emerald-200">
        {label}
      </p>
      <div className="mt-1 text-base font-semibold text-white break-words">
        {value}
      </div>
    </div>
  );

  const traceLabel =
    lastTraceId ||
    [...messages]
      .slice()
      .reverse()
      .find((m) => m.traceId)?.traceId ||
    "Awaiting reply";

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 p-4 text-slate-50">
      <div className="mx-auto flex max-w-7xl flex-col gap-4">
        <header className="rounded-2xl border border-white/10 bg-white/5 px-6 py-5 shadow-2xl shadow-emerald-500/10 backdrop-blur">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1">
              <p className="text-xs uppercase tracking-[0.25em] text-emerald-200">
                Airline Ops Pilot
              </p>
              <h1 className="text-2xl font-semibold text-white">
                Multi-Agent Orchestration Desk
              </h1>
              <p className="text-sm text-slate-200/80">
                Track delegations, guardrails, and customer context in real
                time.
              </p>
            </div>
            <div className="hidden items-center gap-2 rounded-full border border-emerald-400/30 bg-emerald-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-emerald-100 sm:flex">
              Live Session
            </div>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <MetaCard
              label="Conversation"
              value={conversationId ?? "Starting up"}
            />
            <MetaCard
              label="Active Agent"
              value={currentAgent || "Triage Agent"}
            />
            <MetaCard label="Last Trace" value={traceLabel} />
          </div>
        </header>

        <div className="flex h-[calc(100vh-13rem)] flex-col gap-3 lg:flex-row">
          <AgentPanel
            agents={agents}
            currentAgent={currentAgent}
            events={events}
            guardrails={guardrails}
            context={context}
          />
          <Chat
            messages={messages}
            onSendMessage={handleSendMessage}
            isLoading={isLoading}
            conversationId={conversationId ?? undefined}
            onFeedback={handleFeedback}
          />
        </div>
      </div>
    </main>
  );
}
