# Prüft den Übersetzungskern unter Windows PowerShell 5.1 (läuft in GitHub Actions auf windows-latest)
$ErrorActionPreference = 'Stop'
$script:okList = New-Object System.Collections.ArrayList
trap { Write-Host ("::error::Ausnahme: {0} (Zeile {1}: {2})" -f $_.Exception.Message, $_.InvocationInfo.ScriptLineNumber, $_.InvocationInfo.Line.Trim()); exit 1 }
$root = Split-Path -Parent $PSScriptRoot
$src = [IO.File]::ReadAllText((Join-Path $root 'PCPflege.ps1'), [Text.Encoding]::UTF8)
$t = $null; $e = $null
$ast = [Management.Automation.Language.Parser]::ParseInput($src, [ref]$t, [ref]$e)
$e | Select-Object -First 10 | ForEach-Object { Write-Host ("::error::PS 5.1 Parser L{0}: {1}" -f $_.Extent.StartLineNumber, $_.Message) }
if ($e.Count) { throw 'PCPflege.ps1 hat Syntaxfehler unter PowerShell 5.1' }
$a = $ast.FindAll({ $args[0] -is [Management.Automation.Language.AssignmentStatementAst] -and $args[0].Left.Extent.Text -eq '$I18nCs' }, $true) | Select-Object -First 1
$cs = $a.Right.Expression.Value
Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase, System.Xaml
Add-Type -TypeDefinition $cs -ReferencedAssemblies PresentationFramework, PresentationCore, WindowsBase, System.Xaml, System
$d = New-Object 'System.Collections.Generic.Dictionary[string,object]'
$d['Speichern'] = 'Save'; $d['Netzwerk'] = 'Network'; $d['{0} Programme gefunden, {1} davon vorausgewählt.'] = '{0} programs found, {1} of them preselected.'
$d['Fehler beim Start'] = 'Error at startup'; $d['Status'] = 'State'; $d['Nur mein Windows-Konto'] = 'Only my Windows account'; $d['Kritisch'] = 'Critical'
$d['Spalte A'] = 'Column A'; $d['Hinweis zum Knopf'] = 'Button hint'; $d['Erledigt'] = 'Done'
[PcTools.I18n]::Load('en-US', $d); [PcTools.I18n]::Install()
$fail = 0
function Check($got, $want, $what) { if ($got -ceq $want) { [void]$script:okList.Add($what) } else { Write-Host ("::error::FAIL {0} -> '{1}' (erwartet '{2}')" -f $what, $got, $want); $script:fail++ } }
Check ([PcTools.I18n]::T('Speichern')) 'Save' 'exakt'
Check ([PcTools.I18n]::T('  Speichern ')) '  Save ' 'Leerzeichen'
Check ([PcTools.I18n]::T('13 Programme gefunden, 4 davon vorausgewählt.')) '13 programs found, 4 of them preselected.' 'Platzhalter'
Check ([PcTools.I18n]::T("Speichern`nNetzwerk")) "Save`nNetwork" 'mehrzeilig'
Check ([PcTools.I18n]::T('Status: läuft')) 'State: läuft' 'Bezeichnung: Wert'
Check ([PcTools.I18n]::T('Fehler beim Start - Code 5')) 'Error at startup - Code 5' 'Teilstück'
Check ([PcTools.I18n]::T('Unbekannt')) 'Unbekannt' 'unbekannt bleibt'
Check ([PcTools.I18n]::Html('<p>Speichern</p><b>Kritisch</b>')) '<p>Save</p><b>Critical</b>' 'HTML'
$x = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation" xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml" Title="Netzwerk" Width="300" Height="300" ShowInTaskbar="False" WindowStartupLocation="Manual" Left="-2000" Top="-2000">
 <StackPanel>
  <TextBlock x:Name="T1" Text="Speichern"/>
  <TextBlock x:Name="T2">Netzwerk <Bold>Kritisch</Bold></TextBlock>
  <Button x:Name="B1" Content="Speichern" ToolTip="Hinweis zum Knopf"/>
  <ComboBox x:Name="C1" SelectedIndex="0"><ComboBoxItem Content="Nur mein Windows-Konto"/></ComboBox>
  <ComboBox x:Name="C2" Uid="notr" SelectedIndex="0"><ComboBoxItem Uid="notr" Content="Speichern"/></ComboBox>
  <DataGrid x:Name="G1" AutoGenerateColumns="False" Height="80"><DataGrid.Columns><DataGridTextColumn Header="Spalte A" Binding="{Binding A}"/></DataGrid.Columns></DataGrid>
 </StackPanel>
