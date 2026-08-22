from pathlib import Path
import runpy

MODULE = runpy.run_path(Path(__file__).resolve().parents[1] / "termux" / "centinal26_app_inventory.py")
parse_package_lines = MODULE["parse_package_lines"]


def test_parser_deduplicates_and_sorts_packages():
    text = "\n".join([
        "package:/data/app/b/base.apk=com.example.beta installer=com.android.vending uid:10234 versionCode:12",
        "package:/data/app/a/base.apk=com.example.alpha installer=com.android.vending uid:10233 versionCode:7",
        "package:/data/app/b/base.apk=com.example.beta installer=com.android.vending uid:10234 versionCode:12",
    ])
    rows = parse_package_lines(text)
    assert [row["package"] for row in rows] == ["com.example.alpha", "com.example.beta"]
    assert rows[0]["version_code"] == 7
    assert rows[1]["uid"] == 10234


def test_parser_supports_minimal_pm_output():
    rows = parse_package_lines("package:/system/app/Foo/Foo.apk=com.android.foo\n")
    assert rows == [{
        "package": "com.android.foo",
        "source_path": "/system/app/Foo/Foo.apk",
        "installer": None,
        "uid": None,
        "version_code": None,
    }]


def test_non_package_lines_are_ignored():
    assert parse_package_lines("warning: unavailable\n") == []
