@echo off
setlocal

::----------------------------------------------------------------
:: Build the Sphinx documentation of mlib (_docs\source) into
:: _docs\_build\html, from an empty output folder. Optional: run it when the
:: documentation is wanted, after format_mlib.bat and test_mlib.bat
:: (see CONTRIBUTING.md).
::
::   build_mlib_docs.bat              build, then wait for a key
::   build_mlib_docs.bat --no-pause   do not wait (for terminals and other scripts)
::
:: Exit code: 0 when the build succeeded, otherwise 1 or the code of Sphinx.
::
:: The Japanese messages are in messages.txt and shown by _message.bat (this
:: file stays ASCII). The last message starts with [OK] or [NG].
::----------------------------------------------------------------
rem Sphinx lives in the one environment of setup.bat, together with ruff.
set "MLIB_TOOLS_DIR=%~dp0"
set "SAY=call "%~dp0_message.bat""
set "MLIB_DOCS_PYTHON=%~dp0.venv\Scripts\python.exe"
set "MLIB_DOCS_SOURCE=%~dp0..\_docs\source"
set "MLIB_DOCS_MAYAPY_FILE=%~dp0.mayapy-site\mayapy-path.txt"
set "MLIB_DOCS_RESULT=1"
set "MLIB_DOCS_MESSAGE=docs.noEnvironment"
rem Resolve ".." so that the path shown at the end can be read and copied.
for %%P in ("%~dp0..\_docs\_build\html") do set "MLIB_DOCS_OUTPUT=%%~fP"

if exist "%MLIB_DOCS_PYTHON%" goto clean
rem setup.bat used mayapy when no Python was found: run Sphinx with the same
rem mayapy and the packages it installed into .mayapy-site.
if exist "%MLIB_DOCS_MAYAPY_FILE%" set /p MLIB_DOCS_PYTHON=<"%MLIB_DOCS_MAYAPY_FILE%"
if not exist "%MLIB_DOCS_PYTHON%" goto finish
set "PYTHONNOUSERSITE=1"
set "PYTHONPATH=%~dp0.mayapy-site"

:clean
rem Sphinx never deletes files from an existing output folder, so files that
rem were removed from the sources (for example old _static assets) would stay
rem in the build. Start every rebuild from an empty output folder.
set "MLIB_DOCS_MESSAGE=docs.cannotClean"
if exist "%MLIB_DOCS_OUTPUT%" rmdir /s /q "%MLIB_DOCS_OUTPUT%"
if exist "%MLIB_DOCS_OUTPUT%" goto finish

rem -P keeps the current folder off sys.path: run from the mlib folder, its json package
rem would shadow the standard json module that Sphinx imports.
rem -n reports cross references that do not resolve (nitpick_ignore_regex in conf.py lists the allowed ones).
%SAY% docs.building
"%MLIB_DOCS_PYTHON%" -P -m sphinx -E -a -b html -n -W --keep-going "%MLIB_DOCS_SOURCE%" "%MLIB_DOCS_OUTPUT%"
set "MLIB_DOCS_RESULT=%ERRORLEVEL%"
set "MLIB_DOCS_MESSAGE=docs.ng"
if "%MLIB_DOCS_RESULT%"=="0" set "MLIB_DOCS_MESSAGE=docs.ok"

:finish
%SAY% blank line %MLIB_DOCS_MESSAGE% line
echo.
if /I not "%~1"=="--no-pause" pause
exit /b %MLIB_DOCS_RESULT%
