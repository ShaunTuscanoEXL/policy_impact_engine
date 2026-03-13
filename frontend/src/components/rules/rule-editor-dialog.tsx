"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogClose,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Plus, Trash2, Loader2 } from "lucide-react";
import type { Rule, Condition, Action } from "@/lib/types";

const FIELD_OPTIONS = [
  "bureau_score",
  "dti_ratio",
  "monthly_income",
  "employment_type",
  "employment_tenure_months",
  "active_loans",
  "unsecured_loans",
  "credit_utilization_ratio",
  "inquiries_last_3m",
  "salary_credit_consistency_6m",
  "banking_stability_index",
  "desired_amount",
  "cash_deposits_6m",
  "city_tier",
  "max_dpd_last_12m",
  "cheque_bounces_6m",
];

const OPERATOR_OPTIONS = [
  ">=",
  "<=",
  ">",
  "<",
  "==",
  "!=",
  "in",
  "not_in",
  "between",
];

const ACTION_TYPE_OPTIONS = ["SET", "REJECT", "ADJUST", "FLAG"] as const;
const RULE_TYPE_OPTIONS = [
  "ELIGIBILITY",
  "PRICING",
  "CAP",
  "THRESHOLD",
  "SCORING",
] as const;

interface RuleEditorDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  rule: Rule | null; // null = create new
  onSave: (data: RuleFormData) => Promise<void>;
  saving: boolean;
}

export interface RuleFormData {
  rule_name: string;
  description: string;
  rule_type: string;
  priority: number;
  conditions: Condition[];
  actions: Action[];
}

function emptyCondition(): Condition {
  return { field: "bureau_score", operator: ">=", value: "", logic: "AND" };
}

function emptyAction(): Action {
  return { action_type: "SET", target_field: "", value: "", description: "" };
}

