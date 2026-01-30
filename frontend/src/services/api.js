const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const WS_URL = API_URL.replace(/^http/, "ws") + "/ws/sentiment";

export const fetchPosts = async (limit = 50, offset = 0, filters = {}) => {
  const params = new URLSearchParams({ limit, offset, ...filters });
  const response = await fetch(`${API_URL}/api/posts?${params}`);
  return response.json();
};

export const fetchDistribution = async (hours = 24) => {
  const response = await fetch(
    `${API_URL}/api/sentiment/distribution?hours=${hours}`,
  );
  return response.json();
};

export const fetchAggregateData = async (period = "hour") => {
  const response = await fetch(
    `${API_URL}/api/sentiment/aggregate?period=${period}`,
  );
  return response.json();
};

export const connectWebSocket = (onMessage, onOpen, onError, onClose) => {
  const ws = new WebSocket(WS_URL);
  ws.onopen = () => onOpen && onOpen();
  ws.onmessage = (event) => onMessage(JSON.parse(event.data));
  ws.onerror = (err) => onError && onError(err);
  ws.onclose = () => onClose && onClose();
  return ws;
};
