"""Nada se escribe fuera de la carpeta del proyecto, salvo en la carpeta temporal
de Claude Code para este proyecto.

Claude Code llama a este script antes de cada herramienta que escribe archivos o
corre comandos (ver `hooks` en .claude/settings.json). Lee la llamada en JSON por
la entrada estándar y la bloquea saliendo con 2: el motivo va a stderr.

- **Archivos** (Write, Edit, NotebookEdit): solo dentro del proyecto o de su
  carpeta temporal de Claude Code, más la memoria de este proyecto y los planes,
  que también son de Claude Code.
- **Comandos** (Bash, PowerShell, Monitor): se bloquea el que nombra cualquier
  otra ruta o una carpeta del sistema ($TEMP, %TEMP%, $env:TEMP, /tmp, ~,
  AppData...), aunque solo sea para leerla.

La carpeta temporal (`%TEMP%\\claude\\<este proyecto>`) queda fuera de OneDrive,
así que lo temporal no se sube a la nube; lo que se entrega va en entregas/. La
carpeta temporal general de Windows sigue bloqueada: ahí cayeron dos archivos
por error en octubre de 2026. Un programa que por su cuenta escriba fuera, sin
nombrar la ruta en el comando, no se ve desde aquí: en Windows Claude Code no
tiene sandbox para los comandos.
"""

import json
import os
import re
import sys

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SLUG = re.sub(r"[^A-Za-z0-9]", "-", PROJECT)
CLAUDE_HOME = os.path.join(os.path.expanduser("~"), ".claude")
MEMORY = os.path.join(CLAUDE_HOME, "projects", SLUG, "memory")
PLANS = os.path.join(CLAUDE_HOME, "plans")
# Claude Code's temp folder for this project: session scratchpads and the output
# of background commands. Not the whole temp folder, which stays blocked.
WORK = os.path.join(
    os.environ.get("TEMP") or os.path.join(os.path.expanduser("~"), "AppData", "Local", "Temp"),
    "claude", SLUG)

FILE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
SHELL_TOOLS = {"Bash", "PowerShell", "Monitor"}

STOP = r"\s\"'`|;&<>()"
# Variables and calls that point at system folders, in bash, cmd, PowerShell and
# Python spellings.
SYSTEM = re.compile(
    r"\$\{?(?:TEMP|TMP|TMPDIR|HOME|HOMEPATH|USERPROFILE|APPDATA|LOCALAPPDATA|PROGRAMDATA"
    r"|ONEDRIVE|PUBLIC|SYSTEMROOT|WINDIR)\b"
    r"|%(?:TEMP|TMP|HOMEPATH|USERPROFILE|APPDATA|LOCALAPPDATA|PROGRAMDATA|ONEDRIVE"
    r"|PUBLIC|SYSTEMROOT|WINDIR)%"
    r"|\$env:(?:TEMP|TMP|HOME|HOMEPATH|USERPROFILE|APPDATA|LOCALAPPDATA|PROGRAMDATA"
    r"|ONEDRIVE|PUBLIC|SYSTEMROOT|WINDIR)\b"
    r"|\bgettempdir\b|\bexpanduser\b|\bPath\.home\b|\bmktemp\b"
    r"|\[Environment\]::GetFolderPath|::GetTempPath",
    re.IGNORECASE)
HOME = re.compile(r"(?<![\w~])~(?=[/\\]|$|[" + STOP + "])")
TMP = re.compile(r"(?<![\w.~/\\-])/tmp(?=/|$|[" + STOP + "])")
UNC = re.compile(r"(?<![\w\\])\\\\[^\s\\]+\\")
DRIVE = re.compile(r"(?<![\w])([A-Za-z]:[\\/][^" + STOP + "]*)")
MSYS = re.compile(r"(?<![\w.~/\\-])(/[A-Za-z]/[^" + STOP + "]+)")
UP = re.compile(r"(?:^|(?<=[\s\"'=(:]))(\.\.(?:[\\/][^" + STOP + "]*)?)(?=$|[" + STOP + "])")
CD_ROOT = re.compile(
    r"\b(?:cd|pushd|Set-Location|Push-Location|sl)\s+[\"']?(?:[A-Za-z]:[\\/]?|/[A-Za-z]?/?|\\)"
    r"[\"']?(?=$|[\s;&|])", re.IGNORECASE)


def native(path: str) -> str:
    """`/c/Users/x` (Git Bash) as `C:/Users/x`, and `~` as the home folder."""
    path = path.strip().strip("\"'")
    found = re.match(r"^/([A-Za-z])(/|$)", path)
    if found:
        path = found.group(1) + ":/" + path[3:]
    return os.path.expanduser(path)


def inside(path: str, cwd: str, roots) -> bool:
    full = os.path.normcase(os.path.abspath(os.path.join(cwd, native(path))))
    for root in roots:
        top = os.path.normcase(os.path.abspath(root))
        if full == top or full.startswith(top.rstrip("\\/") + os.sep):
            return True
    return False


def block(what: str) -> None:
    print(f"Bloqueado: {what} está fuera de la carpeta del proyecto ({PROJECT}). "
          f"Lo temporal va en {WORK} (sin usar $TEMP) y lo que se entrega, en "
          "entregas/.", file=sys.stderr)
    sys.exit(2)


def check_file(tool_input: dict, cwd: str) -> None:
    path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    if path and not inside(path, cwd, (PROJECT, WORK, MEMORY, PLANS)):
        block(f"«{path}»")


def check_command(command: str, cwd: str) -> None:
    for pattern in (SYSTEM, HOME, TMP, UNC, CD_ROOT):
        found = pattern.search(command)
        if found:
            block(f"«{found.group(0).strip()}», en el comando,")
    for pattern in (DRIVE, MSYS, UP):
        for found in pattern.finditer(command):
            path = found.group(1)
            if not inside(path, cwd, (PROJECT, WORK)):
                block(f"«{path}», en el comando,")


def main() -> None:
    # Claude Code reads the reason as UTF-8; Windows would write it in its own
    # code page and the accents would arrive broken.
    sys.stderr.reconfigure(encoding="utf-8")
    try:
        call = json.loads(sys.stdin.buffer.read().decode("utf-8"))
        tool = call.get("tool_name", "")
        tool_input = call.get("tool_input") or {}
        cwd = call.get("cwd") or PROJECT
        if tool in FILE_TOOLS:
            check_file(tool_input, cwd)
        elif tool in SHELL_TOOLS:
            check_command(str(tool_input.get("command") or ""), cwd)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - when in doubt, nothing goes through
        print(f"Bloqueado: no se pudo comprobar la llamada ({type(exc).__name__}).",
              file=sys.stderr)
        sys.exit(2)
    sys.exit(0)


main()
