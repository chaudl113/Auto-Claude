"""
Real-time Terminal Sharing Module
================================

Enables collaborative debugging through terminal session sharing.

Features:
- WebSocket-based terminal sharing
- Multi-user terminal sessions
- Session management
- Read-only/viewer modes
- Session recording and playback
"""

import asyncio
import json
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
from collections import deque

try:
    import websockets
    import websockets.server
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False


class SessionRole(str, Enum):
    """Role of user in terminal session."""
    OWNER = "owner"  # Full control
    COLLABORATOR = "collaborator"  # Can type and view
    VIEWER = "viewer"  # Read-only


class SessionStatus(str, Enum):
    """Status of terminal sharing session."""
    ACTIVE = "active"
    PAUSED = "paused"
    TERMINATED = "terminated"
    RECORDING = "recording"


@dataclass
class TerminalSession:
    """Represents a shared terminal session."""
    session_id: str
    owner_id: str
    project_path: str
    created_at: datetime
    status: SessionStatus = SessionStatus.ACTIVE
    participants: Dict[str, SessionRole] = field(default_factory=dict)
    commands: List[Dict[str, Any]] = field(default_factory=list)
    is_recording: bool = False
    recording_file: Optional[Path] = None
    max_participants: int = 10
    
    @property
    def participant_count(self) -> int:
        """Get number of participants."""
        return len(self.participants)
    
    @property
    def is_full(self) -> bool:
        """Check if session is at capacity."""
        return len(self.participants) >= self.max_participants
    
    def can_join(self) -> bool:
        """Check if new participant can join."""
        return self.status == SessionStatus.ACTIVE and not self.is_full
    
    def add_participant(self, user_id: str, role: SessionRole) -> bool:
        """Add a participant to the session."""
        if self.is_full:
            return False
        self.participants[user_id] = role
        return True
    
    def remove_participant(self, user_id: str) -> None:
        """Remove a participant from the session."""
        self.participants.pop(user_id, None)
    
    def has_role(self, user_id: str, role: SessionRole) -> bool:
        """Check if user has specific role."""
        return self.participants.get(user_id) == role


@dataclass
class TerminalMessage:
    """Message in terminal session."""
    message_id: str
    session_id: str
    sender_id: str
    message_type: str  # "output", "input", "command", "error", "system"
    content: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


