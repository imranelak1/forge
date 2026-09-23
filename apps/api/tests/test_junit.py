"""No provider credentials, database, filesystem resolution or network are used."""

from pathlib import Path

import pytest

from forge.integrations import junit
from forge.integrations.junit import JUnitError, parse_junit

FIXTURES = Path(__file__).parent / "fixtures" / "junit"


def test_nested_suites_count_leaf_cases_once_and_preserve_parameterized_names() -> None:
    report = parse_junit((FIXTURES / "nested.xml").read_bytes())
    assert report.warnings == ()
    assert report.declared_total == 5
    assert report.counts == {"tests": 5, "passed": 2, "failed": 1, "error": 1, "skipped": 1}
    assert report.execution_count == 5
    assert [(suite.key, suite.parent_key, suite.path) for suite in report.suites] == [
        ("1", None, ("root",)),
        ("2", "1", ("root", "parameterized")),
    ]
    assert report.suites[0].counts == report.counts
    assert report.suites[1].counts["tests"] == 4
    assert report.cases[1].identity_key != report.cases[2].identity_key
    assert report.cases[1].duration_seconds == 0.125
    assert report.cases[0].duration_seconds == 0
    assert report.cases[4].duration_seconds is None
    assert "PRIVATE" not in repr(report) and "private-key" not in repr(report)


def test_surefire_retries_have_ordered_executions_and_only_one_final_leaf_outcome() -> None:
    report = parse_junit((FIXTURES / "surefire.xml").read_bytes())
    assert not report.warnings
    assert report.counts["tests"] == 3
    assert report.counts["passed"] == 2 and report.counts["failed"] == 1
    assert report.execution_count == 7
    assert [case.outcome for case in report.cases] == [
        "failed",
        "error",
        "passed",
        "failed",
        "failed",
        "failed",
        "passed",
    ]
    recovered = report.cases[:3]
    assert [case.retry_ordinal for case in recovered] == [0, 1, 2]
    assert [case.is_final for case in recovered] == [False, False, True]
    assert len({case.identity_key for case in recovered}) == 1
    assert [case.duration_seconds for case in recovered] == [None, None, 0.1]
    assert [case.duration_seconds for case in report.cases[3:6]] == [0.3, None, None]
    assert "LOG" not in repr(report)


def test_repeated_names_are_distinct_ambiguous_cases_not_implicit_retries() -> None:
    payload = b"""<testsuites><testsuite name="s"><testcase classname="C" name="same"/>
      <testcase classname="C" name="same"><failure/></testcase></testsuite>
      <testsuite name="s"><testcase classname="C" name="same"/></testsuite></testsuites>"""
    report = parse_junit(payload)
    assert report.counts["tests"] == 3
    assert report.warnings == ("ambiguous_duplicate_identity",)
    assert len({case.identity_key for case in report.cases}) == 3
    assert all(case.identity_quality == "ambiguous" for case in report.cases)
    assert all(case.is_final and case.retry_ordinal == 0 for case in report.cases)
    assert parse_junit(payload) == report


def test_explicit_parameter_values_framework_and_fallback_path_are_identity_dimensions() -> None:
    payload = b"""<testsuite name="s"><testcase classname="C" name="same" parameters="a"/>
      <testcase classname="C" name="same" parameters="b"/></testsuite>"""
    report = parse_junit(payload)
    assert report.cases[0].identity_key != report.cases[1].identity_key
    assert (
        report.cases[0].identity_key
        != parse_junit(payload, framework="other").cases[0].identity_key
    )
    # Class/file identities do not change when a report wraps the same test in another suite.
    assert (
        report.cases[0].identity_key
        == parse_junit(payload.replace(b'name="s"', b'name="t"')).cases[0].identity_key
    )
    fallback = parse_junit(b'<testsuite name="s"><testcase name="same"/></testsuite>')
    other = parse_junit(b'<testsuite name="t"><testcase name="same"/></testsuite>')
    assert fallback.cases[0].identity_quality == "fallback"
    assert fallback.cases[0].identity_key != other.cases[0].identity_key
    assert fallback.warnings == ("fallback_identity",)


