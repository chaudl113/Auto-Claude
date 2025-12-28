"""
Enhanced Secret Detection Module
================================

Scans for secrets in source code, binaries, and config files.

Features:
- Multi-format scanning (source, binary, config)
- Pattern-based secret detection
- File type detection
- Configurable patterns
- False positive reduction
- Scan result reporting
"""

import re
import json
import base64
import struct
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple, Any, Pattern
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class FileType(str, Enum):
    """Types of files to scan."""
    SOURCE = "source"
    BINARY = "binary"
    CONFIG = "config"
    ALL = "all"


class SecretType(str, Enum):
    """Categories of secrets."""
    API_KEY = "api_key"
    DATABASE = "database"
    CREDENTIAL = "credential"
    TOKEN = "token"
    SECRET = "secret"
    SSH = "ssh_key"
    CERTIFICATE = "certificate"
    PRIVATE_KEY = "private_key"
    PASSWORD = "password"
    OAUTH = "oauth"
    JWT = "jwt"
    AWS = "aws_key"
    GOOGLE = "google_key"
    AZURE = "azure_key"
    OTHER = "other"


@dataclass
class SecretPattern:
    """Pattern for detecting a secret type."""
    name: str
    secret_type: SecretType
    pattern: Pattern
    description: str
    severity: str = "high"
    examples: List[str] = field(default_factory=list)
    false_positive_patterns: List[str] = field(default_factory=list)


@dataclass
class SecretMatch:
    """Detected secret match."""
    file_path: str
    line_number: Optional[int]
    position: Optional[int]
    secret_type: SecretType
    pattern_name: str
    matched_text: str
    context: Optional[str] = None
    file_type: FileType
    severity: str = "high"
    is_binary: bool = False
    confidence: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "file_path": self.file_path,
            "line_number": self.line_number,
            "position": self.position,
            "secret_type": self.secret_type.value,
            "pattern_name": self.pattern_name,
            "matched_text": self.matched_text[:20] + "..." if len(self.matched_text) > 20 else self.matched_text,
            "context": self.context,
            "file_type": self.file_type.value,
            "severity": self.severity,
            "is_binary": self.is_binary,
            "confidence": self.confidence
        }


@dataclass
class ScanResult:
    """Result of secret scanning."""
    project_path: str
    scan_duration_seconds: float
    files_scanned: int
    secrets_found: List[SecretMatch] = field(default_factory=list)
    false_positives: int = 0
    by_type: Dict[str, int] = field(default_factory=dict)
    by_severity: Dict[str, int] = field(default_factory=dict)
    
    def add_secret(self, secret: SecretMatch) -> None:
        """Add a found secret."""
        self.secrets_found.append(secret)
        
        # Count by type
        secret_type = secret.secret_type.value
        self.by_type[secret_type] = self.by_type.get(secret_type, 0) + 1
        
        # Count by severity
        self.by_severity[secret.severity] = self.by_severity.get(secret.severity, 0) + 1
    
    def mark_false_positive(self, secret: SecretMatch) -> None:
        """Mark a match as false positive."""
        if secret in self.secrets_found:
            self.secrets_found.remove(secret)
            self.false_positives += 1
    
    def summary(self) -> Dict[str, Any]:
        """Get summary of scan results."""
        return {
            "project_path": str(self.project_path),
            "scan_duration_seconds": self.scan_duration_seconds,
            "files_scanned": self.files_scanned,
            "secrets_found": len(self.secrets_found),
            "false_positives": self.false_positives,
            "by_type": self.by_type,
            "by_severity": self.by_severity
        }


