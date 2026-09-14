' Startet start_windows.bat komplett unsichtbar (kein Konsolenfenster, kein
' Taskleisten-Eintrag) - fuer eine Desktop-/Startmenue-Verknuepfung.
' start_windows.bat selbst bleibt fuer den manuellen Doppelklick nutzbar (zeigt
' dort z.B. Meldungen beim allerersten Setup).
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
skriptOrdner = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = skriptOrdner
shell.Run """" & skriptOrdner & "\start_windows.bat""", 0, False
