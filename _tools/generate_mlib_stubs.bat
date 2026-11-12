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
::   --no-pause                         do not wait for a key at the end
::                                      (for terminals and other scripts)
::
:: Needs Python 3.9 to 3.14 of the Windows Python launcher (py),
:: or mayapy of Maya 2027-2023. Every one of them generates the same stubs.
::----------------------------------------------------------------
SET "SCRIPT=%~dp0generate_mlib_stubs.py"
SET "MLIB_STUBS_PY="
SET "MLIB_STUBS_RESULT=2"
SET "MLIB_STUBS_PAUSE=1"
SET "MLIB_STUBS_ARGS="

rem Take --no-pause out of the arguments; pass the others to the script.
:parse_args
IF "%~1"=="" GOTO :args_done
IF /I "%~1"=="--no-pause" (
    SET "MLIB_STUBS_PAUSE="
) ELSE (
    SET "MLIB_STUBS_ARGS=%MLIB_STUBS_ARGS% %1"
)
SHIFT
GOTO :parse_args
:args_done
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
    py -%MLIB_STUBS_PY% "%SCRIPT%"%MLIB_STUBS_ARGS%
    GOTO :done
)

rem Fall back to mayapy of Maya 2027-2023 (Python 3.9 or newer).
FOR %%V IN (2027 2026 2025 2024 2023) DO (
    IF EXIST "C:\Program Files\Autodesk\Maya%%V\bin\mayapy.exe" (
        ECHO Using "C:\Program Files\Autodesk\Maya%%V\bin\mayapy.exe".
        "C:\Program Files\Autodesk\Maya%%V\bin\mayapy.exe" "%SCRIPT%"%MLIB_STUBS_ARGS%
        GOTO :done
    )
)
ECHO [ERROR] Python 3.9 to 3.14 was not found with the Python launcher (py), and neither was mayapy of Maya 2027-2023.
GOTO :finish

:done
SET "MLIB_STUBS_RESULT=%ERRORLEVEL%"

:finish
rem Wait for a key so that the result stays readable when the batch was
rem started by a double click (the same as the Sphinx batch files).
IF DEFINED MLIB_STUBS_PAUSE (
    ECHO.
    PAUSE
)
EXIT /b %MLIB_STUBS_RESULT%
