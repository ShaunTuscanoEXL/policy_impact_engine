"use client";

import { useEffect, useState } from "react";
import api from "@/lib/api";
import type { BrdDocument } from "@/lib/types";
import { PageTransition, StaggerContainer, StaggerItem } from "@/components/page-transition";
import { StatsCards } from "@/components/dashboard/stats-cards";
import { QuickActions } from "@/components/dashboard/quick-actions";
import { LayoutDashboard } from "lucide-react";

export default function DashboardPage() {
  const [loading, setLoading] = useState(true);
  const [brdCount, setBrdCount] = useState<number | null>(null);

  useEffect(() => {
    async function fetchDashboardData() {
      setLoading(true);
      try {
        const res = await api.get<BrdDocument[]>("/brds");
        setBrdCount(res.data.length);
      } catch {
        // Error handled silently
      } finally {
        setLoading(false);
      }
    }

    fetchDashboardData();
  }, []);

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
              Overview of BRDs, rules, and test cases
            </p>
          </div>
        </div>

        {/* Bento Grid */}
        <StaggerContainer className="grid grid-cols-4 gap-5">
          {/* Row 1: stat cards */}
          <StatsCards
            brdCount={brdCount}
            loading={loading}
          />

          {/* Row 2: Quick Actions (span 4) */}
          <StaggerItem className="col-span-4">
            <QuickActions />
          </StaggerItem>
        </StaggerContainer>
      </div>
    </PageTransition>
  );
}