@pytest.mark.parametrize(
    "duration", ["-1", "nan", "NaN", "inf", "1e10000", "31536001", "bad", "9" * 100]
)
def test_invalid_duration_is_missing_with_warning_not_zero(duration: str) -> None:
    report = parse_junit(
        f'<testsuite><testcase classname="C" name="n" time="{duration}"/></testsuite>'.encode()
    )
    assert report.cases[0].duration_seconds is None
    assert report.warnings == ("invalid_duration",)


def test_count_mismatch_malformed_counts_and_unsupported_retry_metadata_are_quality_evidence() -> (
    None
):
    report = parse_junit(b"""<testsuites tests="8">
      <testsuite tests="-1" failures="invalid" errors="1">
      <testcase classname="C" name="n" retry="1"/><testcase classname="C" name="m" retry="2"/>
      </testsuite></testsuites>""")
    assert report.counts["tests"] == 2
    assert report.declared_total == 8
    assert set(report.warnings) == {
        "declared_count_mismatch",
        "invalid_declared_count",
        "unsupported_retry_metadata",
    }
    assert all(
        case.retry_ordinal == 0 and case.identity_quality == "ambiguous" for case in report.cases
    )


def test_contradictory_outcomes_or_retry_dialects_do_not_invent_recovery() -> None:
    report = parse_junit(b"""<testsuite><testcase name="mixed"><skipped/><failure/></testcase>
      <testcase name="retry"><failure/><flakyFailure/></testcase></testsuite>""")
    assert all(case.outcome == "failed" for case in report.cases)
    assert all(case.is_final and case.identity_quality == "ambiguous" for case in report.cases)
    assert set(report.warnings) == {"multiple_outcome_elements", "unsupported_retry_dialect"}


def test_failure_messages_are_bounded_and_output_is_never_returned() -> None:
    report = parse_junit(
        (
            f'<testsuite><testcase classname="C" name="n"><failure message="{"x" * 3000}">'
            f"{'body' * 3000}</failure><system-out>secret</system-out></testcase></testsuite>"
        ).encode()
    )
    assert len(report.cases[0].message or "") == junit.MAX_MESSAGE
    assert report.warnings == ("failure_message_truncated",)
    assert "secret" not in repr(report)


def test_output_subtree_cannot_smuggle_text_through_a_nested_stacktrace() -> None:
    report = parse_junit(b"""<testsuite><testcase classname="C" name="n">
      <flakyFailure message="safe"><system-out><stackTrace>SECRET OUTPUT</stackTrace>
      </system-out><stackTrace>failure evidence</stackTrace></flakyFailure>
      </testcase></testsuite>""")
    assert "SECRET" not in repr(report)
    assert "failure evidence" in (report.cases[0].message or "")


@pytest.mark.parametrize(
    "payload,code",
    [
        (b"", "malformed_xml"),
        (b"<testsuite>", "malformed_xml"),
        (b"<testsuite/><testsuite/>", "malformed_xml"),
        (b'<?xml version="1.0" encoding="SECRET-unknown"?><testsuite/>', "malformed_xml"),
        (b"<testsuite><testcase name='SECRET'>&unknown;</testcase></testsuite>", "malformed_xml"),
        (b"<other/>", "unsupported_root"),
        (b"<testsuites><testcase name='n'/></testsuites>", "invalid_structure"),
        (b"<testsuite><unknown><testcase name='n'/></unknown></testsuite>", "invalid_structure"),
        (b"<testsuite><failure/></testsuite>", "invalid_structure"),
        (
            b"<testsuite><testcase name='n' status='failed'/></testsuite>",
            "unsupported_outcome_attribute",
        ),
        (b"PK\x03\x04anything", "archives_not_supported"),
        (b"\x1f\x8banything", "archives_not_supported"),
    ],
)
def test_rejected_reports_have_fixed_safe_errors(payload: bytes, code: str) -> None:
    with pytest.raises(JUnitError) as error:
        parse_junit(payload)
    assert error.value.code == code
    assert str(error.value) == code and "SECRET" not in str(error.value)


