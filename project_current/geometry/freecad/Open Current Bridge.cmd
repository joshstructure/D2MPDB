@echo off
setlocal
set "BRIDGE_FREECAD=%ProgramFiles%\FreeCAD 1.1\bin\freecad.exe"
set "BRIDGE_OPENER=%~dp0Open_Current_Bridge.FCMacro"
if not exist "%BRIDGE_FREECAD%" (
    echo FreeCAD 1.1 was not found at "%BRIDGE_FREECAD%".
    echo Update BRIDGE_FREECAD in this launcher to your installed FreeCAD executable.
    pause
    exit /b 1
)
if not exist "%BRIDGE_OPENER%" (
    echo Keep this launcher beside Open_Current_Bridge.FCMacro and the runtime folder.
    pause
    exit /b 1
)
start "" "%BRIDGE_FREECAD%" "%BRIDGE_OPENER%"
exit /b 0
