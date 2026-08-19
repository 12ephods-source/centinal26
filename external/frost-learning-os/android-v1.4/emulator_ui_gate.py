#!/usr/bin/env python3
import json
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

OUT = Path("emulator-evidence")
OUT.mkdir(exist_ok=True)


def adb(*args, check=True, text=True):
    p = subprocess.run(["adb", *args], check=False, capture_output=True, text=text)
    if check and p.returncode:
        raise RuntimeError(f"adb {' '.join(args)} failed: {p.stderr if text else p.returncode}")
    return p.stdout if text else p.stdout


def wait_for_device():
    adb("wait-for-device")
    for _ in range(120):
        if adb("shell", "getprop", "sys.boot_completed", check=False).strip() == "1":
            return
        time.sleep(1)
    raise RuntimeError("emulator boot did not complete")


def screenshot(name):
    p = subprocess.run(["adb", "exec-out", "screencap", "-p"], check=True, capture_output=True)
    (OUT / f"{name}.png").write_bytes(p.stdout)


def dump_ui(name):
    adb("shell", "uiautomator", "dump", "/sdcard/window.xml")
    xml = adb("exec-out", "cat", "/sdcard/window.xml")
    (OUT / f"{name}.xml").write_text(xml, encoding="utf-8")
    return ET.fromstring(xml)


def all_nodes(root):
    return list(root.iter("node"))


def node_text(n):
    return " ".join(filter(None, [n.attrib.get("text", ""), n.attrib.get("content-desc", "")]))


def find_text(root, needle):
    needle = needle.lower()
    for n in all_nodes(root):
        if needle in node_text(n).lower():
            return n
    raise AssertionError(f"UI text not found: {needle}")


def bounds_center(n):
    m = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", n.attrib.get("bounds", ""))
    if not m:
        raise AssertionError(f"bad bounds: {n.attrib.get('bounds')}")
    x1, y1, x2, y2 = map(int, m.groups())
    return (x1 + x2) // 2, (y1 + y2) // 2


def click_text(needle, name):
    root = dump_ui(name)
    n = find_text(root, needle)
    x, y = bounds_center(n)
    adb("shell", "input", "tap", str(x), str(y))
    time.sleep(1)


def first_edit(root):
    for n in all_nodes(root):
        if "EditText" in n.attrib.get("class", ""):
            return n
    raise AssertionError("answer EditText not found")


def answer(value, label):
    root = dump_ui(f"{label}-before-input")
    edit = first_edit(root)
    x, y = bounds_center(edit)
    adb("shell", "input", "tap", str(x), str(y))
    adb("shell", "input", "text", value)
    time.sleep(.5)
    click_text("Check reasoning", f"{label}-submit")
    root = dump_ui(f"{label}-result")
    find_text(root, "Correct")
    screenshot(f"{label}-correct")


def resumed_activity():
    return adb("shell", "dumpsys", "activity", "activities", check=False)


def main():
    result = {
        "schema": "FLOS_ANDROID_EMULATOR_UI_GATE_v1",
        "classification": "HOST_EMULATED_ANDROID_EVIDENCE",
        "physical_device": False,
        "checks": [],
    }
    try:
        wait_for_device()
        adb("install", "-r", "app/build/outputs/apk/debug/app-debug.apk")
        result["checks"].append("APK_INSTALL_PASS")

        pkg = adb("shell", "dumpsys", "package", "com.robertfrost.learningos")
        assert "versionName=1.4.1" in pkg
        assert "versionCode=15" in pkg
        assert "android.permission.INTERNET" not in pkg
        result["checks"].append("PACKAGE_METADATA_PASS")
        result["checks"].append("NO_INTERNET_PERMISSION_PASS")

        adb("shell", "am", "start", "-W", "-n", "com.robertfrost.learningos/.MainActivity")
        time.sleep(3)
        root = dump_ui("01-launch")
        find_text(root, "Frost Learning OS")
        find_text(root, "Student")
        find_text(root, "Teacher")
        find_text(root, "Evidence")
        find_text(root, "Simplify: 3(x + 4)")
        screenshot("01-launch")
        result["checks"].append("LAUNCH_UI_PASS")

        answer("3x+12", "02-d1")
        click_text("Next adaptive question", "03-next-d2")
        root = dump_ui("03-d2")
        find_text(root, "Simplify: 5(2y - 3)")
        answer("10y-15", "03-d2")
        result["checks"].append("TWO_DISTINCT_CORRECT_ITEMS_PASS")

        click_text("Next adaptive question", "04-next-transfer")
        root = dump_ui("04-transfer")
        find_text(root, "Transfer")
        screenshot("04-transfer")
        result["checks"].append("TRANSFER_AFTER_DISTINCT_EVIDENCE_PASS")

        click_text("Teacher", "05-teacher-click")
        root = dump_ui("05-teacher")
        find_text(root, "Teacher intervention queue")
        find_text(root, "Distributive Property")
        find_text(root, "READY")
        screenshot("05-teacher")
        result["checks"].append("TEACHER_DASHBOARD_PASS")

        click_text("Evidence", "06-evidence-click")
        root = dump_ui("06-evidence")
        find_text(root, "Evidence ledger")
        find_text(root, "VERIFIED")
        find_text(root, "ANSWER_SUBMITTED")
        screenshot("06-evidence")
        result["checks"].append("EVIDENCE_LEDGER_PASS")

        click_text("Export JSON evidence", "07-export-click")
        time.sleep(2)
        acts = resumed_activity()
        (OUT / "07-export-activity.txt").write_text(acts, encoding="utf-8")
        if "documentsui" not in acts.lower():
            raise AssertionError("native DocumentsUI was not resumed by export")
        screenshot("07-native-export-picker")
        result["checks"].append("NATIVE_EXPORT_PICKER_PASS")
        adb("shell", "input", "keyevent", "4")
        time.sleep(1)

        click_text("Reset local data", "08-reset-click")
        root = dump_ui("08-reset-confirm")
        find_text(root, "Reset local learner evidence?")
        screenshot("08-reset-confirm")
        result["checks"].append("RESET_CONFIRMATION_PASS")
        try:
            click_text("Cancel", "08-reset-cancel")
        except Exception:
            adb("shell", "input", "keyevent", "4")

        logcat = adb("logcat", "-d", check=False)
        (OUT / "logcat.txt").write_text(logcat, encoding="utf-8")
        result["decision"] = "PASS_HOST_EMULATED_UI_FLOW"
    except Exception as exc:
        result["decision"] = "FAIL"
        result["error"] = str(exc)
        try:
            screenshot("failure")
            dump_ui("failure")
            (OUT / "logcat.txt").write_text(adb("logcat", "-d", check=False), encoding="utf-8")
        except Exception:
            pass
        raise
    finally:
        (OUT / "EMULATOR_GATE_RESULT.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
