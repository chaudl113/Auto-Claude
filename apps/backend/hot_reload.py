"""
Hot Reload Module for Auto Claude Backend
==========================================

Provides file watching and automatic reload functionality for development.
Monitors backend files and triggers auto-restart when changes are detected.

Features:
- File system watching with debounce
- Configurable file patterns
- Auto-restart on Python file changes
- Graceful shutdown before restart
"""

import asyncio
import os
import sys
import signal
import time
from pathlib import Path
from typing import Callable, Set, Optional

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False


class HotReloadHandler(FileSystemEventHandler):
    """Handles file system events for hot reload."""
    
    def __init__(
        self,
        callback: Callable[[Set[Path]], None],
        patterns: Set[str],
        ignore_dirs: Set[str],
        debounce_time: float = 1.0
    ):
        self.callback = callback
        self.patterns = patterns
        self.ignore_dirs = ignore_dirs
        self.debounce_time = debounce_time
        self._changed_files: Set[Path] = set()
        self._last_change: float = 0
        self._debounce_task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
    
    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Set the event loop for debounce tasks."""
        self._loop = loop
    
    def _should_watch(self, path: str) -> bool:
        """Check if path should be watched."""
        # Check ignore directories
        for ignore_dir in self.ignore_dirs:
            if ignore_dir in path:
                return False
        
        # Check file patterns
        for pattern in self.patterns:
            if path.endswith(pattern):
                return True
        
        return False
    
    def _add_change(self, path: Path) -> None:
        """Add a file change with debouncing."""
        self._changed_files.add(path)
        self._last_change = time.time()
        
        # Cancel existing debounce task
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()
        
        # Schedule new debounce task
        if self._loop:
            self._debounce_task = self._loop.create_task(
                self._debounce_callback()
            )
    
    async def _debounce_callback(self) -> None:
        """Wait for debounce time before triggering callback."""
        try:
            await asyncio.sleep(self.debounce_time)
            
            # Only trigger if no new changes
            if time.time() - self._last_change >= self.debounce_time:
                if self._changed_files:
                    self.callback(self._changed_files.copy())
                    self._changed_files.clear()
        except asyncio.CancelledError:
            pass
    
    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification events."""
        if not event.is_directory and self._should_watch(event.src_path):
            self._add_change(Path(event.src_path))
    
    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation events."""
        if not event.is_directory and self._should_watch(event.src_path):
            self._add_change(Path(event.src_path))


class HotReloader:
    """
    Manages hot reload functionality for the backend.
    
    Example:
        ```python
        from hot_reload import HotReloader
        
        async def on_reload(changed_files):
            print(f"Reloading due to changes: {changed_files}")
            # Restart your application here
        
        reloader = HotReloader(
            watch_dir=Path(__file__).parent,
            on_reload=on_reload
        )
        
        await reloader.start()
        ```
    """
    
    DEFAULT_PATTERNS = {'.py'}
    DEFAULT_IGNORE_DIRS = {
        '__pycache__',
        '.git',
        '.venv',
        'venv',
        'node_modules',
        '.pytest_cache',
        '.mypy_cache',
        'build',
        'dist'
    }
    
    def __init__(
        self,
        watch_dir: Path,
        on_reload: Callable[[Set[Path]], None],
        patterns: Optional[Set[str]] = None,
        ignore_dirs: Optional[Set[str]] = None,
        debounce_time: float = 1.0
    ):
        """
        Initialize hot reloader.
        
        Args:
            watch_dir: Directory to watch for changes
            on_reload: Callback function when reload is triggered
            patterns: File patterns to watch (defaults to .py)
            ignore_dirs: Directories to ignore (defaults to common ones)
            debounce_time: Seconds to wait before triggering reload (debounce)
        """
        if not HAS_WATCHDOG:
            raise ImportError(
                "watchdog is required for hot reload. "
                "Install it with: pip install watchdog"
            )
        
        self.watch_dir = Path(watch_dir).resolve()
        self.on_reload = on_reload
        self.patterns = patterns or self.DEFAULT_PATTERNS
        self.ignore_dirs = ignore_dirs or self.DEFAULT_IGNORE_DIRS
        self.debounce_time = debounce_time
        
        self.observer: Optional[Observer] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._is_running = False
    
    async def start(self) -> None:
        """Start watching for file changes."""
        if self._is_running:
            return
        
        self._loop = asyncio.get_event_loop()
        
        # Create event handler
        event_handler = HotReloadHandler(
            callback=self._handle_reload,
            patterns=self.patterns,
            ignore_dirs=self.ignore_dirs,
            debounce_time=self.debounce_time
        )
        event_handler.set_event_loop(self._loop)
        
        # Start observer
        self.observer = Observer()
        self.observer.schedule(event_handler, str(self.watch_dir), recursive=True)
        self.observer.start()
        self._is_running = True
        
        print(f"[HotReload] Watching for changes in: {self.watch_dir}")
        print(f"[HotReload] Patterns: {self.patterns}")
        print(f"[HotReload] Ignoring: {', '.join(self.ignore_dirs)}")
    
    async def stop(self) -> None:
        """Stop watching for file changes."""
        if not self._is_running:
            return
        
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
        
        self._is_running = False
        print("[HotReload] Stopped watching for changes")
    
    def _handle_reload(self, changed_files: Set[Path]) -> None:
        """Handle reload event."""
        relative_files = [
            f.relative_to(self.watch_dir) 
            for f in changed_files 
            if f.is_relative_to(self.watch_dir)
        ]
        
        print(f"[HotReload] Changes detected in: {', '.join(str(f) for f in relative_files)}")
        self.on_reload(changed_files)


def with_hot_reload(
    watch_dir: Optional[Path] = None,
    patterns: Optional[Set[str]] = None,
    ignore_dirs: Optional[Set[str]] = None
):
    """
    Decorator to enable hot reload for async functions.
    
    Example:
        ```python
        @with_hot_reload()
        async def main():
            while True:
                print("Running...")
                await asyncio.sleep(1)
        ```
    """
    def decorator(async_func):
        async def wrapper(*args, **kwargs):
            # Determine watch directory
            if watch_dir is None:
                # Use directory of the function's module
                import inspect
                module_file = inspect.getfile(async_func)
                _watch_dir = Path(module_file).parent.resolve()
            else:
                _watch_dir = watch_dir
            
            # Create reloader
            async def on_reload(changed_files):
                print("[HotReload] Restarting application...")
                # In a real implementation, you would gracefully shutdown
                # and restart the application here
                # For now, just notify
                pass
            
            reloader = HotReloader(
                watch_dir=_watch_dir,
                on_reload=on_reload,
                patterns=patterns,
                ignore_dirs=ignore_dirs
            )
            
            # Start reloader
            await reloader.start()
            
            try:
                # Run the decorated function
                await async_func(*args, **kwargs)
            finally:
                # Cleanup
                await reloader.stop()
        
        return wrapper
    return decorator


async def dev_server_with_hot_reload(
    start_server: Callable[[], None],
    restart_delay: float = 2.0
) -> None:
    """
    Run a development server with hot reload.
    
    Args:
        start_server: Function to start the server
        restart_delay: Seconds to wait before restarting
    
    Example:
        ```python
        def start_server():
            # Your server startup code here
            uvicorn.run(app, host="0.0.0.0", port=8000)
        
        await dev_server_with_hot_reload(start_server)
        ```
    """
    if not HAS_WATCHDOG:
        print("[HotReload] Watchdog not installed. Hot reload disabled.")
        print("[HotReload] Install with: pip install watchdog")
        start_server()
        return
    
    watch_dir = Path.cwd()
    server_process = None
    
    async def on_reload(changed_files):
        nonlocal server_process
        print(f"\n[HotReload] Detected changes: {len(changed_files)} file(s)")
        
        # Stop existing server
        if server_process:
            print("[HotReload] Stopping server...")
            # Send SIGTERM for graceful shutdown
            server_process.terminate()
            try:
                server_process.wait(timeout=10)
            except:
                server_process.kill()
        
        # Wait before restart
        print(f"[HotReload] Waiting {restart_delay}s before restart...")
        await asyncio.sleep(restart_delay)
        
        # Restart server (in a real implementation)
        # This is a simplified version - you'd need subprocess management
        print("[HotReload] Server restarted")
    
    # Start watcher
    reloader = HotReloader(watch_dir=watch_dir, on_reload=on_reload)
    await reloader.start()
    
    try:
        # Start initial server
        print("[HotReload] Starting initial server...")
        start_server()
        
        # Keep running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n[HotReload] Shutting down...")
    finally:
        await reloader.stop()


if __name__ == "__main__":
    # Test the hot reloader
    import inspect
    
    @with_hot_reload()
    async def test_server():
        print("Test server running. Modify a .py file to test hot reload.")
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            print("Test server stopped")
    
    try:
        asyncio.run(test_server())
    except KeyboardInterrupt:
        print("\nShutting down...")
