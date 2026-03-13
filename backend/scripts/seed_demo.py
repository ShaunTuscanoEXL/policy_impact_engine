#!/usr/bin/env python3
"""Seed demo data via the REST API.

Run with:
    python scripts/seed_demo.py [--base-url http://localhost:8000]

Expects:
    - The backend API to be running
    - Sample BRD files in data/sample_brds/
    - Sample dataset in data/sample_datasets/
"""

import argparse
import sys
import time
from pathlib import Path
import requests

BASE_URL = "http://localhost:8000/api/v1"


def upload_brds(base_url: str) -> list[dict]:
    """Upload all sample BRDs."""
    brds = []
    brd_dir = Path(__file__).parent.parent / "data" / "sample_brds"

    for brd_file in sorted(brd_dir.glob("*.docx")):
        print(f"  Uploading {brd_file.name}...")
        with open(brd_file, "rb") as f:
            response = requests.post(
                f"{base_url}/brds/upload",
                files={"file": (brd_file.name, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            )

        if response.status_code == 200:
            data = response.json()
            brds.append(data)
            print(f"    Uploaded: {data['id']}")
        else:
            print(f"    Failed: {response.text}")

    return brds


def upload_dataset(base_url: str) -> dict | None:
    """Upload the sample dataset."""
    dataset_path = Path(__file__).parent.parent / "data" / "sample_datasets" / "loan_applications_500.csv"

    if not dataset_path.exists():
        print(f"  Dataset not found at {dataset_path}")
        return None

    print(f"  Uploading {dataset_path.name}...")
    with open(dataset_path, "rb") as f:
        response = requests.post(
            f"{base_url}/datasets/upload",
            files={"file": (dataset_path.name, f, "text/csv")},
            data={"name": "Loan Applications (500)", "description": "500 sample loan applications with realistic distributions"},
        )

    if response.status_code == 200:
        data = response.json()
        print(f"    Uploaded: {data['id']} ({data.get('row_count', '?')} rows)")
        return data
    else:
        print(f"    Failed: {response.text}")
        return None


def run_pipeline(base_url: str, brd_id: str, dataset_id: str, scenario_name: str) -> dict | None:
    """Trigger pipeline with auto-approve."""
    print(f"  Running pipeline for scenario '{scenario_name}'...")

    response = requests.post(
        f"{base_url}/pipeline/run",
        json={
            "brd_id": brd_id,
            "dataset_id": dataset_id,
            "scenario_name": scenario_name,
            "auto_approve": True,
        },
        timeout=300,  # Pipeline can take a while
    )

    if response.status_code == 200:
        data = response.json()
        status = data.get("status")
        print(f"    Status: {status}")
        if status == "COMPLETED":
            impact = data.get("impact_summary", {})
            print(f"    Affected: {impact.get('affected_customers', '?')}/{impact.get('total_customers', '?')} ({impact.get('affected_percentage', '?')}%)")
            print(f"    Rules extracted: {data.get('rules_extracted', '?')}")
        elif status == "FAILED":
            print(f"    Error: {data.get('error', 'Unknown')}")
        return data
    else:
        print(f"    Failed: {response.text}")
        return None


def create_scenario(base_url: str, name: str, simulation_ids: list[str]) -> dict | None:
    """Create a comparison scenario."""
    print(f"  Creating scenario '{name}'...")

    response = requests.post(
        f"{base_url}/scenarios",
        json={
            "name": name,
            "description": f"Comparison of {len(simulation_ids)} simulations",
            "simulation_ids": simulation_ids,
        },
    )

    if response.status_code == 200:
        data = response.json()
        print(f"    Created: {data['id']}")
        return data
    else:
        print(f"    Failed: {response.text}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Seed demo data for Policy Impact Engine")
    parser.add_argument("--base-url", default=BASE_URL, help="API base URL")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")

    # Check API health
    try:
        health = requests.get(f"{base_url.rsplit('/api', 1)[0]}/health", timeout=5)
        if health.status_code != 200:
            print(f"API not healthy: {health.status_code}")
            sys.exit(1)
    except requests.ConnectionError:
        print(f"Cannot connect to API at {base_url}")
        print("Make sure the backend is running: uvicorn app.main:app --reload")
        sys.exit(1)

    print("\n=== Policy Impact Engine Demo Seeder ===\n")

    # Step 1: Upload BRDs
    print("[1/4] Uploading sample BRDs...")
    brds = upload_brds(base_url)
    print(f"  Uploaded {len(brds)} BRDs\n")

    # Step 2: Upload dataset
    print("[2/4] Uploading sample dataset...")
    dataset = upload_dataset(base_url)
    if not dataset:
        print("Failed to upload dataset. Aborting.")
        sys.exit(1)
    print()

    # Step 3: Run pipelines
    print("[3/4] Running simulations...")
    simulation_ids = []

    if len(brds) >= 1:
        result1 = run_pipeline(base_url, brds[0]["id"], dataset["id"], "BRD-001: DTI Cap Tightening")
        if result1 and result1.get("simulation_id"):
            simulation_ids.append(result1["simulation_id"])

    if len(brds) >= 4:
        result4 = run_pipeline(base_url, brds[3]["id"], dataset["id"], "BRD-004: Post-COVID Risk Tightening")
        if result4 and result4.get("simulation_id"):
            simulation_ids.append(result4["simulation_id"])

    print()

    # Step 4: Create comparison scenario
    print("[4/4] Creating comparison scenario...")
    if len(simulation_ids) >= 2:
        create_scenario(base_url, "DTI Tightening vs Post-COVID Tightening", simulation_ids)
    else:
        print("  Not enough simulations to create a comparison")

    print("\n=== Demo seeding complete! ===")
    print(f"  Visit http://localhost:3000 to see the dashboard")
    print()


if __name__ == "__main__":
    main()