class TerminalSharingServer:
    """
    WebSocket server for terminal sharing.
    
    Example:
        ```python
        from terminal_sharing import TerminalSharingServer
        
        server = TerminalSharingServer(host="localhost", port=8765)
        
        async def on_command(session_id, command, user_id):
            print(f"Command from {user_id}: {command}")
            # Execute command and send output back
        
        server.on_command = on_command
        
        await server.start()
        ```
    """
    
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8765,
        max_sessions: int = 10
    ):
        """
        Initialize terminal sharing server.
        
        Args:
            host: Host to bind to
            port: Port to listen on
            max_sessions: Maximum concurrent sessions
        """
        if not HAS_WEBSOCKETS:
            raise ImportError(
                "websockets library required. Install with: pip install websockets"
            )
        
        self.host = host
        self.port = port
        self.max_sessions = max_sessions
        
        self.sessions: Dict[str, TerminalSession] = {}
        self.clients: Dict[str, websockets.server.WebSocketServerProtocol] = {}
        self.session_to_clients: Dict[str, Set[str]] = {}
        
        # Event handlers
        self.on_command: Optional[callable] = None
        self.on_output: Optional[callable] = None
        self.on_join: Optional[callable] = None
        self.on_leave: Optional[callable] = None
        
        self._server: Optional[websockets.server.serve] = None
    
    async def start(self) -> None:
        """Start the terminal sharing server."""
        print(f"[TerminalSharing] Starting server on {self.host}:{self.port}")
        
        async def handler(websocket, path):
            await self._handle_client(websocket)
        
        self._server = websockets.server.serve(handler, self.host, self.port)
        print(f"[TerminalSharing] Server started successfully")
    
    async def stop(self) -> None:
        """Stop the terminal sharing server."""
        print("[TerminalSharing] Stopping server...")
        
        # Close all connections
        for client in self.clients.values():
            await client.close()
        
        # Stop server
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        
        print("[TerminalSharing] Server stopped")
    
    async def _handle_client(
        self,
        websocket: websockets.server.WebSocketServerProtocol
    ) -> None:
        """Handle a new client connection."""
        client_id = str(uuid.uuid4())
        self.clients[client_id] = websocket
        
        print(f"[TerminalSharing] Client connected: {client_id}")
        
        try:
            # Handle messages from client
            async for message in websocket:
                await self._handle_message(client_id, message)
        except websockets.exceptions.ConnectionClosed:
            print(f"[TerminalSharing] Client disconnected: {client_id}")
        finally:
            await self._cleanup_client(client_id)
    
    async def _handle_message(self, client_id: str, message: str) -> None:
        """Handle a message from a client."""
        try:
            data = json.loads(message)
            message_type = data.get("type", "")
            
            if message_type == "create_session":
                await self._handle_create_session(client_id, data)
            elif message_type == "join_session":
                await self._handle_join_session(client_id, data)
            elif message_type == "leave_session":
                await self._handle_leave_session(client_id, data)
            elif message_type == "terminal_input":
                await self._handle_terminal_input(client_id, data)
            elif message_type == "terminal_output":
                await self._handle_terminal_output(client_id, data)
            elif message_type == "request_participants":
                await self._handle_request_participants(client_id, data)
            else:
                print(f"[TerminalSharing] Unknown message type: {message_type}")
        
        except json.JSONDecodeError:
            print(f"[TerminalSharing] Invalid JSON from client {client_id}")
    
    async def _handle_create_session(self, client_id: str, data: Dict[str, Any]) -> None:
        """Handle session creation request."""
        project_path = data.get("project_path")
        max_participants = data.get("max_participants", 10)
        is_recording = data.get("is_recording", False)
        
        session_id = str(uuid.uuid4())
        session = TerminalSession(
            session_id=session_id,
            owner_id=client_id,
            project_path=project_path,
            created_at=datetime.now(),
            max_participants=max_participants,
            is_recording=is_recording
        )
        
        # Add owner as participant
        session.add_participant(client_id, SessionRole.OWNER)
        
        self.sessions[session_id] = session
        self.session_to_clients[session_id] = {client_id}
        
        # Send session created response
        response = {
            "type": "session_created",
            "session_id": session_id,
            "status": session.status.value,
            "participant_id": client_id,
            "role": SessionRole.OWNER.value
        }
        
        await self._send_to_client(client_id, response)
        
        # Call join handler
        if self.on_join:
            await self.on_join(session_id, client_id, SessionRole.OWNER)
    
    async def _handle_join_session(self, client_id: str, data: Dict[str, Any]) -> None:
        """Handle session join request."""
        session_id = data.get("session_id")
        
        if session_id not in self.sessions:
            response = {
                "type": "error",
                "message": "Session not found"
            }
            await self._send_to_client(client_id, response)
            return
        
        session = self.sessions[session_id]
        
        if not session.can_join():
            response = {
                "type": "error",
                "message": f"Cannot join session: {session.status.value}"
            }
            await self._send_to_client(client_id, response)
            return
        
        # Determine role (default to viewer)
        role = SessionRole(data.get("role", SessionRole.VIEWER.value))
        if not isinstance(role, SessionRole):
            role = SessionRole.VIEWER
        
        # Add participant
        if not session.add_participant(client_id, role):
            response = {
                "type": "error",
                "message": "Session is full"
            }
            await self._send_to_client(client_id, response)
            return
        
        # Update session participants
        self.session_to_clients[session_id].add(client_id)
        
        # Send join response
        response = {
            "type": "session_joined",
            "session_id": session_id,
            "status": session.status.value,
            "participant_id": client_id,
            "role": role.value,
            "project_path": session.project_path
        }
        
        await self._send_to_client(client_id, response)
        
        # Notify other participants
        notification = {
            "type": "participant_joined",
            "participant_id": client_id,
            "role": role.value
        }
        
        await self._broadcast_to_session(session_id, notification, exclude=client_id)
        
        # Send terminal history to new participant
        await self._send_terminal_history(client_id, session)
        
        # Call join handler
        if self.on_join:
            await self.on_join(session_id, client_id, role)
    
    async def _handle_leave_session(self, client_id: str, data: Dict[str, Any]) -> None:
        """Handle session leave request."""
        session_id = data.get("session_id")
        
        if session_id not in self.sessions:
            return
        
        session = self.sessions[session_id]
        role = session.participants.get(client_id)
        
        session.remove_participant(client_id)
        self.session_to_clients[session_id].discard(client_id)
        
        # Notify other participants
        notification = {
            "type": "participant_left",
            "participant_id": client_id,
            "role": role.value if role else None
        }
        
        await self._broadcast_to_session(session_id, notification, exclude=client_id)
        
        # Call leave handler
        if self.on_leave:
            await self.on_leave(session_id, client_id)
        
        # Terminate session if no participants
        if session.participant_count == 0:
            session.status = SessionStatus.TERMINATED
            await self._broadcast_to_session(session_id, {
                "type": "session_terminated",
                "session_id": session_id
            })
    
    async def _handle_terminal_input(self, client_id: str, data: Dict[str, Any]) -> None:
        """Handle terminal input from participant."""
        session_id = data.get("session_id")
        input_data = data.get("input", "")
        
        if session_id not in self.sessions:
            return
        
        session = self.sessions[session_id]
        role = session.participants.get(client_id)
        
        # Only owners and collaborators can send input
        if role in [SessionRole.OWNER, SessionRole.COLLABORATOR]:
            # Record command
            session.commands.append({
                "sender_id": client_id,
                "input": input_data,
                "timestamp": datetime.now().isoformat()
            })
            
            # Broadcast to all participants
            message = {
                "type": "terminal_input",
                "sender_id": client_id,
                "role": role.value,
                "input": input_data,
                "timestamp": datetime.now().isoformat()
            }
            
            await self._broadcast_to_session(session_id, message)
            
            # Call command handler
            if self.on_command:
                await self.on_command(session_id, input_data, client_id)
    
    async def _handle_terminal_output(self, client_id: str, data: Dict[str, Any]) -> None:
        """Handle terminal output (from terminal owner)."""
        session_id = data.get("session_id")
        output_data = data.get("output", "")
        
        if session_id not in self.sessions:
            return
        
        session = self.sessions[session_id]
        
        # Only owner can send output
        if session.participants.get(client_id) == SessionRole.OWNER:
            # Record output
            session.commands.append({
                "type": "output",
                "content": output_data,
                "timestamp": datetime.now().isoformat()
            })
            
            # Broadcast to all participants
            message = {
                "type": "terminal_output",
                "output": output_data,
                "timestamp": datetime.now().isoformat()
            }
            
            await self._broadcast_to_session(session_id, message)
            
            # Call output handler
            if self.on_output:
                await self.on_output(session_id, output_data)
    
    async def _handle_request_participants(self, client_id: str, data: Dict[str, Any]) -> None:
        """Handle request for participant list."""
        session_id = data.get("session_id")
        
        if session_id not in self.sessions:
            return
        
        session = self.sessions[session_id]
        
        participants = [
            {
                "participant_id": pid,
                "role": role.value
            }
            for pid, role in session.participants.items()
        ]
        
        response = {
            "type": "participants_list",
            "session_id": session_id,
            "participants": participants
        }
        
        await self._send_to_client(client_id, response)
    
    async def _send_to_client(self, client_id: str, message: Dict[str, Any]) -> None:
        """Send a message to a specific client."""
        if client_id in self.clients:
            try:
                await self.clients[client_id].send(json.dumps(message))
            except websockets.exceptions.ConnectionClosed:
                await self._cleanup_client(client_id)
    
    async def _broadcast_to_session(
        self,
        session_id: str,
        message: Dict[str, Any],
        exclude: Optional[str] = None
    ) -> None:
        """Broadcast a message to all participants in a session."""
        if session_id not in self.session_to_clients:
            return
        
        for client_id in self.session_to_clients[session_id].copy():
            if client_id != exclude and client_id in self.clients:
                try:
                    await self.clients[client_id].send(json.dumps(message))
                except websockets.exceptions.ConnectionClosed:
                    await self._cleanup_client(client_id)
    
    async def _send_terminal_history(self, client_id: str, session: TerminalSession) -> None:
        """Send terminal history to a participant."""
        history = {
            "type": "terminal_history",
            "session_id": session.session_id,
            "history": session.commands
        }
        
        await self._send_to_client(client_id, history)
    
    async def _cleanup_client(self, client_id: str) -> None:
        """Clean up a disconnected client."""
        # Remove from all sessions
        for session_id, clients in self.session_to_clients.items():
            clients.discard(client_id)
            
            # Remove from session participants
            if session_id in self.sessions:
                self.sessions[session_id].remove_participant(client_id)
        
        # Remove client
        if client_id in self.clients:
            del self.clients[client_id]


