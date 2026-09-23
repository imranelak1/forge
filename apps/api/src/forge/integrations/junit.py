"""Bounded, network-free JUnit XML normalization.

Expat callbacks retain normalized leaf records, never an XML tree or captured logs.
Only Maven Surefire's documented flaky/rerun elements establish retry ordering.
https://docs.python.org/3.13/library/pyexpat.html
https://maven.apache.org/surefire/maven-surefire-plugin/examples/rerun-failing-tests.html
"""

import hashlib
import json
import math
from dataclasses import dataclass, field, replace
from typing import Literal, NoReturn
from xml.parsers import expat

MAX_BYTES = 10 * 1024 * 1024
MAX_CASES = 100_000  # Includes expanded retry executions, not just XML testcase elements.
MAX_SUITES = 10_000
MAX_DEPTH = 64
MAX_ELEMENTS = 500_000
MAX_MESSAGE = 2_048
MAX_IDENTITY_FIELD = 2_048
MAX_DURATION_SECONDS = 31_536_000.0

Outcome = Literal["passed", "failed", "error", "skipped"]
IdentityQuality = Literal["exact", "fallback", "ambiguous"]
_OUTCOMES = {"failure": "failed", "error": "error", "skipped": "skipped"}
_RETRIES = {"flakyFailure", "flakyError", "rerunFailure", "rerunError"}
_IGNORED = {"properties", "property", "system-out", "system-err"}
_COUNTERS = {"tests": "tests", "failures": "failed", "errors": "error", "skipped": "skipped"}


