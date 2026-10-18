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
    this.isExplicitlyClosed = false;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectTimeout = null;
  }

  connect() {
    this.isExplicitlyClosed = false;
    const wsBase = getWsBase();
    this.ws = new WebSocket(`${wsBase}/interviews/ws/${this.sessionId}`);
    
    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.onEvent(data.event_type, data.payload);
      } catch (err) {
        console.error("Error parsing WebSocket message:", err);
      }
    };

    this.ws.onerror = (error) => {
      console.error("WebSocket error:", error);
    };

    this.ws.onclose = () => {
      console.log("WebSocket disconnected");
      if (!this.isExplicitlyClosed && this.reconnectAttempts < this.maxReconnectAttempts) {
        this.reconnectAttempts++;
        const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 8000);
        console.log(`Reconnecting WebSocket in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
        this.reconnectTimeout = setTimeout(() => this.connect(), delay);
      }
    };
  }

  isOpen() {
    return this.ws && this.ws.readyState === WebSocket.OPEN;
  }

  submitAnswer(answerText, lastQuestion = null) {
    if (this.isOpen()) {
      const payload = {
        type: "submit_answer",
        answer: answerText
      };
      if (lastQuestion) payload.last_question = lastQuestion;
      this.ws.send(JSON.stringify(payload));
      return true;
    } else {
      console.warn("Cannot send message, socket not connected.");
      return false;
    }
  }

  disconnect() {
    this.isExplicitlyClosed = true;
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    if (this.ws) {
      this.ws.close();
    }
  }
}
