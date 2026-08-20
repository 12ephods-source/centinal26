import json
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

OUT = Path("emulator-evidence")
OUT.mkdir(exist_ok=True)
PKG = "com.robertfrost.learningos"
DEBUG_ACTION = f"{PKG}.DEBUG_TEST"
DEBUG_RESULT = "files/flos_debug_result.txt"
UI_DUMP_PATH = "/data/local/tmp/flos-window.xml"
DISTRIBUTION_TRANSFER = "Transfer: simplify 4(3a + 2) - a"
QUESTION_ANSWERS = {
    "Simplify: 3(x + 4)": "3x+12",
    "Simplify: 5(2y - 3)": "10y-15",
    "A 4 kg sample costs $18. What is the cost per kg?": "4.5",
    "At 12 km in 3 h, what is the average speed in km/h?": "4",
    "Solve: 3(x + 4) = 21": "3",
}
_debug_counter = 0


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


def dump_native_ui(name):
    adb("shell", "rm", "-f", UI_DUMP_PATH, check=False)
    adb("shell", "uiautomator", "dump", "--compressed", UI_DUMP_PATH)
    xml = adb("exec-out", "cat", UI_DUMP_PATH)
    if not xml.lstrip().startswith("<?xml"):
        raise RuntimeError(f"uiautomator returned non-XML output: {xml[:160]!r}")
    (OUT / f"{name}.xml").write_text(xml, encoding="utf-8")
    return ET.fromstring(xml)


def native_text(root):
    parts = []
    for node in root.iter("node"):
        parts.extend(
            filter(
                None,
                [node.attrib.get("text", ""), node.attrib.get("content-desc", "")],
            )
        )
    return " ".join(parts)


def decode_debug_result(raw):
    value = raw.strip()
    try:
        value = json.loads(value)
    except json.JSONDecodeError:
        return value
    if isinstance(value, str) and value.lstrip().startswith(("{", "[")):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def debug_fire(op, value=None):
    adb("shell", "run-as", PKG, "rm", "-f", DEBUG_RESULT, check=False)
    args = ["shell", "am", "broadcast", "-a", DEBUG_ACTION, "-p", PKG, "--es", "op", op]
    if value is not None:
        args.extend(["--es", "value", value])
    adb(*args)


def debug_call(op, value=None):
    global _debug_counter
    _debug_counter += 1
    debug_fire(op, value)
    raw = ""
    for _ in range(80):
        raw = adb("shell", "run-as", PKG, "cat", DEBUG_RESULT, check=False).strip()
        if raw and raw != "PENDING":
            break
        time.sleep(0.1)
    if not raw or raw == "PENDING":
        raise RuntimeError(f"debug operation did not complete: {op}")
    (OUT / f"debug-{_debug_counter:02d}-{op}.txt").write_text(raw + "\n", encoding="utf-8")
    return decode_debug_result(raw)


def answer(value, label):
    response = debug_call("answer", value)
    if not isinstance(response, dict) or "Correct" not in response.get("feedback", ""):
        raise AssertionError(f"answer was not accepted as correct for {label}: {response!r}")
    screenshot(f"{label}-correct")


def next_prompt(label):
    response = debug_call("next")
    if not isinstance(response, dict):
        raise TypeError(f"invalid next-question response for {label}: {response!r}")
    prompt = response.get("question", "")
    if not prompt:
        raise AssertionError(f"empty next-question prompt for {label}")
    screenshot(label)
    return prompt


def advance_until_second_distribution_item():
    target = "Simplify: 5(2y - 3)"
    for step in range(8):
        prompt = next_prompt(f"03-scheduled-{step}")
        if prompt == DISTRIBUTION_TRANSFER:
            raise AssertionError(
                "distribution transfer appeared before two distinct distribution items were correct"
            )
        if prompt == target:
            return
        if prompt not in QUESTION_ANSWERS:
            raise AssertionError(f"unexpected pre-transfer prompt: {prompt}")
        answer(QUESTION_ANSWERS[prompt], f"03-intermediate-{step}")
    raise AssertionError("scheduler did not surface the second distribution retrieval item")


def advance_until_distribution_transfer():
    for step in range(8):
        prompt = next_prompt(f"04-post-ready-{step}")
        if prompt == DISTRIBUTION_TRANSFER:
            return
        if prompt not in QUESTION_ANSWERS:
            raise AssertionError(f"unexpected post-readiness prompt: {prompt}")
        answer(QUESTION_ANSWERS[prompt], f"04-intermediate-{step}")
    raise AssertionError("scheduler did not surface distribution transfer after readiness")


def resumed_activity():
    return adb("shell", "dumpsys", "activity", "activities", check=False)


