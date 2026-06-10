import subprocess
import threading

END_MARKER = "__END_OF_COMMAND_123__"

class PowerShellWorker:
    def __init__(self):
        self.proc = None
        self.lock = threading.Lock()
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
            ["powershell", "-NoLogo", "-NoExit", "-Command", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        self._init_session()

    def _send(self, command):
        try:
            self.proc.stdin.write(command + "\n")
            self.proc.stdin.flush()
        except (OSError, ValueError):
            # Process might be dead, try to restart once
            self._start_process()
            self.proc.stdin.write(command + "\n")
            self.proc.stdin.flush()

    def _init_session(self):
        try:
            self._send("$env:AZURE_IDENTITY_DISABLE_WAM = 1")
            self._send("Write-Output 'PS session ready'")
            self._send("Import-Module Microsoft.Graph -ErrorAction SilentlyContinue")
            self._send(f"echo {END_MARKER}")

            # flush initial output
            for line in self.proc.stdout:
                if END_MARKER in line:
                    break
        except Exception as e:
            print(f"Failed to initialize PS session: {e}")
    
    def connect(self):
        with self.lock:
            self._send("Connect-MgGraph -Scopes Application.ReadWrite.All, Directory.ReadWrite.All -NoWelcome")
            self._send(f"echo {END_MARKER}")
            output = []
            for line in self.proc.stdout:
                if END_MARKER in line:
                    break
                output.append(line)
            return "".join(output)

    def disconnect(self):
        with self.lock:
            self._send("Disconnect-MgGraph -ErrorAction SilentlyContinue")
            self._send(f"echo {END_MARKER}")
            output = []
            for line in self.proc.stdout:
                if END_MARKER in line:
                    break
                output.append(line)
            return "".join(output)

    def get_status(self):
        with self.lock:
            # Check if process is still alive first
            if self.proc.poll() is not None:
                return "Disconnected (Process Dead)"
            
            self._send("if (Get-MgContext) { Write-Output 'Connected' } else { Write-Output 'Disconnected' }")
            self._send(f"echo {END_MARKER}")
            output = []
            for line in self.proc.stdout:
                if END_MARKER in line:
                    break
                output.append(line)
            return "".join(output).strip()

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

            output = []

            for line in self.proc.stdout:
                if END_MARKER in line:
                    break
                output.append(line)

            return "".join(output)