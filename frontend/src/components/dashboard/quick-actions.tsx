"use client";

import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { FileText, Database, FlaskConical, ArrowRight } from "lucide-react";

const actions = [
  { href: "/brds", label: "Upload BRD", description: "Parse business rules from documents", icon: FileText, iconBg: "bg-blue-50 dark:bg-blue-500/10", iconColor: "text-blue-600 dark:text-blue-400", hoverBorder: "hover:border-blue-300 dark:hover:border-blue-500/30" },
  { href: "/loan-records", label: "Browse Loan Records", description: "View and search loan application data", icon: Database, iconBg: "bg-emerald-50 dark:bg-emerald-500/10", iconColor: "text-emerald-600 dark:text-emerald-400", hoverBorder: "hover:border-emerald-300 dark:hover:border-emerald-500/30" },
  { href: "/test-suites", label: "View Test Suites", description: "Manage and run test cases", icon: FlaskConical, iconBg: "bg-pink-50 dark:bg-pink-500/10", iconColor: "text-pink-600 dark:text-pink-400", hoverBorder: "hover:border-pink-300 dark:hover:border-pink-500/30" },
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