class JUnitError(ValueError):
    """Safe fixed error code; never includes report text or Expat's source context."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ParsedSuite:
    key: str
    parent_key: str | None
    path: tuple[str, ...]
    name: str
    ordinal: int
    declared_counts: dict[str, int]
    counts: dict[str, int]


@dataclass(frozen=True, slots=True)
class ParsedCase:
    suite_key: str
    ordinal: int
    source_ordinal: int
    identity_key: str
    identity_quality: IdentityQuality
    classname: str | None
    name: str
    file: str | None
    parameterization: str | None
    retry_ordinal: int
    is_final: bool
    outcome: Outcome
    duration_seconds: float | None
    message: str | None


@dataclass(frozen=True, slots=True)
class ParsedReport:
    suites: tuple[ParsedSuite, ...]
    cases: tuple[ParsedCase, ...]
    warnings: tuple[str, ...]
    declared_total: int | None
    counts: dict[str, int]
    execution_count: int


def _counts() -> dict[str, int]:
    return {"tests": 0, "passed": 0, "failed": 0, "error": 0, "skipped": 0}


def _digest(parts: object) -> str:
    return hashlib.sha256(
        json.dumps(parts, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@dataclass(slots=True)
class _Suite:
    key: str | None
    parent_key: str | None
    path: tuple[str, ...]
    name: str
    ordinal: int
    declared: dict[str, int]
    counts: dict[str, int] = field(default_factory=_counts)


@dataclass(slots=True)
class _Failure:
    tag: str
    duration: float | None
    message: list[str] = field(default_factory=list)
    length: int = 0


@dataclass(slots=True)
class _Case:
    suite: _Suite
    source_ordinal: int
    name: str
    classname: str | None
    file: str | None
    parameters: str | None
    duration: float | None
    quality: IdentityQuality
    failures: list[_Failure] = field(default_factory=list)


class _Parser:
    def __init__(self, framework: str) -> None:
        self.framework = framework
        self.tags: list[str] = []
        self.containers: list[_Suite] = []
        self.suites: list[ParsedSuite] = []
        self.cases: list[ParsedCase] = []
        self.warnings: set[str] = set()
        self.case: _Case | None = None
        self.failure: _Failure | None = None
        self.elements = 0
        self.suite_count = 0
        self.source_count = 0
        self.execution_count = 0
        self.declared_total: int | None = None
        self.counts = _counts()
        self.identities: dict[str, int] = {}
        self.occurrences: dict[int, int] = {}

    def identity_field(self, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        if len(value) > MAX_IDENTITY_FIELD:
            raise JUnitError("identity_field_too_long")
        return value

    def duration(self, value: str | None) -> float | None:
        if value is None:
            return None
        try:
            if len(value) > 64:
                raise ValueError
            duration = float(value)
            if not math.isfinite(duration) or not 0 <= duration <= MAX_DURATION_SECONDS:
                raise ValueError
            return duration
        except ValueError:
            self.warnings.add("invalid_duration")
            return None

    def declared(self, attrs: dict[str, str]) -> dict[str, int]:
        values = {}
        for field_name in _COUNTERS:
            value = attrs.get(field_name)
            if value is None:
                continue
            if len(value) > 10 or not value.isascii() or not value.isdecimal():
                self.warnings.add("invalid_declared_count")
                continue
            count = int(value)
            if count > 2_147_483_647:
                self.warnings.add("invalid_declared_count")
                continue
            values[field_name] = count
        return values

    def start(self, expanded: str, attrs: dict[str, str]) -> None:
        tag = expanded.rsplit("}", 1)[-1]
        if "}" in expanded:
            self.warnings.add("namespaced_report")
        self.elements += 1
        if self.elements > MAX_ELEMENTS:
            raise JUnitError("too_many_elements")
        if len(self.tags) >= MAX_DEPTH:
            raise JUnitError("nesting_too_deep")
        if len(attrs) > 64 or sum(len(k) + len(v) for k, v in attrs.items()) > 65_536:
            raise JUnitError("attributes_too_large")
        parent = self.tags[-1] if self.tags else None
        if parent is None and tag not in {"testsuite", "testsuites"}:
            raise JUnitError("unsupported_root")
        self.tags.append(tag)
        if tag in {"testsuite", "testsuites"}:
            if parent not in {None, "testsuite", "testsuites"}:
                raise JUnitError("invalid_structure")
            self.start_suite(tag, attrs)
        elif tag == "testcase":
            if parent != "testsuite" or self.case is not None:
                raise JUnitError("invalid_structure")
            self.start_case(attrs)
        elif tag in _OUTCOMES or tag in _RETRIES:
            if parent != "testcase" or self.case is None:
                raise JUnitError("invalid_structure")
            self.execution_count += 1
            if self.execution_count > MAX_CASES:
                raise JUnitError("too_many_cases")
            self.failure = _Failure(tag, self.duration(attrs.get("time")))
            self.case.failures.append(self.failure)
            self.message(attrs.get("message", ""))
        elif tag not in _IGNORED and not (tag == "stackTrace" and parent in _RETRIES):
            self.warnings.add("unsupported_element")
            if self.case is not None:
                self.case.quality = "ambiguous"

    def start_suite(self, tag: str, attrs: dict[str, str]) -> None:
        parent = next((s for s in reversed(self.containers) if s.key is not None), None)
        name = self.identity_field(attrs.get("name")) or "[unnamed suite]"
        declared = self.declared(attrs)
        if len(self.tags) == 1:
            self.declared_total = declared.get("tests")
        if tag == "testsuite":
            self.suite_count += 1
            if self.suite_count > MAX_SUITES:
                raise JUnitError("too_many_suites")
            key, ordinal = str(self.suite_count), self.suite_count
            path = (*parent.path, name) if parent else (name,)
        else:
            key, ordinal = None, 0
            path = parent.path if parent else ()
        self.containers.append(
            _Suite(key, parent.key if parent else None, path, name, ordinal, declared)
        )

    def start_case(self, attrs: dict[str, str]) -> None:
        self.source_count += 1
        if self.source_count > MAX_CASES:
            raise JUnitError("too_many_cases")
        suite = self.containers[-1]
        name = self.identity_field(attrs.get("name"))
        classname = self.identity_field(attrs.get("classname"))
        file = self.identity_field(attrs.get("file"))
        parameters = self.identity_field(attrs.get("parameters") or attrs.get("parameter"))
        quality: IdentityQuality = "exact" if classname or file else "fallback"
        if name is None:
            self.warnings.add("missing_test_name")
            quality = "ambiguous"
        if any(field in attrs for field in ("retry", "retries", "retryAttempt", "attempt")):
            self.warnings.add("unsupported_retry_metadata")
            quality = "ambiguous"
        # Tags are the supported JUnit outcome evidence. Do not turn a dialect's
        # negative/unknown attribute-only result into an apparent successful test.
        for field_name in ("status", "result"):
            if field_name in attrs and attrs[field_name] not in {"run", "passed", "success"}:
                raise JUnitError("unsupported_outcome_attribute")
        self.case = _Case(
            suite,
            self.source_count,
            name or "[unnamed testcase]",
            classname,
            file,
            parameters,
            self.duration(attrs.get("time")),
            quality,
        )

    def message(self, value: str) -> None:
        if self.failure is None or not value:
            return
        remaining = MAX_MESSAGE - self.failure.length
        if len(value) > remaining:
            self.warnings.add("failure_message_truncated")
        if remaining > 0:
            fragment = value[:remaining]
            self.failure.message.append(fragment)
            self.failure.length += len(fragment)

    def text(self, value: str) -> None:
        # Ignore properties, captured output and nested output under Surefire failures.
        if any(tag in _IGNORED for tag in self.tags):
            return
        if self.tags and (
            self.tags[-1] in _OUTCOMES or self.tags[-1] in _RETRIES or self.tags[-1] == "stackTrace"
        ):
            self.message(value)

    def end(self, expanded: str) -> None:
        tag = expanded.rsplit("}", 1)[-1]
        if tag in _OUTCOMES or tag in _RETRIES:
            self.failure = None
        elif tag == "testcase":
            self.finish_case()
            self.case = None
        elif tag in {"testsuite", "testsuites"}:
            suite = self.containers.pop()
            for field_name, count in suite.declared.items():
                if count != suite.counts[_COUNTERS[field_name]]:
                    self.warnings.add("declared_count_mismatch")
            if suite.key is not None:
                self.suites.append(
                    ParsedSuite(
                        suite.key,
                        suite.parent_key,
                        suite.path,
                        suite.name,
                        suite.ordinal,
                        suite.declared,
                        suite.counts,
                    )
                )
            if self.containers:
                for outcome, count in suite.counts.items():
                    self.containers[-1].counts[outcome] += count
            else:
                self.counts = suite.counts
        self.tags.pop()

    def finish_case(self) -> None:
        case = self.case
        assert case is not None and case.suite.key is not None
        normal = [f for f in case.failures if f.tag in _OUTCOMES]
        flaky = [f for f in case.failures if f.tag.startswith("flaky")]
        reruns = [f for f in case.failures if f.tag.startswith("rerun")]
        executions: list[tuple[Outcome, float | None, str | None]] = []
        if flaky and not normal and not reruns:
            executions.extend(self.failure_execution(f) for f in flaky)
            executions.append(("passed", case.duration, None))
        elif reruns and not flaky and len(normal) == 1 and normal[0].tag != "skipped":
            outcome, _, message = self.failure_execution(normal[0])
            executions.append((outcome, case.duration, message))
            executions.extend(self.failure_execution(f) for f in reruns)
        else:
            if flaky or reruns:
                self.warnings.add("unsupported_retry_dialect")
                case.quality = "ambiguous"
            if len(normal) > 1:
                self.warnings.add("multiple_outcome_elements")
                case.quality = "ambiguous"
            evidence = normal or flaky or reruns
            if evidence:
                # Contradictory evidence is explicitly marked ambiguous. Never call
                # a failure successful merely because a skipped element also exists.
                failure = min(
                    evidence,
                    key=lambda f: (
                        0 if f.tag.lower().endswith("error") else 1 if f.tag != "skipped" else 2
                    ),
                )
                outcome, _, message = self.failure_execution(failure)
                executions.append((outcome, case.duration, message))
            else:
                executions.append(("passed", case.duration, None))
        if len(self.cases) + len(executions) > MAX_CASES:
            raise JUnitError("too_many_cases")
        basis: list[object] = [
            self.framework,
            case.file,
            case.classname,
            case.name,
            case.parameters,
        ]
        if case.file is None and case.classname is None:
            basis.append(list(case.suite.path))
        identity = _digest(basis)
        occurrence = self.identities.get(identity, 0) + 1
        self.identities[identity] = occurrence
        self.occurrences[case.source_ordinal] = occurrence
        for retry, (outcome, duration, message) in enumerate(executions):
            self.cases.append(
                ParsedCase(
                    suite_key=case.suite.key,
                    ordinal=len(self.cases) + 1,
                    source_ordinal=case.source_ordinal,
                    identity_key=identity,
                    identity_quality=case.quality,
                    classname=case.classname,
                    name=case.name,
                    file=case.file,
                    parameterization=case.parameters,
                    retry_ordinal=retry,
                    is_final=retry == len(executions) - 1,
                    outcome=outcome,
                    duration_seconds=duration,
                    message=message,
                )
            )
        case.suite.counts[executions[-1][0]] += 1
        case.suite.counts["tests"] += 1

    @staticmethod
    def failure_execution(failure: _Failure) -> tuple[Outcome, float | None, str | None]:
        outcome: Outcome = (
            "skipped"
            if failure.tag == "skipped"
            else ("error" if failure.tag.lower().endswith("error") else "failed")
        )
        return outcome, failure.duration, "".join(failure.message).strip() or None

    def result(self) -> ParsedReport:
        # A repeated leaf is not proof of a retry. All such occurrences remain
        # separate, with ambiguous identity ineligible for historical flakiness.
        for index, case in enumerate(self.cases):
            if self.identities[case.identity_key] > 1:
                self.warnings.add("ambiguous_duplicate_identity")
                self.cases[index] = replace(
                    case,
                    identity_key=_digest(
                        [case.identity_key, self.occurrences[case.source_ordinal]]
                    ),
                    identity_quality="ambiguous",
                )
        if not self.cases:
            self.warnings.add("empty_report")
        if any(case.identity_quality == "fallback" for case in self.cases):
            self.warnings.add("fallback_identity")
        return ParsedReport(
            tuple(sorted(self.suites, key=lambda suite: suite.ordinal)),
            tuple(self.cases),
            tuple(sorted(self.warnings)),
            self.declared_total,
            self.counts,
            len(self.cases),
        )


def _forbidden(*args: object) -> NoReturn:
    raise JUnitError("dtd_or_entity_forbidden")


def parse_junit(payload: bytes, *, framework: str = "junit") -> ParsedReport:
    """Normalize uncompressed XML; callers must separately authorize report scope.

    Messages are bounded, untrusted failure text, not redacted or safe to log.
    Ingestion may omit them entirely. Neither properties nor output are returned.
    """
    if len(payload) > MAX_BYTES:
        raise JUnitError("report_too_large")
    if not framework or len(framework) > 100:
        raise JUnitError("invalid_framework")
    if payload.startswith((b"PK\x03\x04", b"\x1f\x8b", b"BZh", b"\xfd7zXZ\x00")):
        raise JUnitError("archives_not_supported")
    if expat.version_info < (2, 6, 0):
        raise JUnitError("xml_parser_unavailable")
    state = _Parser(framework)
    parser = expat.ParserCreate(namespace_separator="}")
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    parser.SetReparseDeferralEnabled(True)
    parser.StartDoctypeDeclHandler = _forbidden
    parser.EntityDeclHandler = _forbidden
    parser.ExternalEntityRefHandler = _forbidden
    parser.SkippedEntityHandler = _forbidden
    parser.StartElementHandler = state.start
    parser.EndElementHandler = state.end
    parser.CharacterDataHandler = state.text
    try:
        parser.Parse(payload, True)
    except (expat.ExpatError, ValueError, LookupError) as exc:
        if isinstance(exc, JUnitError):
            raise
        raise JUnitError("malformed_xml") from None
    return state.result()
