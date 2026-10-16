"""Recalculate a workbook in installed Microsoft Excel so formula results are cached.

openpyxl writes formulas without results. Excel (via COM, driven by Windows
PowerShell) performs a full recalculation and saves the file in place, so the
delivered workbook opens with values and the regression tests can read them.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

POWERSHELL = r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'

_SCRIPT = r'''
$ErrorActionPreference = 'Stop'
$path = $args[0]
$excel = New-Object -ComObject Excel.Application
try {
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $excel.AskToUpdateLinks = $false
    $book = $excel.Workbooks.Open($path, 0, $false)
    try {
        $excel.CalculateFull()
        $book.Save()
    } finally {
        $book.Close($true)
    }
} finally {
    $excel.Quit()
    [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($excel)
}
'''


def excel_available() -> bool:
    probe = ("try { $x = New-Object -ComObject Excel.Application; $x.Quit(); "
             "[void][Runtime.InteropServices.Marshal]::ReleaseComObject($x); 'yes' } catch { 'no' }")
    try:
        out = subprocess.run([POWERSHELL, '-NoProfile', '-NonInteractive', '-Command', probe],
                             capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return out.stdout.strip().endswith('yes')


def recalculate(path: Path, timeout: int = 600) -> None:
    path = Path(path).resolve()
    command = [POWERSHELL, '-NoProfile', '-NonInteractive', '-Command',
               f'& {{{_SCRIPT}}} "{path}"']
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f'Excel recalculation failed:\n{result.stdout}\n{result.stderr}')
