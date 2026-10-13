<#
    Baut die fünf Download-Pakete und version.json aus dem Quellcode (lokal oder in GitHub Actions).
    Aufruf:  pwsh ./build/Build-Packages.ps1 [-Out dist]
    Nimmt PCPflege.ps1 aus dem Projektordner (in der Release-Pipeline vorher durch die signierte Fassung ersetzt).
#>
param([string]$Out = 'dist')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$ver = (Select-String -Path PCPflege.ps1 -Pattern "^\`$AppVersion = '([^']+)'").Matches[0].Groups[1].Value
if (-not $ver) { throw 'AppVersion in PCPflege.ps1 nicht gefunden.' }
New-Item -ItemType Directory -Path $Out -Force | Out-Null
Get-ChildItem $Out -Filter '*.zip' -ErrorAction SilentlyContinue | Remove-Item -Force
$stage = Join-Path $Out 'stage'

function New-Pkg([string]$Name, [bool]$Portable, [bool]$Lite) {
    $d = Join-Path $stage $Name; $pt = Join-Path $d 'PC-Tools'
    New-Item -ItemType Directory -Path (Join-Path $pt 'Zubehoer') -Force | Out-Null
    Copy-Item PCPflege.ps1, PCPflege.ico, Komplett-Reparatur.cmd -Destination $pt
    if (Test-Path (Join-Path $Out 'PC-Tools.exe')) { Copy-Item (Join-Path $Out 'PC-Tools.exe') -Destination $pt }
    if (Test-Path lang) { New-Item -ItemType Directory -Path (Join-Path $pt 'lang') -Force | Out-Null; Copy-Item lang/*.json -Destination (Join-Path $pt 'lang') }
    Copy-Item Zubehoer/* -Destination (Join-Path $pt 'Zubehoer') -Recurse
    Copy-Item SICHERHEIT.md -Destination (Join-Path $pt 'Zubehoer')
    if ($Portable) {
        Copy-Item pakete/portabel/* -Destination $pt
        New-Item -ItemType Directory -Path (Join-Path $pt 'Surface') -Force | Out-Null
    } else {
        Copy-Item PCPflege.cmd -Destination $pt
        $t = (Get-Content pakete/vollversion/LIESMICH.txt -Raw) -replace '^PC-Tools [\d\.]+', ('PC-Tools ' + $ver)
        Set-Content -Path (Join-Path $pt 'LIESMICH.txt') -Value $t -Encoding UTF8 -NoNewline
    }
    if ($Lite) { Copy-Item pakete/lite/lite.txt -Destination $pt }
    return $d
}
$pk = [ordered]@{
    ("PC-Tools-$ver")                = (New-Pkg 'voll' $false $false)
    ("PC-Tools-$ver-portabel")       = (New-Pkg 'voll-portabel' $true $false)
    ("PC-Tools-Lite-$ver")           = (New-Pkg 'lite' $false $true)
    ("PC-Tools-Lite-$ver-portabel")  = (New-Pkg 'lite-portabel' $true $true)
}
foreach ($k in $pk.Keys) { Compress-Archive -Path (Join-Path $pk[$k] 'PC-Tools') -DestinationPath (Join-Path $Out "$k.zip") }
# Alle Pakete in einem
$all = Join-Path $stage "PC-Tools-$ver-Alle-Pakete"
New-Item -ItemType Directory -Path $all | Out-Null
Copy-Item -Path (Join-Path $pk["PC-Tools-$ver-portabel"] 'PC-Tools') -Destination (Join-Path $all 'Vollversion-portabel/PC-Tools') -Recurse
Copy-Item -Path (Join-Path $pk["PC-Tools-Lite-$ver-portabel"] 'PC-Tools') -Destination (Join-Path $all 'Lite-portabel/PC-Tools') -Recurse
Compress-Archive -Path $all -DestinationPath (Join-Path $Out "PC-Tools-$ver-Alle-Pakete.zip")
# version.json für das Selbstupdate
$sha = { param($f) (Get-FileHash $f -Algorithm SHA256).Hash }
$vj = [ordered]@{ Version = $ver; Date = (Get-Date -Format 'yyyy-MM-dd HH:mm'); Notes = "PC-Tools $ver"; Files = @(
    [ordered]@{ Name = 'PCPflege.ps1'; Sha256 = (& $sha PCPflege.ps1) },
    [ordered]@{ Name = 'PCPflege.ico'; Sha256 = (& $sha PCPflege.ico) },
    [ordered]@{ Name = 'PCPflege.cmd'; Sha256 = (& $sha PCPflege.cmd) }) }
$vj | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $Out 'version.json') -Encoding UTF8
Remove-Item $stage -Recurse -Force
Get-ChildItem $Out | ForEach-Object { '{0,-45} {1,12:N0}' -f $_.Name, $_.Length }
