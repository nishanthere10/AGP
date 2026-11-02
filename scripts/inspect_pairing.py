import json

d = json.load(open("results/dataset_pairing_validation.json"))
summary = d["summary"]
print("STATUS:", summary["status"])
print("leak_total:", summary["leak_total"])
for leak in summary["leak_records"]:
    print(leak)
print("anomalies:", len(summary["anomalies"]))
for a in summary["anomalies"][:10]:
    print(a)
