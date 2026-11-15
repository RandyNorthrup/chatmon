"""Write probe-screen-readers.yml with run_chatmon.py and drive_voiceover.py embedded (the probe branch holds the
workflow file alone)."""

import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).parent


def block(name: str) -> str:
    return textwrap.indent((HERE / name).read_text(encoding="utf-8"), " " * 10)


HEAD = """\
name: Probe screen readers

# A throwaway probe before v0.10.0, on a branch of its own that holds only this file and is deleted afterwards:
# does a real VoiceOver speak what Chatmon announces? Chatmon runs from source with CI's pinned packages (as CI's
# macOS leg installs them) and is told what to say the ways a person meets it: a hook's message with Chatmon in
# front, a command typed in its ask box, and a message and an agent's alert while another app is in front, then
# Chatmon brought forward. VoiceOver is driven and read through its own AppleScript, which guidepup/setup-action
# turns on; each new `content of last phrase` is kept with its time. Chatmon's own log, a trace of what it handed
# VoiceOver (run_chatmon.py: Chatmon's functions wrapped, not changed) and screenshots go in the artifact.
# Later passes run hypotheses, applied by run_chatmon.py and labelled so: held announcements posted 2.5 s after
# Chatmon becomes the active app, and the ask box's title handing keyboard focus to its entry. They test proposed
# fixes; Chatmon's own code is unchanged. Round 4 also ran an nvda job: the same kind of probe with NVDA on a
# Windows runner.
on:
  push:
    branches: [probe/screen-readers]

permissions:
  contents: read

env:
  PIP_DISABLE_PIP_VERSION_CHECK: "1"

jobs:
  voiceover:
    runs-on: macos-latest
    timeout-minutes: 45
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
          sparse-checkout: |
            /*
            !/art/
            !/docs/
          sparse-checkout-cone-mode: false
      - uses: actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0 # v7.1.0
        with:
          python-version: "3.14"
      - run: python -m pip install --require-hashes -r packaging/requirements-test.txt
      - name: VoiceOver's AppleScript control, and the runner's permissions to drive it
        uses: guidepup/setup-action@acf1a64cc26292ebe0db6a28d1341bd1bae93c65 # 0.21.0
      - name: The probe's scripts, and Chatmon's settings (named, so it doesn't ask; no update or break checks)
        run: |
          mkdir -p "$RUNNER_TEMP/probe" "$RUNNER_TEMP/out"
          cat > "$RUNNER_TEMP/probe/run_chatmon.py" <<'PY'
{shim}          PY
          cat > "$RUNNER_TEMP/probe/drive_voiceover.py" <<'PY'
{driver}          PY
          conf="$HOME/Library/Application Support/chatmon"
          mkdir -p "$conf"
          printf '%s\\n' 'name = "Chatmon"' '[updates]' 'check = false' '[breaks]' 'remind = false' '[heads_up]' 'updates = false' > "$conf/config.toml"
          cp "$conf/config.toml" "$RUNNER_TEMP/out/config.toml"
          shasum -a 256 "$RUNNER_TEMP/probe/"*.py | tee "$RUNNER_TEMP/out/scripts.sha256"
      - name: Probe VoiceOver
        run: python "$RUNNER_TEMP/probe/drive_voiceover.py" "$RUNNER_TEMP/out" "$GITHUB_WORKSPACE" "$RUNNER_TEMP/probe/run_chatmon.py"
      - name: Chatmon's own log, and what ran
        if: ${{{{ always() }}}}
        run: |
          cp "$HOME/Library/Application Support/chatmon/state/chatmon.log" "$RUNNER_TEMP/out/" || true
          {{ sw_vers; uname -a; python --version; python -m pip freeze; git -C "$GITHUB_WORKSPACE" rev-parse HEAD; }} > "$RUNNER_TEMP/out/environment.txt" 2>&1
          defaults read com.apple.VoiceOver4/default SCREnableAppleScript >> "$RUNNER_TEMP/out/environment.txt" 2>&1 || true
      - if: ${{{{ always() }}}}
        uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2
        with:
          name: voiceover-transcript
          path: ${{{{ runner.temp }}}}/out
          if-no-files-found: error
          retention-days: 30
"""

