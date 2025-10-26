function Invoke-NiceGUIPack {
    param ([switch]$OneFile)
    Remove-Item build, dist -Recurse -ErrorAction SilentlyContinue
    nicegui-pack.exe --name psvr2toolkit-installer --windowed ($OneFile ? '--onefile' : '--') src\psvr2toolkit_installer\__main__.py
}

Invoke-NiceGUIPack
7z.exe a psvr2toolkit-installer dist\psvr2toolkit-installer
Invoke-NiceGUIPack -OneFile
Move-Item dist\* . -Force
flit.exe publish
Remove-Item build, dist -Recurse -ErrorAction SilentlyContinue
Pause