class SecretScanner:
    """
    Scanner for detecting secrets in various file types.
    
    Example:
        ```python
        from secret_detection import SecretScanner
        
        scanner = SecretScanner(
            project_path=Path.cwd(),
            file_types=[FileType.SOURCE, FileType.CONFIG]
        )
        
        result = scanner.scan()
        
        print(f"Found {result.secrets_found} secrets:")
        for secret in result.secrets_found:
            print(f"  {secret.file_path}: {secret.secret_type.value}")
        ```
    """
    
    # Predefined patterns for common secrets
    PATTERNS = [
        SecretPattern(
            name="api_key_generic",
            secret_type=SecretType.API_KEY,
            pattern=re.compile(r'(api[_-]?key["\s:=]+["\s]+[a-zA-Z0-9_\-]{20,}', re.IGNORECASE),
            description="Generic API key",
            severity="high",
            false_positive_patterns=[r'"API_KEY"', r'"api_key"']
        ),
        SecretPattern(
            name="aws_access_key",
            secret_type=SecretType.AWS,
            pattern=re.compile(r'AKIA[0-9A-Z]{16}', re.IGNORECASE),
            description="AWS Access Key ID",
            severity="critical"
        ),
        SecretPattern(
            name="aws_secret_key",
            secret_type=SecretType.AWS,
            pattern=re.compile(r'aws_secret_key["\s:=]+["\s]+[a-zA-Z0-9/+]{40}', re.IGNORECASE),
            description="AWS Secret Key",
            severity="critical"
        ),
        SecretPattern(
            name="database_connection_string",
            secret_type=SecretType.DATABASE,
            pattern=re.compile(r'(mysql|postgres|mongodb|mssql|sqlite)://[^:\s/@]+:[^:\s/@]+@', re.IGNORECASE),
            description="Database connection string",
            severity="critical"
        ),
        SecretPattern(
            name="github_token",
            secret_type=SecretType.TOKEN,
            pattern=re.compile(r'ghp_[a-zA-Z0-9]{36}', re.IGNORECASE),
            description="GitHub Personal Access Token",
            severity="high"
        ),
        SecretPattern(
            name="slack_token",
            secret_type=SecretType.TOKEN,
            pattern=re.compile(r'xox[baprs]-[a-zA-Z0-9\-]+', re.IGNORECASE),
            description="Slack Token",
            severity="high"
        ),
        SecretPattern(
            name="ssh_private_key",
            secret_type=SecretType.SSH,
            pattern=re.compile(r'-----BEGIN [A-Z ]+PRIVATE KEY-----', re.IGNORECASE),
            description="SSH Private Key",
            severity="critical"
        ),
        SecretPattern(
            name="rsa_private_key",
            secret_type=SecretType.PRIVATE_KEY,
            pattern=re.compile(r'-----BEGIN RSA PRIVATE KEY-----', re.IGNORECASE),
            description="RSA Private Key",
            severity="critical"
        ),
        SecretPattern(
            name="api_token",
            secret_type=SecretType.TOKEN,
            pattern=re.compile(r'(api[_-]?token|access[_-]?token)["\s:=]+["\s]+[a-zA-Z0-9_\-\.]{20,}', re.IGNORECASE),
            description="API Token",
            severity="high",
            false_positive_patterns=[r'"api_token"', r'"access_token"']
        ),
        SecretPattern(
            name="password_in_url",
            secret_type=SecretType.PASSWORD,
            pattern=re.compile(r'[?&](password|passwd|pwd)["\s:=]+["\s]+[^&\s]+', re.IGNORECASE),
            description="Password in URL",
            severity="high",
            false_positive_patterns=[r'password=', r'password=', r'example.com']
        ),
        SecretPattern(
            name="google_api_key",
            secret_type=SecretType.GOOGLE,
            pattern=re.compile(r'AIza[0-9A-Za-z\-_]{35}', re.IGNORECASE),
            description="Google API Key",
            severity="high"
        ),
        SecretPattern(
            name="azure_storage_key",
            secret_type=SecretType.AZURE,
            pattern=re.compile(r'[?&](storage[_-]?account[_-]?key|storage[_-]?connection[_-]?string)["\s:=]+["\s]+[a-zA-Z0-9\-]+', re.IGNORECASE),
            description="Azure Storage Key",
            severity="critical"
        ),
        SecretPattern(
            name="jwt_token",
            secret_type=SecretType.JWT,
            pattern=re.compile(r'eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+', re.IGNORECASE),
            description="JWT Token",
            severity="medium"
        ),
        SecretPattern(
            name="oauth_bearer",
            secret_type=SecretType.OAUTH,
            pattern=re.compile(r'Bearer [a-zA-Z0-9\-\.]{20,}', re.IGNORECASE),
            description="OAuth Bearer Token",
            severity="medium"
        ),
        SecretPattern(
            name="private_key_pem",
            secret_type=SecretType.PRIVATE_KEY,
            pattern=re.compile(r'-----BEGIN (EC |RSA |DSA |OPENSSH) PRIVATE KEY-----', re.IGNORECASE),
            description="PEM Private Key",
            severity="critical"
        ),
        SecretPattern(
            name="certificate",
            secret_type=SecretType.CERTIFICATE,
            pattern=re.compile(r'-----BEGIN (CERTIFICATE|TRUSTED CERTIFICATE)-----', re.IGNORECASE),
            description="SSL/TLS Certificate",
            severity="medium"
        ),
        SecretPattern(
            name="secret_key_generic",
            secret_type=SecretType.SECRET,
            pattern=re.compile(r'(secret[_-]?key|private[_-]?key|app[_-]?secret)["\s:=]+["\s]+[a-zA-Z0-9_\-]{20,}', re.IGNORECASE),
            description="Generic Secret Key",
            severity="high",
            false_positive_patterns=[r'"secret_key"', r'"private_key"', r'"app_secret"']
        ),
        SecretPattern(
            name="mailgun_key",
            secret_type=SecretType.API_KEY,
            pattern=re.compile(r'key-[a-f0-9]{32}', re.IGNORECASE),
            description="Mailgun API Key",
            severity="high"
        ),
        SecretPattern(
            name="stripe_api_key",
            secret_type=SecretType.API_KEY,
            pattern=re.compile(r'sk_(live|test)_[a-zA-Z0-9]{24}', re.IGNORECASE),
            description="Stripe API Key",
            severity="critical"
        ),
        SecretPattern(
            name="twilio_key",
            secret_type=SecretType.API_KEY,
            pattern=re.compile(r'AC[a-z0-9]{32}', re.IGNORECASE),
            description="Twilio API Key",
            severity="critical"
        ),
    ]
    
    SOURCE_EXTENSIONS = {
        '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs',
        '.cpp', '.c', '.cs', '.rb', '.php', '.swift', '.kt',
        '.sh', '.bash', '.zsh', '.ps1', '.psm1',
        '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg'
    }
    
    CONFIG_EXTENSIONS = {
        '.env', '.env.local', '.env.development', '.env.production',
        '.config', '.conf', '.ini', '.cfg',
        'secrets.json', 'config.json', 'credentials.json'
    }
    
    BINARY_SIGNATURES = {
        b'PK\x03\x04': 'zip',
        b'\x7fELF': 'elf',
        b'MZ': 'exe',
        b'\xca\xfe\xba\xbe': 'macho',
        b'\x89PNG': 'png',  # Not really binary but ignore
        b'GIF8': 'gif',  # Not really binary but ignore
    }
    
    IGNORED_DIRECTORIES = {
        '__pycache__', '.git', '.venv', 'venv', 'node_modules',
        '.pytest_cache', '.mypy_cache', 'build', 'dist', '.idea',
        '.vscode', 'target', 'bin', 'obj', 'out'
    }
    
    def __init__(
        self,
        project_path: Path,
        file_types: Optional[List[FileType]] = None,
        custom_patterns: Optional[List[SecretPattern]] = None,
        ignore_patterns: Optional[List[str]] = None,
        max_file_size_mb: int = 10
    ):
        """
        Initialize secret scanner.
        
        Args:
            project_path: Project root directory
            file_types: Types of files to scan (default: all)
            custom_patterns: Additional patterns to scan for
            ignore_patterns: Regex patterns to ignore
            max_file_size_mb: Maximum file size to scan (MB)
        """
        self.project_path = Path(project_path).resolve()
        self.file_types = file_types or [FileType.SOURCE, FileType.CONFIG, FileType.BINARY]
        self.patterns = custom_patterns or self.PATTERNS
        self.ignore_patterns = ignore_patterns or []
        self.max_file_size = max_file_size_mb * 1024 * 1024
        self._ignore_regex = [re.compile(p) for p in self.ignore_patterns]
    
    def scan(self) -> ScanResult:
        """
        Scan project for secrets.
        
        Returns:
            ScanResult with all findings
        """
        import time
        start_time = time.time()
        
        print(f"\n{'='*60}")
        print("SECRET SCANNER")
        print(f"{'='*60}")
        print(f"Project: {self.project_path}")
        print(f"File Types: {[ft.value for ft in self.file_types]}")
        print(f"Patterns: {len(self.patterns)}")
        print(f"{'='*60}\n")
        
        result = ScanResult(
            project_path=self.project_path,
            scan_duration_seconds=0,
            files_scanned=0
        )
        
        # Scan each file type
        if FileType.SOURCE in self.file_types:
            self._scan_source_files(result)
        if FileType.CONFIG in self.file_types:
            self._scan_config_files(result)
        if FileType.BINARY in self.file_types:
            self._scan_binary_files(result)
        
        # Remove false positives
        self._filter_false_positives(result)
        
        # Calculate duration
        result.scan_duration_seconds = time.time() - start_time
        
        # Print summary
        self._print_summary(result)
        
        return result
    
    def _scan_source_files(self, result: ScanResult) -> None:
        """Scan source code files."""
        print("Scanning source files...")
        
        for ext in self.SOURCE_EXTENSIONS:
            for file_path in self.project_path.rglob(f"*{ext}"):
                if self._should_skip_file(file_path):
                    continue
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        for line_num, line in enumerate(f, 1):
                            self._scan_line(line, line_num, file_path, FileType.SOURCE, result)
                except Exception as e:
                    print(f"  [ERROR] Failed to read {file_path}: {e}")
        
        result.files_scanned += len(list(self.project_path.rglob("*.py")))
    
    def _scan_config_files(self, result: ScanResult) -> None:
        """Scan configuration files."""
        print("Scanning configuration files...")
        
        for ext in self.CONFIG_EXTENSIONS:
            for file_path in self.project_path.rglob(f"*{ext}"):
                if self._should_skip_file(file_path):
                    continue
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        for line_num, line in enumerate(f, 1):
                            self._scan_line(line, line_num, file_path, FileType.CONFIG, result)
                except Exception as e:
                    print(f"  [ERROR] Failed to read {file_path}: {e}")
    
    def _scan_binary_files(self, result: ScanResult) -> None:
        """Scan binary files for potential secrets."""
        print("Scanning binary files...")
        
        # Common binary file extensions
        binary_extensions = ['.exe', '.dll', '.so', '.dylib', '.bin', '.o', '.a', '.lib']
        
        for ext in binary_extensions:
            for file_path in self.project_path.rglob(f"*{ext}"):
                if self._should_skip_file(file_path):
                    continue
                
                # Check file size
                if file_path.stat().st_size > self.max_file_size:
                    print(f"  [SKIP] File too large: {file_path}")
                    continue
                
                try:
                    with open(file_path, 'rb') as f:
                        data = f.read()
                        
                        # Check for string patterns in binary
                        self._scan_binary_data(data, file_path, result)
                except Exception as e:
                    print(f"  [ERROR] Failed to read {file_path}: {e}")
    
    def _should_skip_file(self, file_path: Path) -> bool:
        """Check if file should be skipped."""
        # Check ignored directories
        for part in file_path.parts:
            if part in self.IGNORED_DIRECTORIES:
                return True
        
        # Check custom ignore patterns
        for regex in self._ignore_regex:
            if regex.search(str(file_path)):
                return True
        
        # Check if file is too large
        try:
            if file_path.stat().st_size > self.max_file_size:
                return True
        except:
            return True
        
        return False
    
    def _scan_line(
        self,
        line: str,
        line_num: int,
        file_path: Path,
        file_type: FileType,
        result: ScanResult
    ) -> None:
        """Scan a single line for secrets."""
        for pattern in self.patterns:
            matches = pattern.pattern.finditer(line)
            for match in matches:
                matched_text = match.group()
                
                # Check false positive patterns
                is_false_positive = False
                for fp_pattern in pattern.false_positive_patterns:
                    if fp_pattern in matched_text:
                        is_false_positive = True
                        break
                
                if not is_false_positive:
                    secret = SecretMatch(
                        file_path=str(file_path),
                        line_number=line_num,
                        position=match.start(),
                        secret_type=pattern.secret_type,
                        pattern_name=pattern.name,
                        matched_text=matched_text,
                        context=self._get_context(line, match.start()),
                        file_type=file_type,
                        severity=pattern.severity,
                        is_binary=False
                    )
                    
                    result.add_secret(secret)
    
    def _scan_binary_data(
        self,
        data: bytes,
        file_path: Path,
        result: ScanResult
    ) -> None:
        """Scan binary data for secrets."""
        try:
            # Try to decode as text (UTF-8 or ASCII)
            text = data.decode('utf-8', errors='ignore')
        except:
            text = data.decode('ascii', errors='ignore')
        
        # Scan text version
        self._scan_line(text, None, file_path, FileType.BINARY, result)
    
    def _get_context(self, line: str, position: int) -> str:
        """Get context around a match."""
        start = max(0, position - 20)
        end = min(len(line), position + 20)
        return line[start:end]
    
    def _filter_false_positives(self, result: ScanResult) -> None:
        """Filter out false positives using heuristics."""
        true_secrets = []
        
        for secret in result.secrets_found:
            is_false_positive = False
            
            # Heuristic 1: Very short matches are likely false positives
            if len(secret.matched_text) < 10:
                is_false_positive = True
            
            # Heuristic 2: Common example values
            false_positive_values = [
                'your-api-key-here',
                'replace-with-your-key',
                'example.com',
                'test123',
                'changeme',
                'placeholder',
                'xxx'
            ]
            
            if any(fp.lower() in secret.matched_text.lower() for fp in false_positive_values):
                is_false_positive = True
            
            # Heuristic 3: Only alphanumeric and very common
            if secret.matched_text.isalnum() and len(secret.matched_text) > 30:
                is_false_positive = True
            
            if not is_false_positive:
                true_secrets.append(secret)
            else:
                result.false_positives += 1
        
        result.secrets_found = true_secrets
    
    def _print_summary(self, result: ScanResult) -> None:
        """Print scan summary."""
        print(f"\n{'='*60}")
        print("SCAN SUMMARY")
        print(f"{'='*60}")
        print(f"Duration: {result.scan_duration_seconds:.2f}s")
        print(f"Files Scanned: {result.files_scanned}")
        print(f"Secrets Found: {len(result.secrets_found)}")
        print(f"False Positives: {result.false_positives}")
        
        if result.by_severity:
            print(f"\nBy Severity:")
            for severity, count in sorted(result.by_severity.items()):
                print(f"  {severity}: {count}")
        
        if result.by_type:
            print(f"\nBy Type:")
            for secret_type, count in sorted(result.by_type.items()):
                print(f"  {secret_type}: {count}")
        
        print(f"\n{'='*60}")
        
        if len(result.secrets_found) > 0:
            print("⚠ SECRETS DETECTED ⚠")
            print("\nSecrets found in:")
            for secret in result.secrets_found:
                print(f"\n{secret.file_path}")
                print(f"  Line: {secret.line_number}")
                print(f"  Type: {secret.secret_type.value}")
                print(f"  Pattern: {secret.pattern_name}")
                print(f"  Severity: {secret.severity}")
                print(f"  Match: {secret.matched_text[:50]}")
        else:
            print("✓ NO SECRETS FOUND ✓")
            print("\nAll files are clean!")
    
    def to_json(self, result: ScanResult) -> str:
        """Export scan result to JSON."""
        return json.dumps({
            "scan_summary": result.summary(),
            "secrets": [s.to_dict() for s in result.secrets_found]
        }, indent=2, default=str)


