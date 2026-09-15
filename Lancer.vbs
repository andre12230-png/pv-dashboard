' Lance pv-dashboard de maniere totalement silencieuse (aucune console).
' Cherche pyw.exe dans le PATH (le Python Launcher Windows officiel) puis
' lance l'app avec un chemin absolu, car WshShell.Run ne fait PAS de
' PATH lookup sur les .exe (contrairement a cmd).
' Pour un mode debug avec console visible, utilisez Lancer.bat.

Option Explicit

' --- helper : cherche un .exe dans %PATH%, retourne "" si introuvable ---
Function FindInPath(exeName)
    Dim sh2, fso2, paths, p, full
    Set sh2 = CreateObject("WScript.Shell")
    Set fso2 = CreateObject("Scripting.FileSystemObject")
    paths = Split(sh2.ExpandEnvironmentStrings("%PATH%"), ";")
    For Each p In paths
        If p <> "" Then
            full = fso2.BuildPath(p, exeName)
            If fso2.FileExists(full) Then
                FindInPath = full
                Exit Function
            End If
        End If
    Next
    FindInPath = ""
End Function

Dim sh, fso, racine, pyw
Set sh  = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
racine  = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = racine

pyw = FindInPath("pyw.exe")
If pyw = "" Then
    MsgBox "Python Launcher (pyw.exe) introuvable dans le PATH." & vbCrLf & vbCrLf & _
           "Installez Python 3 depuis python.org (cochez 'Add Python " & _
           "to PATH' et 'Install launcher for all users').", _
           vbCritical, "pv-dashboard"
    WScript.Quit 1
End If

sh.Run """" & pyw & """ """ & racine & "\run.py""", 0, False
