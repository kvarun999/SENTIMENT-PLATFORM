import React from "react";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from "recharts";

const COLORS = {
  positive: "#10B981",
  negative: "#EF4444",
  neutral: "#6B7280",
};

export default function DistributionChart({ distribution = {} }) {
  const data = Object.keys(distribution)
    .map((key) => ({
      name: key.charAt(0).toUpperCase() + key.slice(1),
      value: distribution[key],
      color: COLORS[key] || "#374151",
    }))
    .filter((item) => item.value > 0);

  if (data.length === 0)
    return (
      <div className="text-gray-500 text-center py-20">No data available</div>
    );

  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            innerRadius={60}
            outerRadius={80}
            paddingAngle={5}
            dataKey="value"
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{ backgroundColor: "#1F2937", border: "none" }}
          />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
