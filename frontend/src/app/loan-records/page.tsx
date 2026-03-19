"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import api from "@/lib/api";
import type { LoanRecordListItem, LoanRecordStats } from "@/lib/types";
import { toast } from "sonner";
import { PageTransition } from "@/components/page-transition";
import { motion } from "framer-motion";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Database,
  Search,
  Loader2,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";

const PAGE_SIZE = 20;

function decisionBadge(status: string | null) {
  if (!status) return <Badge variant="outline">N/A</Badge>;
  const upper = status.toUpperCase();
  if (upper === "APPROVED")
    return <Badge className="bg-emerald-500/10 text-emerald-600 border-emerald-500/20">Approved</Badge>;
  if (upper === "REJECTED")
    return <Badge variant="destructive">Rejected</Badge>;
  if (upper === "CONDITIONAL")
    return <Badge className="bg-amber-500/10 text-amber-600 border-amber-500/20">Conditional</Badge>;
  return <Badge variant="secondary">{status}</Badge>;
}

function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "\u2014";
  return value.toLocaleString("en-US");
}

function formatCurrency(value: number | null | undefined): string {
  if (value === null || value === undefined) return "\u2014";
  return value.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

export default function LoanRecordsPage() {
  const router = useRouter();
  const [records, setRecords] = useState<LoanRecordListItem[]>([]);
  const [stats, setStats] = useState<LoanRecordStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);

  const fetchRecords = useCallback(async (currentPage: number, query: string) => {
    setLoading(true);
    try {
      const params: Record<string, any> = {
        skip: (currentPage - 1) * PAGE_SIZE,
        limit: PAGE_SIZE,
      };
      if (query.trim()) {
        params.search = query.trim();
      }
      const { data } = await api.get("/loan-records", { params });
      if (Array.isArray(data)) {
        setRecords(data);
        setTotalCount(data.length >= PAGE_SIZE ? currentPage * PAGE_SIZE + 1 : (currentPage - 1) * PAGE_SIZE + data.length);
      } else if (data.items) {
        setRecords(data.items);
        setTotalCount(data.total ?? data.items.length);
      }
    } catch {
      toast.error("Failed to load loan records.");
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchStats = useCallback(async () => {
    try {
      const { data } = await api.get<LoanRecordStats>("/loan-records/stats");
      setStats(data);
    } catch {
      // Stats are optional, fail silently
    }
  }, []);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  useEffect(() => {
    fetchRecords(page, search);
  }, [page, fetchRecords]);

  const handleSearch = () => {
    setPage(1);
    fetchRecords(1, search);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSearch();
  };

  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));

  return (
    <PageTransition>
      <div className="space-y-8">
        {/* Header */}
        <div>
          <p className="text-xs text-muted-foreground mb-4">Dashboard / Loan Records</p>
          <div className="flex items-center gap-3">
            <div className="icon-badge bg-emerald-100 dark:bg-emerald-900/30">
              <Database className="size-5 text-emerald-600 dark:text-emerald-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight">
                <span className="text-gradient">Loan Records</span>
              </h1>
              <p className="text-sm text-muted-foreground">
                Browse and search loan application data.
              </p>
            </div>
          </div>
        </div>

        {/* Stats Panel */}
        {stats && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <Card className="card-elevated border-border/40">
                <CardContent className="p-4">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1">Total Records</p>
                  <p className="text-2xl font-bold tabular-nums">{formatNumber(stats.total_records)}</p>
                </CardContent>
              </Card>

              <Card className="card-elevated border-border/40">
                <CardContent className="p-4">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">Decision Distribution</p>
                  <div className="space-y-1">
                    {Object.entries(stats.decision_distribution).map(([key, count]) => (
                      <div key={key} className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground">{key}</span>
                        <span className="font-medium tabular-nums">{count}</span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              <Card className="card-elevated border-border/40">
                <CardContent className="p-4">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">Bureau Score Range</p>
                  <div className="space-y-1 text-sm">
                    <div className="flex justify-between"><span className="text-muted-foreground">Min</span><span className="font-medium tabular-nums">{formatNumber(stats.bureau_score_range.min)}</span></div>
                    <div className="flex justify-between"><span className="text-muted-foreground">Max</span><span className="font-medium tabular-nums">{formatNumber(stats.bureau_score_range.max)}</span></div>
                    <div className="flex justify-between"><span className="text-muted-foreground">Avg</span><span className="font-medium tabular-nums">{formatNumber(Math.round(stats.bureau_score_range.avg))}</span></div>
                  </div>
                </CardContent>
              </Card>

              <Card className="card-elevated border-border/40">
                <CardContent className="p-4">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">Income Range</p>
                  <div className="space-y-1 text-sm">
                    <div className="flex justify-between"><span className="text-muted-foreground">Min</span><span className="font-medium tabular-nums">{formatCurrency(stats.income_range.min)}</span></div>
                    <div className="flex justify-between"><span className="text-muted-foreground">Max</span><span className="font-medium tabular-nums">{formatCurrency(stats.income_range.max)}</span></div>
                    <div className="flex justify-between"><span className="text-muted-foreground">Avg</span><span className="font-medium tabular-nums">{formatCurrency(Math.round(stats.income_range.avg))}</span></div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </motion.div>
        )}

        {/* Search */}
        <div className="flex items-center gap-3">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
            <Input
              placeholder="Search by loan application ID..."
              className="pl-9"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={handleKeyDown}
            />
          </div>
          <Button variant="secondary" size="sm" onClick={handleSearch}>
            Search
          </Button>
        </div>

        {/* Table */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.1 }}
        >
          <Card className="card-elevated border-border/40">
            {loading ? (
              <div className="flex items-center justify-center py-16">
                <Loader2 className="size-6 animate-spin text-muted-foreground" />
              </div>
            ) : records.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <Database className="size-12 text-muted-foreground/20" />
                <p className="mt-3 text-sm text-muted-foreground">
                  No loan records found.
                </p>
              </div>
            ) : (
              <>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-emerald-500/20">Loan Application ID</TableHead>
                      <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-emerald-500/20">Decision Status</TableHead>
                      <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-emerald-500/20">Bureau Score</TableHead>
                      <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-emerald-500/20">Monthly Income</TableHead>
                      <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b-2 border-emerald-500/20">Desired Amount</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {records.map((record) => (
                      <TableRow
                        key={record.id}
                        className="group cursor-pointer transition-colors duration-150 hover:bg-accent/50"
                        onClick={() => router.push(`/loan-records/${record.id}`)}
                      >
                        <TableCell className="font-medium">
                          <div className="flex items-center gap-2">
                            <Database className="size-4 text-emerald-500" />
                            {record.loan_application_id}
                          </div>
                        </TableCell>
                        <TableCell>{decisionBadge(record.decision_status)}</TableCell>
                        <TableCell className="tabular-nums">{formatNumber(record.bureau_score)}</TableCell>
                        <TableCell className="tabular-nums">{formatCurrency(record.monthly_income)}</TableCell>
                        <TableCell className="tabular-nums">{formatCurrency(record.desired_amount)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>

                {/* Pagination */}
                <div className="flex items-center justify-between border-t px-4 py-3">
                  <p className="text-xs text-muted-foreground">
                    Page {page}
                  </p>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={page <= 1}
                      onClick={() => setPage((p) => p - 1)}
                    >
                      <ChevronLeft className="size-4" />
                      Previous
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={records.length < PAGE_SIZE}
                      onClick={() => setPage((p) => p + 1)}
                    >
                      Next
                      <ChevronRight className="size-4" />
                    </Button>
                  </div>
                </div>
              </>
            )}
          </Card>
        </motion.div>
      </div>
    </PageTransition>
  );
}
