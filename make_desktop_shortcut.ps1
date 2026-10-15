$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktopDir = [Environment]::GetFolderPath('Desktop')
$pythonwPath = Join-Path $projectDir '.venv\Scripts\pythonw.exe'
$mainPath = Join-Path $projectDir 'main.py'
$scriptPath = Join-Path $projectDir 'launch_hidden.vbs'

# Point the shortcut directly at the venv interpreter when available. This
# avoids Windows file-association errors for .vbs files. Keep the WScript
# fallback so the shortcut can still be created before dependencies are set up.
if ([System.IO.File]::Exists($pythonwPath)) {
    $targetPath = $pythonwPath
    $shortcutArguments = '"' + $mainPath + '"'
} else {
    $targetPath = Join-Path $env:WINDIR 'System32\wscript.exe'
    $shortcutArguments = '"' + $scriptPath + '"'
}

$chineseName = ([char]0x72D0) + ([char]0x72F8) + ([char]0x5F85) + ([char]0x529E) + ([char]0x5C0F) + ([char]0x7EC4) + ([char]0x4EF6) + '.lnk'
$shortcutNames = @('FoxTodoWidget.lnk', $chineseName)
$shell = New-Object -ComObject WScript.Shell

foreach ($shortcutName in $shortcutNames) {
    $shortcutPath = Join-Path $desktopDir $shortcutName
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $targetPath
    $shortcut.Arguments = $shortcutArguments
    $shortcut.WorkingDirectory = $projectDir
    $shortcut.Description = 'Fox Todo Widget (Windows Script Host)'
    $shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,44"
    $shortcut.Save()
    Write-Host "Created shortcut: $shortcutPath"
}
