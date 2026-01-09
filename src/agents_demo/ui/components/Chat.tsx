"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import type { Message } from "@/lib/types";
import ReactMarkdown from "react-markdown";
import { SeatMap } from "./seat-map";

interface ChatProps {
  messages: Message[];
  onSendMessage: (message: string) => void;
  /** Whether waiting for assistant response */
  isLoading?: boolean;
  conversationId?: string;
  onFeedback?: (
    messageId: string,
    traceId: string | undefined,
    positive: boolean
  ) => void;
  onRatingSubmit?: (
    messageId: string,
    traceId: string | undefined,
    rating?: number,
    comment?: string
  ) => void;
}

export function Chat({
  messages,
  onSendMessage,
  isLoading,
  onFeedback,
  onRatingSubmit,
  conversationId,
}: ChatProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [inputText, setInputText] = useState("");
  const [isComposing, setIsComposing] = useState(false);
  const [showSeatMap, setShowSeatMap] = useState(false);
  const [selectedSeat, setSelectedSeat] = useState<string | undefined>(undefined);
  const [seenSeatMapTriggers, setSeenSeatMapTriggers] = useState(0);
  const [draftRatings, setDraftRatings] = useState<Record<string, number>>({});
  const [draftComments, setDraftComments] = useState<Record<string, string>>({});

  // Auto-scroll to bottom when messages or loading indicator change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "instant" });
  }, [messages, isLoading]);

  // Watch for special seat map trigger messages; open the selector once per trigger.
  useEffect(() => {
    const triggerCount = messages.filter(
      (m) => m.role === "assistant" && m.content === "DISPLAY_SEAT_MAP"
    ).length;

    if (triggerCount > seenSeatMapTriggers) {
      setSeenSeatMapTriggers(triggerCount);
      setSelectedSeat(undefined);
      setShowSeatMap(true);
    }
  }, [messages, seenSeatMapTriggers]);

  const handleSend = useCallback(() => {
    if (!inputText.trim()) return;
    onSendMessage(inputText);
    setInputText("");
  }, [inputText, onSendMessage]);

  const handleSeatSelect = useCallback(
    (seat: string) => {
      setSelectedSeat(seat);
      setShowSeatMap(false);
      onSendMessage(`I would like seat ${seat}`);
    },
    [onSendMessage]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey && !isComposing) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend, isComposing]
  );

  const handleRatingSelect = useCallback((messageId: string, rating: number) => {
    setDraftRatings((prev) => ({ ...prev, [messageId]: rating }));
  }, []);

  const handleCommentChange = useCallback((messageId: string, value: string) => {
    setDraftComments((prev) => ({ ...prev, [messageId]: value }));
  }, []);

  const handleRatingSubmit = useCallback(
    (messageId: string, traceId: string | undefined) => {
      if (!onRatingSubmit || !traceId) return;
      const rating = draftRatings[messageId];
      const comment = (draftComments[messageId] ?? "").trim();
      if (!rating && !comment) return;
      const payloadComment = comment || undefined;
      onRatingSubmit(messageId, traceId, rating, payloadComment);
      setDraftComments((prev) => {
        const next = { ...prev };
        delete next[messageId];
        return next;
      });
      if (rating) {
        setDraftRatings((prev) => {
          const next = { ...prev };
          delete next[messageId];
          return next;
        });
      }
    },
    [draftComments, draftRatings, onRatingSubmit]
  );

  return (
    <div className="flex flex-col h-full flex-1 bg-white shadow-sm border border-gray-200 border-t-0 rounded-xl">
      <div className="bg-blue-600 text-white h-12 px-4 flex items-center rounded-t-xl">
        <h2 className="font-semibold text-sm sm:text-base lg:text-lg">
          Customer View
        </h2>
      </div>
      {/* Messages */}
      <div className="flex-1 overflow-y-auto min-h-0 md:px-4 pt-4 pb-20">
        {messages.map((msg, idx) => {
          if (msg.content === "DISPLAY_SEAT_MAP") return null; // Skip rendering marker message
          const ratingLocked = msg.rating != null;
          const commentLocked =
            !!msg.feedbackComment && msg.feedbackComment.trim().length > 0;
          const feedbackLocked = ratingLocked || commentLocked;
          const hasDraftRating = !!draftRatings[msg.id];
          const draftComment = (draftComments[msg.id] ?? "").trim();
          return (
            <div
              key={msg.id ?? idx}
              className={`flex mb-5 text-sm ${msg.role === "user" ? "justify-end" : "justify-start"
                }`}
            >
              {msg.role === "user" ? (
                <div className="ml-4 rounded-[16px] rounded-br-[4px] px-4 py-2 md:ml-24 bg-black text-white font-light max-w-[80%]">
                  <ReactMarkdown>{msg.content}</ReactMarkdown>
                </div>
              ) : (
                <div className="mr-4 rounded-[16px] rounded-bl-[4px] px-4 py-2 md:mr-24 text-zinc-900 bg-[#ECECF1] font-light max-w-[80%]">
                  <ReactMarkdown>{msg.content}</ReactMarkdown>
                  {msg.agent && (
                    <div className="text-[11px] text-gray-500 mt-1">via {msg.agent}</div>
                  )}
                  {msg.evaluation && (
                    <div className="mt-2 pt-2 border-t border-gray-200">
                      <div className="text-xs font-medium text-gray-700 mb-1">AI Evaluation Score:</div>
                      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[11px] text-gray-600">
                        <div className="flex justify-between">
                          <span>Overall:</span>
                          <span className="font-semibold">{msg.evaluation.overall_score.toFixed(2)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Helpfulness:</span>
                          <span>{msg.evaluation.helpfulness.toFixed(2)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Accuracy:</span>
                          <span>{msg.evaluation.accuracy.toFixed(2)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Relevance:</span>
                          <span>{msg.evaluation.relevance.toFixed(2)}</span>
                        </div>
                      </div>
                      <div className="mt-1 text-[10px] text-gray-500 italic">
                        {msg.evaluation.reasoning}
                      </div>
                    </div>
                  )}
                  {msg.mcpMetrics && (
                    <div className="mt-2 pt-2 border-t border-gray-200">
                      <div className="text-xs font-medium text-gray-700 mb-1">MCP Tool Metrics:</div>
                      <div className="grid grid-cols-3 gap-x-4 gap-y-1 text-[11px] text-gray-600">
                        <div className="flex justify-between">
                          <span>Total Calls:</span>
                          <span className="font-semibold">{msg.mcpMetrics.totalCalls}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Success Rate:</span>
                          <span className={`font-semibold ${msg.mcpMetrics.successRate === 1 ? 'text-green-600' : 'text-amber-600'}`}>
                            {(msg.mcpMetrics.successRate * 100).toFixed(0)}%
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span>Avg Time:</span>
                          <span>{msg.mcpMetrics.avgTime.toFixed(3)}s</span>
                        </div>
                      </div>
                    </div>
                  )}
                  {msg.role === "assistant" && onFeedback && (
                    <div className="flex items-center gap-2 mt-2 text-xs text-gray-600">
                      <span className="text-[11px]">Feedback:</span>
                      <button
                        className={`px-2 py-1 rounded-full border text-[11px] transition ${
                          msg.feedback === "positive"
                            ? "bg-green-100 border-green-400 text-green-700"
                            : "border-gray-300 hover:border-green-500"
                        }`}
                        disabled={!msg.traceId || !!msg.feedback}
                        onClick={() => onFeedback(msg.id, msg.traceId, true)}
                      >
                        👍
                      </button>
                      <button
                        className={`px-2 py-1 rounded-full border text-[11px] transition ${
                          msg.feedback === "negative"
                            ? "bg-red-100 border-red-400 text-red-700"
                            : "border-gray-300 hover:border-red-500"
                        }`}
                        disabled={!msg.traceId || !!msg.feedback}
                        onClick={() => onFeedback(msg.id, msg.traceId, false)}
                      >
                        👎
                      </button>
                      {!msg.traceId && (
                        <span className="text-[11px] text-gray-400">no trace id</span>
                      )}
                    </div>
                  )}
                  {msg.role === "assistant" && onRatingSubmit && (
                    <div className="mt-2 text-xs text-gray-600">
                      <div className="flex items-center gap-2">
                        <span className="text-[11px]">Rating:</span>
                        <div className="flex items-center gap-1">
                          {[1, 2, 3, 4, 5].map((value) => {
                            const ratingValue = ratingLocked
                              ? msg.rating ?? 0
                              : draftRatings[msg.id] ?? msg.rating ?? 0;
                            const isActive = ratingValue >= value;
                            return (
                              <button
                                key={value}
                                type="button"
                                className={`text-base leading-none transition ${
                                  isActive ? "text-amber-500" : "text-gray-300"
                                } ${
                                  feedbackLocked
                                    ? "cursor-default"
                                    : "hover:text-amber-500"
                                }`}
                                disabled={!msg.traceId || feedbackLocked}
                                onClick={() => handleRatingSelect(msg.id, value)}
                              >
                                {isActive ? "★" : "☆"}
                              </button>
                            );
                          })}
                        </div>
                        {feedbackLocked && (
                          <span className="text-[11px] text-gray-400">submitted</span>
                        )}
                        {!msg.traceId && (
                          <span className="text-[11px] text-gray-400">no trace id</span>
                        )}
                      </div>
                      <div className="mt-2 flex items-start gap-2">
                        <textarea
                          rows={2}
                          placeholder="文字反馈（可选）"
                          className="w-full resize-none rounded-md border border-gray-200 px-2 py-1 text-[11px] text-gray-700 focus:outline-none focus:ring-1 focus:ring-blue-500"
                          value={draftComments[msg.id] ?? msg.feedbackComment ?? ""}
                          onChange={(e) => handleCommentChange(msg.id, e.target.value)}
                          disabled={!msg.traceId || feedbackLocked}
                        />
                        <button
                          type="button"
                          className="rounded-md bg-blue-600 px-3 py-1 text-[11px] text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:bg-gray-300"
                          disabled={
                            !msg.traceId ||
                            feedbackLocked ||
                            (!hasDraftRating && !draftComment)
                          }
                          onClick={() => handleRatingSubmit(msg.id, msg.traceId)}
                        >
                          提交
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
        {showSeatMap && (
          <div className="flex justify-start mb-5">
            <div className="mr-4 rounded-[16px] rounded-bl-[4px] md:mr-24">
              <SeatMap
                conversationId={conversationId}
                onSeatSelect={handleSeatSelect}
                selectedSeat={selectedSeat}
              />
            </div>
          </div>
        )}
        {isLoading && (
          <div className="flex mb-5 text-sm justify-start">
            <div className="h-3 w-3 bg-black rounded-full animate-pulse" />
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="p-2 md:px-4">
        <div className="flex items-center">
          <div className="flex w-full items-center pb-4 md:pb-1">
            <div className="flex w-full flex-col gap-1.5 rounded-2xl p-2.5 pl-1.5 bg-white border border-stone-200 shadow-sm transition-colors">
              <div className="flex items-end gap-1.5 md:gap-2 pl-4">
                <div className="flex min-w-0 flex-1 flex-col">
                  <textarea
                    id="prompt-textarea"
                    tabIndex={0}
                    dir="auto"
                    rows={2}
                    placeholder="Message..."
                    className="mb-2 resize-none border-0 focus:outline-none text-sm bg-transparent px-0 pb-6 pt-2"
                    value={inputText}
                    onChange={(e) => setInputText(e.target.value)}
                    onKeyDown={handleKeyDown}
                    onCompositionStart={() => setIsComposing(true)}
                    onCompositionEnd={() => setIsComposing(false)}
                  />
                </div>
                <button
                  disabled={!inputText.trim()}
                  className="flex h-8 w-8 items-end justify-center rounded-full bg-black text-white hover:opacity-70 disabled:bg-gray-300 disabled:text-gray-400 transition-colors focus:outline-none"
                  onClick={handleSend}
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="32"
                    height="32"
                    fill="none"
                    viewBox="0 0 32 32"
                    className="icon-2xl"
                  >
                    <path
                      fill="currentColor"
                      fillRule="evenodd"
                      d="M15.192 8.906a1.143 1.143 0 0 1 1.616 0l5.143 5.143a1.143 1.143 0 0 1-1.616 1.616l-3.192-3.192v9.813a1.143 1.143 0 0 1-2.286 0v-9.813l-3.192 3.192a1.143 1.143 0 1 1-1.616-1.616z"
                      clipRule="evenodd"
                    />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
