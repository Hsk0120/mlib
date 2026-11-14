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
::
:: Exit code: the code of generate_mlib_stubs.py (0 when it succeeded, or
:: when the stubs are current with --check). 2 when no Python was found.
::
:: The Japanese messages are in messages.txt and shown by _message.bat (this
:: file stays ASCII). The last message starts with [OK] or [NG].
::----------------------------------------------------------------
rem Keep the paths before the argument loop: SHIFT changes %0.
SET "SCRIPT=%~dp0generate_mlib_stubs.py"
SET "SAY=CALL "%~dp0_message.bat""
SET "MLIB_STUBS_PY="
SET "MLIB_STUBS_MAYAPY="
SET "MLIB_STUBS_RESULT=2"
SET "MLIB_STUBS_PAUSE=1"
SET "MLIB_STUBS_ARGS="
rem The key of the result message: stubs or stubs.check, then .ok or .ng.
SET "MLIB_STUBS_KIND=stubs"
SET "MLIB_STUBS_MESSAGE=stubs.noPython"

rem Take --no-pause out of the arguments; pass the others to the script.
:parse_args
IF "%~1"=="" GOTO :args_done
IF /I "%~1"=="--check" SET "MLIB_STUBS_KIND=stubs.check"
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
rem (setup.bat starts at 3.11, because Sphinx needs it; the stubs do not).
FOR %%V IN (3.14 3.13 3.12 3.11 3.10 3.9) DO (
    IF NOT DEFINED MLIB_STUBS_PY (
        py -%%V -c "import sys" >NUL 2>&1
        IF NOT ERRORLEVEL 1 SET "MLIB_STUBS_PY=%%V"
    )
)
IF NOT DEFINED MLIB_STUBS_PY GOTO :find_mayapy
py -%MLIB_STUBS_PY% "%SCRIPT%"%MLIB_STUBS_ARGS%
GOTO :done

:find_mayapy
rem Fall back to mayapy of Maya 2027-2023 (Python 3.9 or newer).
FOR %%V IN (2027 2026 2025 2024 2023) DO (
    IF NOT DEFINED MLIB_STUBS_MAYAPY IF EXIST "C:\Program Files\Autodesk\Maya%%V\bin\mayapy.exe" SET "MLIB_STUBS_MAYAPY=C:\Program Files\Autodesk\Maya%%V\bin\mayapy.exe"
)
IF NOT DEFINED MLIB_STUBS_MAYAPY GOTO :finish
%SAY% stubs.usingMayapy
"%MLIB_STUBS_MAYAPY%" "%SCRIPT%"%MLIB_STUBS_ARGS%

:done
SET "MLIB_STUBS_RESULT=%ERRORLEVEL%"
SET "MLIB_STUBS_MESSAGE=%MLIB_STUBS_KIND%.ng"
IF "%MLIB_STUBS_RESULT%"=="0" SET "MLIB_STUBS_MESSAGE=%MLIB_STUBS_KIND%.ok"

:finish
%SAY% blank line %MLIB_STUBS_MESSAGE% line

rem Wait for a key so that the result stays readable when the batch was
rem started by a double click (the same as the other batch files).
IF DEFINED MLIB_STUBS_PAUSE (
    ECHO.
    PAUSE
)
EXIT /b %MLIB_STUBS_RESULT%
