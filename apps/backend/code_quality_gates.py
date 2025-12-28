"""
Code Quality Gates Module
=========================

Automated code quality checks including linting, type checking, and coverage.

Features:
- Configurable quality checks
- Linting (Ruff)
- Type checking (mypy)
- Coverage reporting
- Quality gates with pass/fail
- HTML coverage reports
- JSON output for CI integration
"""

import json
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Any, Set


class CheckType(str, Enum):
    """Types of code quality checks."""
    LINT = "lint"
    TYPECHECK = "typecheck"
    COVERAGE = "coverage"
    FORMAT = "format"
    SECURITY = "security"
    TESTS = "tests"


class CheckStatus(str, Enum):
    """Status of a quality check."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class QualityCheck:
    """Result of a single quality check."""
    name: str
    type: CheckType
    status: CheckStatus
    score: Optional[float] = None
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    duration_seconds: Optional[float] = None
    files_checked: int = 0
    issues_found: int = 0


@dataclass
class QualityGateResult:
    """Overall result of quality gate run."""
    checks: List[QualityCheck]
    overall_status: CheckStatus
    total_issues: int
    total_files_checked: int
    duration_seconds: float
    summary: Dict[str, Any]


class CodeQualityGate:
    """
    Code quality gate runner.
    
    Example:
        ```python
        from code_quality_gates import CodeQualityGate
        
        gate = CodeQualityGate(
            project_dir=Path.cwd(),
            required_checks=[CheckType.LINT, CheckType.TYPECHECK, CheckType.COVERAGE],
            thresholds={
                "coverage_minimum": 80,
                "lint_errors_max": 0
            }
        )
        
        result = gate.run()
        if result.overall_status == CheckStatus.PASSED:
            print("All quality gates passed!")
        else:
            print("Quality gates failed. See details.")
            print(result.to_json())
        ```
    """
    
    DEFAULT_THRESHOLDS = {
        "coverage_minimum": 80.0,
        "lint_errors_max": 0,
        "lint_warnings_max": 10,
        "typecheck_errors_max": 0,
        "test_pass_rate_minimum": 100.0
    }
    
    def __init__(
        self,
        project_dir: Path,
        required_checks: Optional[List[CheckType]] = None,
        thresholds: Optional[Dict[str, float]] = None,
        exclude_patterns: Optional[List[str]] = None,
        python_paths: Optional[List[str]] = None
    ):
        """
        Initialize code quality gate.
        
        Args:
            project_dir: Project root directory
            required_checks: List of checks to run (default: all)
            thresholds: Quality thresholds (default: DEFAULT_THRESHOLDS)
            exclude_patterns: File patterns to exclude from checks
            python_paths: Additional Python paths for type checking
        """
        self.project_dir = Path(project_dir).resolve()
        self.required_checks = required_checks or [
            CheckType.LINT,
            CheckType.TYPECHECK,
            CheckType.COVERAGE,
            CheckType.FORMAT
        ]
        self.thresholds = {**self.DEFAULT_THRESHOLDS, **(thresholds or {})}
        self.exclude_patterns = exclude_patterns or [
            "__pycache__",
            ".venv",
            "venv",
            ".pytest_cache",
            ".mypy_cache",
            "build",
            "dist",
            "*.egg-info"
        ]
        self.python_paths = python_paths or []
        self._checks: List[QualityCheck] = []
        self._start_time: Optional[float] = None
    
    def run(self) -> QualityGateResult:
        """Run all required quality checks."""
        self._start_time = time.time()
        self._checks = []
        
        print(f"\n{'='*60}")
        print("CODE QUALITY GATE")
        print(f"{'='*60}")
        print(f"Project: {self.project_dir}")
        print(f"Checks: {[c.value for c in self.required_checks]}")
        print(f"Thresholds: {self.thresholds}")
        print(f"{'='*60}\n")
        
        # Run each check
        for check_type in self.required_checks:
            try:
                check = self._run_check(check_type)
                self._checks.append(check)
                self._print_check_result(check)
            except Exception as e:
                self._checks.append(QualityCheck(
                    name=f"{check_type.value}_error",
                    type=check_type,
                    status=CheckStatus.ERROR,
                    message=str(e)
                ))
                print(f"ERROR in {check_type.value}: {e}")
        
        # Calculate overall result
        total_issues = sum(c.issues_found for c in self._checks)
        total_files = sum(c.files_checked for c in self._checks)
        duration = time.time() - (self._start_time or 0)
        
        # Overall status: FAILED if any check failed, PASSED otherwise
        failed_checks = [c for c in self._checks if c.status == CheckStatus.FAILED]
        overall_status = CheckStatus.FAILED if failed_checks else CheckStatus.PASSED
        
        # Build summary
        summary = {
            "checks_passed": len([c for c in self._checks if c.status == CheckStatus.PASSED]),
            "checks_failed": len([c for c in self._checks if c.status == CheckStatus.FAILED]),
            "checks_skipped": len([c for c in self._checks if c.status == CheckStatus.SKIPPED]),
            "total_issues": total_issues,
            "total_files_checked": total_files,
            "thresholds": self.thresholds
        }
        
        result = QualityGateResult(
            checks=self._checks,
            overall_status=overall_status,
            total_issues=total_issues,
            total_files_checked=total_files,
            duration_seconds=duration,
            summary=summary
        )
        
        # Print summary
        self._print_summary(result)
        
        return result
    
    def _run_check(self, check_type: CheckType) -> QualityCheck:
        """Run a single quality check."""
        start_time = time.time()
        
        if check_type == CheckType.LINT:
            return self._check_lint(start_time)
        elif check_type == CheckType.TYPECHECK:
            return self._check_typecheck(start_time)
        elif check_type == CheckType.COVERAGE:
            return self._check_coverage(start_time)
        elif check_type == CheckType.FORMAT:
            return self._check_format(start_time)
        elif check_type == CheckType.SECURITY:
            return self._check_security(start_time)
        elif check_type == CheckType.TESTS:
            return self._check_tests(start_time)
        else:
            return QualityCheck(
                name=check_type.value,
                type=check_type,
                status=CheckStatus.SKIPPED,
                message=f"Unknown check type: {check_type}"
            )
    
    def _check_lint(self, start_time: float) -> QualityCheck:
        """Run Ruff linting."""
        print("\nRunning linting (Ruff)...")
        
        try:
            result = subprocess.run(
                ["ruff", "check", str(self.project_dir), "--output-format=json"],
                capture_output=True,
                text=True,
                cwd=self.project_dir
            )
        except FileNotFoundError:
            return QualityCheck(
                name="lint",
                type=CheckType.LINT,
                status=CheckStatus.SKIPPED,
                message="Ruff not installed. Install with: pip install ruff",
                duration_seconds=time.time() - start_time
            )
        
        duration = time.time() - start_time
        
        if result.returncode == 0:
            return QualityCheck(
                name="lint",
                type=CheckType.LINT,
                status=CheckStatus.PASSED,
                score=100.0,
                message="No lint issues found",
                duration_seconds=duration
            )
        
        # Parse errors
        errors = json.loads(result.stdout) if result.stdout else []
        error_count = len(errors)
        
        # Count errors vs warnings
        errors_list = [e for e in errors if e.get("type") == "E"]
        warnings_list = [e for e in errors if e.get("type") == "W"]
        
        max_errors = self.thresholds.get("lint_errors_max", 0)
        max_warnings = self.thresholds.get("lint_warnings_max", 10)
        
        status = CheckStatus.PASSED
        if len(errors_list) > max_errors or len(warnings_list) > max_warnings:
            status = CheckStatus.FAILED
        
        # Collect unique files
        files_checked = len(set(e.get("filename", "") for e in errors))
        
        return QualityCheck(
            name="lint",
            type=CheckType.LINT,
            status=status,
            score=max(0, 100 - (error_count * 5)),
            message=f"{error_count} issues found ({len(errors_list)} errors, {len(warnings_list)} warnings)",
            details={
                "errors": errors_list[:20],  # Limit output
                "warnings": warnings_list[:20],
                "errors_count": len(errors_list),
                "warnings_count": len(warnings_list)
            },
            duration_seconds=duration,
            files_checked=files_checked,
            issues_found=error_count
        )
    
    def _check_typecheck(self, start_time: float) -> QualityCheck:
        """Run MyPy type checking."""
        print("\nRunning type checking (MyPy)...")
        
        cmd = ["mypy", str(self.project_dir), "--json"]
        for path in self.python_paths:
            cmd.extend(["-p", path])
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.project_dir
            )
        except FileNotFoundError:
            return QualityCheck(
                name="typecheck",
                type=CheckType.TYPECHECK,
                status=CheckStatus.SKIPPED,
                message="MyPy not installed. Install with: pip install mypy",
                duration_seconds=time.time() - start_time
            )
        
        duration = time.time() - start_time
        
        if result.returncode == 0:
            return QualityCheck(
                name="typecheck",
                type=CheckType.TYPECHECK,
                status=CheckStatus.PASSED,
                score=100.0,
                message="No type errors found",
                duration_seconds=duration
            )
        
        # Parse errors
        errors = []
        for line in result.stdout.split("\n"):
            if line.strip():
                try:
                    errors.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        
        max_errors = self.thresholds.get("typecheck_errors_max", 0)
        status = CheckStatus.PASSED
        if len(errors) > max_errors:
            status = CheckStatus.FAILED
        
        files_checked = len(set(e.get("file", "") for e in errors))
        
        return QualityCheck(
            name="typecheck",
            type=CheckType.TYPECHECK,
            status=status,
            score=max(0, 100 - (len(errors) * 10)),
            message=f"{len(errors)} type errors found",
            details={
                "errors": errors[:10],
                "errors_count": len(errors)
            },
            duration_seconds=duration,
            files_checked=files_checked,
            issues_found=len(errors)
        )
    
    def _check_coverage(self, start_time: float) -> QualityCheck:
        """Run coverage check."""
        print("\nRunning coverage check...")
        
        try:
            result = subprocess.run(
                ["coverage", "report", "--json"],
                capture_output=True,
                text=True,
                cwd=self.project_dir
            )
        except FileNotFoundError:
            return QualityCheck(
                name="coverage",
                type=CheckType.COVERAGE,
                status=CheckStatus.SKIPPED,
                message="Coverage not installed. Install with: pip install coverage",
                duration_seconds=time.time() - start_time
            )
        
        duration = time.time() - start_time
        
        try:
            coverage_data = json.loads(result.stdout)
            total_coverage = coverage_data.get("totals", {}).get("percent_covered", 0)
        except json.JSONDecodeError:
            return QualityCheck(
                name="coverage",
                type=CheckType.COVERAGE,
                status=CheckStatus.ERROR,
                message="Failed to parse coverage report",
                duration_seconds=duration
            )
        
        minimum = self.thresholds.get("coverage_minimum", 80.0)
        status = CheckStatus.PASSED if total_coverage >= minimum else CheckStatus.FAILED
        
        files_checked = coverage_data.get("files", [])
        
        return QualityCheck(
            name="coverage",
            type=CheckType.COVERAGE,
            status=status,
            score=total_coverage,
            message=f"Total coverage: {total_coverage:.1f}% (minimum: {minimum}%)",
            details={
                "coverage": coverage_data.get("totals", {}),
                "below_threshold": total_coverage < minimum,
                "gap": minimum - total_coverage if total_coverage < minimum else 0
            },
            duration_seconds=duration,
            files_checked=len(files_checked),
            issues_found=0
        )
    
    def _check_format(self, start_time: float) -> QualityCheck:
        """Run format check (Ruff format)."""
        print("\nRunning format check (Ruff format)...")
        
        try:
            result = subprocess.run(
                ["ruff", "format", "--check", str(self.project_dir)],
                capture_output=True,
                text=True,
                cwd=self.project_dir
            )
        except FileNotFoundError:
            return QualityCheck(
                name="format",
                type=CheckType.FORMAT,
                status=CheckStatus.SKIPPED,
                message="Ruff not installed. Install with: pip install ruff",
                duration_seconds=time.time() - start_time
            )
        
        duration = time.time() - start_time
        
        if result.returncode == 0:
            return QualityCheck(
                name="format",
                type=CheckType.FORMAT,
                status=CheckStatus.PASSED,
                score=100.0,
                message="All files properly formatted",
                duration_seconds=duration
            )
        
        # Parse output
        unformatted_files = []
        for line in result.stdout.split("\n"):
            if "Would reformat" in line or "would reformat" in line:
                file_match = line.split()[-1]
                if file_match:
                    unformatted_files.append(file_match)
        
        return QualityCheck(
            name="format",
            type=CheckType.FORMAT,
            status=CheckStatus.FAILED,
            score=max(0, 100 - (len(unformatted_files) * 5)),
            message=f"{len(unformatted_files)} files need formatting",
            details={
                "files": unformatted_files[:20]
            },
            duration_seconds=duration,
            files_checked=len(unformatted_files),
            issues_found=len(unformatted_files)
        )
    
    def _check_security(self, start_time: float) -> QualityCheck:
        """Run security scan (Bandit)."""
        print("\nRunning security scan (Bandit)...")
        
        try:
            result = subprocess.run(
                ["bandit", "-r", str(self.project_dir), "-f", "json"],
                capture_output=True,
                text=True,
                cwd=self.project_dir
            )
        except FileNotFoundError:
            return QualityCheck(
                name="security",
                type=CheckType.SECURITY,
                status=CheckStatus.SKIPPED,
                message="Bandit not installed. Install with: pip install bandit",
                duration_seconds=time.time() - start_time
            )
        
        duration = time.time() - start_time
        
        try:
            security_data = json.loads(result.stdout)
            issues = security_data.get("results", [])
        except json.JSONDecodeError:
            return QualityCheck(
                name="security",
                type=CheckType.SECURITY,
                status=CheckStatus.ERROR,
                message="Failed to parse security report",
                duration_seconds=duration
            )
        
        # Filter issues by severity
        high_severity = [i for i in issues if i.get("issue_severity") == "HIGH"]
        medium_severity = [i for i in issues if i.get("issue_severity") == "MEDIUM"]
        low_severity = [i for i in issues if i.get("issue_severity") == "LOW"]
        
        # Check against thresholds
        max_high = self.thresholds.get("security_high_max", 0)
        max_medium = self.thresholds.get("security_medium_max", 0)
        
        status = CheckStatus.PASSED
        if len(high_severity) > max_high or len(medium_severity) > max_medium:
            status = CheckStatus.FAILED
        
        return QualityCheck(
            name="security",
            type=CheckType.SECURITY,
            status=status,
            score=max(0, 100 - (len(high_severity) * 20 + len(medium_severity) * 10)),
            message=f"{len(issues)} security issues found ({len(high_severity)} high, {len(medium_severity)} medium)",
            details={
                "high_severity": high_severity[:10],
                "medium_severity": medium_severity[:10],
                "low_severity": low_severity[:10]
            },
            duration_seconds=duration,
            files_checked=len(set(i.get("filename", "") for i in issues)),
            issues_found=len(issues)
        )
    
    def _check_tests(self, start_time: float) -> QualityCheck:
        """Run tests and check pass rate."""
        print("\nRunning tests (pytest)...")
        
        try:
            result = subprocess.run(
                ["pytest", "--json-report", "--json-report-file=/tmp/test_report.json"],
                capture_output=True,
                text=True,
                cwd=self.project_dir
            )
        except FileNotFoundError:
            return QualityCheck(
                name="tests",
                type=CheckType.TESTS,
                status=CheckStatus.SKIPPED,
                message="Pytest not installed. Install with: pip install pytest",
                duration_seconds=time.time() - start_time
            )
        
        duration = time.time() - start_time
        
        # Parse test results
        try:
            with open("/tmp/test_report.json") as f:
                test_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Parse from stdout
            return QualityCheck(
                name="tests",
                type=CheckType.TESTS,
                status=CheckStatus.FAILED,
                message="Tests failed or no test report available",
                duration_seconds=duration
            )
        
        total = test_data.get("summary", {}).get("total", 0)
        passed = test_data.get("summary", {}).get("passed", 0)
        failed = test_data.get("summary", {}).get("failed", 0)
        pass_rate = (passed / total * 100) if total > 0 else 0
        
        minimum = self.thresholds.get("test_pass_rate_minimum", 100.0)
        status = CheckStatus.PASSED if pass_rate >= minimum else CheckStatus.FAILED
        
        return QualityCheck(
            name="tests",
            type=CheckType.TESTS,
            status=status,
            score=pass_rate,
            message=f"Tests: {passed}/{total} passed ({pass_rate:.1f}%)",
            details={
                "total": total,
                "passed": passed,
                "failed": failed,
                "pass_rate": pass_rate
            },
            duration_seconds=duration,
            files_checked=0,
            issues_found=failed
        )
    
    def _print_check_result(self, check: QualityCheck) -> None:
        """Print result of a single check."""
        status_symbol = "✓" if check.status == CheckStatus.PASSED else \
                      "✗" if check.status == CheckStatus.FAILED else \
                      "⊘" if check.status == CheckStatus.SKIPPED else \
                      "⚠"
        
        status_color = "\033[92m" if check.status == CheckStatus.PASSED else \
                       "\033[91m" if check.status == CheckStatus.FAILED else \
                       "\033[93m"
        
        print(f"{status_color}{status_symbol}\033[0m {check.name}:")
        print(f"  Status: {check.status.value}")
        if check.score is not None:
            print(f"  Score: {check.score:.1f}/100")
        print(f"  Message: {check.message}")
        print(f"  Duration: {check.duration_seconds:.2f}s")
        if check.files_checked > 0:
            print(f"  Files checked: {check.files_checked}")
        if check.issues_found > 0:
            print(f"  Issues: {check.issues_found}")
    
    def _print_summary(self, result: QualityGateResult) -> None:
        """Print overall summary."""
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        print(f"Overall Status: {result.overall_status.value}")
        print(f"Total Issues: {result.total_issues}")
        print(f"Files Checked: {result.total_files_checked}")
        print(f"Duration: {result.duration_seconds:.2f}s")
        print(f"\nChecks Passed: {result.summary['checks_passed']}")
        print(f"Checks Failed: {result.summary['checks_failed']}")
        print(f"Checks Skipped: {result.summary['checks_skipped']}")
        print(f"{'='*60}\n")
        
        if result.overall_status == CheckStatus.FAILED:
            print("\n⚠ QUALITY GATE FAILED ⚠")
            print("Some checks did not meet thresholds.")
            print("Review the output above for details.")
            sys.exit(1)
        else:
            print("\n✓ QUALITY GATE PASSED ✓")
            print("All checks passed successfully!")
            sys.exit(0)
    
    def to_json(self) -> str:
        """Export result to JSON."""
        return json.dumps({
            "project_dir": str(self.project_dir),
            "checks": [
                {
                    "name": c.name,
                    "type": c.type.value,
                    "status": c.status.value,
                    "score": c.score,
                    "message": c.message,
                    "details": c.details,
                    "duration_seconds": c.duration_seconds,
                    "files_checked": c.files_checked,
                    "issues_found": c.issues_found
                }
                for c in self._checks
            ],
            "overall_status": self.overall_status.value,
            "total_issues": self.total_issues,
            "total_files_checked": self.total_files_checked,
            "duration_seconds": self.duration_seconds,
            "summary": self.summary
        }, indent=2)


import time


def main():
    """CLI entry point for quality gates."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run code quality gates")
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=Path.cwd(),
        help="Project directory (default: cwd)"
    )
    parser.add_argument(
        "--checks",
        nargs="+",
        choices=["lint", "typecheck", "coverage", "format", "security", "tests"],
        default=None,
        help="Checks to run (default: all)"
    )
    parser.add_argument(
        "--coverage-min",
        type=float,
        default=80.0,
        help="Minimum coverage percentage (default: 80)"
    )
    parser.add_argument(
        "--lint-errors-max",
        type=int,
        default=0,
        help="Maximum lint errors allowed (default: 0)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file for JSON results"
    )
    
    args = parser.parse_args()
    
    # Convert checks
    check_map = {
        "lint": CheckType.LINT,
        "typecheck": CheckType.TYPECHECK,
        "coverage": CheckType.COVERAGE,
        "format": CheckType.FORMAT,
        "security": CheckType.SECURITY,
        "tests": CheckType.TESTS
    }
    
    required_checks = [check_map[c] for c in args.checks] if args.checks else None
    
    # Create thresholds
    thresholds = {}
    if args.coverage_min:
        thresholds["coverage_minimum"] = args.coverage_min
    if args.lint_errors_max:
        thresholds["lint_errors_max"] = args.lint_errors_max
    
    # Run quality gate
    gate = CodeQualityGate(
        project_dir=args.project_dir,
        required_checks=required_checks,
        thresholds=thresholds
    )
    
    result = gate.run()
    
    # Output JSON if requested
    if args.output:
        with open(args.output, "w") as f:
            f.write(result.to_json())
        print(f"\nResults written to: {args.output}")


if __name__ == "__main__":
    main()
