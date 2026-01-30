import React, { useState, useEffect } from "react";
import {
  MessageSquare,
  TrendingUp,
  AlertTriangle,
  Activity,
} from "lucide-react";
import {
  fetchPosts,
  fetchDistribution,
  connectWebSocket,
} from "../services/api";
import DistributionChart from "./DistributionChart";
import SentimentChart from "./SentimentChart";

export default function Dashboard() {
  const [posts, setPosts] = useState([]);
  const [stats, setStats] = useState({ total: 0, distribution: {} });
  const [trendData, setTrendData] = useState([]);
  const [status, setStatus] = useState("connecting");

  useEffect(() => {
    let ws;

    const fetchDataAndConnect = async () => {
      // 1. Fetch initial data to prevent race conditions
      try {
        const [postsData, distData] = await Promise.all([
          fetchPosts(20),
          fetchDistribution(),
        ]);
        setPosts(postsData.posts || []);
        setStats(distData);
      } catch (error) {
        console.error("Failed to fetch initial data:", error);
        setStatus("disconnected");
        return; // Don't proceed to connect WebSocket if initial fetch fails
      }

      // 2. Now, connect the WebSocket
      ws = connectWebSocket(
        (message) => {
          // A. Handle new analyzed posts
          if (message.type === "new_post") {
            const newPost = message.data;
            setPosts((prev) => [newPost, ...prev].slice(0, 50));

            // UPDATE COUNTS: Use the same label keys as the backend
            setStats((prev) => {
              const sentiment = newPost.sentiment?.sentiment_label || "neutral";
              return {
                ...prev,
                total: (prev.total || 0) + 1,
                distribution: {
                  ...prev.distribution,
                  [sentiment]: (prev.distribution?.[sentiment] || 0) + 1,
                },
              };
            });
          }

          // B. Handle periodic metrics updates (Line Chart)
          if (message.type === "metrics_update") {
            const time = new Date(message.timestamp).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            });
            setTrendData((prev) =>
              [
                ...prev,
                {
                  time,
                  ...message.data.last_minute,
                },
              ].slice(-20),
            );
          }
        },
        () => setStatus("connected"),    // onOpen
        () => setStatus("disconnected"), // onError
        () => setStatus("disconnected")  // onClose
      );
    };

    fetchDataAndConnect();

    // 3. Cleanup on component unmount
    return () => {
      if (ws) {
        ws.close();
      }
    };
  }, []); // Empty dependency array ensures this runs only once

  return (
    <div className="min-h-screen bg-gray-900 text-white p-6">
      <header className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold">Sentiment Command Center</h1>
        <span
          className={`px-4 py-1 rounded-full text-sm font-bold ${status === "connected" ? "bg-green-900 text-green-300" : "bg-red-900 text-red-300"}`}
        >
          ● {status.toUpperCase()}
        </span>
      </header>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <StatCard title="Total" value={stats.total} icon={<MessageSquare />} />
        <StatCard
          title="Positive"
          value={stats.distribution?.positive}
          icon={<TrendingUp />}
          color="text-green-400"
        />
        <StatCard
          title="Negative"
          value={stats.distribution?.negative}
          icon={<AlertTriangle />}
          color="text-red-400"
        />
        <StatCard
          title="Neutral"
          value={stats.distribution?.neutral}
          icon={<Activity />}
          color="text-gray-400"
        />
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-8">
        <div className="lg:col-span-2 bg-gray-800 p-6 rounded-xl border border-gray-700">
          <h3 className="text-lg font-semibold mb-4">Sentiment Trend</h3>
          <SentimentChart data={trendData} />
        </div>
        <div className="bg-gray-800 p-6 rounded-xl border border-gray-700">
          <h3 className="text-lg font-semibold mb-4">Distribution</h3>
          <DistributionChart distribution={stats.distribution} />
        </div>
      </div>

      {/* --- LIVE FEED SECTION ADDED BACK --- */}
      <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
        <div className="p-4 border-b border-gray-700">
          <h3 className="text-lg font-semibold">Live Feed</h3>
        </div>
        <div className="max-h-96 overflow-y-auto">
          {posts.map((post, i) => {
            const label = post.sentiment?.label || post.sentiment?.sentiment_label || "neutral";
            return (
              <div key={i} className="p-4 border-b border-gray-700 hover:bg-gray-750">
                <div className="flex justify-between items-start mb-1">
                  <span className="font-medium text-blue-400">@{post.author || "Anonymous"}</span>
                  <span className={`text-xs px-2 py-1 rounded-full uppercase ${
                    label === "positive" ? "bg-green-900 text-green-300" :
                    label === "negative" ? "bg-red-900 text-red-300" : "bg-gray-700 text-gray-300"
                  }`}>
                    {label}
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

function StatCard({ title, value, icon, color }) {
  return (
    <div className="bg-gray-800 p-6 rounded-xl border border-gray-700 flex items-center justify-between">
      <div>
        <p className="text-gray-400 text-sm">{title}</p>
        <h2 className={`text-2xl font-bold ${color}`}>{value || 0}</h2>
      </div>
      <div className="text-gray-500">{icon}</div>
    </div>
  );
}