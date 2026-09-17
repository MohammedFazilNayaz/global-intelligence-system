import json

with open("scratch/sources_audit_results.json", encoding="utf-8") as f:
    data = json.load(f)

print(f"Total sources: {len(data)}")

print("\n" + "="*80)
print("=== SOURCES REQUIRING ATTENTION (0 DOCS, FAILURES, OR NON-HEALTHY) ===")
print("="*80)
for s in data:
    if s["doc_count"] == 0 or s["consecutive_failures"] > 0 or s["health_status"] != "HEALTHY" or not s["active"]:
        print(f"NAME:     {s['name']} (Type: {s['source_type']}, Active: {s['active']})")
        print(f"REGION:   {s['region']} | DOMAIN: {s['domain']}")
        print(f"STATUS:   Health: {s['health_status']} | Freshness: {s['freshness_status']} | Failures: {s['consecutive_failures']} | Docs: {s['doc_count']}")
        print(f"URL:      {s['feed_url']}")
        print(f"LAST ERR: {s['last_error']}")
        print(f"LAST OK:  {s['last_successful_fetch']}")
        print("-" * 80)

print("\n" + "="*80)
print("=== HEALTHY SOURCES PRODUCING CONTENT ===")
print("="*80)
for s in data:
    if s["doc_count"] > 0 and s["consecutive_failures"] == 0 and s["health_status"] == "HEALTHY" and s["active"]:
        print(f"{s['name'][:30]:30} | Docs: {s['doc_count']:4} | Latest Pub: {s['latest_doc_published']} | Last Fetch: {s['last_successful_fetch'][:19]}")
