import React from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

export default function SentimentChart({ data }) {
  if (!data || data.length === 0)
    return (
      <div className="text-gray-500 text-center py-20">
        Waiting for live updates...
      </div>
    );

  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis dataKey="time" stroke="#9CA3AF" />
          <YAxis stroke="#9CA3AF" />
          <Tooltip
            contentStyle={{ backgroundColor: "#1F2937", border: "none" }}
          />
          <Legend />
          <Line
            type="monotone"
            dataKey="positive"
            stroke="#10B981"
            strokeWidth={2}
            dot={false}
          />
          <Line
            type="monotone"
            dataKey="negative"
            stroke="#EF4444"
            strokeWidth={2}
            dot={false}
          />
          <Line
            type="monotone"
            dataKey="neutral"
            stroke="#6B7280"
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
