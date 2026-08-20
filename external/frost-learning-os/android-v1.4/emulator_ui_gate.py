import json
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

OUT = Path("emulator-evidence")
OUT.mkdir(exist_ok=True)
UI_DUMP_PATH = "/data/local/tmp/flos-window.xml"


def adb(*args, check=True):
    process = subprocess.run(
        ["adb", *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if check and process.returncode:
        detail = process.stderr.strip() or process.stdout.strip()
        raise RuntimeError(f"adb {' '.join(args)} failed: {detail}")
    return process.stdout


def write_diag(name, *args):
    output = adb(*args, check=False)
    (OUT / name).write_text(output, encoding="utf-8")
    return output


def wait_for_device():
    adb("wait-for-device")
    for _ in range(120):
        if adb("shell", "getprop", "sys.boot_completed", check=False).strip() == "1":
            return
        time.sleep(1)
    raise RuntimeError("emulator boot did not complete")


def wake_and_unlock():
    adb("shell", "input", "keyevent", "KEYCODE_WAKEUP", check=False)
    adb("shell", "wm", "dismiss-keyguard", check=False)
    adb("shell", "input", "keyevent", "82", check=False)
    time.sleep(1)


def screenshot(name):
    process = subprocess.run(
        ["adb", "exec-out", "screencap", "-p"],
        check=True,
        capture_output=True,
        timeout=30,
    )
    (OUT / f"{name}.png").write_bytes(process.stdout)


def dump_ui(name):
    last_error = None
    for attempt in range(3):
        try:
            adb("shell", "rm", "-f", UI_DUMP_PATH, check=False)
            adb("shell", "uiautomator", "dump", "--compressed", UI_DUMP_PATH)
            xml = adb("exec-out", "cat", UI_DUMP_PATH)
            if not xml.lstrip().startswith("<?xml"):
                raise RuntimeError(f"uiautomator returned non-XML output: {xml[:160]!r}")
            (OUT / f"{name}.xml").write_text(xml, encoding="utf-8")
            return ET.fromstring(xml)
        except (RuntimeError, subprocess.SubprocessError, ET.ParseError) as error:
            last_error = error
            time.sleep(attempt + 1)
    raise RuntimeError(f"uiautomator dump failed after retries: {last_error}")


def all_nodes(root):
    return list(root.iter("node"))


def node_text(node):
    return " ".join(
        filter(None, [node.attrib.get("text", ""), node.attrib.get("content-desc", "")])
    )


def find_text(root, needle):
    normalized = needle.lower()
    for node in all_nodes(root):
        if normalized in node_text(node).lower():
            return node
    raise AssertionError(f"UI text not found: {needle}")


def bounds_center(node):
    match = re.fullmatch(
        r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]",
        node.attrib.get("bounds", ""),
    )
    if not match:
        raise AssertionError(f"bad bounds: {node.attrib.get('bounds')}")
    x1, y1, x2, y2 = map(int, match.groups())
    return (x1 + x2) // 2, (y1 + y2) // 2


def click_text(needle, name):
    root = dump_ui(name)
    node = find_text(root, needle)
    x, y = bounds_center(node)
    adb("shell", "input", "tap", str(x), str(y))
    time.sleep(1)


def first_edit(root):
    for node in all_nodes(root):
        if "EditText" in node.attrib.get("class", ""):
            return node
    raise AssertionError("answer EditText not found")


def answer(value, label):
    root = dump_ui(f"{label}-before-input")
    edit = first_edit(root)
    x, y = bounds_center(edit)
    adb("shell", "input", "tap", str(x), str(y))
    adb("shell", "input", "text", value)
    time.sleep(0.5)
    click_text("Check reasoning", f"{label}-submit")
    root = dump_ui(f"{label}-result")
    find_text(root, "Correct")
    screenshot(f"{label}-correct")


def resumed_activity():
    return adb("shell", "dumpsys", "activity", "activities", check=False)


def capture_runtime_context(prefix):
    screenshot(prefix)
    write_diag(f"{prefix}-activity.txt", "shell", "dumpsys", "activity", "activities")
    write_diag(f"{prefix}-window.txt", "shell", "dumpsys", "window", "windows")
    write_diag(f"{prefix}-webview.txt", "shell", "dumpsys", "webviewupdate")
    write_diag(f"{prefix}-package.txt", "shell", "dumpsys", "package", "com.robertfrost.learningos")
    write_diag(f"{prefix}-logcat.txt", "logcat", "-d")


def preserve_failure_context():
    errors = []
    for action in (
        lambda: capture_runtime_context("failure"),
        lambda: dump_ui("failure"),
    ):
        try:
            action()
        except (
            AssertionError,
            RuntimeError,
            subprocess.SubprocessError,
            subprocess.TimeoutExpired,
            ET.ParseError,
            OSError,
        ) as capture_error:
            errors.append(str(capture_error))
    if errors:
        (OUT / "failure-capture-errors.txt").write_text(
            "\n".join(errors) + "\n",
            encoding="utf-8",
        )


def main():
    result = {
        "schema": "FLOS_ANDROID_EMULATOR_UI_GATE_v1",
        "classification": "HOST_EMULATED_ANDROID_EVIDENCE",
        "physical_device": False,
        "checks": [],
    }
    try:
        wait_for_device()
        wake_and_unlock()
        adb("install", "-r", "app/build/outputs/apk/debug/app-debug.apk")
        result["checks"].append("APK_INSTALL_PASS")

        pkg = adb("shell", "dumpsys", "package", "com.robertfrost.learningos")
        assert "versionName=1.4.1" in pkg
        assert "versionCode=15" in pkg
        assert "android.permission.INTERNET" not in pkg
        result["checks"].append("PACKAGE_METADATA_PASS")
        result["checks"].append("NO_INTERNET_PERMISSION_PASS")

        launch = adb(
            "shell",
            "am",
            "start",
            "-W",
            "-n",
            "com.robertfrost.learningos/.MainActivity",
        )
        (OUT / "01-launch-command.txt").write_text(launch, encoding="utf-8")
        time.sleep(4)
        capture_runtime_context("01-pre-ui-dump")
        activity = resumed_activity().lower()
        if "com.robertfrost.learningos" not in activity:
            raise AssertionError("Frost Learning OS is not present in activity state after launch")

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
        activities = resumed_activity()
        (OUT / "07-export-activity.txt").write_text(activities, encoding="utf-8")
        if "documentsui" not in activities.lower():
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
        except (AssertionError, RuntimeError):
            adb("shell", "input", "keyevent", "4")

        write_diag("final-logcat.txt", "logcat", "-d")
        result["decision"] = "PASS_HOST_EMULATED_UI_FLOW"
    except (
        AssertionError,
        RuntimeError,
        subprocess.SubprocessError,
        subprocess.TimeoutExpired,
        ET.ParseError,
        OSError,
    ) as exc:
        result["decision"] = "FAIL"
        result["error"] = str(exc)
        preserve_failure_context()
        raise
    finally:
        (OUT / "EMULATOR_GATE_RESULT.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
