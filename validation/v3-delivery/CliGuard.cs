// Experiment-only boundary guard. No credentials or argument payloads are logged.
using System;
using System.IO;
using System.Text;
using System.Linq;
using System.Diagnostics;
using System.Threading.Tasks;
class CliGuard {
    static void Mark(string value) {
        string path = Environment.GetEnvironmentVariable("CHEM_PROBE_COUNTER");
        if (!String.IsNullOrEmpty(path)) File.AppendAllText(path, value);
    }
    static string Quote(string value) {
        var b = new StringBuilder("\""); int slash = 0;
        foreach (char c in value) {
            if (c == '\\') { slash++; continue; }
            b.Append('\\', c == '"' ? slash * 2 + 1 : slash);
            b.Append(c); slash = 0;
        }
        b.Append('\\', slash * 2); b.Append('"'); return b.ToString();
    }
    static int Main(string[] args) {
        if (Path.GetFileNameWithoutExtension(Environment.GetCommandLineArgs()[0]).Equals("codex", StringComparison.OrdinalIgnoreCase)) {
            Mark("M"); Console.Error.WriteLine("Experiment model guard: inference forbidden"); return 98;
        }
        bool build = args.Length > 0 && (args[0] == "build" || (args[0] == "buildx" && args.Contains("build")));
        Mark(build ? "B" : "D");
        string missing = Environment.GetEnvironmentVariable("CHEM_PROBE_MISSING_IMAGE");
        if (!String.IsNullOrEmpty(missing) && args.Contains(missing) &&
            (args[0] == "inspect" || (args.Length > 1 && args[0] == "image" && args[1] == "inspect"))) {
            Mark("F"); Console.Error.WriteLine("Injected isolated observation: No such image: " + missing); return 1;
        }
        var info = new ProcessStartInfo(Environment.GetEnvironmentVariable("CHEM_PROBE_REAL_DOCKER"), String.Join(" ", args.Select(Quote)));
        info.UseShellExecute = false; info.CreateNoWindow = true;
        info.RedirectStandardOutput = true; info.RedirectStandardError = true;
        using (var p = Process.Start(info)) {
            Task a = p.StandardOutput.BaseStream.CopyToAsync(Console.OpenStandardOutput());
            Task b = p.StandardError.BaseStream.CopyToAsync(Console.OpenStandardError());
            p.WaitForExit(); Task.WaitAll(a,b); return p.ExitCode;
        }
    }
}
