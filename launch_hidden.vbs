Option Explicit

Dim fso, shell, baseDir, pythonw, command
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
baseDir = fso.GetParentFolderName(WScript.ScriptFullName)

pythonw = fso.BuildPath(baseDir, ".venv\Scripts\pythonw.exe")
If Not fso.FileExists(pythonw) Then
    pythonw = "pythonw.exe"
End If

command = Chr(34) & pythonw & Chr(34) & " " & Chr(34) & fso.BuildPath(baseDir, "main.py") & Chr(34)
On Error Resume Next
shell.Run command, 0, False
If Err.Number <> 0 Then
    Err.Clear
    MsgBox "没有找到 pythonw.exe。请先双击“安装依赖.bat”。", 48, "狐狸待办小组件"
End If
On Error GoTo 0
