import subprocess
import threading

END_MARKER = "__END_OF_COMMAND_123__"

class PowerShellWorker:
    def __init__(self):
        self.proc = subprocess.Popen(
            ["powershell", "-NoLogo", "-NoExit", "-Command", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        self.lock = threading.Lock()

        # Init session 1x
        self._init_session()

    def _send(self, command):
        self.proc.stdin.write(command + "\n")
        self.proc.stdin.flush()

    
    def _init_session(self):
        self._send("$env:AZURE_IDENTITY_DISABLE_WAM = 1")
        self._send("Disconnect-MgGraph -ErrorAction SilentlyContinue")
        self._send("Write-Output 'PS session ready'")
        self._send("Import-Module Microsoft.Graph")
        self._send("Connect-MgGraph -Scopes Application.ReadWrite.All, Directory.ReadWrite.All -NoWelcome")
        self._send(f"echo {END_MARKER}")

        # flush initial output
        for line in self.proc.stdout:
            if END_MARKER in line:
                break
    
    def run(self, script_path, args_string):
        with self.lock:

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