"""
Enhanced Debug Logging Module
==============================

Provides structured logging with distributed tracing support.
Includes context tracking, log levels, and correlation IDs.

Features:
- Structured JSON logging
- Distributed tracing with correlation IDs
- Log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Context-aware logging (automatic request/transaction tracking)
- Performance timing
- Stack trace capture
"""

import json
import logging
import sys
import time
import traceback
import uuid
from contextvars import ContextVar
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, List, Callable
from functools import wraps


class LogLevel(str, Enum):
    """Log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogEntry:
    """Structured log entry."""
    
    def __init__(
        self,
        level: LogLevel,
        message: str,
        correlation_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        error: Optional[Exception] = None,
        stack_trace: Optional[str] = None,
        duration_ms: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.level = level
        self.message = message
        self.correlation_id = correlation_id or get_correlation_id()
        self.context = context or {}
        self.error = error
        self.stack_trace = stack_trace
        self.duration_ms = duration_ms
        self.metadata = metadata or {}
        self.timestamp = datetime.utcnow().isoformat()
        self.logger_name = get_logger_name()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert log entry to dictionary."""
        entry = {
            "timestamp": self.timestamp,
            "level": self.level,
            "message": self.message,
            "logger": self.logger_name,
            "correlation_id": self.correlation_id
        }
        
        if self.context:
            entry["context"] = self.context
        
        if self.error:
            entry["error"] = {
                "type": type(self.error).__name__,
                "message": str(self.error)
            }
            if self.stack_trace:
                entry["error"]["stack_trace"] = self.stack_trace
        
        if self.duration_ms is not None:
            entry["duration_ms"] = round(self.duration_ms, 2)
        
        if self.metadata:
            entry["metadata"] = self.metadata
        
        return entry
    
    def to_json(self) -> str:
        """Convert log entry to JSON string."""
        return json.dumps(self.to_dict(), indent=None, default=str)


# Context variables for distributed tracing
correlation_id_var: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)
logger_name_var: ContextVar[Optional[str]] = ContextVar('logger_name', default=None)
trace_context_var: ContextVar[Dict[str, Any]] = ContextVar('trace_context', default={})


def get_correlation_id() -> str:
    """Get or create correlation ID for current context."""
    cid = correlation_id_var.get()
    if cid is None:
        cid = str(uuid.uuid4())
        correlation_id_var.set(cid)
    return cid


def get_logger_name() -> str:
    """Get logger name for current context."""
    return logger_name_var.get() or "auto-claude"


def get_trace_context() -> Dict[str, Any]:
    """Get current trace context."""
    return trace_context_var.get()


def set_correlation_id(cid: str) -> None:
    """Set correlation ID for current context."""
    correlation_id_var.set(cid)


def set_trace_context(key: str, value: Any) -> None:
    """Set a value in trace context."""
    context = trace_context_var.get()
    context[key] = value
    trace_context_var.set(context)