export function RuleEditorDialog({
  open,
  onOpenChange,
  rule,
  onSave,
  saving,
}: RuleEditorDialogProps) {
  const [formData, setFormData] = useState<RuleFormData>({
    rule_name: "",
    description: "",
    rule_type: "ELIGIBILITY",
    priority: 1,
    conditions: [emptyCondition()],
    actions: [emptyAction()],
  });

  const isEditMode = rule !== null;

  // Populate form when editing
  useEffect(() => {
    if (rule) {
      setFormData({
        rule_name: rule.rule_name,
        description: rule.description,
        rule_type: rule.rule_type,
        priority: rule.priority,
        conditions:
          rule.conditions.length > 0
            ? rule.conditions.map((c) => ({ ...c }))
            : [emptyCondition()],
        actions:
          rule.actions.length > 0
            ? rule.actions.map((a) => ({ ...a }))
            : [emptyAction()],
      });
    } else {
      setFormData({
        rule_name: "",
        description: "",
        rule_type: "ELIGIBILITY",
        priority: 1,
        conditions: [emptyCondition()],
        actions: [emptyAction()],
      });
    }
  }, [rule, open]);

  const updateCondition = useCallback(
    (index: number, field: keyof Condition, value: any) => {
      setFormData((prev) => {
        const conditions = [...prev.conditions];
        conditions[index] = { ...conditions[index], [field]: value };
        return { ...prev, conditions };
      });
    },
    []
  );

  const addCondition = useCallback(() => {
    setFormData((prev) => ({
      ...prev,
      conditions: [...prev.conditions, emptyCondition()],
    }));
  }, []);

  const removeCondition = useCallback((index: number) => {
    setFormData((prev) => ({
      ...prev,
      conditions: prev.conditions.filter((_, i) => i !== index),
    }));
  }, []);

  const updateAction = useCallback(
    (index: number, field: keyof Action, value: any) => {
      setFormData((prev) => {
        const actions = [...prev.actions];
        actions[index] = { ...actions[index], [field]: value };
        return { ...prev, actions };
      });
    },
    []
  );

  const addAction = useCallback(() => {
    setFormData((prev) => ({
      ...prev,
      actions: [...prev.actions, emptyAction()],
    }));
  }, []);

  const removeAction = useCallback((index: number) => {
    setFormData((prev) => ({
      ...prev,
      actions: prev.actions.filter((_, i) => i !== index),
    }));
  }, []);

  const handleSubmit = () => {
    onSave(formData);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {isEditMode ? "Edit Rule" : "Add New Rule"}
          </DialogTitle>
          <DialogDescription>
            {isEditMode
              ? "Update the rule configuration below."
              : "Define a new rule with conditions and actions."}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5 py-2">
          {/* Basic fields */}
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <label className="text-xs font-medium">Rule Name</label>
              <Input
                value={formData.rule_name}
                onChange={(e) =>
                  setFormData((prev) => ({
                    ...prev,
                    rule_name: e.target.value,
                  }))
                }
                placeholder="e.g., Min Bureau Score Check"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label className="text-xs font-medium">Rule Type</label>
                <Select
                  value={formData.rule_type}
                  onValueChange={(val) =>
                    setFormData((prev) => ({
                      ...prev,
                      rule_type: val ?? prev.rule_type,
                    }))
                  }
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {RULE_TYPE_OPTIONS.map((opt) => (
                      <SelectItem key={opt} value={opt}>
                        {opt}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-medium">Priority</label>
                <Input
                  type="number"
                  min={1}
                  max={100}
                  value={formData.priority}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      priority: parseInt(e.target.value) || 1,
                    }))
                  }
                />
              </div>
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium">Description</label>
            <textarea
              className="flex min-h-[60px] w-full rounded-lg border border-input bg-transparent px-3 py-2 text-sm outline-none focus-visible:border-[#0070f3] focus-visible:ring-3 focus-visible:ring-[#0070f3]/20 disabled:cursor-not-allowed disabled:opacity-50"
              value={formData.description}
              onChange={(e) =>
                setFormData((prev) => ({
                  ...prev,
                  description: e.target.value,
                }))
              }
              placeholder="Describe what this rule does..."
            />
          </div>

          <Separator />

          {/* Conditions */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <label className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Conditions
              </label>
              <Button variant="ghost" size="sm" onClick={addCondition}>
                <Plus className="mr-1 size-3.5" />
                Add Condition
              </Button>
            </div>
            <div className="space-y-2">
              {formData.conditions.map((cond, i) => (
                <div key={i} className="flex items-center gap-2">
                  {i > 0 && (
                    <Select
                      value={cond.logic || "AND"}
                      onValueChange={(val) =>
                        updateCondition(i, "logic", val ?? "AND")
                      }
                    >
                      <SelectTrigger className="w-[70px]">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="AND">AND</SelectItem>
                        <SelectItem value="OR">OR</SelectItem>
                      </SelectContent>
                    </Select>
                  )}
                  {i === 0 && <div className="w-[70px]" />}

                  <Select
                    value={cond.field}
                    onValueChange={(val) =>
                      updateCondition(i, "field", val ?? cond.field)
                    }
                  >
                    <SelectTrigger className="w-[180px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {FIELD_OPTIONS.map((f) => (
                        <SelectItem key={f} value={f}>
                          {f}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>

                  <Select
                    value={cond.operator}
                    onValueChange={(val) =>
                      updateCondition(i, "operator", val ?? cond.operator)
                    }
                  >
                    <SelectTrigger className="w-[80px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {OPERATOR_OPTIONS.map((op) => (
                        <SelectItem key={op} value={op}>
                          {op}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>

                  <Input
                    className="flex-1"
                    placeholder="Value"
                    value={
                      typeof cond.value === "object"
                        ? JSON.stringify(cond.value)
                        : String(cond.value ?? "")
                    }
                    onChange={(e) =>
                      updateCondition(i, "value", e.target.value)
                    }
                  />

                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => removeCondition(i)}
                    disabled={formData.conditions.length <= 1}
                  >
                    <Trash2 className="size-3.5 text-muted-foreground" />
                  </Button>
                </div>
              ))}
            </div>
          </div>

          <Separator />

          {/* Actions */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <label className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Actions
              </label>
              <Button variant="ghost" size="sm" onClick={addAction}>
                <Plus className="mr-1 size-3.5" />
                Add Action
              </Button>
            </div>
            <div className="space-y-2">
              {formData.actions.map((action, i) => (
                <div key={i} className="flex items-center gap-2">
                  <Select
                    value={action.action_type}
                    onValueChange={(val) =>
                      updateAction(
                        i,
                        "action_type",
                        (val as Action["action_type"]) ?? action.action_type
                      )
                    }
                  >
                    <SelectTrigger className="w-[100px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {ACTION_TYPE_OPTIONS.map((at) => (
                        <SelectItem key={at} value={at}>
                          {at}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>

                  <Input
                    className="w-[160px]"
                    placeholder="Target field"
                    value={action.target_field}
                    onChange={(e) =>
                      updateAction(i, "target_field", e.target.value)
                    }
                  />

                  <Input
                    className="w-[100px]"
                    placeholder="Value"
                    value={
                      typeof action.value === "object"
                        ? JSON.stringify(action.value)
                        : String(action.value ?? "")
                    }
                    onChange={(e) =>
                      updateAction(i, "value", e.target.value)
                    }
                  />

                  <Input
                    className="flex-1"
                    placeholder="Description"
                    value={action.description}
                    onChange={(e) =>
                      updateAction(i, "description", e.target.value)
                    }
                  />

                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => removeAction(i)}
                    disabled={formData.actions.length <= 1}
                  >
                    <Trash2 className="size-3.5 text-muted-foreground" />
                  </Button>
                </div>
              ))}
            </div>
          </div>
        </div>

        <DialogFooter>
          <DialogClose render={<Button variant="outline" />}>
            Cancel
          </DialogClose>
          <Button onClick={handleSubmit} disabled={saving || !formData.rule_name}>
            {saving && <Loader2 className="mr-2 size-4 animate-spin" />}
            {isEditMode ? "Save Changes" : "Add Rule"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
