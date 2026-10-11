// DotaCS: the bridge built into the plugin. Dota posts to http://127.0.0.1:3000/dota, the plugin answers directly.
// If port 3000 is already taken (bridge.py is running), the plugin falls back to posting to bridge.py.
using System.Net;
using System.Net.Sockets;
using System.Text;
using CounterStrikeSharp.API.Core;
using Microsoft.Extensions.Logging;

namespace DotaCSBridge;

public partial class DotaCSBridge
{
    private TcpListener? _relay;
    private volatile bool _relayOn;
    private readonly object _relayLock = new();
    private List<string> _rPlayers = new(), _rHeroes = new(), _rBuildings = new(), _rToCs = new(), _rToDota = new();
    private DateTime _rCsTime = DateTime.MinValue, _rDotaTime = DateTime.MinValue;

    private void StartRelay()
    {
        try
        {
            _relay = new TcpListener(IPAddress.Loopback, 3000);
            _relay.Server.ExclusiveAddressUse = true;
            _relay.Start();
            _relayOn = true;
            new Thread(RelayLoop) { IsBackground = true, Name = "DotaCS relay" }.Start();
            Logger.LogInformation("DotaCS built-in bridge listening on 127.0.0.1:3000");
        }
        catch (Exception e)
        {
            _relayOn = false;
            Logger.LogInformation("DotaCS port 3000 busy, using external bridge.py ({Error})", e.Message);
        }
    }

    private void StopRelay()
    {
        _relayOn = false;
        try { _relay?.Stop(); } catch { }
    }

    private static List<string> RelaySplit(string body) =>
        body.Split('\n').Select(l => l.Trim()).Where(l => l.Length > 0 && l != "none").ToList();

    // called on the game thread instead of the HTTP post to bridge.py
    private void RelayExchangeCs(string body)
    {
        var lines = RelaySplit(body);
        string answer;
        lock (_relayLock)
        {
            var now = DateTime.UtcNow;
            _rPlayers = lines.Where(l => l.StartsWith("P ")).ToList();
            _rToDota.AddRange(lines.Where(l => l.StartsWith("D ") || l.StartsWith("T ")));
            _rCsTime = now;
            var outLines = new List<string>();
            if ((now - _rDotaTime).TotalSeconds < 2.0) { outLines.AddRange(_rHeroes); outLines.AddRange(_rBuildings); }
            outLines.AddRange(_rToCs);
            _rToCs.Clear();
            answer = outLines.Count > 0 ? string.Join("\n", outLines) : "none";
        }
        _incoming.Enqueue(answer);
        if (!_connected) { _connected = true; Logger.LogInformation("DotaCS built-in bridge active"); }
    }

    private string RelayExchangeDota(string body)
    {
        var lines = RelaySplit(body);
        lock (_relayLock)
        {
            var now = DateTime.UtcNow;
            _rHeroes = lines.Where(l => l.StartsWith("H ") || l.StartsWith("U ")).ToList();
            var b = lines.Where(l => l.StartsWith("B ")).ToList();
            if (b.Count > 0) _rBuildings = b;
            _rToCs.AddRange(lines.Where(l => l.StartsWith("C ") || l.StartsWith("E ")));
            if (_rToCs.Count > 5000) _rToCs.RemoveRange(0, _rToCs.Count - 5000);
            _rDotaTime = now;
            var outLines = new List<string>();
            if ((now - _rCsTime).TotalSeconds < 2.0) outLines.AddRange(_rPlayers);
            outLines.AddRange(_rToDota);
            _rToDota.Clear();
            return outLines.Count > 0 ? string.Join("\n", outLines) : "none";
        }
    }

    private void RelayLoop()
    {
        while (_relayOn)
        {
            TcpClient client;
            try { client = _relay!.AcceptTcpClient(); }
            catch { if (!_relayOn) return; continue; }
            ThreadPool.QueueUserWorkItem(_ => HandleRelayClient(client));
        }
    }

    private void HandleRelayClient(TcpClient client)
    {
        using (client)
        {
            try
            {
                client.ReceiveTimeout = 2000;
                client.SendTimeout = 2000;
                var stream = client.GetStream();
                // read headers
                var buf = new List<byte>(4096);
                var one = new byte[1];
                while (buf.Count < 65536)
                {
                    if (stream.Read(one, 0, 1) <= 0) return;
                    buf.Add(one[0]);
                    var n = buf.Count;
                    if (n >= 4 && buf[n - 4] == '\r' && buf[n - 3] == '\n' && buf[n - 2] == '\r' && buf[n - 1] == '\n') break;
                }
                var head = Encoding.ASCII.GetString(buf.ToArray());
                var firstLine = head.Split("\r\n")[0];
                var parts = firstLine.Split(' ');
                var method = parts.Length > 0 ? parts[0] : "";
                var path = parts.Length > 1 ? parts[1] : "/";
                var length = 0;
                foreach (var h in head.Split("\r\n"))
                    if (h.StartsWith("Content-Length:", StringComparison.OrdinalIgnoreCase))
                        int.TryParse(h.Substring(15).Trim(), out length);
                length = Math.Clamp(length, 0, 4 * 1024 * 1024);
                var body = new byte[length];
                var read = 0;
                while (read < length)
                {
                    var r = stream.Read(body, read, length - read);
                    if (r <= 0) break;
                    read += r;
                }

                string answer;
                if (method == "POST" && path.StartsWith("/dota")) answer = RelayExchangeDota(Encoding.UTF8.GetString(body, 0, read));
                else if (method == "POST" && path.StartsWith("/cs")) answer = "none";   // only the plugin itself talks for CS
                else answer = "DotaCS bridge is running (built into the CS2 plugin)";

                var data = Encoding.UTF8.GetBytes(answer);
                var header = Encoding.ASCII.GetBytes(
                    "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: " + data.Length + "\r\nConnection: close\r\n\r\n");
                stream.Write(header, 0, header.Length);
                stream.Write(data, 0, data.Length);
                stream.Flush();
            }
            catch { }
        }
    }
}
