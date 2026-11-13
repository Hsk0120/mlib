@echo off
setlocal

::----------------------------------------------------------------
:: Check the mlib sources against the coding rules (import order, order of
:: the class members, blank lines, spacing, input assertions, encodings),
:: and apply the automatic fixes. Maya is not needed.
::
::   check_mlib_layout.bat                 check all of mlib
::   check_mlib_layout.bat nodes\node.py   check the given files or folders
::   check_mlib_layout.bat --fix           fix the import order, the order of
::                                         the class members and the blank
::                                         lines, then check again to list
::                                         what is left (files or folders can
::                                         be given as well)
::   check_mlib_layout.bat --fix-asserts TypeError nodes\node.py --line 12
::                                         turn the input assertion reported
::                                         on that line into a raise of the
::                                         chosen type (TypeError/ValueError)
::   --no-pause                            do not wait for a key at the end
::                                         (for terminals and other scripts)
::
:: The other modes of check_mlib_layout.py (--outline, --snapshot, --compare)
:: are passed to the script as they are.
:: --fix never changes the spacing, the comments at the end of a line or the
:: named lambdas (L030-L034): they are only reported, fix them by hand.
::
:: Exit code: 0 when there is no violation, 1 when there are violations,
:: 2 when the arguments are wrong or no Python was found.
::
:: Needs Python 3.9 to 3.14 of the Windows Python launcher (py),
:: or mayapy of Maya 2027-2023.
::----------------------------------------------------------------
SET "SCRIPT=%~dp0check_mlib_layout.py"
SET "MLIB_LAYOUT_CMD="
SET "MLIB_LAYOUT_RESULT=2"
SET "MLIB_LAYOUT_PAUSE=1"
SET "MLIB_LAYOUT_FIX="
SET "MLIB_LAYOUT_MODE="
SET "MLIB_LAYOUT_ARGS="

rem Take --no-pause, --fix and --check out of the arguments, and remember
rem whether another mode was given; pass the others to the script.
:parse_args
IF "%~1"=="" GOTO :args_done
IF /I "%~1"=="--no-pause" SET "MLIB_LAYOUT_PAUSE=" & GOTO :next_arg
IF /I "%~1"=="--fix" SET "MLIB_LAYOUT_FIX= --fix" & GOTO :next_arg
IF /I "%~1"=="--check" GOTO :next_arg
FOR %%M IN (--fix-asserts --outline --snapshot --compare -h --help) DO IF /I "%~1"=="%%M" SET "MLIB_LAYOUT_MODE=1"
SET "MLIB_LAYOUT_ARGS=%MLIB_LAYOUT_ARGS% %1"
:next_arg
SHIFT
GOTO :parse_args
:args_done
rem Only look for an installed Python: never let the launcher install one.
SET "PYLAUNCHER_ALLOW_INSTALL="

rem Ask the Windows Python launcher for each version, newest first.
rem "python" is not used: it can be the Microsoft Store placeholder, which
rem opens the Store instead of running Python. "py -3" is not used either:
rem it picks the newest installed Python, and 3.15 or later is not accepted
rem (the same range as generate_mlib_stubs.bat).
FOR %%V IN (3.14 3.13 3.12 3.11 3.10 3.9) DO (
    IF NOT DEFINED MLIB_LAYOUT_CMD (
        py -%%V -c "import sys" >NUL 2>&1
        IF NOT ERRORLEVEL 1 SET "MLIB_LAYOUT_CMD=py -%%V"
    )
)
IF DEFINED MLIB_LAYOUT_CMD GOTO :run

rem Fall back to mayapy of Maya 2027-2023 (Python 3.9 or newer).
FOR %%V IN (2027 2026 2025 2024 2023) DO (
    IF NOT DEFINED MLIB_LAYOUT_CMD IF EXIST "C:\Program Files\Autodesk\Maya%%V\bin\mayapy.exe" (
        ECHO Using "C:\Program Files\Autodesk\Maya%%V\bin\mayapy.exe".
        SET MLIB_LAYOUT_CMD="C:\Program Files\Autodesk\Maya%%V\bin\mayapy.exe"
    )
)
IF DEFINED MLIB_LAYOUT_CMD GOTO :run
ECHO [ERROR] Python 3.9 to 3.14 was not found with the Python launcher (py), and neither was mayapy of Maya 2027-2023.
GOTO :finish

:run
rem Another mode was given: run the script with the arguments as they are
rem (with --fix too, the script reports that the modes cannot be combined).
IF DEFINED MLIB_LAYOUT_MODE GOTO :run_as_given
IF NOT DEFINED MLIB_LAYOUT_FIX GOTO :run_check

rem --fix: write the automatic fixes, then check to list what is left.
%MLIB_LAYOUT_CMD% "%SCRIPT%" --fix%MLIB_LAYOUT_ARGS%
SET "MLIB_LAYOUT_RESULT=%ERRORLEVEL%"
IF NOT "%MLIB_LAYOUT_RESULT%"=="0" GOTO :finish
ECHO.

:run_check
%MLIB_LAYOUT_CMD% "%SCRIPT%" --check%MLIB_LAYOUT_ARGS%
SET "MLIB_LAYOUT_RESULT=%ERRORLEVEL%"
GOTO :finish

:run_as_given
%MLIB_LAYOUT_CMD% "%SCRIPT%"%MLIB_LAYOUT_FIX%%MLIB_LAYOUT_ARGS%
SET "MLIB_LAYOUT_RESULT=%ERRORLEVEL%"

:finish
rem Wait for a key so that the result stays readable when the batch was
rem started by a double click (the same as generate_mlib_stubs.bat).
IF DEFINED MLIB_LAYOUT_PAUSE (
    ECHO.
    PAUSE
)
EXIT /b %MLIB_LAYOUT_RESULT%
