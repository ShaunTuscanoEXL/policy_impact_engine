"""Run large BRD extraction 3 times and log rule counts — unbuffered."""
import sys
import requests
import time

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)

API = "http://localhost:8001/api/v1"
BRD_ID = "416dd6b7-7aaa-48fc-a6cf-04023868805e"

results = []

for run in range(1, 4):
    print(f"\n{'='*50}")
    print(f"RUN {run}/3 - Starting extraction...")
    sys.stdout.flush()

    # Delete existing rule sets for this BRD first
    try:
        workflow = requests.get(f"{API}/brds/{BRD_ID}/workflow", timeout=10).json()
        if workflow.get("rule_set"):
            rs_id = workflow["rule_set"]["id"]
            requests.delete(f"{API}/rule-sets/{rs_id}", timeout=10)
            print(f"  Deleted old rule set {rs_id}")
    except Exception as e:
        print(f"  Cleanup note: {e}")
    sys.stdout.flush()

    start = time.time()
    try:
        resp = requests.post(
            f"{API}/brds/{BRD_ID}/extract-rules",
            json={},
            timeout=300,  # 5 min timeout for LLM calls
        )
        elapsed = time.time() - start

        if resp.status_code == 200:
            data = resp.json()
            count = data["rules_count"]
            rs_id = data["rule_set_id"]
            print(f"  RESULT: {count} rules in {elapsed:.1f}s")

            # Get rule details
            rs_resp = requests.get(f"{API}/rule-sets/{rs_id}", timeout=10)
            if rs_resp.status_code == 200:
                rs = rs_resp.json()
                rule_ids = sorted([r["rule_id"] for r in rs.get("rules", [])])
                print(f"  First 5 IDs: {rule_ids[:5]}")
                print(f"  Last 5 IDs:  {rule_ids[-5:]}")
                nums = []
                for rid in rule_ids:
                    try:
                        nums.append(int(rid.replace("RULE-", "")))
                    except:
                        pass
                if nums:
                    expected = set(range(1, max(nums) + 1))
                    missing = sorted(expected - set(nums))
                    dupes = [n for n in nums if nums.count(n) > 1]
                    print(f"  Range: RULE-001 to RULE-{max(nums):03d}")
                    if missing:
                        print(f"  MISSING: {missing}")
                    else:
                        print(f"  No gaps")
                    if dupes:
                        print(f"  DUPLICATES: {set(dupes)}")

            results.append({"run": run, "count": count, "time": round(elapsed, 1)})
        else:
            print(f"  ERROR {resp.status_code}: {resp.text[:300]}")
            results.append({"run": run, "count": 0, "error": resp.text[:100]})
    except Exception as e:
        elapsed = time.time() - start
        print(f"  EXCEPTION after {elapsed:.1f}s: {e}")
        results.append({"run": run, "count": 0, "error": str(e)})

    sys.stdout.flush()

print(f"\n{'='*50}")
print("SUMMARY")
print(f"{'='*50}")
for r in results:
    print(f"  Run {r['run']}: {r.get('count', 0)} rules in {r.get('time', '?')}s")
counts = [r["count"] for r in results if r["count"] > 0]
if counts:
    print(f"  Min={min(counts)}  Max={max(counts)}  Spread={max(counts) - min(counts)}")
print("DONE")
