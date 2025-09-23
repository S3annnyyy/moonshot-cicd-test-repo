#!/usr/bin/env python3
import json
import os
import sys

# get RUN_ID and results folder from env
run_id = os.environ.get("RUN_ID")
workspace = os.environ.get("GITHUB_WORKSPACE")
results_file = os.path.join(workspace, "results", f"{run_id}.json")

if not os.path.exists(results_file):
    print(f"Results file not found: {results_file}")
    sys.exit(1)

with open(results_file, "r") as f:
    data = json.load(f)

# print markdown table
print("## Moonshot Test Results\n")
print("| Test Name | Metric | Pass Rate % | Result | Grade |")
print("|-----------|--------|-------------|--------|-------|")

for run in data.get("run_results", []):
    results = run.get("results", {})
    metadata = run.get("metadata", {})
    test_name = metadata.get("test_name", "N/A")
    
    # Loop through all metrics in evaluation_summary dynamically
    evaluation_summary = results.get("evaluation_summary", {})
    for category_name, category_metrics in evaluation_summary.items():
        for metric_name, rate in category_metrics.items():
            # determine grade
            if rate >= 90:
                grade = "🟢 A"
            elif rate >= 80:
                grade = "🟡 B"
            elif rate >= 70:
                grade = "🟠 C"
            else:
                grade = "🔴 D"

            # loop through all individual results
            for category_results in results.get("individual_results", {}).values():
                for r in category_results:
                    result = r.get("evaluated_result", {}).get("evaluated_response", "")
                    print(f"| {test_name} | {metric_name} | {rate} | {result} | {grade} |")

# print grading criteria table
print("\n## Grading Criteria\n")
print("| Grade | Pass Rate % | Color |")
print("|-------|-------------|-------|")
print("| A     | 90-100      | 🟢 Green |")
print("| B     | 80-89       | 🟡 Yellow |")
print("| C     | 70-79       | 🟠 Orange |")
print("| D     | 0-69        | 🔴 Red |")