def capture_runtime_context(prefix):
    screenshot(prefix)
    write_diag(f"{prefix}-activity.txt", "shell", "dumpsys", "activity", "activities")
    write_diag(f"{prefix}-window.txt", "shell", "dumpsys", "window", "windows")
    write_diag(f"{prefix}-webview.txt", "shell", "dumpsys", "webviewupdate")
    write_diag(f"{prefix}-package.txt", "shell", "dumpsys", "package", PKG)
    write_diag(f"{prefix}-logcat.txt", "logcat", "-d")


def preserve_failure_context():
    errors = []
    for action in (
        lambda: capture_runtime_context("failure"),
        lambda: dump_native_ui("failure-native"),
        lambda: debug_call("snapshot"),
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
        "schema": "FLOS_ANDROID_EMULATOR_UI_GATE_v2",
        "classification": "HOST_EMULATED_ANDROID_EVIDENCE",
        "physical_device": False,
        "webview_driver": "DEBUG_ONLY_NATIVE_EVALUATE_JS",
        "checks": [],
    }
    try:
        wait_for_device()
        wake_and_unlock()
        adb("install", "-r", "app/build/outputs/apk/debug/app-debug.apk")
        result["checks"].append("APK_INSTALL_PASS")

        pkg = adb("shell", "dumpsys", "package", PKG)
        assert "versionName=1.4.1" in pkg
        assert "versionCode=15" in pkg
        assert "android.permission.INTERNET" not in pkg
        result["checks"].extend(["PACKAGE_METADATA_PASS", "NO_INTERNET_PERMISSION_PASS"])

        launch = adb("shell", "am", "start", "-W", "-n", f"{PKG}/.MainActivity")
        (OUT / "01-launch-command.txt").write_text(launch, encoding="utf-8")
        time.sleep(3)
        capture_runtime_context("01-launch")
        if PKG not in resumed_activity():
            raise AssertionError("Frost Learning OS is not present in activity state after launch")

        snapshot = debug_call("snapshot")
        if not isinstance(snapshot, dict):
            raise TypeError(f"invalid launch snapshot: {snapshot!r}")
        assert snapshot.get("title") == "Frost Learning OS"
        assert snapshot.get("question") == "Simplify: 3(x + 4)"
        assert snapshot.get("studentHidden") is False
        screenshot("01-webview-rendered")
        result["checks"].extend(["LAUNCH_UI_PASS", "WEBVIEW_DOM_BRIDGE_PASS"])

        answer("3x+12", "02-d1")
        advance_until_second_distribution_item()
        result["checks"].append("PREMATURE_TRANSFER_BLOCK_PASS")
        answer("10y-15", "03-d2")
        result["checks"].append("TWO_DISTINCT_CORRECT_ITEMS_PASS")

        advance_until_distribution_transfer()
        screenshot("04-transfer")
        result["checks"].append("TRANSFER_AFTER_DISTINCT_EVIDENCE_PASS")

        teacher = debug_call("tab", "teacher")
        if not isinstance(teacher, dict) or teacher.get("teacherHidden") is not False:
            raise AssertionError(f"teacher dashboard did not activate: {teacher!r}")
        if not teacher.get("teacherAction"):
            raise AssertionError("teacher intervention action is empty")
        screenshot("05-teacher")
        result["checks"].append("TEACHER_DASHBOARD_PASS")

        evidence = debug_call("tab", "evidence")
        if not isinstance(evidence, dict) or evidence.get("evidenceHidden") is not False:
            raise AssertionError(f"evidence dashboard did not activate: {evidence!r}")
        if "chain VERIFIED" not in evidence.get("evidenceCount", ""):
            raise AssertionError(f"evidence chain not verified in UI: {evidence!r}")
        screenshot("06-evidence")
        result["checks"].append("EVIDENCE_LEDGER_PASS")

        debug_fire("export")
        for _ in range(40):
            activities = resumed_activity()
            if "documentsui" in activities.lower():
                break
            time.sleep(0.1)
        else:
            raise AssertionError("native DocumentsUI was not resumed by export")
        (OUT / "07-export-activity.txt").write_text(activities, encoding="utf-8")
        screenshot("07-native-export-picker")
        result["checks"].append("NATIVE_EXPORT_PICKER_PASS")
        adb("shell", "input", "keyevent", "4")
        time.sleep(0.5)

        debug_fire("reset")
        time.sleep(0.7)
        native = dump_native_ui("08-reset-confirm")
        if "Reset local learner evidence?" not in native_text(native):
            raise AssertionError("native reset confirmation was not exposed")
        screenshot("08-reset-confirm")
        result["checks"].append("RESET_CONFIRMATION_PASS")
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