@pytest.mark.parametrize(
    "declaration",
    [
        '<!DOCTYPE testsuite SYSTEM "https://invalid.example/secret.dtd">',
        '<!DOCTYPE testsuite [<!ENTITY data SYSTEM "file:///etc/passwd">]>',
        '<!DOCTYPE testsuite [<!ENTITY % remote SYSTEM "https://invalid.example/e">%remote;]>',
        '<!DOCTYPE testsuite [<!ENTITY a "a"><!ENTITY b "&a;&a;&a;"><!ENTITY c "&b;&b;&b;">]>',
        "<!DOCTYPE testsuite>",
    ],
)
@pytest.mark.parametrize("encoding", ["utf-8", "utf-16"])
def test_dtd_and_entities_rejected_including_utf16(declaration: str, encoding: str) -> None:
    payload = (f'<?xml version="1.0" encoding="{encoding}"?>{declaration}<testsuite/>').encode(
        encoding
    )
    with pytest.raises(JUnitError, match="^dtd_or_entity_forbidden$"):
        parse_junit(payload)


def test_standard_xml_escaping_utf16_and_namespaces_work_without_external_entities() -> None:
    payload = (
        '<?xml version="1.0" encoding="utf-16"?><testsuite xmlns="urn:junit">'
        '<testcase classname="C" name="a &amp; b &#9731;"/></testsuite>'
    )
    report = parse_junit(payload.encode("utf-16"))
    assert report.cases[0].name == "a & b ☃"
    assert report.warnings == ("namespaced_report",)


def test_limits_cover_body_nesting_suites_elements_identity_and_expanded_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(JUnitError, match="^report_too_large$"):
        parse_junit(b" " * (junit.MAX_BYTES + 1))
    with pytest.raises(JUnitError, match="^nesting_too_deep$"):
        parse_junit(
            b"<testsuite>" * (junit.MAX_DEPTH + 1) + b"</testsuite>" * (junit.MAX_DEPTH + 1)
        )
    with pytest.raises(JUnitError, match="^identity_field_too_long$"):
        parse_junit(
            b'<testsuite><testcase name="'
            + b"x" * (junit.MAX_IDENTITY_FIELD + 1)
            + b'"/></testsuite>'
        )
    with pytest.raises(JUnitError, match="^attributes_too_large$"):
        parse_junit(b'<testsuite attribute="' + b"x" * 65_537 + b'"/>')
    monkeypatch.setattr(junit, "MAX_SUITES", 1)
    with pytest.raises(JUnitError, match="^too_many_suites$"):
        parse_junit(b"<testsuite><testsuite/></testsuite>")
    monkeypatch.setattr(junit, "MAX_ELEMENTS", 2)
    with pytest.raises(JUnitError, match="^too_many_elements$"):
        parse_junit(b"<testsuite><properties><property/></properties></testsuite>")
    monkeypatch.setattr(junit, "MAX_ELEMENTS", 500_000)
    monkeypatch.setattr(junit, "MAX_CASES", 2)
    with pytest.raises(JUnitError, match="^too_many_cases$"):
        parse_junit(b"<testsuite><testcase><flakyFailure/><flakyError/></testcase></testsuite>")


def test_one_hundred_thousand_cases_supported_and_next_case_rejected() -> None:
    leaf = b'<testcase classname="C" name="duplicate"/>'
    report = parse_junit(b"<testsuite>" + leaf * 100_000 + b"</testsuite>")
    assert report.execution_count == 100_000
    assert len({case.identity_key for case in report.cases}) == 100_000
    with pytest.raises(JUnitError, match="^too_many_cases$"):
        parse_junit(b"<testsuite>" + leaf * 100_001 + b"</testsuite>")


def test_empty_unknown_and_missing_identity_evidence_are_visible() -> None:
    assert parse_junit(b"<testsuite/>").warnings == ("empty_report",)
    report = parse_junit(b"<testsuite><unknown/><testcase/></testsuite>")
    assert set(report.warnings) == {"missing_test_name", "unsupported_element"}
    assert report.cases[0].identity_quality == "ambiguous"


def test_old_expat_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(junit.expat, "version_info", (2, 5, 0))
    with pytest.raises(JUnitError, match="^xml_parser_unavailable$"):
        parse_junit(b"<testsuite/>")
