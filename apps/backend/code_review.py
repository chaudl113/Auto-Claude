"""
Built-in Code Review Module
===========================

Provides AI-powered code review with pre-commit and PR integration.

Features:
- Pre-commit hooks for AI review
- GitHub PR integration
- Review comment generation
- Code quality scoring
- Automated feedback
- Review templates
"""

import json
import subprocess
import sys
import asyncio
from pathlib import Path
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from functools import wraps

try:
    from claude_agent_sdk import Anthropic
    HAS_CLAUDE_SDK = True
except ImportError:
    HAS_CLAUDE_SDK = False


class ReviewSeverity(str, Enum):
    """Severity of review feedback."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ReviewCategory(str, Enum):
    """Categories of code review feedback."""
    CODE_QUALITY = "code_quality"
    SECURITY = "security"
    PERFORMANCE = "performance"
    STYLE = "style"
    DOCUMENTATION = "documentation"
    TESTING = "testing"
    BEST_PRACTICES = "best_practices"


@dataclass
class ReviewComment:
    """Single review comment for code."""
    file_path: str
    line_number: int
    end_line_number: Optional[int] = None
    severity: ReviewSeverity = ReviewSeverity.MEDIUM
    category: ReviewCategory = ReviewCategory.CODE_QUALITY
    message: str
    suggestion: Optional[str] = None
    code_snippet: Optional[str] = None
    rule_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "file_path": self.file_path,
            "line_number": self.line_number,
            "end_line_number": self.end_line_number,
            "severity": self.severity.value,
            "category": self.category.value,
            "message": self.message,
            "suggestion": self.suggestion,
            "code_snippet": self.code_snippet,
            "rule_id": self.rule_id
        }


@dataclass
class FileReview:
    """Review results for a single file."""
    file_path: str
    language: str
    comments: List[ReviewComment] = field(default_factory=list)
    overall_score: float = 100.0
    issues_by_severity: Dict[str, int] = field(default_factory=dict)
    issues_by_category: Dict[str, int] = field(default_factory=dict)
    
    @property
    def total_issues(self) -> int:
        """Get total number of issues."""
        return len(self.comments)
    
    @property
    def critical_issues(self) -> int:
        """Count critical issues."""
        return len([c for c in self.comments if c.severity == ReviewSeverity.CRITICAL])
    
    @property
    def has_critical_issues(self) -> bool:
        """Check if file has any critical issues."""
        return self.critical_issues > 0


@dataclass
class CodeReviewReport:
    """Complete code review report for a pull request or commit."""
    base_commit: str
    head_commit: str
    branch_name: str
    files_reviewed: Dict[str, FileReview] = field(default_factory=dict)
    total_files: int = 0
    total_issues: int = 0
    overall_score: float = 100.0
    reviewed_at: datetime = field(default_factory=datetime.now)
    review_duration_seconds: float = 0.0
    
    @property
    def summary(self) -> Dict[str, Any]:
        """Get review summary."""
        return {
            "total_files": self.total_files,
            "total_issues": self.total_issues,
            "overall_score": self.overall_score,
            "reviewed_at": self.reviewed_at.isoformat(),
            "review_duration": self.review_duration_seconds
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary."""
        return {
            "base_commit": self.base_commit,
            "head_commit": self.head_commit,
            "branch_name": self.branch_name,
            "files_reviewed": {
                path: {
                    "language": review.language,
                    "comments": [c.to_dict() for c in review.comments],
                    "overall_score": review.overall_score,
                    "issues_by_severity": review.issues_by_severity,
                    "issues_by_category": review.issues_by_category
                }
                for path, review in self.files_reviewed.items()
            },
            "total_files": self.total_files,
            "total_issues": self.total_issues,
            "overall_score": self.overall_score,
            "reviewed_at": self.reviewed_at.isoformat(),
            "review_duration_seconds": self.review_duration_seconds,
            "summary": self.summary
        }


