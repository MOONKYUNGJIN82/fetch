using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;
using System.Reflection;
[assembly: AssemblyTitle("Fetch")]
[assembly: AssemblyProduct("Fetch")]
[assembly: AssemblyCompany("KALLOS")]
[assembly: AssemblyVersion("1.6.2.0")]
class FetchLauncher {
    [STAThread] static int Main(string[] args) {
        string root = AppDomain.CurrentDomain.BaseDirectory;
        bool test = Array.IndexOf(args, "--self-test") >= 0;
        try {
            var start = new ProcessStartInfo();
            start.FileName = Path.Combine(root, "runtime", test ? "python.exe" : "pythonw.exe");
            start.Arguments = "-I \"" + Path.Combine(root, "app", "instagram_downloader_ui.py") + "\"";
            if (test) start.Arguments += " --self-test";
            start.WorkingDirectory = root;
            start.UseShellExecute = false;
            start.CreateNoWindow = true;
            start.EnvironmentVariables.Remove("PYTHONHOME");
            start.EnvironmentVariables.Remove("PYTHONPATH");
            using (var process = Process.Start(start)) {
                if (test) { process.WaitForExit(); return process.ExitCode; }
            }
            return 0;
        } catch (Exception error) {
            if (!test) MessageBox.Show(error.Message, "Fetch", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
