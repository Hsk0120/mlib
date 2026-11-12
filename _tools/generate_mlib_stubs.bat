@echo off
setlocal

::----------------------------------------------------------------
:: Generate the mlib type stubs (*.pyi next to each *.py of mlib)
:: for VS Code (Pylance) completion and signature help, from the docstrings.
:: The .py sources are not changed. Commit the updated .pyi with the .py.
::
::   generate_mlib_stubs.bat            regenerate the stubs
::   generate_mlib_stubs.bat --report   also list annotations left out
::   generate_mlib_stubs.bat --check    only check that the stubs are current
::
:: Needs Python 3.9 to 3.14 of the Windows Python launcher (py),
:: or mayapy of Maya 2027-2023. Every one of them generates the same stubs.
::----------------------------------------------------------------
SET "SCRIPT=%~dp0generate_mlib_stubs.py"
SET "MLIB_STUBS_PY="
rem Only look for an installed Python: never let the launcher install one.
SET "PYLAUNCHER_ALLOW_INSTALL="

rem Ask the Windows Python launcher for each version, newest first.
rem "python" is not used: it can be the Microsoft Store placeholder, which
rem opens the Store instead of running Python. "py -3" is not used either:
rem it picks the newest installed Python, and 3.15 or later is not accepted
rem (the same range as _docs\setup.bat).
FOR %%V IN (3.14 3.13 3.12 3.11 3.10 3.9) DO (
    IF NOT DEFINED MLIB_STUBS_PY (
        py -%%V -c "import sys" >NUL 2>&1
        IF NOT ERRORLEVEL 1 SET "MLIB_STUBS_PY=%%V"
    )
)
IF DEFINED MLIB_STUBS_PY (
    py -%MLIB_STUBS_PY% "%SCRIPT%" %*
    GOTO :done
)

rem Fall back to mayapy of Maya 2027-2023 (Python 3.9 or newer).
FOR %%V IN (2027 2026 2025 2024 2023) DO (
    IF EXIST "C:\Program Files\Autodesk\Maya%%V\bin\mayapy.exe" (
        ECHO Using "C:\Program Files\Autodesk\Maya%%V\bin\mayapy.exe".
        "C:\Program Files\Autodesk\Maya%%V\bin\mayapy.exe" "%SCRIPT%" %*
        GOTO :done
    )
)
ECHO [ERROR] Python 3.9 to 3.14 was not found with the Python launcher (py), and neither was mayapy of Maya 2027-2023.
EXIT /b 2

:done
EXIT /b %ERRORLEVEL%
