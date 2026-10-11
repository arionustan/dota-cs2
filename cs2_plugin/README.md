# DotaCSBridge (CS2 plugin)

CounterStrikeSharp plugin. Build: set `CS2ServerDir` to your CS2 server folder (the one with `game/csgo/addons/counterstrikesharp`), then

```
dotnet build -c Release -p:CS2ServerDir="C:\cs2server\cs2"
```

Copy `bin/Release/net10.0/DotaCSBridge.dll` to `game/csgo/addons/counterstrikesharp/plugins/DotaCSBridge/`.
