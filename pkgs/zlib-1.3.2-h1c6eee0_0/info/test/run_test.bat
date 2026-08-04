

@echo on

if not exist %LIBRARY_LIB%\zlibstatic.lib exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if not exist %LIBRARY_LIB%\zlib.lib exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if not exist %LIBRARY_LIB%\pkgconfig\zlib.pc exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if not exist %LIBRARY_INC%\zlib.h exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if exist %LIBRARY_LIB%\zlibwapi.lib exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
call test_compile_flags.bat
IF %ERRORLEVEL% NEQ 0 exit /B 1
exit /B 0
