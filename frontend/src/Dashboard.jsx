import React, { useState, useEffect } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";
import {
  Activity,
  MessageSquare,
  TrendingUp,
  AlertTriangle,
} from "lucide-react";

const API_URL = "http://localhost:8000";
const WS_URL =
  window.location.protocol === "https:"
    ? "wss://localhost:8000/ws/sentiment"
    : "ws://localhost:8000/ws/sentiment";
// -----------------------

export default function Dashboard() {
  const [posts, setPosts] = useState([]);
  const [stats, setStats] = useState({ total_posts: 0, distribution: {} });
  const [status, setStatus] = useState("disconnected");
  const [trendData, setTrendData] = useState([]);

  // 1. Fetch Initial Data
  useEffect(() => {
    fetch(`${API_URL}/api/posts?limit=20`)
      .then((res) => res.json())
      .then((data) => {
        console.log("Initial posts:", data);
        setPosts(data.posts || []);
      })
      .catch((err) => console.error("Failed to fetch posts:", err));

    fetch(`${API_URL}/api/sentiment/stats`)
      .then((res) => res.json())
      .then((data) => {
        console.log("Initial stats:", data);
        // FIX: Handle both potential key names
        const total =
          data.total_posts !== undefined ? data.total_posts : data.total;

        setStats({
          total_posts: total,
          distribution: data.distribution || {},
        });
      })
      .catch((err) => console.error("Failed to fetch stats:", err));
  }, []);

  // 2. WebSocket Connection
  useEffect(() => {
    console.log("Attempting WebSocket connection...");
    const ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      console.log("WebSocket Connected!");
      setStatus("connected");
    };

    ws.onclose = () => {
      console.log("WebSocket Disconnected");
      setStatus("disconnected");
    };

    ws.onmessage = (event) => {
      // Parse the message
      const message = JSON.parse(event.data);
      console.log("WebSocket received:", message);

      if (message.type === "new_post") {
        const newPost = message.data;

        // Update Feed
        setPosts((prev) => [newPost, ...prev].slice(0, 50));

        // Update Stats safely
        setStats((prev) => {
          const label = newPost.sentiment.sentiment_label;
          const currentDist = prev.distribution || {};
          return {
            total_posts: (prev.total_posts || 0) + 1,
            distribution: {
              ...currentDist,
              [label]: (currentDist[label] || 0) + 1,
            },
          };
        });

        // Update Trend
        setTrendData((prev) => {
          const now = new Date().toLocaleTimeString();
          return [
            ...prev,
            {
              time: now,
              sentiment: newPost.sentiment.confidence_score,
            },
          ].slice(-20);
        });
      }
    };

    return () => ws.close();
  }, []);

  // Chart Data
  const pieData = [
    {
      name: "Positive",
      value: stats.distribution?.positive || 0,
      color: "#10B981",
    },
    {
      name: "Negative",
      value: stats.distribution?.negative || 0,
      color: "#EF4444",
    },
    {
      name: "Neutral",
      value: stats.distribution?.neutral || 0,
      color: "#6B7280",
    },
  ];

  return (
    <div className="min-h-screen bg-gray-900 text-white p-6">
      {/* Header */}
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold">Sentiment Command Center</h1>
          <p className="text-gray-400">Real-time Brand Monitoring</p>
        </div>
        <div
          className={`px-4 py-2 rounded-full font-bold ${
            status === "connected"
              ? "bg-green-900 text-green-300"
              : "bg-red-900 text-red-300"
          }`}
        >
          ● {status.toUpperCase()}
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <Card
          title="Total Posts"
          value={stats.total_posts}
          icon={<MessageSquare />}
        />
        <Card
          title="Positive"
          value={stats.distribution?.positive}
          color="text-green-400"
          icon={<TrendingUp />}
        />
        <Card
          title="Negative"
          value={stats.distribution?.negative}
          color="text-red-400"
          icon={<AlertTriangle />}
        />
        <Card
          title="Neutral"
          value={stats.distribution?.neutral}
          color="text-gray-400"
          icon={<Activity />}
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-8">
        <div className="lg:col-span-2 bg-gray-800 p-4 rounded-xl border border-gray-700">
          <h3 className="text-lg font-semibold mb-4">
            Sentiment Confidence Trend
          </h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="time" stroke="#9CA3AF" />
                <YAxis stroke="#9CA3AF" domain={[0, 1]} />
                <Tooltip
                  contentStyle={{ backgroundColor: "#1F2937", border: "none" }}
                />
                <Line
                  type="monotone"
                  dataKey="sentiment"
                  stroke="#8884d8"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-gray-800 p-4 rounded-xl border border-gray-700">
          <h3 className="text-lg font-semibold mb-4">Distribution</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  innerRadius={60}
                  outerRadius={80}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {pieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Legend />
                <Tooltip
                  contentStyle={{ backgroundColor: "#1F2937", border: "none" }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Live Feed */}
      <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
        <div className="p-4 border-b border-gray-700">
          <h3 className="text-lg font-semibold">Live Feed</h3>
        </div>
        <div className="max-h-96 overflow-y-auto">
          {posts.map((post, i) => {
            // FIX: Check BOTH naming conventions
            // API uses 'label', WebSocket uses 'sentiment_label'
            const sentimentLabel =
              post.sentiment?.label ||
              post.sentiment?.sentiment_label ||
              "neutral";

            return (
              <div
                key={i}
                className="p-4 border-b border-gray-700 hover:bg-gray-750"
              >
                <div className="flex justify-between items-start mb-1">
                  <span className="font-medium text-blue-400">
                    @{post.author || "Anonymous"}
                  </span>
                  {/* Render the Badge */}
                  <span
                    className={`text-xs px-2 py-1 rounded-full uppercase ${
                      sentimentLabel === "positive"
                        ? "bg-green-900 text-green-300"
                        : sentimentLabel === "negative"
                        ? "bg-red-900 text-red-300"
                        : "bg-gray-700 text-gray-300"
                    }`}
                  >
                    {sentimentLabel}
                  </span>
                </div>
                <p className="text-gray-300">{post.content}</p>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// THE FIX: Safe Card Component
function Card({ title, value, icon, color = "text-white" }) {
  // If value is null/undefined, show 0.
  const safeValue = value === undefined || value === null ? 0 : value;

  return (
    <div className="bg-gray-800 p-6 rounded-xl border border-gray-700 flex items-center justify-between">
      <div>
        <p className="text-gray-400 text-sm mb-1">{title}</p>
        <h2 className={`text-2xl font-bold ${color}`}>{safeValue}</h2>
      </div>
      <div className="text-gray-500">{icon}</div>
    </div>
  );
}
