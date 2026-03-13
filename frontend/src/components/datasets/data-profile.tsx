"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { BarChart3 } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

interface DataProfileProps {
  dataProfile: Record<string, any>;
}

interface NumericStats {
  min?: number;
  max?: number;
  mean?: number;
  median?: number;
  std?: number;
  "25%"?: number;
  "75%"?: number;
  count?: number;
}

function isNumericProfile(profile: any): profile is NumericStats {
  return (
    profile &&
    typeof profile === "object" &&
    ("mean" in profile || "min" in profile || "std" in profile)
  );
}

function NumericProfileCard({
  column,
  stats,
}: {
  column: string;
  stats: NumericStats;
}) {
  const statItems = [
    { label: "Min", value: stats.min },
    { label: "Max", value: stats.max },
    { label: "Mean", value: stats.mean },
    { label: "Median", value: stats.median },
    { label: "Std Dev", value: stats.std },
    { label: "Q25", value: stats["25%"] },
    { label: "Q75", value: stats["75%"] },
  ].filter((s) => s.value !== undefined && s.value !== null);

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium">{column}</CardTitle>
          <Badge variant="secondary">numeric</Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-x-6 gap-y-2">
          {statItems.map(({ label, value }) => (
            <div key={label} className="flex justify-between text-sm">
              <span className="text-muted-foreground">{label}</span>
              <span className="font-mono tabular-nums">
                {typeof value === "number" ? value.toLocaleString(undefined, { maximumFractionDigits: 2 }) : String(value)}
              </span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function CategoricalProfileCard({
  column,
  valueCounts,
}: {
  column: string;
  valueCounts: Record<string, number>;
}) {
  const entries = Object.entries(valueCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8);

  const chartData = entries.map(([name, count]) => ({ name, count }));

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium">{column}</CardTitle>
          <Badge variant="outline">categorical</Badge>
        </div>
      </CardHeader>
      <CardContent>
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={160}>
            <BarChart
              data={chartData}
              layout="vertical"
              margin={{ top: 0, right: 0, bottom: 0, left: 0 }}
            >
              <XAxis type="number" hide />
              <YAxis
                type="category"
                dataKey="name"
                width={80}
                tick={{ fontSize: 12 }}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                contentStyle={{
                  fontSize: 12,
                  borderRadius: 8,
                }}
              />
              <Bar
                dataKey="count"
                fill="hsl(var(--primary))"
                radius={[0, 4, 4, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-sm text-muted-foreground">No values available.</p>
        )}
      </CardContent>
    </Card>
  );
}

export function DataProfile({ dataProfile }: DataProfileProps) {
  const columns = Object.keys(dataProfile);

  if (columns.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <BarChart3 className="size-10 text-muted-foreground/40" />
        <p className="mt-3 text-sm text-muted-foreground">
          No data profile available for this dataset.
        </p>
      </div>
    );
  }

  const numericColumns: [string, NumericStats][] = [];
  const categoricalColumns: [string, Record<string, number>][] = [];

  for (const col of columns) {
    const profile = dataProfile[col];
    if (isNumericProfile(profile)) {
      numericColumns.push([col, profile]);
    } else if (
      profile &&
      typeof profile === "object" &&
      !Array.isArray(profile)
    ) {
      // Treat as categorical value counts
      const valueCounts = profile.value_counts ?? profile;
      if (typeof valueCounts === "object") {
        categoricalColumns.push([col, valueCounts]);
      }
    }
  }

  return (
    <div className="space-y-6">
      {numericColumns.length > 0 && (
        <div>
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Numeric Columns
          </h3>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {numericColumns.map(([col, stats]) => (
              <NumericProfileCard key={col} column={col} stats={stats} />
            ))}
          </div>
        </div>
      )}

      {categoricalColumns.length > 0 && (
        <div>
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Categorical Columns
          </h3>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {categoricalColumns.map(([col, counts]) => (
              <CategoricalProfileCard
                key={col}
                column={col}
                valueCounts={counts}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
