# Baut PC-Tools.exe mit dem C#-Compiler von .NET Framework 4.x (auf jedem Windows vorhanden, kein SDK nötig)
param([string]$Version = '0.0.0', [string]$Out = 'dist')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path $csc)) { $csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe' }
$v = (($Version -split '[^\d]+' | Where-Object { $_ }) + @('0', '0', '0', '0'))[0..3] -join '.'
$src = Join-Path $env:TEMP 'PC-Tools-launcher.cs'
(Get-Content (Join-Path $PSScriptRoot 'PC-Tools.cs') -Raw).Replace('__VERSION__', $v) | Set-Content $src -Encoding UTF8
New-Item -ItemType Directory -Path $Out -Force | Out-Null
$exe = Join-Path (Resolve-Path $Out) 'PC-Tools.exe'
& $csc /nologo /target:winexe /optimize+ /platform:anycpu "/out:$exe" "/win32icon:$(Join-Path $root 'PCPflege.ico')" "/win32manifest:$(Join-Path $PSScriptRoot 'app.manifest')" /reference:System.Windows.Forms.dll $src
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $exe)) { throw 'Kompilieren fehlgeschlagen' }
Get-Item $exe | Select-Object Name, Length, @{ n = 'Version'; e = { $_.VersionInfo.FileVersion } }
