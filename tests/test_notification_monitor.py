#!/usr/bin/env python3
"""
test_notification_monitor.py

End-to-end test suite for BROS Completion Monitor & Notification Engine.
Covers:
TEST 1: success return notification
TEST 2: BLOCKED return notification
TEST 3: FAILED return notification
TEST 4: cross-agent isolation
TEST 5: duplicate suppression
TEST 6: notification failure does not rerun execution
TEST 7: monitor auto-close
"""

import datetime
import json
import os
import sys
from pathlib import Path

# Add current workspace to path
sys.path.insert(0, str(Path(__file__).parent))

import matt_antigravity_handoff_watcher as watcher
import matt_antigravity_notifier as notifier


def run_tests():
    print("=" * 70)
    print("RUNNING BROS COMPLETION MONITOR & NOTIFICATION TEST SUITE")
    print("=" * 70)

    supa_url, supa_key = watcher.load_supabase_credentials()
    if not supa_url or not supa_key:
        print("[FAIL] Missing Supabase credentials")
        sys.exit(1)

    monitor = notifier.AntigravityCompletionMonitor(supa_url, supa_key)
    results = {}

    test_prefix = f"TEST-NOTIF-SYNTHETIC-{int(datetime.datetime.now().timestamp())}"

    def create_synthetic_dispatch(hid: str, from_agent: str, from_inst: str, to_agent: str, ret_agent: str, ret_inst: str, status: str = "IN_PROGRESS"):
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        row = {
            "handoff_id": hid,
            "from_agent": from_agent,
            "from_agent_instance": from_inst,
            "to_agent": to_agent,
            "owner": "d-mac",
            "return_to_agent": ret_agent,
            "return_agent_instance": ret_inst,
            "return_channel": "SUPABASE+GITHUB",
            "status": status,
            "handoff_markdown": f"Synthetic test handoff {hid}",
            "created_at": now_iso,
            "claimed_at": now_iso,
            "claimed_by": "ANTIGRAVITY",
        }
        code, res, err = watcher.supabase_request(supa_url, supa_key, "agent_handoff_dispatch", method="POST", body=row)
        if code not in (200, 201):
            raise RuntimeError(f"Failed to create synthetic dispatch {hid}: {err}")
        return hid

    def cleanup_synthetic_dispatch(hid: str):
        # Cascades to agent_handoff_notifications and agent_handoff_returns
        watcher.supabase_request(supa_url, supa_key, "agent_handoff_dispatch", method="DELETE", params={"handoff_id": f"eq.{hid}"})

    # -------------------------------------------------------------
    # TEST 1: SUCCESS RETURN NOTIFICATION
    # -------------------------------------------------------------
    print("\n--- TEST 1: SUCCESS RETURN NOTIFICATION ---")
    hid_1 = f"{test_prefix}-001"
    try:
        create_synthetic_dispatch(hid_1, "MATT-006", "MATT-006-BRIDGE-GOVERNANCE", "ANTIGRAVITY", "MATT-006", "MATT-006-BRIDGE-GOVERNANCE", "IN_PROGRESS")
        # 1. Register monitor
        reg_res = monitor.register_monitor(
            handoff_id=hid_1,
            from_agent="MATT-006",
            from_agent_instance="MATT-006-BRIDGE-GOVERNANCE",
            return_to_agent="MATT-006",
            return_agent_instance="MATT-006-BRIDGE-GOVERNANCE",
            project_folder="NAS",
            project_area="Matt Antigravity Bridge Setup",
            project_execution_id="proj_exec_synth_001",
        )
        print("Registration result:", reg_res.get("status"))

        # 2. Process terminal success return
        proc_res = monitor.process_terminal_return(
            handoff_id=hid_1,
            terminal_status="RETURNED_TO_MATT",
            return_commit="commit_synth_001",
            return_payload="RETURN_STATUS: RETURNED_TO_MATT\nAll tests passed successfully.",
            from_agent="MATT-006",
            from_agent_instance="MATT-006-BRIDGE-GOVERNANCE",
            return_to_agent="MATT-006",
            return_agent_instance="MATT-006-BRIDGE-GOVERNANCE",
            project_folder="NAS",
            project_area="Matt Antigravity Bridge Setup",
        )
        print("Process return result:", proc_res)

        # 3. Verify database state
        code, rows, err = watcher.supabase_request(supa_url, supa_key, "agent_handoff_notifications", params={"handoff_id": f"eq.{hid_1}"})
        row = rows[0] if (code == 200 and rows) else {}
        test1_pass = (
            proc_res.get("action") == "NOTIFICATION_DELIVERED"
            and proc_res.get("notification_status") == "SENT"
            and proc_res.get("monitor_status") == "MONITOR_CLOSED"
            and row.get("notification_status") == "SENT"
            and row.get("monitor_status") == "MONITOR_CLOSED"
            and row.get("terminal_status") == "RETURNED_TO_MATT"
        )
        results["TEST_1_SUCCESS_NOTIFICATION"] = "PASS" if test1_pass else f"FAIL ({proc_res})"
        print("TEST 1 OUTCOME:", results["TEST_1_SUCCESS_NOTIFICATION"])
    except Exception as e:
        results["TEST_1_SUCCESS_NOTIFICATION"] = f"FAIL ({e})"
        print("TEST 1 ERROR:", e)
    finally:
        cleanup_synthetic_dispatch(hid_1)

    # -------------------------------------------------------------
    # TEST 2: BLOCKED RETURN NOTIFICATION
    # -------------------------------------------------------------
    print("\n--- TEST 2: BLOCKED RETURN NOTIFICATION ---")
    hid_2 = f"{test_prefix}-002"
    try:
        create_synthetic_dispatch(hid_2, "MATT-006", "MATT-006-BRIDGE-GOVERNANCE", "ANTIGRAVITY", "MATT-006", "MATT-006-BRIDGE-GOVERNANCE", "IN_PROGRESS")
        monitor.register_monitor(hid_2, "MATT-006", "MATT-006-BRIDGE-GOVERNANCE", "MATT-006", "MATT-006-BRIDGE-GOVERNANCE")

        proc_res = monitor.process_terminal_return(
            handoff_id=hid_2,
            terminal_status="BLOCKED",
            return_commit="commit_synth_002",
            return_payload="BLOCKERS: Execution pre-flight gate failed.\nRETURN_STATUS: BLOCKED",
            from_agent="MATT-006",
            from_agent_instance="MATT-006-BRIDGE-GOVERNANCE",
            return_to_agent="MATT-006",
            return_agent_instance="MATT-006-BRIDGE-GOVERNANCE",
            reason="Execution pre-flight gate failed.",
        )
        print("Process return result:", proc_res)

        code, rows, err = watcher.supabase_request(supa_url, supa_key, "agent_handoff_notifications", params={"handoff_id": f"eq.{hid_2}"})
        row = rows[0] if (code == 200 and rows) else {}
        test2_pass = (
            proc_res.get("action") == "NOTIFICATION_DELIVERED"
            and proc_res.get("terminal_status") == "BLOCKED"
            and row.get("terminal_status") == "BLOCKED"
            and row.get("notification_status") == "SENT"
            and row.get("monitor_status") == "MONITOR_CLOSED"
        )
        results["TEST_2_BLOCKED_NOTIFICATION"] = "PASS" if test2_pass else f"FAIL ({proc_res})"
        print("TEST 2 OUTCOME:", results["TEST_2_BLOCKED_NOTIFICATION"])
    except Exception as e:
        results["TEST_2_BLOCKED_NOTIFICATION"] = f"FAIL ({e})"
        print("TEST 2 ERROR:", e)
    finally:
        cleanup_synthetic_dispatch(hid_2)

    # -------------------------------------------------------------
    # TEST 3: FAILED RETURN NOTIFICATION
    # -------------------------------------------------------------
    print("\n--- TEST 3: FAILED RETURN NOTIFICATION ---")
    hid_3 = f"{test_prefix}-003"
    try:
        create_synthetic_dispatch(hid_3, "MATT-006", "MATT-006-BRIDGE-GOVERNANCE", "ANTIGRAVITY", "MATT-006", "MATT-006-BRIDGE-GOVERNANCE", "IN_PROGRESS")
        monitor.register_monitor(hid_3, "MATT-006", "MATT-006-BRIDGE-GOVERNANCE", "MATT-006", "MATT-006-BRIDGE-GOVERNANCE")

        proc_res = monitor.process_terminal_return(
            handoff_id=hid_3,
            terminal_status="PROJECT_DISPATCH_FAILED",
            return_commit="commit_synth_003",
            from_agent="MATT-006",
            from_agent_instance="MATT-006-BRIDGE-GOVERNANCE",
            return_to_agent="MATT-006",
            return_agent_instance="MATT-006-BRIDGE-GOVERNANCE",
            reason="Process spawned non-zero exit code 1",
        )
        print("Process return result:", proc_res)

        code, rows, err = watcher.supabase_request(supa_url, supa_key, "agent_handoff_notifications", params={"handoff_id": f"eq.{hid_3}"})
        row = rows[0] if (code == 200 and rows) else {}
        test3_pass = (
            proc_res.get("action") == "NOTIFICATION_DELIVERED"
            and proc_res.get("terminal_status") == "PROJECT_DISPATCH_FAILED"
            and row.get("notification_status") == "SENT"
            and row.get("monitor_status") == "MONITOR_CLOSED"
        )
        results["TEST_3_FAILED_NOTIFICATION"] = "PASS" if test3_pass else f"FAIL ({proc_res})"
        print("TEST 3 OUTCOME:", results["TEST_3_FAILED_NOTIFICATION"])
    except Exception as e:
        results["TEST_3_FAILED_NOTIFICATION"] = f"FAIL ({e})"
        print("TEST 3 ERROR:", e)
    finally:
        cleanup_synthetic_dispatch(hid_3)

    # -------------------------------------------------------------
    # TEST 4: CROSS-AGENT ISOLATION
    # -------------------------------------------------------------
    print("\n--- TEST 4: CROSS-AGENT ISOLATION ---")
    hid_4 = f"{test_prefix}-004"
    try:
        # Dispatched by ALPHA, but attempted return to BETA
        create_synthetic_dispatch(hid_4, "TEST-GPT-ALPHA", "ALPHA-INSTANCE-01", "ANTIGRAVITY", "TEST-GPT-ALPHA", "ALPHA-INSTANCE-01", "IN_PROGRESS")
        monitor.register_monitor(hid_4, "TEST-GPT-ALPHA", "ALPHA-INSTANCE-01", "TEST-GPT-ALPHA", "ALPHA-INSTANCE-01")

        # Rogue attempt to deliver return to BETA
        proc_res = monitor.process_terminal_return(
            handoff_id=hid_4,
            terminal_status="RETURNED_TO_AGENT",
            return_commit="commit_synth_004",
            from_agent="TEST-GPT-ALPHA",
            from_agent_instance="ALPHA-INSTANCE-01",
            return_to_agent="TEST-GPT-BETA",
            return_agent_instance="BETA-INSTANCE-01",
        )
        print("Cross-agent attempt result:", proc_res)

        test4_pass = (
            proc_res.get("action") == "DENIED_CROSS_AGENT"
            and "CROSS-AGENT VIOLATION" in proc_res.get("error", "")
        )
        results["TEST_4_CROSS_AGENT_ISOLATION"] = "PASS" if test4_pass else f"FAIL ({proc_res})"
        print("TEST 4 OUTCOME:", results["TEST_4_CROSS_AGENT_ISOLATION"])
    except Exception as e:
        results["TEST_4_CROSS_AGENT_ISOLATION"] = f"FAIL ({e})"
        print("TEST 4 ERROR:", e)
    finally:
        cleanup_synthetic_dispatch(hid_4)

    # -------------------------------------------------------------
    # TEST 5: DUPLICATE SUPPRESSION
    # -------------------------------------------------------------
    print("\n--- TEST 5: DUPLICATE SUPPRESSION ---")
    hid_5 = f"{test_prefix}-005"
    try:
        create_synthetic_dispatch(hid_5, "MATT-006", "MATT-006-BRIDGE-GOVERNANCE", "ANTIGRAVITY", "MATT-006", "MATT-006-BRIDGE-GOVERNANCE", "IN_PROGRESS")
        monitor.register_monitor(hid_5, "MATT-006", "MATT-006-BRIDGE-GOVERNANCE", "MATT-006", "MATT-006-BRIDGE-GOVERNANCE")

        # First call: delivered
        first_res = monitor.process_terminal_return(
            handoff_id=hid_5,
            terminal_status="RETURNED_TO_MATT",
            return_commit="commit_synth_005",
            from_agent="MATT-006",
            from_agent_instance="MATT-006-BRIDGE-GOVERNANCE",
            return_to_agent="MATT-006",
            return_agent_instance="MATT-006-BRIDGE-GOVERNANCE",
        )
        print("First delivery:", first_res.get("action"))

        # Second call on repeated polling: MUST BE SUPPRESSED
        second_res = monitor.process_terminal_return(
            handoff_id=hid_5,
            terminal_status="RETURNED_TO_MATT",
            return_commit="commit_synth_005",
            from_agent="MATT-006",
            from_agent_instance="MATT-006-BRIDGE-GOVERNANCE",
            return_to_agent="MATT-006",
            return_agent_instance="MATT-006-BRIDGE-GOVERNANCE",
        )
        print("Second delivery:", second_res.get("action"))

        test5_pass = (
            first_res.get("action") == "NOTIFICATION_DELIVERED"
            and second_res.get("action") == "SUPPRESSED_DUPLICATE"
        )
        results["TEST_5_DUPLICATE_SUPPRESSION"] = "PASS" if test5_pass else f"FAIL (1st={first_res}, 2nd={second_res})"
        print("TEST 5 OUTCOME:", results["TEST_5_DUPLICATE_SUPPRESSION"])
    except Exception as e:
        results["TEST_5_DUPLICATE_SUPPRESSION"] = f"FAIL ({e})"
        print("TEST 5 ERROR:", e)
    finally:
        cleanup_synthetic_dispatch(hid_5)

    # -------------------------------------------------------------
    # TEST 6: NOTIFICATION FAILURE DOES NOT RERUN EXECUTION
    # -------------------------------------------------------------
    print("\n--- TEST 6: NOTIFICATION FAILURE DOES NOT RERUN EXECUTION ---")
    hid_6 = f"{test_prefix}-006"
    try:
        create_synthetic_dispatch(hid_6, "MATT-006", "MATT-006-BRIDGE-GOVERNANCE", "ANTIGRAVITY", "MATT-006", "MATT-006-BRIDGE-GOVERNANCE", "IN_PROGRESS")
        monitor.register_monitor(hid_6, "MATT-006", "MATT-006-BRIDGE-GOVERNANCE", "MATT-006", "MATT-006-BRIDGE-GOVERNANCE")

        # Simulate delivery failure
        proc_res = monitor.process_terminal_return(
            handoff_id=hid_6,
            terminal_status="RETURNED_TO_MATT",
            return_commit="commit_synth_006",
            from_agent="MATT-006",
            from_agent_instance="MATT-006-BRIDGE-GOVERNANCE",
            return_to_agent="MATT-006",
            return_agent_instance="MATT-006-BRIDGE-GOVERNANCE",
            force_fail_delivery=True,
        )
        print("Failed delivery result:", proc_res)

        # Check dispatch status in DB - MUST REMAIN IN_PROGRESS (not reset to AUTHORIZED)
        code, rows, err = watcher.supabase_request(supa_url, supa_key, "agent_handoff_dispatch", params={"handoff_id": f"eq.{hid_6}"})
        disp_row = rows[0] if (code == 200 and rows) else {}

        # Check notification status in DB - MUST BE NOTIFICATION_FAILED
        n_code, n_rows, n_err = watcher.supabase_request(supa_url, supa_key, "agent_handoff_notifications", params={"handoff_id": f"eq.{hid_6}"})
        notif_row = n_rows[0] if (n_code == 200 and n_rows) else {}

        test6_pass = (
            proc_res.get("action") == "NOTIFICATION_FAILED"
            and proc_res.get("execution_rerun") is False
            and notif_row.get("notification_status") == "FAILED"
            and notif_row.get("monitor_status") == "NOTIFICATION_FAILED"
            and disp_row.get("status") != "AUTHORIZED"
        )
        results["TEST_6_FAILURE_HANDLING_NO_RERUN"] = "PASS" if test6_pass else f"FAIL (proc={proc_res}, notif={notif_row})"
        print("TEST 6 OUTCOME:", results["TEST_6_FAILURE_HANDLING_NO_RERUN"])
    except Exception as e:
        results["TEST_6_FAILURE_HANDLING_NO_RERUN"] = f"FAIL ({e})"
        print("TEST 6 ERROR:", e)
    finally:
        cleanup_synthetic_dispatch(hid_6)

    # -------------------------------------------------------------
    # TEST 7: MONITOR AUTO-CLOSE
    # -------------------------------------------------------------
    print("\n--- TEST 7: MONITOR AUTO-CLOSE ---")
    hid_7 = f"{test_prefix}-007"
    try:
        create_synthetic_dispatch(hid_7, "MATT-006", "MATT-006-BRIDGE-GOVERNANCE", "ANTIGRAVITY", "MATT-006", "MATT-006-BRIDGE-GOVERNANCE", "IN_PROGRESS")
        monitor.register_monitor(hid_7, "MATT-006", "MATT-006-BRIDGE-GOVERNANCE", "MATT-006", "MATT-006-BRIDGE-GOVERNANCE")

        proc_res = monitor.process_terminal_return(
            handoff_id=hid_7,
            terminal_status="RETURNED_TO_MATT",
            return_commit="commit_synth_007",
            from_agent="MATT-006",
            from_agent_instance="MATT-006-BRIDGE-GOVERNANCE",
            return_to_agent="MATT-006",
            return_agent_instance="MATT-006-BRIDGE-GOVERNANCE",
        )
        
        # Verify monitor status is CLOSED
        code, rows, err = watcher.supabase_request(supa_url, supa_key, "agent_handoff_notifications", params={"handoff_id": f"eq.{hid_7}"})
        notif_row = rows[0] if (code == 200 and rows) else {}

        test7_pass = (
            proc_res.get("monitor_status") == "MONITOR_CLOSED"
            and notif_row.get("monitor_status") == "MONITOR_CLOSED"
            and notif_row.get("notification_status") == "SENT"
        )
        results["TEST_7_MONITOR_AUTO_CLOSE"] = "PASS" if test7_pass else f"FAIL (row={notif_row})"
        print("TEST 7 OUTCOME:", results["TEST_7_MONITOR_AUTO_CLOSE"])
    except Exception as e:
        results["TEST_7_MONITOR_AUTO_CLOSE"] = f"FAIL ({e})"
        print("TEST 7 ERROR:", e)
    finally:
        cleanup_synthetic_dispatch(hid_7)

    print("\n" + "=" * 70)
    print("FINAL TEST SUMMARY:")
    all_pass = True
    for test_name, status in results.items():
        print(f"  {test_name}: {status}")
        if status != "PASS":
            all_pass = False
    print("=" * 70)
    print("ALL TESTS PASSED:", all_pass)
    return all_pass


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
