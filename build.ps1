function Invoke-NiceGUIPack {
    param ([switch]$OneFile)
    Remove-Item build, dist -Recurse -ErrorAction SilentlyContinue
    nicegui-pack.exe --name $Name --windowed ($OneFile ? '--onefile' : '--') src\$Module\__main__.py
}

$Name = 'psvr2toolkit-installer'
$Module = $Name -replace '-', '_'

Invoke-NiceGUIPack
7z.exe a $Name dist\$Name
Invoke-NiceGUIPack -OneFile
Move-Item dist\* . -Force
flit.exe publish
Remove-Item build, dist -Recurse -ErrorAction SilentlyContinue
Pause