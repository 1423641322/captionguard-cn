using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Reflection;

[assembly: AssemblyTitle("CaptionGuard CN")]
[assembly: AssemblyDescription("Premiere local Chinese caption service")]
[assembly: AssemblyCompany("CaptionGuard CN")]
[assembly: AssemblyProduct("CaptionGuard CN")]
[assembly: AssemblyVersion("0.3.0.0")]
[assembly: AssemblyFileVersion("0.3.0.0")]

internal static class Program
{
    private const string AppVersion = "0.3.0";
    private const string PayloadResource = "CaptionGuardPayload";

    [STAThread]
    private static int Main(string[] args)
    {
        try
        {
            string localAppData = Environment.GetFolderPath(
                Environment.SpecialFolder.LocalApplicationData
            );
            string appDirectory = Path.Combine(localAppData, "CaptionGuardCN", "app", AppVersion);
            EnsurePayload(appDirectory);

            string python = Path.Combine(appDirectory, "python", "pythonw.exe");
            string entryPoint = Path.Combine(appDirectory, "backend", "captionguard_desktop.py");
            var startInfo = new ProcessStartInfo
            {
                FileName = python,
                Arguments = Quote(entryPoint) + FormatArguments(args),
                WorkingDirectory = appDirectory,
                UseShellExecute = false,
                CreateNoWindow = true,
            };
            startInfo.EnvironmentVariables["CAPTIONGUARD_LAUNCHER"] =
                Assembly.GetExecutingAssembly().Location;
            Process.Start(startInfo);
            return 0;
        }
        catch (Exception exception)
        {
            System.Windows.Forms.MessageBox.Show(
                "CaptionGuard CN 启动失败：\n" + exception.Message,
                "CaptionGuard CN",
                System.Windows.Forms.MessageBoxButtons.OK,
                System.Windows.Forms.MessageBoxIcon.Error
            );
            return 1;
        }
    }

    private static void EnsurePayload(string appDirectory)
    {
        string marker = Path.Combine(appDirectory, ".complete");
        if (File.Exists(marker))
        {
            return;
        }

        if (Directory.Exists(appDirectory))
        {
            Directory.Delete(appDirectory, true);
        }
        Directory.CreateDirectory(appDirectory);

        using (Stream payload = Assembly.GetExecutingAssembly().GetManifestResourceStream(
            PayloadResource
        ))
        {
            if (payload == null)
            {
                throw new InvalidOperationException("安装数据不存在。");
            }

            using (var archive = new ZipArchive(payload, ZipArchiveMode.Read))
            {
                foreach (ZipArchiveEntry entry in archive.Entries)
                {
                    string destination = Path.GetFullPath(Path.Combine(appDirectory, entry.FullName));
                    string root = Path.GetFullPath(appDirectory) + Path.DirectorySeparatorChar;
                    if (!destination.StartsWith(root, StringComparison.OrdinalIgnoreCase))
                    {
                        throw new InvalidDataException("安装数据包含无效路径。");
                    }

                    if (String.IsNullOrEmpty(entry.Name))
                    {
                        Directory.CreateDirectory(destination);
                        continue;
                    }

                    Directory.CreateDirectory(Path.GetDirectoryName(destination));
                    entry.ExtractToFile(destination, true);
                }
            }
        }

        File.WriteAllText(marker, AppVersion);
    }

    private static string FormatArguments(string[] args)
    {
        if (args == null || args.Length == 0)
        {
            return String.Empty;
        }

        string result = String.Empty;
        foreach (string argument in args)
        {
            result += " " + Quote(argument);
        }
        return result;
    }

    private static string Quote(string value)
    {
        return "\"" + value.Replace("\\", "\\\\").Replace("\"", "\\\"") + "\"";
    }
}
