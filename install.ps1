$ErrorActionPreference = 'Stop'

$packageDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$sourceDir = Join-Path $packageDir 'FoxTodoWidget'
$targetDir = Join-Path $env:LOCALAPPDATA 'FoxTodoWidget'
$sourceExePath = Join-Path $sourceDir 'FoxTodoWidget.exe'
$exePath = Join-Path $targetDir 'FoxTodoWidget.exe'

if (-not (Test-Path -LiteralPath $sourceExePath)) {
    throw 'FoxTodoWidget.exe was not found. The release package is incomplete.'
}

New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
Copy-Item -Path (Join-Path $sourceDir '*') -Destination $targetDir -Recurse -Force
New-Item -ItemType Directory -Force -Path (Join-Path $targetDir 'data') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $targetDir 'exports') | Out-Null

$desktopDir = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktopDir 'FoxTodoWidget.lnk'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $exePath
$shortcut.WorkingDirectory = $targetDir
$shortcut.Description = 'FoxTodoWidget'
$shortcut.Save()

Start-Process -FilePath $exePath -WorkingDirectory $targetDir
