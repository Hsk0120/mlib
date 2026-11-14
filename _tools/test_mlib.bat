@echo off
setlocal

::----------------------------------------------------------------
:: Run every test of mlib: first the ones that do not need Maya, then the
:: ones that run in mayapy.
::
::   test_mlib.bat --versions 2027          noMaya/, then inMaya/ in Maya 2027
::   test_mlib.bat --versions 2022 2027     the same, in those versions
::   test_mlib.bat                          the same, in Maya 2025 only (the
::                                          default: one run must stay short)
::   test_mlib.bat --suite unit             only inMaya/unit/ (also integration, all)
::   test_mlib.bat --tests test_joint.py    only those files
::   test_mlib.bat --no-maya                only noMaya/
::   test_mlib.bat --no-pause               do not wait for a key at the end
::                                          (from a terminal or a script)
::
:: Arguments other than --no-maya and --no-pause are passed to
:: __tests__\runMaya.py unchanged.
:: The code itself is checked by format_mlib.bat, which is the other half of
:: the flow (see CONTRIBUTING.md).
::
:: Exit code: 0 when everything passed, otherwise the code of the first
:: failing step. 2 when no Python or no mayapy was found.
::
:: The Japanese messages are in messages.txt and shown by _message.bat (this
:: file stays ASCII). The summary at the end lists each step with [OK], [NG]
:: or [--] (not run), and its last line starts with [OK] or [NG].
::----------------------------------------------------------------
rem Keep the paths before the argument loop: SHIFT changes %0.
SET "TOOLS=%~dp0"
SET "TESTS=%~dp0..\__tests__\"
SET "SAY=CALL "%~dp0_message.bat""
SET "MLIB_TEST_ARGS="
SET "MLIB_TEST_MAYA=1"
SET "MLIB_TEST_PAUSE=1"
SET "MLIB_TEST_RESULT=0"
SET "MLIB_TEST_MESSAGE=test.ok"
rem The result of each step for the summary: OK, NG, or -- (not run).
SET "MLIB_TEST_STEP_NOMAYA=--"
SET "MLIB_TEST_STEP_MAYA=--"

:parse_args
IF "%~1"=="" GOTO :args_done
IF /I "%~1"=="--no-maya" SET "MLIB_TEST_MAYA=" & SHIFT & GOTO :parse_args
IF /I "%~1"=="--no-pause" SET "MLIB_TEST_PAUSE=" & SHIFT & GOTO :parse_args
SET "MLIB_TEST_ARGS=%MLIB_TEST_ARGS% %1"
SHIFT
GOTO :parse_args
:args_done
rem Only look for an installed Python: never let the launcher install one.
SET "PYLAUNCHER_ALLOW_INSTALL="

rem The tests of noMaya/ need a normal Python 3.8 or newer. Prefer the
rem environment of setup.bat, so that one install covers everything.
SET "MLIB_TEST_NOMAYA_PYTHON=%TOOLS%.venv\Scripts\python.exe"
IF NOT EXIST "%MLIB_TEST_NOMAYA_PYTHON%" SET "MLIB_TEST_NOMAYA_PYTHON=py -3"

%SAY% test.step1
%MLIB_TEST_NOMAYA_PYTHON% "%TESTS%runNoMaya.py"
IF NOT ERRORLEVEL 1 GOTO :maya
SET "MLIB_TEST_STEP_NOMAYA=NG"
SET "MLIB_TEST_RESULT=1"
SET "MLIB_TEST_MESSAGE=test.ng.noMaya"
GOTO :summary

:maya
SET "MLIB_TEST_STEP_NOMAYA=OK"
IF DEFINED MLIB_TEST_MAYA GOTO :find_mayapy
%SAY% test.skipMaya
GOTO :summary

:find_mayapy
IF DEFINED MLIB_TEST_PYTHON GOTO :run
FOR %%V IN (2022 2023 2024 2025 2026 2027) DO (
    IF EXIST "%ProgramFiles%\Autodesk\Maya%%V\bin\mayapy.exe" SET "MLIB_TEST_PYTHON=%ProgramFiles%\Autodesk\Maya%%V\bin\mayapy.exe"
)
IF DEFINED MLIB_TEST_PYTHON GOTO :run
%SAY% blank test.noMayapy
SET "MLIB_TEST_RESULT=2"
SET "MLIB_TEST_MESSAGE=test.notRun"
GOTO :summary

:run
%SAY% test.step2
"%MLIB_TEST_PYTHON%" "%TESTS%runMaya.py"%MLIB_TEST_ARGS%
SET "MLIB_TEST_RESULT=%ERRORLEVEL%"
SET "MLIB_TEST_STEP_MAYA=OK"
IF "%MLIB_TEST_RESULT%"=="0" GOTO :summary
SET "MLIB_TEST_STEP_MAYA=NG"
SET "MLIB_TEST_MESSAGE=test.ng.maya"

:summary
%SAY% blank line test.steps rule %MLIB_TEST_MESSAGE% legend line

rem Wait for a key so that the result stays readable when the batch was
rem started by a double click (the same as the other batch files).
IF DEFINED MLIB_TEST_PAUSE (
    ECHO.
    PAUSE
)
EXIT /b %MLIB_TEST_RESULT%
