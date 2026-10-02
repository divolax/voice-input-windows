Option Explicit

Dim shell, fso, folder, wmi, processes, command
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
Set wmi = GetObject("winmgmts:\\.\root\cimv2")

' Do not start a second keyboard listener: duplicate instances compete for Ctrl+Alt.
Set processes = wmi.ExecQuery("SELECT ProcessId FROM Win32_Process WHERE Name = 'python.exe' AND CommandLine LIKE '%local-dictation%dictation.py%'")
If processes.Count > 0 Then
    WScript.Quit 0
End If

folder = fso.GetParentFolderName(WScript.ScriptFullName)
command = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & folder & "\start.ps1"""
shell.Run command, 0, False
