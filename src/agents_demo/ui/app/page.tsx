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
            feedback:
              m.feedback === 1
                ? "positive"
                : m.feedback === 0
                ? "negative"
                : m.feedback ?? null,
            rating: m.rating ?? null,
            feedbackComment: m.comment ?? null,
          }))
        );
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
        feedback:
          m.feedback === 1
            ? "positive"
            : m.feedback === 0
            ? "negative"
            : m.feedback ?? null,
        rating: m.rating ?? null,
        feedbackComment: m.comment ?? null,
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

  const handleRatingSubmit = async (
    messageId: string,
    traceId: string | undefined,
    rating?: number,
    comment?: string
  ) => {
    if (!conversationId || !traceId) return;
    const trimmedComment = comment?.trim();
    if (rating == null && !trimmedComment) return;
    await sendFeedback({
      conversation_id: conversationId,
      message_id: messageId,
      trace_id: traceId,
      rating,
      comment: trimmedComment,
    });
    setMessages((prev) =>
      prev.map((m) =>
        m.id === messageId
          ? {
              ...m,
              rating: rating ?? m.rating ?? null,
              feedbackComment: trimmedComment ?? m.feedbackComment ?? null,
            }
          : m
      )
    );
  };

  return (
    <main className="flex h-screen gap-3 bg-gray-100 p-3">
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
        onRatingSubmit={handleRatingSubmit}
      />
    </main>
  );
}
