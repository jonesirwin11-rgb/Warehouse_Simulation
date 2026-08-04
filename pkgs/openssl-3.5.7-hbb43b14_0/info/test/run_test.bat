

@echo on

copy NUL checksum.txt
IF %ERRORLEVEL% NEQ 0 exit /B 1
openssl sha256 checksum.txt
IF %ERRORLEVEL% NEQ 0 exit /B 1
openssl ecparam -name prime256v1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if "%SSL_CERT_FILE%"=="" exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if not exist "%SSL_CERT_FILE%" exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
python -c "import urllib.request; urllib.request.urlopen('https://pypi.org')"
IF %ERRORLEVEL% NEQ 0 exit /B 1
pkg-config --print-errors --exact-version "3.5.7" openssl
IF %ERRORLEVEL% NEQ 0 exit /B 1
if not exist "%LIBRARY_LIB%\libcrypto.lib" exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if not exist "%LIBRARY_LIB%\libssl.lib" exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if not exist "%LIBRARY_LIB%\pkgconfig\libssl.pc" exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if not exist "%LIBRARY_LIB%\pkgconfig\libcrypto.pc" exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if not exist "%LIBRARY_LIB%\pkgconfig\openssl.pc" exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if not exist "%LIBRARY_BIN%\openssl.exe" exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
if not exist "%LIBRARY_INC%\openssl" exit 1
IF %ERRORLEVEL% NEQ 0 exit /B 1
exit /B 0
