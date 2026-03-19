"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import api from "@/lib/api";
import type { LoanRecord } from "@/lib/types";
import { toast } from "sonner";
import { PageTransition } from "@/components/page-transition";
import { JsonViewer } from "@/components/loan-records/json-viewer";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Database, ArrowLeft, Loader2, FileJson } from "lucide-react";

function decisionBadge(payload: Record<string, any>) {
  const status =
    payload?.decision_status ??
    payload?.decisionStatus ??
    payload?.status ??
    null;
  if (!status) return null;
  const upper = String(status).toUpperCase();
  if (upper === "APPROVED")
    return <Badge className="bg-emerald-500/10 text-emerald-600 border-emerald-500/20">Approved</Badge>;
  if (upper === "REJECTED")
    return <Badge variant="destructive">Rejected</Badge>;
  if (upper === "CONDITIONAL")
    return <Badge className="bg-amber-500/10 text-amber-600 border-amber-500/20">Conditional</Badge>;
  return <Badge variant="secondary">{status}</Badge>;
}

export default function LoanRecordDetailPage() {
  const params = useParams<{ id: string }>();
  const [record, setRecord] = useState<LoanRecord | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchRecord() {
      try {
        const { data } = await api.get<LoanRecord>(`/loan-records/${params.id}`);
        setRecord(data);
      } catch {
        toast.error("Failed to load loan record.");
      } finally {
        setLoading(false);
      }
    }
    if (params.id) fetchRecord();
  }, [params.id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!record) {
    return (
      <PageTransition>
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <Database className="size-12 text-muted-foreground/20" />
          <p className="mt-3 text-sm text-muted-foreground">Loan record not found.</p>
          <Button variant="outline" size="sm" className="mt-4" render={<Link href="/loan-records" />}>
            <ArrowLeft className="size-4 mr-1" />
            Back to Loan Records
          </Button>
        </div>
      </PageTransition>
    );
  }

  const statusBadge = decisionBadge(record.response_payload ?? {});

  return (
    <PageTransition>
      <div className="space-y-8">
        {/* Breadcrumb + Header */}
        <div>
          <p className="text-xs text-muted-foreground mb-4">
            <Link href="/loan-records" className="hover:text-foreground transition-colors">
              Dashboard / Loan Records
            </Link>
            {" / "}
            {record.loan_application_id}
          </p>
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="icon-sm" render={<Link href="/loan-records" />}>
              <ArrowLeft className="size-4" />
            </Button>
            <div className="icon-badge bg-emerald-100 dark:bg-emerald-900/30">
              <Database className="size-5 text-emerald-600 dark:text-emerald-400" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold tracking-tight">
                  <span className="text-gradient">{record.loan_application_id}</span>
                </h1>
                {statusBadge}
              </div>
              <p className="text-sm text-muted-foreground">
                Created {new Date(record.created_at).toLocaleDateString("en-US", {
                  year: "numeric",
                  month: "short",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </p>
            </div>
          </div>
        </div>

        {/* Payload Tabs */}
        <Tabs defaultValue="request">
          <TabsList>
            <TabsTrigger value="request">
              <FileJson className="size-4 mr-1.5" />
              Request Payload
            </TabsTrigger>
            <TabsTrigger value="response">
              <FileJson className="size-4 mr-1.5" />
              Response Payload
            </TabsTrigger>
          </TabsList>

          <TabsContent value="request">
            <Card className="card-elevated border-border/40 mt-4">
              <CardContent className="p-6">
                {record.request_payload && Object.keys(record.request_payload).length > 0 ? (
                  <JsonViewer data={record.request_payload} initialExpanded={true} />
                ) : (
                  <p className="text-sm text-muted-foreground">No request payload data.</p>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="response">
            <Card className="card-elevated border-border/40 mt-4">
              <CardContent className="p-6">
                {record.response_payload && Object.keys(record.response_payload).length > 0 ? (
                  <JsonViewer data={record.response_payload} initialExpanded={true} />
                ) : (
                  <p className="text-sm text-muted-foreground">No response payload data.</p>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </PageTransition>
  );
}
