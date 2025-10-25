Remove-Item build, dist -Recurse
nicegui-pack.exe --name "psvr2toolkit-installer" --windowed --onefile src\psvr2toolkit_installer\__main__.py
Move-Item dist\psvr2toolkit-installer.exe .
Remove-Item build, dist -Recurse
nicegui-pack.exe --name "psvr2toolkit-installer" --windowed src\psvr2toolkit_installer\__main__.py
Pause