</Window>
'@
$w = [Windows.Markup.XamlReader]::Parse($x)
$w.FindName('G1').ItemsSource = @([pscustomobject]@{ A = 'Kritisch' })
$w.Show()
$w.Dispatcher.Invoke([Action] { }, [Windows.Threading.DispatcherPriority]::ApplicationIdle)
Check $w.Title 'Network' 'Fenstertitel'
Check $w.FindName('T1').Text 'Save' 'TextBlock'
Check $w.FindName('T2').Text 'Network Critical' 'TextBlock mit Inlines'
$w.FindName('T1').Text = 'Erledigt'; Check $w.FindName('T1').Text 'Done' 'TextBlock später geändert'
$b = $w.FindName('B1'); Check ([string]$b.Content) 'Speichern' 'Button-Inhalt bleibt deutsch (Logik)'
$b.ApplyTemplate() | Out-Null
$tbs = New-Object System.Collections.ArrayList
function Get-Tbs($o) { if ($o -is [Windows.Controls.TextBlock]) { [void]$tbs.Add($o.Text) }; for ($i = 0; $i -lt [Windows.Media.VisualTreeHelper]::GetChildrenCount($o); $i++) { Get-Tbs ([Windows.Media.VisualTreeHelper]::GetChild($o, $i)) } }
Get-Tbs $b; Check (($tbs -join '|')) 'Save' 'Button-Anzeige'
Check ([string]$b.ToolTip) 'Button hint' 'ToolTip'
$tbs.Clear(); Get-Tbs $w.FindName('C1'); Check ([string](@($tbs) -join '|')) 'Only my Windows account' 'ComboBox-Anzeige'
Check ([string]$w.FindName('C1').SelectedItem.Content) 'Nur mein Windows-Konto' 'ComboBox-Wert bleibt deutsch'
$tbs.Clear(); Get-Tbs $w.FindName('C2'); Check ([string](@($tbs) -join '|')) 'Speichern' 'notr bleibt unübersetzt'
Check ([string]$w.FindName('G1').Columns[0].Header) 'Column A' 'Tabellenkopf'
$tbs.Clear(); Get-Tbs $w.FindName('G1'); Check ([string](@($tbs) -contains 'Critical')) 'True' 'Tabellenzelle'
$w.Close()
# Taskleistensymbol (C#) übersetzbar und aufrufbar
$m = [regex]::Match($src, "(?s)@'\r?\n(using System;\r?\nusing System.Runtime.InteropServices;\r?\nnamespace PCPflege \{\r?\n    public static class TaskbarIcon.*?)\r?\n'@")
if (-not $m.Success) { Write-Host '::error::TaskbarIcon-Quelltext nicht gefunden'; $fail++ } else {
    Add-Type -TypeDefinition $m.Groups[1].Value
    $w2 = New-Object Windows.Window; $w2.Width = 100; $w2.Height = 100; $w2.Left = -3000; $w2.ShowInTaskbar = $false
    $w2.Show(); $h = (New-Object Windows.Interop.WindowInteropHelper $w2).Handle
    [PCPflege.TaskbarIcon]::Apply($h, (Join-Path $root 'PCPflege.ico'), 'RHEDV.PCPflege.Test', 'cmd.exe', 'PC-Tools'); $w2.Close()
    [void]$script:okList.Add('Taskleistensymbol')
}
# Sprachdateien prüfen
foreach ($f in @(Get-ChildItem (Join-Path $root 'lang') -Filter '*.json' -ErrorAction SilentlyContinue)) {
    Add-Type -AssemblyName System.Web.Extensions
    $js = New-Object Web.Script.Serialization.JavaScriptSerializer; $js.MaxJsonLength = [int]::MaxValue
    $o = $js.DeserializeObject([IO.File]::ReadAllText($f.FullName, [Text.Encoding]::UTF8))
    $n = $o['strings'].Count; $bad = 0
    foreach ($k in $o['strings'].Keys) { $v = [string]$o['strings'][$k]; $pk = @([regex]::Matches($k, '\{\d+') | ForEach-Object { $_.Value } | Sort-Object -Unique); $pv = @([regex]::Matches($v, '\{\d+') | ForEach-Object { $_.Value } | Sort-Object -Unique); if (($pk -join ',') -ne ($pv -join ',')) { $bad++; if ($bad -le 5) { Write-Host ("::warning::Platzhalter ({0}): {1} => {2}" -f $f.Name, $k, $v) } } }
    Write-Host ("::notice::Sprachdatei {0}: {1} Texte, {2} mit abweichenden Platzhaltern" -f $f.Name, $n, $bad)
    if ($bad) { $fail++ }
}
Write-Host ("::notice::Bestanden: " + ($script:okList -join ', '))
if ($fail) { Write-Host "::error::$fail Prüfung(en) fehlgeschlagen"; exit 1 }