class AIReviewer:
    """
    AI-powered code reviewer using Claude.
    
    Example:
        ```python
        from code_review import AIReviewer
        
        reviewer = AIReviewer(
            api_key="your-anthropic-api-key",
            model="claude-3-opus-20240229"
        )
        
        # Review a file
        report = await reviewer.review_file(
            file_path="src/main.py",
            context="Add error handling"
        )
        
        print(f"Score: {report.overall_score}")
        print(f"Issues: {report.total_issues}")
        
        for comment in report.comments:
            print(f"Line {comment.line_number}: {comment.message}")
        ```
    """
    
    REVIEW_PROMPT = """You are an expert code reviewer. Review the provided code and provide constructive feedback.

Analyze the code for:
1. Code quality (readability, maintainability)
2. Security vulnerabilities
3. Performance issues
4. Style consistency
5. Documentation
6. Testing coverage
7. Best practices

For each issue found, provide:
- Line number
- Severity (critical/high/medium/low/info)
- Category (code_quality/security/performance/style/documentation/testing/best_practices)
- Clear message
- Suggested fix

Return results as JSON:
{
    "comments": [
        {
            "file_path": "string",
            "line_number": number,
            "end_line_number": number (optional),
            "severity": "critical/high/medium/low/info",
            "category": "code_quality/security/performance/style/documentation/testing/best_practices",
            "message": "string",
            "suggestion": "string",
            "code_snippet": "string",
            "rule_id": "string"
        }
    ],
    "overall_score": 0-100,
    "summary": "string"
}

Be specific and actionable. If code is excellent, still score it high and provide positive feedback."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-sonnet-20240229"
    ):
        """
        Initialize AI reviewer.
        
        Args:
            api_key: Anthropic API key (if None, reads from env)
            model: Claude model to use
        """
        if not HAS_CLAUDE_SDK:
            raise ImportError(
                "claude-agent-sdk required. Install with: pip install claude-agent-sdk"
            )
        
        self.api_key = api_key
        self.model = model
        self._client: Optional[Anthropic] = None
    
    def _get_client(self) -> Anthropic:
        """Get or create Claude client."""
        if self._client is None:
            self._client = Anthropic(api_key=self.api_key)
        return self._client
    
    async def review_file(
        self,
        file_path: Path,
        context: Optional[str] = None,
        max_tokens: int = 4096
    ) -> FileReview:
        """
        Review a single file using AI.
        
        Args:
            file_path: Path to file to review
            context: Additional context for the review
            max_tokens: Maximum tokens for response
        
        Returns:
            FileReview with feedback
        """
        # Read file content
        with open(file_path) as f:
            content = f.read()
        
        # Detect language
        language = self._detect_language(file_path)
        
        # Build prompt
        prompt = self._build_prompt(content, language, context)
        
        # Get AI review
        client = self._get_client()
        
        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            review_text = response.content[0].text
            review_data = self._parse_review_response(review_text)
            
            # Build file review
            comments = []
            for comment_data in review_data.get("comments", []):
                comment = ReviewComment(
                    file_path=str(file_path),
                    line_number=comment_data.get("line_number", 0),
                    end_line_number=comment_data.get("end_line_number"),
                    severity=ReviewSeverity(comment_data.get("severity", "medium")),
                    category=ReviewCategory(comment_data.get("category", "code_quality")),
                    message=comment_data.get("message", ""),
                    suggestion=comment_data.get("suggestion"),
                    code_snippet=comment_data.get("code_snippet"),
                    rule_id=comment_data.get("rule_id")
                )
                comments.append(comment)
            
            # Calculate score and categorize issues
            file_review = FileReview(
                file_path=str(file_path),
                language=language,
                comments=comments,
                overall_score=review_data.get("overall_score", 100.0)
            )
            
            # Categorize issues
            for comment in comments:
                sev = comment.severity.value
                cat = comment.category.value
                file_review.issues_by_severity[sev] = file_review.issues_by_severity.get(sev, 0) + 1
                file_review.issues_by_category[cat] = file_review.issues_by_category.get(cat, 0) + 1
            
            return file_review
        
        except Exception as e:
            print(f"[AIReviewer] Error reviewing file {file_path}: {e}")
            return FileReview(
                file_path=str(file_path),
                language=language,
                comments=[],
                overall_score=0.0
            )
    
    async def review_changes(
        self,
        files_changed: List[Tuple[str, str, str]],  # (path, old_content, new_content)
        context: Optional[str] = None,
        max_tokens: int = 8192
    ) -> CodeReviewReport:
        """
        Review changed files (for PR reviews).
        
        Args:
            files_changed: List of (path, old_content, new_content) tuples
            context: PR/commit context
            max_tokens: Maximum tokens for response
        
        Returns:
            CodeReviewReport with all feedback
        """
        start_time = datetime.now()
        
        # Review each changed file
        files_reviewed = {}
        total_issues = 0
        total_score = 0.0
        
        for file_path, old_content, new_content in files_changed:
            path = Path(file_path)
            
            # Create diff prompt
            diff_prompt = self._build_diff_prompt(old_content, new_content, path, context)
            
            # Get AI review
            client = self._get_client()
            
            try:
                response = client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    messages=[
                        {
                            "role": "user",
                            "content": diff_prompt
                        }
                    ]
                )
                
                review_text = response.content[0].text
                review_data = self._parse_review_response(review_text)
                
                # Build file review
                comments = []
                for comment_data in review_data.get("comments", []):
                    comment = ReviewComment(
                        file_path=str(path),
                        line_number=comment_data.get("line_number", 0),
                        end_line_number=comment_data.get("end_line_number"),
                        severity=ReviewSeverity(comment_data.get("severity", "medium")),
                        category=ReviewCategory(comment_data.get("category", "code_quality")),
                        message=comment_data.get("message", ""),
                        suggestion=comment_data.get("suggestion"),
                        code_snippet=comment_data.get("code_snippet"),
                        rule_id=comment_data.get("rule_id")
                    )
                    comments.append(comment)
                
                file_review = FileReview(
                    file_path=str(path),
                    language=self._detect_language(path),
                    comments=comments,
                    overall_score=review_data.get("overall_score", 100.0)
                )
                
                # Categorize issues
                for comment in comments:
                    sev = comment.severity.value
                    cat = comment.category.value
                    file_review.issues_by_severity[sev] = file_review.issues_by_severity.get(sev, 0) + 1
                    file_review.issues_by_category[cat] = file_review.issues_by_category.get(cat, 0) + 1
                
                files_reviewed[str(path)] = file_review
                total_issues += file_review.total_issues
                total_score += file_review.overall_score
            
            except Exception as e:
                print(f"[AIReviewer] Error reviewing {file_path}: {e}")
                continue
        
        # Calculate overall score
        overall_score = total_score / len(files_changed) if files_changed else 100.0
        duration = (datetime.now() - start_time).total_seconds()
        
        return CodeReviewReport(
            base_commit="HEAD~1",  # Placeholder
            head_commit="HEAD",  # Placeholder
            branch_name="feature-branch",  # Placeholder
            files_reviewed=files_reviewed,
            total_files=len(files_changed),
            total_issues=total_issues,
            overall_score=overall_score,
            review_duration_seconds=duration
        )
    
    def _detect_language(self, file_path: Path) -> str:
        """Detect programming language from file extension."""
        ext = file_path.suffix.lower()
        
        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'jsx',
            '.tsx': 'tsx',
            '.go': 'go',
            '.rs': 'rust',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.cs': 'csharp',
            '.rb': 'ruby',
            '.php': 'php',
            '.swift': 'swift',
            '.kt': 'kotlin'
        }
        
        return language_map.get(ext, 'text')
    
    def _build_prompt(
        self,
        content: str,
        language: str,
        context: Optional[str]
    ) -> str:
        """Build review prompt for file content."""
        prompt = f"""Review the following {language} code:

