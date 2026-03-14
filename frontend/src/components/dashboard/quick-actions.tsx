"use client";

import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { FileText, PlayCircle, GitCompare, ArrowRight } from "lucide-react";

const actions = [
  { href: "/brds", label: "Upload BRD", description: "Parse business rules from documents", icon: FileText, iconBg: "bg-blue-50 dark:bg-blue-500/10", iconColor: "text-blue-600 dark:text-blue-400", hoverBorder: "hover:border-blue-300 dark:hover:border-blue-500/30" },
  { href: "/simulations/new", label: "New Simulation", description: "Run a policy impact simulation", icon: PlayCircle, iconBg: "bg-violet-50 dark:bg-violet-500/10", iconColor: "text-violet-600 dark:text-violet-400", hoverBorder: "hover:border-violet-300 dark:hover:border-violet-500/30" },
  { href: "/scenarios", label: "Compare Scenarios", description: "Side-by-side scenario analysis", icon: GitCompare, iconBg: "bg-amber-50 dark:bg-amber-500/10", iconColor: "text-amber-600 dark:text-amber-400", hoverBorder: "hover:border-amber-300 dark:hover:border-amber-500/30" },
];

export function QuickActions() {
  return (
    <Card className="card-elevated border-border/40">
      <CardContent className="p-4">
        <div className="grid grid-cols-3 gap-4">
          {actions.map((action) => (
            <Link
              key={action.href}
              href={action.href}
              className={`group flex items-center gap-4 rounded-xl border border-border/60 p-4 transition-all duration-200 cursor-pointer hover:shadow-md hover:-translate-y-0.5 ${action.hoverBorder}`}
            >
              <div className={`flex size-10 shrink-0 items-center justify-center rounded-xl ${action.iconBg} transition-colors`}>
                <action.icon className={`h-5 w-5 ${action.iconColor}`} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-foreground">{action.label}</p>
                <p className="text-xs text-muted-foreground truncate">{action.description}</p>
              </div>
              <ArrowRight className="h-4 w-4 text-muted-foreground/30 group-hover:text-primary group-hover:translate-x-0.5 transition-all duration-200" />
            </Link>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
