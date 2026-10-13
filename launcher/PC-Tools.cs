// PC-Tools Starter (Open Source, Apache-2.0)
// Startet PCPflege.ps1 unsichtbar mit Windows PowerShell 5.1 - genau wie PCPflege.cmd, nur als signierbare EXE.
// Keine Netzwerkzugriffe, keine Änderungen am System: der Starter sucht nur das Skript und übergibt die Parameter.
using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text;
using System.Windows.Forms;

[assembly: AssemblyTitle("PC-Tools")]
[assembly: AssemblyDescription("PC-Tools - Windows-Pflege, Reparatur und Netzwerk-Dokumentation (Open Source)")]
[assembly: AssemblyCompany("PC-Tools Open Source Project")]
[assembly: AssemblyProduct("PC-Tools")]
[assembly: AssemblyCopyright("Apache License 2.0 - https://github.com/rhedv42-sudo/pc-tools")]
[assembly: AssemblyVersion("__VERSION__")]
[assembly: AssemblyFileVersion("__VERSION__")]
[assembly: AssemblyInformationalVersion("__VERSION__")]

static class Program {
    static string Quote(string a) {
        if (a.Length > 0 && a.IndexOfAny(new[] { ' ', '\t', '"' }) < 0) return a;
        var sb = new StringBuilder("\"");
        int bs = 0;
        foreach (char c in a) {
            if (c == '\\') { bs++; continue; }
            if (c == '"') { sb.Append('\\', bs * 2 + 1); sb.Append('"'); bs = 0; continue; }
            sb.Append('\\', bs); bs = 0; sb.Append(c);
        }
        sb.Append('\\', bs * 2); sb.Append('"');
        return sb.ToString();
    }
    [STAThread]
    static int Main(string[] args) {
        string dir = AppDomain.CurrentDomain.BaseDirectory;
        string[] candidates = {
            Path.Combine(dir, "PCPflege.ps1"),
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "PCPflege", "PCPflege.ps1")
        };
        string script = null;
        foreach (var c in candidates) if (File.Exists(c)) { script = c; break; }
        if (script == null) {
            MessageBox.Show("PCPflege.ps1 wurde nicht gefunden.\n\nBitte PC-Tools neu installieren: https://github.com/rhedv42-sudo/pc-tools/releases\n\nPCPflege.ps1 was not found - please reinstall PC-Tools.", "PC-Tools", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return 2;
        }
        string sys = Environment.GetFolderPath(Environment.SpecialFolder.System);
        string ps = Path.Combine(sys, @"WindowsPowerShell\v1.0\powershell.exe");
        if (!File.Exists(ps)) ps = "powershell.exe";
        var a = new StringBuilder("-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ");
        a.Append(Quote(script));
        foreach (var x in args) { a.Append(' '); a.Append(Quote(x)); }
        string conhost = Path.Combine(sys, "conhost.exe");
        var psi = new ProcessStartInfo { UseShellExecute = false, WorkingDirectory = Path.GetDirectoryName(script) };
        // conhost --headless verhindert das kurze Aufblitzen eines Konsolenfensters (Windows 10 2004 und neuer)
        if (File.Exists(conhost) && Environment.OSVersion.Version.Build >= 19041) { psi.FileName = conhost; psi.Arguments = "--headless " + Quote(ps) + " " + a; }
        else { psi.FileName = ps; psi.Arguments = a.ToString(); psi.CreateNoWindow = true; }
        try { Process.Start(psi); return 0; }
        catch (Exception ex) { MessageBox.Show("PC-Tools konnte nicht gestartet werden:\n" + ex.Message, "PC-Tools", MessageBoxButtons.OK, MessageBoxIcon.Error); return 1; }
    }
}
