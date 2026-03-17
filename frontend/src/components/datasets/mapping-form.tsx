"use client";

import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import { Loader2, Save } from "lucide-react";

interface MappingFormProps {
  columns: string[];
  detectedMapping: Record<string, any>;
  savedMapping: Record<string, any> | null;
  savedConfig: Record<string, any> | null;
  onSave: (mapping: Record<string, any>, config: Record<string, any>) => void;
  saving?: boolean;
}

const REQUIRED_FIELDS = [
  { key: "score_field", label: "Score Field" },
  { key: "income_field", label: "Income Field" },
  { key: "amount_field", label: "Loan Amount Field" },
  { key: "dti_field", label: "DTI Field" },
] as const;

function confidenceBadge(confidence: number | undefined) {
  if (confidence == null) return null;
  const pct = Math.round(confidence * 100);
  let bg: string;
  let text: string;
  if (pct >= 80) {
    bg = "bg-green-100 dark:bg-green-900/30";
    text = "text-green-700 dark:text-green-400";
  } else if (pct >= 50) {
    bg = "bg-yellow-100 dark:bg-yellow-900/30";
    text = "text-yellow-700 dark:text-yellow-400";
  } else {
    bg = "bg-red-100 dark:bg-red-900/30";
    text = "text-red-700 dark:text-red-400";
  }
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${bg} ${text}`}
    >
      {pct}% match
    </span>
  );
}

function getDetectedColumn(
  detectedMapping: Record<string, any>,
  fieldKey: string
): string {
  const entry = detectedMapping[fieldKey];
  if (!entry) return "";
  if (typeof entry === "string") return entry;
  return entry.column ?? entry.field ?? "";
}

function getDetectedConfidence(
  detectedMapping: Record<string, any>,
  fieldKey: string
): number | undefined {
  const entry = detectedMapping[fieldKey];
  if (!entry || typeof entry === "string") return undefined;
  return entry.confidence;
}

export function MappingForm({
  columns,
  detectedMapping,
  savedMapping,
  savedConfig,
  onSave,
  saving = false,
}: MappingFormProps) {
  const initialFields = useMemo(() => {
    const result: Record<string, string> = {};
    for (const { key } of REQUIRED_FIELDS) {
      result[key] = savedMapping?.[key] ?? getDetectedColumn(detectedMapping, key);
    }
    return result;
  }, [savedMapping, detectedMapping]);

  const defaultConfig =
    savedConfig ?? detectedMapping?.default_baseline_config ?? {};

  const [fields, setFields] = useState<Record<string, string>>(initialFields);
  const [minScore, setMinScore] = useState<number>(defaultConfig.min_score ?? 700);
  const [maxDti, setMaxDti] = useState<number>(defaultConfig.max_dti ?? 0.4);
  const [minIncome, setMinIncome] = useState<number>(
    defaultConfig.min_income ?? 25000
  );

  const updateField = (key: string, value: string) => {
    setFields((prev) => ({ ...prev, [key]: value }));
  };

  const allFilled = REQUIRED_FIELDS.every((f) => fields[f.key]?.trim());
  const allDistinct = useMemo(() => {
    const values = REQUIRED_FIELDS.map((f) => fields[f.key]?.trim()).filter(Boolean);
    return new Set(values).size === values.length;
  }, [fields]);
  const canSave = allFilled && allDistinct && !saving;

  const handleSave = () => {
    if (!canSave) return;
    const mapping = {
      score_field: fields.score_field,
      income_field: fields.income_field,
      amount_field: fields.amount_field,
      dti_field: fields.dti_field,
    };
    const config = { min_score: minScore, max_dti: maxDti, min_income: minIncome };
    onSave(mapping, config);
  };

  return (
    <div className="space-y-6">
      {/* Required Column Mapping */}
      <Card>
        <CardHeader>
          <CardTitle>Required Column Mapping</CardTitle>
          <CardDescription>
            Map your dataset columns to the required engine fields. Each field
            must be mapped to a distinct column.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {REQUIRED_FIELDS.map(({ key, label }) => {
            const confidence = getDetectedConfidence(detectedMapping, key);
            const isFromDetected = !savedMapping?.[key] && !!getDetectedColumn(detectedMapping, key);
            return (
              <div key={key} className="grid grid-cols-[160px_1fr_auto] items-center gap-3">
                <label
                  htmlFor={`mapping-${key}`}
                  className="text-sm font-medium"
                >
                  {label} <span className="text-destructive">*</span>
                </label>
                <select
                  id={`mapping-${key}`}
                  value={fields[key]}
                  onChange={(e) => updateField(key, e.target.value)}
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm"
                >
                  <option value="">Select column...</option>
                  {columns.map((col) => (
                    <option key={col} value={col}>
                      {col}
                    </option>
                  ))}
                </select>
                <div className="w-24 text-right">
                  {isFromDetected && confidenceBadge(confidence)}
                </div>
              </div>
            );
          })}
          {allFilled && !allDistinct && (
            <p className="text-sm text-destructive">
              Each field must be mapped to a different column.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Baseline Configuration */}
      <Card>
        <CardHeader>
          <CardTitle>Baseline Configuration</CardTitle>
          <CardDescription>
            Set threshold values used as baseline for policy impact analysis.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="space-y-2">
              <label htmlFor="cfg-min-score" className="text-sm font-medium">
                Min Score
              </label>
              <Input
                id="cfg-min-score"
                type="number"
                value={minScore}
                onChange={(e) => setMinScore(Number(e.target.value))}
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="cfg-max-dti" className="text-sm font-medium">
                Max DTI
              </label>
              <Input
                id="cfg-max-dti"
                type="number"
                step="0.01"
                value={maxDti}
                onChange={(e) => setMaxDti(Number(e.target.value))}
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="cfg-min-income" className="text-sm font-medium">
                Min Income
              </label>
              <Input
                id="cfg-min-income"
                type="number"
                value={minIncome}
                onChange={(e) => setMinIncome(Number(e.target.value))}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Save */}
      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={!canSave}>
          {saving ? (
            <Loader2 className="mr-2 size-4 animate-spin" />
          ) : (
            <Save className="mr-2 size-4" />
          )}
          Save Mapping
        </Button>
      </div>
    </div>
  );
}
