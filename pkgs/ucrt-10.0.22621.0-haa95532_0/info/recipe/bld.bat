@echo on

mkdir %LIBRARY_BIN%

%BUILD_PREFIX%/Library/usr/lib/p7zip/7z.exe x 22621.1.220506-1250.ni_release_WindowsSDK.iso -aoa
if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%

msiexec /a "%SRC_DIR%\Installers\Universal CRT Redistributable-x86_en-us.msi" /qb TARGETDIR="%SRC_DIR%\tmp"
if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%

xcopy "tmp\Windows Kits\10\Redist\%PKG_VERSION%\ucrt\DLLs\x64\"* "%PREFIX%"
if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%

xcopy "tmp\Windows Kits\10\Redist\%PKG_VERSION%\ucrt\DLLs\x64\"* "%LIBRARY_BIN%"
if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%
