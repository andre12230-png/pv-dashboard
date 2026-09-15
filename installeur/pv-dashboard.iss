; ==========================================================================
;  Recette de l'installeur Windows de Gestion Photovoltaïque (Inno Setup 6).
;
;  Ne pas compiler ce fichier directement : lancer
;      py faire_installeur.py
;  qui vérifie le dossier construit, fournit le numéro de version et
;  produit distribution\pv-dashboard-Setup-X.Y.Z.exe.
;
;  Règle d'or : l'installeur ne livre QUE le programme et les modèles de
;  configuration. Les données (config.yaml rempli, Releves-pv.csv,
;  backups\) vivent dans %LOCALAPPDATA%\pv-dashboard — voir
;  resolve_base_dir() dans app_desktop.py. Ni l'installation, ni la mise à
;  jour, ni la désinstallation n'y touchent.
; ==========================================================================

#ifndef AppVersion
  #error Lancer faire_installeur.py : il fournit le numéro de version.
#endif

; Dossiers du projet, calculés depuis l'emplacement de ce fichier.
#define Racine AddBackslash(SourcePath) + "..\"
#define Construit Racine + "dist\pv-dashboard"

[Setup]
; Identifiant permanent de l'application : c'est lui qui permet à une
; nouvelle version de reconnaître et de remplacer l'ancienne. NE JAMAIS LE
; CHANGER, sinon Windows verrait deux logiciels distincts.
AppId={{3F7B2C94-5A1E-4D86-B0C3-9E4A71D25F68}
AppName=Gestion Photovoltaïque
AppVersion={#AppVersion}
AppVerName=Gestion Photovoltaïque {#AppVersion}
AppPublisher=andre12230-png

; Installation pour l'utilisateur seul, sans mot de passe administrateur :
; dans %LOCALAPPDATA%\Programs\pv-dashboard, comme Pécule.
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\pv-dashboard
DefaultGroupName=Gestion Photovoltaïque
DisableProgramGroupPage=yes
; Une mise à jour réutilise le dossier déjà choisi, sans reposer la question.
UsePreviousAppDir=yes
DisableDirPage=auto

; Programme 64 bits uniquement.
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; L'application n'est jamais fermée de force (une saisie en cours serait
; perdue) : on demande à l'utilisateur de la fermer, voir [Code].
CloseApplications=no

OutputDir={#Racine}distribution
OutputBaseFilename=pv-dashboard-Setup-{#AppVersion}
SetupIconFile={#Racine}pv-dashboard.ico
UninstallDisplayIcon={app}\pv-dashboard.exe
UninstallDisplayName=Gestion Photovoltaïque
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes

; Informations affichées dans les propriétés du fichier Setup.exe.
VersionInfoVersion={#AppVersion}
VersionInfoProductName=Gestion Photovoltaïque
VersionInfoDescription=Installation de Gestion Photovoltaïque
VersionInfoCompany=andre12230-png

[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "bureau"; Description: "Créer un raccourci sur le Bureau"; GroupDescription: "Raccourcis :"; Flags: unchecked

[InstallDelete]
; Mise à jour : on vide d'abord le moteur du programme, pour qu'aucune
; bibliothèque d'une ancienne version ne traîne. Seulement _internal :
; rien d'autre dans le dossier n'est effacé.
Type: filesandordirs; Name: "{app}\_internal"

[Dirs]
; Le dossier des données existe dès l'installation, pour que le raccourci
; « Dossier des données » mène quelque part avant le premier lancement.
; Il n'est jamais supprimé à la désinstallation : ce sont les relevés.
Name: "{localappdata}\pv-dashboard"; Flags: uninsneveruninstall

[Files]
; Le dossier construit par PyInstaller (pv-dashboard.exe + _internal\). Par
; sécurité, une donnée personnelle oubliée à sa racine n'est JAMAIS livrée
; (le « \ » en tête limite chaque motif à la racine du dossier).
Source: "{#Construit}\*"; DestDir: "{app}"; Excludes: "\config.yaml,\config-local.yaml,\Releves-pv.csv,\backups,\*.log"; Flags: ignoreversion recursesubdirs createallsubdirs
; Les modèles, recopiés dans le dossier des données au premier lancement
; (jamais par-dessus une configuration existante : voir
; installer_modeles_config() dans app_desktop.py).
Source: "{#Racine}config.yaml"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Racine}config-local.exemple.yaml"; DestDir: "{app}"; Flags: ignoreversion
; L'icône de la fenêtre.
Source: "{#Racine}pv-dashboard.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Gestion Photovoltaïque"; Filename: "{app}\pv-dashboard.exe"; WorkingDir: "{app}"
Name: "{group}\Dossier des données"; Filename: "{localappdata}\pv-dashboard"
Name: "{autodesktop}\Gestion Photovoltaïque"; Filename: "{app}\pv-dashboard.exe"; WorkingDir: "{app}"; Tasks: bureau

[Run]
Filename: "{app}\pv-dashboard.exe"; Description: "Lancer Gestion Photovoltaïque"; Flags: nowait postinstall skipifsilent

[Code]
{ Application ouverte pendant une mise à jour ou une désinstallation : ses
  fichiers sont occupés et le remplacement échouerait à moitié. On ne la
  ferme pas de force : on demande à l'utilisateur de le faire, et on
  s'arrête proprement s'il renonce. }

function ApplicationOuverte(): Boolean;
var
  Wmi, Resultats: Variant;
begin
  Result := False;
  try
    Wmi := CreateOleObject('WbemScripting.SWbemLocator');
    Resultats := Wmi.ConnectServer('.', 'root\CIMV2').ExecQuery(
      'SELECT ProcessId FROM Win32_Process WHERE Name = ''pv-dashboard.exe''');
    Result := Resultats.Count > 0;
  except
    { Si Windows ne sait pas répondre, on continue : au pire, Inno Setup
      signalera lui-même un fichier occupé. }
  end;
end;

function AttendreFermeture(): Boolean;
begin
  Result := True;
  while ApplicationOuverte() do
    { En mode silencieux, la réponse par défaut est « Annuler » : pas de
      boucle sans fin. }
    if SuppressibleMsgBox('Gestion Photovoltaïque est ouvert.' + #13#10 + #13#10 +
        'Fermez-le, puis cliquez sur OK.', mbError, MB_OKCANCEL, IDCANCEL) = IDCANCEL then
    begin
      Result := False;
      Exit;
    end;
end;

function InitializeSetup(): Boolean;
begin
  Result := AttendreFermeture();
end;

function InitializeUninstall(): Boolean;
begin
  Result := AttendreFermeture();
end;
