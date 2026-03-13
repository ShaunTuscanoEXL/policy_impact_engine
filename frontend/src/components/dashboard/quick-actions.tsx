"use client";

import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { FileText, PlayCircle, GitCompare, ArrowRight } from "lucide-react";

const actions = [
  { href: "/brds", label: "Upload BRD", description: "Parse business rules from documents", icon: FileText },
  { href: "/simulations/new", label: "New Simulation", description: "Run a policy impact simulation", icon: PlayCircle },
  { href: "/scenarios", label: "Compare Scenarios", description: "Side-by-side scenario analysis", icon: GitCompare },
];

export function QuickActions() {
  return (
    <Card className="border-border/50 shadow-sm">
      <CardContent className="p-4">
        <div className="grid grid-cols-3 gap-3">
          {actions.map((action) => (
            <Link
              key={action.href}
              href={action.href}
              className="group flex items-center gap-3 rounded-lg border border-border/50 p-4 transition-all hover:border-[#0070f3]/30 hover:shadow-sm"
            >
              <action.icon className="h-5 w-5 shrink-0 text-muted-foreground group-hover:text-[#0070f3] transition-colors" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium">{action.label}</p>
                <p className="text-xs text-muted-foreground truncate">{action.description}</p>
              </div>
              <ArrowRight className="h-4 w-4 text-muted-foreground/0 group-hover:text-muted-foreground transition-all" />
            </Link>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
