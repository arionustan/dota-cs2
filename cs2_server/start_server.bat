@echo off
rem DotaCS: starts your local CS2 server with the bridge plugin.
rem Connect from CS2 console:  connect 127.0.0.1:27030
echo Starting CS2 server on port 27030...
"C:\cs2server\cs2\game\bin\win64\cs2.exe" -dedicated -insecure -console -port 27030 +sv_lan 1 +map dotacs_arena +game_type 0 +game_mode 1 +mp_autokick 0 +mp_warmup_pausetimer 1 +sv_hibernate_when_empty 0 +bot_quota 0
