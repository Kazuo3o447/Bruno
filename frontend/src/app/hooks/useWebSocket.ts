"use client";

import { useEffect, useState, useCallback, useRef } from "react";

interface WebSocketMessage {
  type: string;
  data: any;
  timestamp: string;
}

interface UseWebSocketProps {
  symbol?: string;
  onMarketData?: (data: any) => void;
  onAgentStatus?: (data: any) => void;
  onSystemMetrics?: (data: any) => void;
  onAlert?: (data: any) => void;
}

export function useWebSocket({
  symbol = "BTCUSDT",
  onMarketData,
  onAgentStatus,
  onSystemMetrics,
  onAlert,
}: UseWebSocketProps) {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<"connecting" | "connected" | "disconnected">("disconnected");
  
  const wsRefs = useRef<{
    market?: WebSocket;
    agents?: WebSocket;
    system?: WebSocket;
    alerts?: WebSocket;
  }>({});

  const connectWebSocket = useCallback((endpoint: string, onMessage: (data: any) => void) => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const wsUrl = `ws://${apiUrl.replace(/^https?:\/\//, "").replace(/^http:\/\//, "")}${endpoint}`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log(`WebSocket connected: ${endpoint}`);
      setIsConnected(true);
      setConnectionStatus("connected");
    };

    ws.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data);
        setLastMessage(message);
        onMessage(message);
      } catch (error) {
        console.error("WebSocket message error:", error);
      }
    };

    ws.onclose = () => {
      console.log(`WebSocket disconnected: ${endpoint}`);
      setIsConnected(false);
      setConnectionStatus("disconnected");
      
      // Reconnect nach 5 Sekunden
      setTimeout(() => {
        connectWebSocket(endpoint, onMessage);
      }, 5000);
    };

    ws.onerror = (error) => {
      console.error(`WebSocket error on ${endpoint}:`, error);
    };

    return ws;
  }, []);

  useEffect(() => {
    setConnectionStatus("connecting");

    // Market WebSocket
    if (onMarketData) {
      wsRefs.current.market = connectWebSocket(`/ws/market/${symbol}`, onMarketData);
    }

    // Agents WebSocket
    if (onAgentStatus) {
      wsRefs.current.agents = connectWebSocket(`/ws/agents`, onAgentStatus);
    }

    // System WebSocket
    if (onSystemMetrics) {
      wsRefs.current.system = connectWebSocket(`/ws/system`, onSystemMetrics);
    }

    // Alerts WebSocket
    if (onAlert) {
      wsRefs.current.alerts = connectWebSocket(`/ws/alerts`, onAlert);
    }

    return () => {
      // Alle WebSockets schließen
      Object.values(wsRefs.current).forEach((ws) => {
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.close();
        }
      });
    };
  }, [symbol, connectWebSocket, onMarketData, onAgentStatus, onSystemMetrics, onAlert]);

  return {
    isConnected,
    lastMessage,
    connectionStatus,
  };
}

// Einfacher Market Data Hook
export function useMarketData(symbol: string = "BTCUSDT") {
  const [price, setPrice] = useState<number | null>(null);
  const [volume, setVolume] = useState<number | null>(null);
  const [orderbook, setOrderbook] = useState<any>(null);

  const handleMarketData = useCallback((message: WebSocketMessage) => {
    if (message.type === "ticker" && message.data) {
      setPrice(message.data.price || message.data.close);
      setVolume(message.data.volume);
    } else if (message.type === "orderbook" && message.data) {
      setOrderbook(message.data);
    }
  }, []);

  const { isConnected, connectionStatus } = useWebSocket({
    symbol,
    onMarketData: handleMarketData,
  });

  return {
    price,
    volume,
    orderbook,
    isConnected,
    connectionStatus,
  };
}

// Agent Status Hook
export function useAgentStatus() {
  const [agents, setAgents] = useState<any[]>([]);

  const handleAgentStatus = useCallback((message: WebSocketMessage) => {
    if (message.type === "agents_status" && message.data) {
      setAgents(message.data.agents || []);
    }
  }, []);

  const { isConnected } = useWebSocket({
    onAgentStatus: handleAgentStatus,
  });

  return {
    agents,
    isConnected,
  };
}
