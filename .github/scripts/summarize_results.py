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
print("| Test Type | Metric Used | Score (%) | Grade |")
print("|-----------|-------------|-----------|-------|")

for run in data.get("run_results", []):
    eval_summary = run.get("results", {}).get("evaluation_summary", {})
    for test_type, metric_data in eval_summary.items():
        for metric_name, metric_score in metric_data.items():
            if metric_score >= 90:
                grade = "🟢 A"
            elif metric_score >= 80:
                grade = "🟡 B"
            elif metric_score >= 70:
                grade = "🟠 C"
            else:
                 grade = "🔴 D"
            print(f"| {test_type} | {metric_name} | {metric_score} | {grade} |")

# print grading criteria table
print("\n## Grading Criteria\n")
print("| Grade | Score (%) | Color |")
print("|-------|-----------|-------|")
print("| A     | 90-100    | 🟢 Green |")
print("| B     | 80-89     | 🟡 Yellow |")
print("| C     | 70-79     | 🟠 Orange |")
print("| D     | 0-69      | 🔴 Red |")