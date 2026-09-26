"""
Automated Test Suite for Portable Containerized REST Service
Runs all 8 required test cases from the assignment specification without external dependencies.
"""

import sys
import json
import urllib.request
import urllib.error

BASE_URL = "http://localhost:5000"

# ANSI color codes for terminal display
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"


def make_request(path):
    url = f"{BASE_URL}{path}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            status = response.status
            body = response.read().decode("utf-8")
            data = json.loads(body) if body else {}
            return status, data
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8")
        try:
            data = json.loads(body)
        except Exception:
            data = {"raw": body}
        return err.code, data
    except urllib.error.URLError as err:
        return None, {"error": str(err.reason)}


def run_tests():
    print(f"\n{CYAN}======================================================{RESET}")
    print(f"{CYAN}  Running Portable Containerized REST Service Tests   {RESET}")
    print(f"{CYAN}  Target: {BASE_URL}                                   {RESET}")
    print(f"{CYAN}======================================================\n{RESET}")

    # Check connection first
    status, data = make_request("/health")
    if status is None:
        print(f"{RED}[FAIL] Could not connect to {BASE_URL}. Ensure 'docker compose up' is running!{RESET}")
        print(f"Details: {data.get('error')}\n")
        sys.exit(1)

    # Initial stats reading
    _, initial_stats = make_request("/stats")
    initial_count = initial_stats.get("conversions", 0)
    print(f"Current Redis conversions count before test run: {YELLOW}{initial_count}{RESET}\n")

    test_cases = [
        {
            "id": 1,
            "description": "Health check liveness",
            "path": "/health",
            "expected_status": 200,
            "validator": lambda d: d.get("status") == "ok",
            "expect_increment": False
        },
        {
            "id": 2,
            "description": "Convert 0 lbs (edge case: zero)",
            "path": "/convert?lbs=0",
            "expected_status": 200,
            "validator": lambda d: d.get("kg") == 0 and d.get("lbs") == 0,
            "expect_increment": True
        },
        {
            "id": 3,
            "description": "Convert 150 lbs (standard integer)",
            "path": "/convert?lbs=150",
            "expected_status": 200,
            "validator": lambda d: d.get("kg") == 68.039 and d.get("lbs") == 150,
            "expect_increment": True
        },
        {
            "id": 4,
            "description": "Convert 0.1 lbs (standard decimal)",
            "path": "/convert?lbs=0.1",
            "expected_status": 200,
            "validator": lambda d: d.get("kg") == 0.045 and d.get("lbs") == 0.1,
            "expect_increment": True
        },
        {
            "id": 5,
            "description": "Missing lbs query parameter (expected 400)",
            "path": "/convert",
            "expected_status": 400,
            "validator": lambda d: "error" in d,
            "expect_increment": False
        },
        {
            "id": 6,
            "description": "Non-numeric lbs query parameter 'abc' (expected 400)",
            "path": "/convert?lbs=abc",
            "expected_status": 400,
            "validator": lambda d: "error" in d,
            "expect_increment": False
        },
        {
            "id": 7,
            "description": "Negative lbs query parameter '-5' (expected 422)",
            "path": "/convert?lbs=-5",
            "expected_status": 422,
            "validator": lambda d: "error" in d,
            "expect_increment": False
        }
    ]

    passed = 0
    failed = 0
    successful_conversions_in_run = 0

    for tc in test_cases:
        status, body = make_request(tc["path"])
        status_match = (status == tc["expected_status"])
        content_match = tc["validator"](body)

        if status_match and content_match:
            print(f"  {GREEN}[PASS]{RESET} Case {tc['id']}: {tc['description']}")
            print(f"         Request : GET {tc['path']}")
            print(f"         Response: Status {status} | Body: {json.dumps(body)}")
            passed += 1
            if tc["expect_increment"]:
                successful_conversions_in_run += 1
        else:
            print(f"  {RED}[FAIL]{RESET} Case {tc['id']}: {tc['description']}")
            print(f"         Request : GET {tc['path']}")
            print(f"         Expected: Status {tc['expected_status']}")
            print(f"         Actual  : Status {status} | Body: {json.dumps(body)}")
            failed += 1

    # Verify /stats persistence
    expected_final_count = initial_count + successful_conversions_in_run
    status, stats_body = make_request("/stats")
    actual_final_count = stats_body.get("conversions")

    print(f"\n{CYAN}------------------------------------------------------{RESET}")
    print(f"  Verifying Redis Counter Persistence (/stats)")
    print(f"{CYAN}------------------------------------------------------{RESET}")
    print(f"  Expected Redis counter: {expected_final_count} (+{successful_conversions_in_run} conversions in this run)")
    print(f"  Actual Redis counter  : {actual_final_count}")

    if status == 200 and actual_final_count == expected_final_count:
        print(f"  {GREEN}[PASS]{RESET} Case 8: /stats counter accurately tracks successful conversions only.")
        passed += 1
    else:
        print(f"  {RED}[FAIL]{RESET} Case 8: /stats counter mismatch or error.")
        failed += 1

    print(f"\n{CYAN}======================================================{RESET}")
    print(f"  Test Summary: {GREEN}{passed} Passed{RESET}, {RED if failed > 0 else GREEN}{failed} Failed{RESET}")
    print(f"{CYAN}======================================================\n{RESET}")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
