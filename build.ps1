function Invoke-NiceGUIPack {
    param ([switch]$OneFile)
    Remove-Item build, dist -Recurse -ErrorAction SilentlyContinue
    nicegui-pack.exe --name psvr2toolkit-installer --windowed ($OneFile ? '--onefile' : '--') src\psvr2toolkit_installer\__main__.py
}

Invoke-NiceGUIPack
7z.exe a dist\psvr2toolkit-installer
Move-Item dist\psvr2toolkit-installer.7z .
Invoke-NiceGUIPack -OneFile
Move-Item dist\psvr2toolkit-installer\* .
flit.exe publish
Remove-Item build, dist -Recurse -ErrorAction SilentlyContinue
Pause