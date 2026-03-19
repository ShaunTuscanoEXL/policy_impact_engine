"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

interface JsonViewerProps {
  data: Record<string, any>;
  initialExpanded?: boolean;
}

export function JsonViewer({ data, initialExpanded = true }: JsonViewerProps) {
  return (
    <div className="font-mono text-sm">
      <JsonNode data={data} path="" initialExpanded={initialExpanded} />
    </div>
  );
}

function JsonNode({ data, path, initialExpanded }: { data: any; path: string; initialExpanded: boolean }) {
  const [expanded, setExpanded] = useState(initialExpanded);

  if (data === null || data === undefined) {
    return <span className="text-muted-foreground">null</span>;
  }

  if (typeof data !== "object") {
    if (typeof data === "number") return <span className="text-blue-500">{data}</span>;
    if (typeof data === "boolean") return <span className="text-purple-500">{String(data)}</span>;
    return <span className="text-emerald-500">&quot;{String(data)}&quot;</span>;
  }

  const entries = Object.entries(data);
  const isArray = Array.isArray(data);

  return (
    <div className="ml-4">
      <button
        onClick={() => setExpanded(!expanded)}
        className="inline-flex items-center gap-1 text-muted-foreground hover:text-foreground cursor-pointer"
      >
        {expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        <span className="text-xs text-muted-foreground">
          {isArray ? `[${entries.length}]` : `{${entries.length}}`}
        </span>
      </button>
      {expanded && (
        <div className="ml-2 border-l border-border/50 pl-3 space-y-1 mt-1">
          {entries.map(([key, value]) => (
            <div key={key}>
              <span className="text-foreground/70">{key}: </span>
              <JsonNode data={value} path={`${path}.${key}`} initialExpanded={false} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
