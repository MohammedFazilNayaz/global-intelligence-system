import urllib.request
import json
import sys

BASE_URL = "http://127.0.0.1:8000"

def test_endpoint(name, url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TestClient/1.0"})
        with urllib.request.urlopen(req, timeout=10) as response:
            code = response.getcode()
            body = json.loads(response.read().decode("utf-8"))
            print(f"[PASS] {code} {name:<40} -> {url}")
            return True, code, body
    except urllib.error.HTTPError as e:
        print(f"[FAIL] {e.code} {name:<40} -> {url} : {e.reason}")
        return False, e.code, None
    except Exception as exc:
        print(f"[ERROR] {name:<40} -> {url} : {exc}")
        return False, 500, None

def main():
    print("=" * 80)
    print("PHASE 12: DASHBOARD & CORE API ENDPOINT REGRESSION AUDIT")
    print("=" * 80)
    
    endpoints = [
        ("Dashboard Summary", f"{BASE_URL}/api/v1/dashboard/summary"),
        ("Live Intelligence Feed", f"{BASE_URL}/api/v1/intelligence/live?limit=10"),
        ("Geo Features", f"{BASE_URL}/api/v1/geo/features"),
        ("Geo Unresolved", f"{BASE_URL}/api/v1/geo/unresolved"),
        ("Reliability Audit", f"{BASE_URL}/api/v1/system/reliability-audit"),
        ("Market Tickers", f"{BASE_URL}/api/v1/market/tickers"),
    ]
    
    all_pass = True
    results = {}
    for name, url in endpoints:
        ok, code, data = test_endpoint(name, url)
        results[name] = {"code": code, "ok": ok}
        if not ok:
            all_pass = False
            
    # For dossier endpoint, get a real event_id from live intelligence feed
    live_ok, _, live_data = test_endpoint("Get Sample Event for Dossier", f"{BASE_URL}/api/v1/intelligence/live?limit=1")
    if live_ok and live_data and live_data.get("items"):
        event_id = live_data["items"][0]["event_id"]
        dossier_url = f"{BASE_URL}/api/v1/intelligence/events/{event_id}/dossier"
        d_ok, d_code, d_data = test_endpoint("Event Intelligence Dossier", dossier_url)
        results["Event Intelligence Dossier"] = {"code": d_code, "ok": d_ok, "event_id": event_id}
        if not d_ok:
            all_pass = False
    else:
        print("[WARN] Could not retrieve sample event from live feed.")
        all_pass = False
        
    print("\nEndpoint Audit Result: " + ("ALL PASSED (Zero HTTP 500)" if all_pass else "FAILURES DETECTED"))
    with open("scratch/certify_endpoint_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    main()
