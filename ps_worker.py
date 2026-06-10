import subprocess
import threading
import queue
import time

END_MARKER = "__END_OF_COMMAND_123__"

class PowerShellWorker:
    def __init__(self):
        self.proc = None
        self.lock = threading.Lock()
        self.output_queue = queue.Queue()
        self.reader_thread = None
        self._start_process()

    def _start_process(self):
        if self.proc:
            try:
                self.proc.stdin.close()
                self.proc.terminate()
                self.proc.wait(timeout=1)
            except:
                pass

        self.proc = subprocess.Popen(
            ["pwsh", "-NoLogo", "-NoExit", "-Command", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Start reader thread
        self.reader_thread = threading.Thread(target=self._reader, daemon=True)
        self.reader_thread.start()
        
        self._init_session()

    def _reader(self):
        while self.proc and self.proc.stdout:
            line = self.proc.stdout.readline()
            if not line:
                break
            self.output_queue.put(line)

    def _send(self, command):
        with open("logs/ps_worker.log", "a", encoding="utf-8") as f:
            f.write(f"SENDING: {command}\n")
        try:
            self.proc.stdin.write(command + "\n")
            self.proc.stdin.flush()
        except (OSError, ValueError):
            with open("logs/ps_worker.log", "a", encoding="utf-8") as f:
                f.write("PROCESS DEAD, RESTARTING\n")
            self._start_process()
            self.proc.stdin.write(command + "\n")
            self.proc.stdin.flush()

    def _read_until_marker(self, timeout=30):
        output = []
        start_time = time.time()
        
        while True:
            remaining = timeout - (time.time() - start_time)
            if remaining <= 0:
                output.append("\n[ERROR: Timeout waiting for PowerShell response]\n")
                break
            
            try:
                line = self.output_queue.get(timeout=remaining)
                with open("logs/ps_worker.log", "a", encoding="utf-8") as f:
                    f.write(f"RECEIVED: {line}")
                    
                if END_MARKER in line:
                    break
                output.append(line)
            except queue.Empty:
                output.append("\n[ERROR: Timeout waiting for PowerShell response]\n")
                break
            
        return "".join(output)

    def _init_session(self):
        try:
            self._send("$ErrorActionPreference = 'Continue'")
            self._send("$env:AZURE_IDENTITY_DISABLE_WAM = 1")
            # Force plain text output to avoid ANSI escape codes
            self._send("if ($PSStyle) { $PSStyle.OutputRendering = 'PlainText' }")
            self._send("Import-Module Microsoft.Graph.Authentication -ErrorAction SilentlyContinue")
            self._send("Write-Output 'PS session ready'")
            self._send(f"echo {END_MARKER}")

            self._read_until_marker(timeout=15)
        except Exception as e:
            with open("logs/ps_worker.log", "a", encoding="utf-8") as f:
                f.write(f"INIT ERROR: {e}\n")
            print(f"Failed to initialize PS session: {e}")
    
    def connect(self):
        with self.lock:
            # Use -ContextScope Process to ensure it's isolated to this worker
            # and -NoWelcome to reduce noise
            self._send("Connect-MgGraph -Scopes Application.ReadWrite.All, Directory.ReadWrite.All -ContextScope Process")
            self._send("Write-Output 'CONNECT_DONE'")
            self._send(f"echo {END_MARKER}")
            
            return self._read_until_marker(timeout=60)

    def disconnect(self):
        with self.lock:
            self._send("Disconnect-MgGraph -ErrorAction SilentlyContinue")
            self._send(f"echo {END_MARKER}")
            return self._read_until_marker(timeout=10)

    def get_status(self):
        with self.lock:
            if self.proc.poll() is not None:
                return "Disconnected (Process Dead)"
            
            self._send("try { if (Get-MgContext) { Write-Output 'Connected' } else { Write-Output 'Disconnected' } } catch { Write-Output 'Disconnected' }")
            self._send(f"echo {END_MARKER}")
            
            return self._read_until_marker(timeout=5).strip()

    def run(self, script_path, args_string):
        with self.lock:
            # Check if process is still alive
            if self.proc.poll() is not None:
                self._start_process()

            cmd = f"""
    try {{
        & '{script_path}' {args_string} 2>&1
    }} catch {{
        Write-Output "ERROR: $($_.Exception.Message)"
    }}
    """
            self._send(cmd)
            self._send(f"echo {END_MARKER}")

            return self._read_until_marker(timeout=120)