class StructuredLogger:
    """
    Structured logger with distributed tracing support.
    
    Example:
        ```python
        from debug_logging import StructuredLogger, LogLevel
        
        logger = StructuredLogger(__name__)
        
        logger.info("Starting task", context={"task_id": "123"})
        logger.warning("Cache miss", metadata={"cache_key": "users"})
        logger.error("Database connection failed", error=ex)
        ```
    """
    
    def __init__(self, name: str, output_file: Optional[Path] = None):
        """
        Initialize structured logger.
        
        Args:
            name: Logger name
            output_file: Optional file to write logs to (in addition to stdout)
        """
        self.name = name
        self.output_file = output_file
        self._handlers: List[logging.Handler] = []
        
        # Setup Python logging backend
        self._python_logger = logging.getLogger(name)
        self._python_logger.setLevel(logging.DEBUG)
        
        # Add stdout handler
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setLevel(logging.DEBUG)
        self._python_logger.addHandler(stdout_handler)
        self._handlers.append(stdout_handler)
        
        # Add file handler if specified
        if output_file:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(str(output_file))
            file_handler.setLevel(logging.DEBUG)
            self._python_logger.addHandler(file_handler)
            self._handlers.append(file_handler)
    
    def _log(
        self,
        level: LogLevel,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        error: Optional[Exception] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Internal log method."""
        # Merge trace context into context
        trace_context = get_trace_context()
        merged_context = {**trace_context, **(context or {})}
        
        # Get stack trace if error
        stack_trace = None
        if error:
            stack_trace = "".join(traceback.format_exception(
                type(error), error, error.__traceback__
            ))
        
        # Create log entry
        entry = LogEntry(
            level=level,
            message=message,
            context=merged_context,
            error=error,
            stack_trace=stack_trace,
            metadata=metadata
        )
        
        # Output JSON log
        log_line = entry.to_json()
        
        # Also output to Python logger for backward compatibility
        python_level = {
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.INFO: logging.INFO,
            LogLevel.WARNING: logging.WARNING,
            LogLevel.ERROR: logging.ERROR,
            LogLevel.CRITICAL: logging.CRITICAL
        }[level]
        
        self._python_logger.log(python_level, log_line)
    
    def debug(self, message: str, context: Optional[Dict[str, Any]] = None, **metadata) -> None:
        """Log debug message."""
        self._log(LogLevel.DEBUG, message, context=context, metadata=metadata)
    
    def info(self, message: str, context: Optional[Dict[str, Any]] = None, **metadata) -> None:
        """Log info message."""
        self._log(LogLevel.INFO, message, context=context, metadata=metadata)
    
    def warning(self, message: str, context: Optional[Dict[str, Any]] = None, **metadata) -> None:
        """Log warning message."""
        self._log(LogLevel.WARNING, message, context=context, metadata=metadata)
    
    def error(
        self,
        message: str,
        error: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
        **metadata
    ) -> None:
        """Log error message."""
        self._log(LogLevel.ERROR, message, error=error, context=context, metadata=metadata)
    
    def critical(
        self,
        message: str,
        error: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
        **metadata
    ) -> None:
        """Log critical message."""
        self._log(LogLevel.CRITICAL, message, error=error, context=context, metadata=metadata)


def get_logger(name: str, output_file: Optional[Path] = None) -> StructuredLogger:
    """
    Get or create a structured logger.
    
    Args:
        name: Logger name
        output_file: Optional log file path
    
    Returns:
        StructuredLogger instance
    """
    return StructuredLogger(name, output_file)


def trace_operation(operation_name: str):
    """
    Decorator to trace an operation with timing and context.
    
    Example:
        ```python
        from debug_logging import trace_operation
        
        @trace_operation("user_lookup")
        def get_user(user_id):
            return db.query(user_id)
        
        # Logs:
        # DEBUG: Starting operation: user_lookup
        # DEBUG: Completed operation: user_lookup (125ms)
        ```
    """
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            correlation_id = get_correlation_id()
            
            logger.debug(
                f"Starting operation: {operation_name}",
                context={"operation": operation_name, "status": "starting"}
            )
            
            start_time = time.time()
            try:
                set_trace_context("operation", operation_name)
                set_trace_context("status", "running")
                
                result = await func(*args, **kwargs)
                
                duration = (time.time() - start_time) * 1000
                logger.debug(
                    f"Completed operation: {operation_name}",
                    context={"operation": operation_name, "status": "completed"},
                    duration_ms=duration
                )
                
                return result
            except Exception as e:
                duration = (time.time() - start_time) * 1000
                logger.error(
                    f"Failed operation: {operation_name}",
                    error=e,
                    context={"operation": operation_name, "status": "failed"},
                    duration_ms=duration
                )
                raise
            finally:
                set_trace_context("operation", None)
                set_trace_context("status", None)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            
            logger.debug(
                f"Starting operation: {operation_name}",
                context={"operation": operation_name, "status": "starting"}
            )
            
            start_time = time.time()
            try:
                set_trace_context("operation", operation_name)
                set_trace_context("status", "running")
                
                result = func(*args, **kwargs)
                
                duration = (time.time() - start_time) * 1000
                logger.debug(
                    f"Completed operation: {operation_name}",
                    context={"operation": operation_name, "status": "completed"},
                    duration_ms=duration
                )
                
                return result
            except Exception as e:
                duration = (time.time() - start_time) * 1000
                logger.error(
                    f"Failed operation: {operation_name}",
                    error=e,
                    context={"operation": operation_name, "status": "failed"},
                    duration_ms=duration
                )
                raise
            finally:
                set_trace_context("operation", None)
                set_trace_context("status", None)
        
        # Return appropriate wrapper based on whether function is async
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


# Lazy import for asyncio
import asyncio


class TracingContext:
    """
    Context manager for distributed tracing.
    
    Example:
        ```python
        from debug_logging import TracingContext
        
        with TracingContext("task_execution", task_id="123"):
            # All logs in this block will have task_id in context
            logger.info("Processing task")
        ```
    """
    
    def __init__(self, operation: str, **context):
        self.operation = operation
        self.context = context
        self.logger = None
        self._old_correlation_id = None
        self._old_context = {}
    
    def __enter__(self):
        self.logger = get_logger("tracing")
        
        # Create new correlation ID for this trace
        self._old_correlation_id = correlation_id_var.get()
        new_correlation_id = str(uuid.uuid4())
        set_correlation_id(new_correlation_id)
        
        # Save old context and set new context
        self._old_context = trace_context_var.get()
        new_context = {**self._old_context, **self.context}
        trace_context_var.set(new_context)
        
        self.logger.debug(
            f"Entering trace: {self.operation}",
            context=self.context,
            correlation_id=new_correlation_id
        )
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = 0
        
        if exc_type:
            self.logger.error(
                f"Trace failed: {self.operation}",
                error=exc_val if exc_val else Exception("Unknown error"),
                context={"operation": self.operation}
            )
        else:
            self.logger.debug(
                f"Exiting trace: {self.operation}",
                context={"operation": self.operation}
            )
        
        # Restore old context
        if self._old_correlation_id:
            set_correlation_id(self._old_correlation_id)
        trace_context_var.set(self._old_context)
        
        return False


if __name__ == "__main__":
    # Test structured logging
    import os
    from pathlib import Path
    
    log_file = Path(__file__).parent / "test_logs.json"
    logger = get_logger("test", output_file=log_file)
    
    print("Testing structured logging...")
    
    # Test basic logging
    logger.info("Application started", metadata={"version": "1.0.0"})
    logger.warning("Configuration not found", context={"config_key": "API_KEY"})
    
    # Test with correlation ID
    set_correlation_id("test-correlation-123")
    logger.info("Processing request", context={"request_id": "456"})
    
    # Test error logging
    try:
        raise ValueError("Test error")
    except Exception as e:
        logger.error("Something went wrong", error=e, context={"user_id": "789"})
    
    # Test with tracing context
    with TracingContext("test_operation", param1="value1", param2="value2"):
        logger.info("Inside tracing context")
        logger.debug("Debug message in trace")
    
    print(f"\nLogs written to: {log_file}")
    print("\nSample log output:")
    print(log_file.read_text()[-500:] if log_file.exists() else "")
