Option Explicit
Dim shell, files, root, runtime, app
Set shell = CreateObject("WScript.Shell")
Set files = CreateObject("Scripting.FileSystemObject")
root = files.GetParentFolderName(WScript.ScriptFullName)
runtime = shell.ExpandEnvironmentStrings("%USERPROFILE%") & "\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
If Not files.FileExists(runtime) Then
  MsgBox "The bundled Python runtime was not found. Open this project in Codex to restore it.", 48, "NCCE Writing Lab"
  WScript.Quit 1
End If
app = root & "\scripts\writer_quality_gui.py"
shell.CurrentDirectory = root
shell.Run Chr(34) & runtime & Chr(34) & " " & Chr(34) & app & Chr(34), 0, True
