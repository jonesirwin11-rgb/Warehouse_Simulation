

@echo on

if not exist %LIBRARY_BIN%\zlib.dll exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if not exist %PREFIX%\zlib.dll exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
exit /B 0