class TerminalSharingClient:
    """
    Client for connecting to terminal sharing server.
    
    Example:
        ```python
        from terminal_sharing import TerminalSharingClient
        
        client = TerminalSharingClient("ws://localhost:8765")
        
        # Connect to existing session
        await client.join_session(
            session_id="abc-123",
            role="viewer"
        )
        
        # Or create new session
        await client.create_session(
            project_path="/path/to/project",
            max_participants=5
        )
        ```
    """
    
    def __init__(self, server_url: str):
        """
        Initialize terminal sharing client.
        
        Args:
            server_url: WebSocket server URL (e.g., ws://localhost:8765)
        """
        if not HAS_WEBSOCKETS:
            raise ImportError(
                "websockets library required. Install with: pip install websockets"
            )
        
        self.server_url = server_url
        self.websocket: Optional[websockets.client.WebSocketClientProtocol] = None
        self.session_id: Optional[str] = None
        self.participant_id: Optional[str] = None
        self.role: Optional[SessionRole] = None
        
        # Message handlers
        self.on_terminal_output: Optional[callable] = None
        self.on_terminal_input: Optional[callable] = None
        self.on_participant_joined: Optional[callable] = None
        self.on_participant_left: Optional[callable] = None
        self.on_session_terminated: Optional[callable] = None
    
    async def connect(self) -> None:
        """Connect to the terminal sharing server."""
        print(f"[TerminalSharingClient] Connecting to {self.server_url}")
        self.websocket = await websockets.connect(self.server_url)
        print("[TerminalSharingClient] Connected")
    
    async def disconnect(self) -> None:
        """Disconnect from the server."""
        if self.websocket:
            await self.websocket.close()
            print("[TerminalSharingClient] Disconnected")
    
    async def create_session(
        self,
        project_path: str,
        max_participants: int = 10,
        is_recording: bool = False
    ) -> str:
        """
        Create a new terminal sharing session.
        
        Args:
            project_path: Path to project directory
            max_participants: Maximum participants
            is_recording: Whether to record the session
        
        Returns:
            Session ID
        """
        message = {
            "type": "create_session",
            "project_path": project_path,
            "max_participants": max_participants,
            "is_recording": is_recording
        }
        
        await self.websocket.send(json.dumps(message))
        
        # Wait for response
        response = await self._wait_for_response("session_created")
        self.session_id = response["session_id"]
        self.participant_id = response["participant_id"]
        self.role = SessionRole.OWNER
        
        return self.session_id
    
    async def join_session(
        self,
        session_id: str,
        role: str = "viewer"
    ) -> None:
        """
        Join an existing terminal sharing session.
        
        Args:
            session_id: Session ID to join
            role: Participant role (owner, collaborator, viewer)
        """
        message = {
            "type": "join_session",
            "session_id": session_id,
            "role": role
        }
        
        await self.websocket.send(json.dumps(message))
        
        # Wait for response
        response = await self._wait_for_response("session_joined")
        self.session_id = session_id
        self.participant_id = response["participant_id"]
        self.role = SessionRole(role)
        
        print(f"[TerminalSharingClient] Joined session {session_id} as {role}")
    
    async def leave_session(self) -> None:
        """Leave the current terminal sharing session."""
        if not self.session_id:
            return
        
        message = {
            "type": "leave_session",
            "session_id": self.session_id
        }
        
        await self.websocket.send(json.dumps(message))
        
        self.session_id = None
        self.participant_id = None
        self.role = None
    
    async def send_terminal_input(self, input_data: str) -> None:
        """Send terminal input to the session."""
        if not self.session_id:
            raise RuntimeError("Not in a session")
        
        if self.role not in [SessionRole.OWNER, SessionRole.COLLABORATOR]:
            raise RuntimeError("Only owners and collaborators can send input")
        
        message = {
            "type": "terminal_input",
            "session_id": self.session_id,
            "input": input_data
        }
        
        await self.websocket.send(json.dumps(message))
    
    async def send_terminal_output(self, output: str) -> None:
        """Send terminal output (for session owners)."""
        if not self.session_id:
            raise RuntimeError("Not in a session")
        
        if self.role != SessionRole.OWNER:
            raise RuntimeError("Only session owners can send output")
        
        message = {
            "type": "terminal_output",
            "session_id": self.session_id,
            "output": output
        }
        
        await self.websocket.send(json.dumps(message))
    
    async def get_participants(self) -> List[Dict[str, str]]:
        """Get list of participants in current session."""
        if not self.session_id:
            raise RuntimeError("Not in a session")
        
        message = {
            "type": "request_participants",
            "session_id": self.session_id
        }
        
        await self.websocket.send(json.dumps(message))
        
        response = await self._wait_for_response("participants_list")
        return response["participants"]
    
    async def _wait_for_response(self, message_type: str, timeout: float = 5.0) -> Dict[str, Any]:
        """Wait for a specific message type from server."""
        async for message in self.websocket:
            data = json.loads(message)
            if data.get("type") == message_type:
                return data
        
        raise TimeoutError(f"Timeout waiting for {message_type}")
    
    async def _listen_for_messages(self) -> None:
        """Listen for messages from server and route to handlers."""
        async for message in self.websocket:
            data = json.loads(message)
            message_type = data.get("type", "")
            
            if message_type == "terminal_output" and self.on_terminal_output:
                await self.on_terminal_output(data.get("output", ""), data)
            elif message_type == "terminal_input" and self.on_terminal_input:
                await self.on_terminal_input(data.get("input", ""), data)
            elif message_type == "participant_joined" and self.on_participant_joined:
                await self.on_participant_joined(data)
            elif message_type == "participant_left" and self.on_participant_left:
                await self.on_participant_left(data)
            elif message_type == "session_terminated" and self.on_session_terminated:
                await self.on_session_terminated(data)


if __name__ == "__main__":
    # Test server
    async def run_server():
        server = TerminalSharingServer(port=8765)
        
        async def handle_command(session_id, command, user_id):
            print(f"[TEST] Command from {user_id}: {command}")
            # Echo output back
            await server._broadcast_to_session(session_id, {
                "type": "terminal_output",
                "output": f"Executed: {command}\n"
            })
        
        server.on_command = handle_command
        
        await server.start()
        
        # Keep running
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down server...")
            await server.stop()
    
    print("Starting Terminal Sharing Server on port 8765...")
    asyncio.run(run_server())
