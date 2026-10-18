// src/services/socket.js
// Manages the WebSocket connection for a live interview.
import { getApiBase } from "./api.js";

export function getWsBase(rawUrl) {
  const apiBase = getApiBase(rawUrl);
  return apiBase.startsWith("https://")
    ? apiBase.replace(/^https:\/\//, "wss://")
    : apiBase.replace(/^http:\/\//, "ws://");
}

export class InterviewSocket {
  constructor(sessionId, onEvent) {
    this.sessionId = sessionId;
    this.onEvent = onEvent; // Callback for UI updates
    this.ws = null;
  }

  connect() {
    const wsBase = getWsBase();
    this.ws = new WebSocket(`${wsBase}/interviews/ws/${this.sessionId}`);
    
    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.onEvent(data.event_type, data.payload);
    };

    this.ws.onerror = (error) => {
      console.error("WebSocket error:", error);
    };

    this.ws.onclose = () => {
      console.log("WebSocket disconnected");
    };
  }

  submitAnswer(answerText) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: "submit_answer",
        answer: answerText
      }));
    } else {
      console.error("Cannot send message, socket not connected.");
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
    }
  }
}
