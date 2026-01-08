// Helper to call the server
export async function callChatAPI(message: string, conversationId: string) {
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversation_id: conversationId, message }),
    });
    if (!res.ok) throw new Error(`Chat API error: ${res.status}`);
    return res.json();
  } catch (err) {
    console.error("Error sending message:", err);
    return null;
  }
}

export async function sendFeedback(payload: {
  conversation_id: string;
  message_id: string;
  trace_id: string;
  score?: number;
  rating?: number;
  comment?: string;
}) {
  try {
    const res = await fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`Feedback API error: ${res.status}`);
    return res.json();
  } catch (err) {
    console.error("Error sending feedback:", err);
    return null;
  }
}
