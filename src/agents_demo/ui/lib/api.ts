const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

// Helper to call the server
export async function getConversationHistory(conversationId: string) {
  try {
    const res = await fetch(`${API_BASE}/api/history/${conversationId}`);
    if (!res.ok) throw new Error(`History API error: ${res.status}`);
    return res.json();
  } catch (err) {
    console.error("Error fetching history:", err);
    return null;
  }
}

export async function callChatAPI(message: string, conversationId: string) {
  try {
    const res = await fetch(`${API_BASE}/api/chat`, {
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
    const res = await fetch(`${API_BASE}/api/feedback`, {
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