NVDA = """
  nvda:
    # NVDA on a Windows runner's desktop: NV Access's own 2026.3.1 installer (its published SHA-256 checked) made a
    # portable copy, run with its log at the input/output level, whose "Speaking" lines are the transcript.
    runs-on: windows-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
          sparse-checkout: |
            /*
            !/art/
            !/docs/
          sparse-checkout-cone-mode: false
      - uses: actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0 # v7.1.0
        with:
          python-version: "3.14"
      - run: python -m pip install --require-hashes -r packaging/requirements-test.txt
      - name: NVDA 2026.3.1 from NV Access, checked, made a portable copy
        shell: pwsh
        run: |
          $exe = "$env:RUNNER_TEMP\\nvda_2026.3.1.exe"
          Invoke-WebRequest -Uri https://download.nvaccess.org/releases/2026.3.1/nvda_2026.3.1.exe -OutFile $exe
          $hash = (Get-FileHash $exe -Algorithm SHA256).Hash
          if ($hash -ne '6F80A5B0CA720A7D0D314B5BE212F37388BBE81A1107AC3298C1821A1CD3F052') {{ throw "NVDA's installer has SHA-256 $hash" }}
          $sig = Get-AuthenticodeSignature $exe
          "signature: $($sig.Status), $($sig.SignerCertificate.Subject)"
          New-Item -ItemType Directory "$env:RUNNER_TEMP\\out" -Force | Out-Null
          Start-Process -FilePath $exe -ArgumentList '--create-portable-silent', "--portable-path=$env:RUNNER_TEMP\\nvda" -Wait
          $deadline = (Get-Date).AddMinutes(5)
          while (-not (Test-Path "$env:RUNNER_TEMP\\nvda\\nvda.exe") -and (Get-Date) -lt $deadline) {{ Start-Sleep -Seconds 2 }}
          while ((Get-Process -Name nvda*, nvda_* -ErrorAction SilentlyContinue) -and (Get-Date) -lt $deadline) {{ Start-Sleep -Seconds 2 }}
          Get-ChildItem "$env:RUNNER_TEMP\\nvda" | Select-Object -First 12 | Format-Table -AutoSize Name, Length
          "nvda.exe: $(Test-Path "$env:RUNNER_TEMP\\nvda\\nvda.exe")"
      - name: The probe's scripts, and Chatmon's settings (named, so it doesn't ask; no update or break checks)
        shell: bash
        run: |
          mkdir -p "$RUNNER_TEMP/probe" "$RUNNER_TEMP/out"
          cat > "$RUNNER_TEMP/probe/run_chatmon.py" <<'PY'
{shim}          PY
          cat > "$RUNNER_TEMP/probe/drive_windows.py" <<'PY'
{windows}          PY
          conf="$(cygpath -u "$LOCALAPPDATA")/chatmon"
          mkdir -p "$conf"
          printf '%s\\n' 'name = "Chatmon"' '[updates]' 'check = false' '[breaks]' 'remind = false' '[heads_up]' 'updates = false' > "$conf/config.toml"
          cp "$conf/config.toml" "$RUNNER_TEMP/out/config.toml"
          sha256sum "$RUNNER_TEMP/probe/"*.py | tee "$RUNNER_TEMP/out/scripts.sha256"
      - name: Probe NVDA
        shell: bash
        run: python "$RUNNER_TEMP/probe/drive_windows.py" "$RUNNER_TEMP/out" "$GITHUB_WORKSPACE" "$RUNNER_TEMP/probe/run_chatmon.py" nvda "$RUNNER_TEMP/nvda/nvda.exe"
      - name: Chatmon's own log, and what ran
        if: ${{{{ always() }}}}
        shell: bash
        run: |
          cp "$(cygpath -u "$LOCALAPPDATA")/chatmon/state/chatmon.log" "$RUNNER_TEMP/out/" || true
          {{ cmd //c ver; python --version; python -m pip freeze; git -C "$GITHUB_WORKSPACE" rev-parse HEAD; }} > "$RUNNER_TEMP/out/environment.txt" 2>&1
      - if: ${{{{ always() }}}}
        uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2
        with:
          name: nvda-transcript
          path: ${{{{ runner.temp }}}}/out
          if-no-files-found: error
          retention-days: 30
"""

WINDOWS = HERE.parent / "tp2" / "drive_windows.py"
out = HEAD.format(shim=block("run_chatmon.py"), driver=block("drive_voiceover.py"))
if "--nvda" in sys.argv:
    out += NVDA.format(shim=block("run_chatmon.py"), windows=textwrap.indent(WINDOWS.read_text(encoding="utf-8"), " " * 10))
Path(sys.argv[1]).write_text(out, encoding="utf-8", newline="\n")
print(f"wrote {sys.argv[1]}: {len(out)} bytes")
