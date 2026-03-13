"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { SimulationForm } from "@/components/simulations/simulation-form";
import { ChevronLeft } from "lucide-react";
import { PageTransition } from "@/components/page-transition";

export default function NewSimulationPage() {
  return (
    <PageTransition>
    <div className="space-y-8">
      <p className="text-xs text-muted-foreground mb-4">Dashboard / Simulations / New</p>
      <div>
        <Button
          variant="ghost"
          size="sm"
          render={<Link href="/simulations" />}
          className="mb-2"
        >
          <ChevronLeft className="size-4" />
          Back to Simulations
        </Button>
        <h1 className="text-2xl font-semibold tracking-tight">New Simulation</h1>
        <p className="mt-2 text-muted-foreground">
          Configure and run a new policy impact simulation.
        </p>
      </div>

      <div className="max-w-2xl">
        <SimulationForm />
      </div>
    </div>
    </PageTransition>
  );
}
