import io
import csv


def generate_summary_csv(summary_stats: dict) -> str:
    """Generate CSV string from simulation summary stats."""
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["Metric", "Value"])
    writer.writerow(["Total Customers", summary_stats.get("total_customers")])
    writer.writerow(["Affected Customers", summary_stats.get("affected_customers")])
    writer.writerow(["Affected Percentage (%)", summary_stats.get("affected_percentage")])

    # Decision changes
    dc = summary_stats.get("decision_changes", {})
    writer.writerow(["Approved to Rejected", dc.get("approved_to_rejected")])
    writer.writerow(["Rejected to Approved", dc.get("rejected_to_approved")])
    writer.writerow(["Decision Unchanged", dc.get("unchanged")])
    writer.writerow(["Baseline Approved", dc.get("baseline_approved")])
    writer.writerow(["Baseline Rejected", dc.get("baseline_rejected")])
    writer.writerow(["Simulated Approved", dc.get("simulated_approved")])
    writer.writerow(["Simulated Rejected", dc.get("simulated_rejected")])

    # Amount changes
    ac = summary_stats.get("amount_changes", {})
    writer.writerow(["Amount Increased", ac.get("increased")])
    writer.writerow(["Amount Decreased", ac.get("decreased")])
    writer.writerow(["Amount Unchanged", ac.get("unchanged")])
    writer.writerow(["Average Amount Delta", ac.get("avg_delta")])
    writer.writerow(["Total Amount Delta", ac.get("total_delta")])
    writer.writerow(["Rate Increased", ac.get("rate_increased")])
    writer.writerow(["Rate Decreased", ac.get("rate_decreased")])
    writer.writerow(["Average Rate Delta", ac.get("avg_rate_delta")])

    # Financial impact
    fi = summary_stats.get("financial_impact", {})
    for key, val in fi.items():
        writer.writerow([key.replace("_", " ").title(), val])

    return output.getvalue()


def generate_segment_csv(summary_stats: dict) -> str:
    """Generate CSV from segment breakdown."""
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["Segment Type", "Segment Name", "Total", "Affected", "Affected %"])

    segment_breakdown = summary_stats.get("segment_breakdown", {})

    for segment_type, segments in segment_breakdown.items():
        # Clean up segment type label (e.g. "by_bureau_score" -> "Bureau Score")
        label = segment_type.replace("by_", "").replace("_", " ").title()
        for segment_name, values in segments.items():
            writer.writerow([
                label,
                segment_name,
                values.get("total", 0),
                values.get("affected", 0),
                values.get("affected_pct", 0),
            ])

    return output.getvalue()
