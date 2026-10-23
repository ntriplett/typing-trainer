' Desktop-icon target on Windows: runs the launcher with no visible console
' window, then exits (the server itself keeps running detached). Point a
' desktop shortcut at this file.
'
' Expects a venv at ..\.venv relative to this file (created by the one-time
' setup step - see README.md). Update the path below if you package the app
' differently later.

Set shell = CreateObject("WScript.Shell")
scriptDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
pythonw = scriptDir & "\..\.venv\Scripts\pythonw.exe"
launcher = scriptDir & "\start.py"

shell.Run """" & pythonw & """ """ & launcher & """", 0, False
