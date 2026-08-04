



if not exist %LIBRARY_PREFIX%\\bin\\wish.exe exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if not exist %LIBRARY_PREFIX%\\bin\\tclsh.exe exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if not exist %LIBRARY_PREFIX%\\bin\\wish86.exe exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if not exist %LIBRARY_PREFIX%\\bin\\tclsh86.exe exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if not exist %LIBRARY_PREFIX%\\include\\tcl.h exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if not exist %LIBRARY_PREFIX%\\include\\tclDecls.h exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if not exist %LIBRARY_PREFIX%\\include\\tclPlatDecls.h exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if not exist %LIBRARY_PREFIX%\\include\\tclPlatDecls.h exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if not exist %LIBRARY_PREFIX%\\include\\tclTomMathDecls.h exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if not exist %LIBRARY_PREFIX%\\include\\tclTomMath.h exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if not exist %LIBRARY_PREFIX%\\include\\tk.h exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if not exist %LIBRARY_PREFIX%\\include\\tkDecls.h exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if not exist %LIBRARY_PREFIX%\\include\\tkPlatDecls.h exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if not exist %LIBRARY_PREFIX%\\lib\\tcl86t.lib exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if not exist %LIBRARY_PREFIX%\\bin\\tcl86t.dll exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if not exist %LIBRARY_PREFIX%\\lib\\tclstub86.lib exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if not exist %LIBRARY_PREFIX%\\lib\\tk86t.lib exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if not exist %LIBRARY_PREFIX%\\bin\\tk86t.dll exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if not exist %LIBRARY_PREFIX%\\lib\\tkstub86.lib exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
tclsh hello.tcl
IF %ERRORLEVEL% NEQ 0 exit /B 1
tclsh86 hello.tcl
IF %ERRORLEVEL% NEQ 0 exit /B 1
wish hello.tcl
IF %ERRORLEVEL% NEQ 0 exit /B 1
wish86t hello.tcl
IF %ERRORLEVEL% NEQ 0 exit /B 1
exit /B 0