```{language}
{content}
```
"""
        
        if context:
            prompt += f"\nContext: {context}\n"
        
        prompt += f"\n{self.REVIEW_PROMPT}"
        return prompt
    
    def _build_diff_prompt(
        self,
        old_content: str,
        new_content: str,
        file_path: Path,
        context: Optional[str]
    ) -> str:
        """Build review prompt for diff."""
        language = self._detect_language(file_path)
        
        prompt = f"""Review the following changes to {file_path}:

Language: {language}

OLD:
```{language}
{old_content}
```

NEW:
```{language}
{new_content}
```
"""
        
        if context:
            prompt += f"\nContext: {context}\n"
        
        prompt += f"\n{self.REVIEW_PROMPT}"
        return prompt
    
    def _parse_review_response(self, response_text: str) -> Dict[str, Any]:
        """Parse AI review response."""
        try:
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            
            if json_match:
                return json.loads(json_match.group())
            else:
                # Fallback: try parsing entire response
                return json.loads(response_text)
        
        except json.JSONDecodeError:
            # If JSON parsing fails, return minimal structure
            return {
                "comments": [],
                "overall_score": 100.0,
                "summary": "Failed to parse review response"
            }


class PreCommitHook:
    """
    Pre-commit hook for AI code review.
    
    Example:
        ```python
        from code_review import PreCommitHook
        
        hook = PreCommitHook(
            api_key="your-api-key"
        )
        
        # Run hook on staged files
        result = hook.run_staged()
        
        if result.has_critical_issues:
            print("Critical issues found. Commit blocked.")
            sys.exit(1)
        ```
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        block_on_critical: bool = True,
        block_on_high: bool = False,
        min_score: float = 60.0
    ):
        """
        Initialize pre-commit hook.
        
        Args:
            api_key: Anthropic API key
            block_on_critical: Block commits with critical issues
            block_on_high: Block commits with high issues
            min_score: Minimum score to pass
        """
        self.reviewer = AIReviewer(api_key=api_key)
        self.block_on_critical = block_on_critical
        self.block_on_high = block_on_high
        self.min_score = min_score
    
    def run_staged(self) -> CodeReviewReport:
        """Run review on all staged files."""
        # Get staged files
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True,
            text=True
        )
        
        staged_files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
        
        if not staged_files:
            print("No staged files to review.")
            return CodeReviewReport(
                base_commit="HEAD",
                head_commit="HEAD",
                branch_name="",
                files_reviewed={},
                total_files=0,
                total_issues=0,
                overall_score=100.0
            )
        
        # Get file contents
        files_to_review = []
        for file_path in staged_files:
            # Get old content
            old_result = subprocess.run(
                ["git", "show", f"HEAD:{file_path}"],
                capture_output=True,
                text=True
            )
            old_content = old_result.stdout if old_result.returncode == 0 else ""
            
            # Get new content (from index)
            new_result = subprocess.run(
                ["git", "show", f":{file_path}"],
                capture_output=True,
                text=True
            )
            new_content = new_result.stdout if new_result.returncode == 0 else ""
            
            files_to_review.append((file_path, old_content, new_content))
        
        # Run review
        return asyncio.run(self.reviewer.review_changes(files_to_review))
    
    def should_block(self, report: CodeReviewReport) -> bool:
        """Determine if commit should be blocked."""
        # Check for critical issues
        if self.block_on_critical:
            for file_review in report.files_reviewed.values():
                if file_review.has_critical_issues:
                    return True
        
        # Check for high issues
        if self.block_on_high:
            for file_review in report.files_reviewed.values():
                high_count = file_review.issues_by_severity.get("high", 0)
                if high_count > 0:
                    return True
        
        # Check minimum score
        if report.overall_score < self.min_score:
            return True
        
        return False