def main():
    """CLI entry point for secret scanner."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Scan for secrets in project files")
    parser.add_argument(
        "--project-path",
        type=Path,
        default=Path.cwd(),
        help="Project directory (default: cwd)"
    )
    parser.add_argument(
        "--types",
        nargs="+",
        choices=["source", "config", "binary", "all"],
        default=["source", "config"],
        help="File types to scan (default: source config)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file for JSON report"
    )
    parser.add_argument(
        "--max-size",
        type=int,
        default=10,
        help="Maximum file size to scan in MB (default: 10)"
    )
    
    args = parser.parse_args()
    
    # Convert file types
    type_map = {
        "source": FileType.SOURCE,
        "config": FileType.CONFIG,
        "binary": FileType.BINARY,
        "all": FileType.ALL
    }
    
    file_types = [type_map[t] for t in args.types]
    
    # Create scanner
    scanner = SecretScanner(
        project_path=args.project_path,
        file_types=file_types,
        max_file_size_mb=args.max_size
    )
    
    # Run scan
    result = scanner.scan()
    
    # Output JSON if requested
    if args.output:
        with open(args.output, "w") as f:
            f.write(scanner.to_json(result))
        print(f"\nReport written to: {args.output}")
    
    # Exit with error if secrets found
    import sys
    sys.exit(1 if len(result.secrets_found) > 0 else 0)


if __name__ == "__main__":
    main()
