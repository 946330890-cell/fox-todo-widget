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

$desktopDir = Join-Path $env:USERPROFILE 'Desktop'
$shortcutPath = Join-Path $desktopDir 'FoxTodoWidget.lnk'
$shell = New-Object -ComObject WScript.Shell
if (Test-Path -LiteralPath $shortcutPath) {
    Remove-Item -LiteralPath $shortcutPath -Force
}
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $exePath
$shortcut.Arguments = ''
$shortcut.WorkingDirectory = $targetDir
$shortcut.Description = 'FoxTodoWidget'
$shortcut.Save()
$chineseName = ([char]0x72D0) + ([char]0x72F8) + ([char]0x5F85) + ([char]0x529E) + ([char]0x5C0F) + ([char]0x7EC4) + ([char]0x4EF6) + '.lnk'
Copy-Item -LiteralPath $shortcutPath -Destination (Join-Path $desktopDir $chineseName) -Force

Start-Process -FilePath $exePath -WorkingDirectory $targetDir
