#!/usr/bin/env python3
import json
with open("/home/aaksh/projects/LocalAgentBench/results/pilot/task_selection.json") as f:
    d = json.load(f)
print("Task IDs:", d["task_ids"])
print("Count:", len(d["task_ids"]))