def main():
    """CLI entry point for code review."""
    import argparse
    
    parser = argparse.ArgumentParser(description="AI-powered code review")
    parser.add_argument(
        "--files",
        nargs="+",
        help="Files to review"
    )
    parser.add_argument(
        "--pre-commit",
        action="store_true",
        help="Run as pre-commit hook on staged files"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help="Anthropic API key"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="claude-3-sonnet-20240229",
        help="Claude model to use"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file for JSON report"
    )
    
    args = parser.parse_args()
    
    if args.pre_commit:
        # Run as pre-commit hook
        hook = PreCommitHook(api_key=args.api_key)
        report = hook.run_staged()
        
        if hook.should_block(report):
            print("\n⚠ CODE REVIEW FAILED ⚠")
            print(f"Overall Score: {report.overall_score:.1f}/100")
            print(f"Total Issues: {report.total_issues}")
            print("\nCommit blocked. Please fix issues and try again.")
            sys.exit(1)
        else:
            print("\n✓ CODE REVIEW PASSED ✓")
            print(f"Overall Score: {report.overall_score:.1f}/100")
            print(f"Total Issues: {report.total_issues}")
            sys.exit(0)
    
    elif args.files:
        # Review specific files
        import asyncio
        
        reviewer = AIReviewer(api_key=args.api_key, model=args.model)
        
        files_reviewed = {}
        total_issues = 0
        total_score = 0.0
        
        for file_path in args.files:
            path = Path(file_path)
            file_review = asyncio.run(reviewer.review_file(path))
            files_reviewed[str(path)] = file_review
            total_issues += file_review.total_issues
            total_score += file_review.overall_score
            
            print(f"\n{'='*60}")
            print(f"File: {path}")
            print(f"{'='*60}")
            print(f"Score: {file_review.overall_score:.1f}/100")
            print(f"Issues: {file_review.total_issues}")
            
            for comment in file_review.comments:
                print(f"\n{comment.severity.value.upper()} [{comment.category.value}]")
                print(f"  Line {comment.line_number}: {comment.message}")
                if comment.suggestion:
                    print(f"  Suggestion: {comment.suggestion}")
        
        overall_score = total_score / len(args.files) if args.files else 100.0
        
        report = CodeReviewReport(
            base_commit="",
            head_commit="",
            branch_name="",
            files_reviewed=files_reviewed,
            total_files=len(args.files),
            total_issues=total_issues,
            overall_score=overall_score
        )
        
        if args.output:
            with open(args.output, "w") as f:
                json.dump(report.to_dict(), f, indent=2, default=str)
            print(f"\nReport saved to: {args.output}")
    
    else:
        print("Error: No files specified. Use --files or --pre-commit")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
