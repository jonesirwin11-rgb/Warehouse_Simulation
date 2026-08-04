@@echo off

:: Ensure delayed variable expansion
setlocal enabledelayedexpansion

:: CMAKE_PREFIX_PATH is set for both the build and runtime environments.
:: Unlike the build environment, there is a chance that CMAKE_PREFIX_PATH
:: gets modified after activation, but before deactivation. For this reason
:: we are removing the conda library path from CMAKE_PREFIX_PATH that we added
:: instead of restoring the value that was saved in the activation script.

:: Initialize a new variable to store the cleaned path
set "NEW_CMAKE_PREFIX_PATH="

:: Iterate through each path entry
for %%I in (%CMAKE_PREFIX_PATH%) do (
    if /I not "%%I"=="%CONDA_PREFIX%\Library" (
        if defined NEW_CMAKE_PREFIX_PATH (
            set "NEW_CMAKE_PREFIX_PATH=!NEW_CMAKE_PREFIX_PATH!;%%I"
        ) else (
            set "NEW_CMAKE_PREFIX_PATH=%%I"
        )
    )
)

:: Disable setlocal so changes persist
endlocal & set "CMAKE_PREFIX_PATH=%NEW_CMAKE_PREFIX_PATH%"
