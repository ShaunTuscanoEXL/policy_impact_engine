"use client";

import { PageTransition, StaggerContainer, StaggerItem } from "@/components/page-transition";
import { StatsCards } from "@/components/dashboard/stats-cards";
import { QuickActions } from "@/components/dashboard/quick-actions";
import { LayoutDashboard } from "lucide-react";

export default function DashboardPage() {
  return (
    <PageTransition>
      <div className="space-y-8">
        {/* Header */}
        <div className="flex items-center gap-4">
          <div className="icon-badge bg-blue-100 dark:bg-blue-900/30">
            <LayoutDashboard className="size-5 text-blue-600 dark:text-blue-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              <span className="text-gradient">Dashboard</span>
            </h1>
            <p className="text-sm text-muted-foreground">
              Overview of BRDs, loan records, and test suites
            </p>
          </div>
        </div>

        {/* Bento Grid */}
        <StaggerContainer className="grid grid-cols-3 gap-5">
          {/* Row 1: stat cards */}
          <StatsCards />

          {/* Row 2: Quick Actions (span 3) */}
          <StaggerItem className="col-span-3">
            <QuickActions />
          </StaggerItem>
        </StaggerContainer>
      </div>
    </PageTransition>
  );
}
