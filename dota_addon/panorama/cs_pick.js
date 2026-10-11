"use strict";

// Hero selection overlay: host picks the mode, players pick CS or Dota.

(function () {
    var state = { mode: "mixed", roles: {}, locked: 0 };

    function send(name, data) {
        GameEvents.SendCustomGameEventToServer(name, data || {});
    }

    function isHost() {
        var info = Game.GetLocalPlayerInfo();
        return info && info.player_has_host_privileges;
    }

    function render() {
        var me = Players.GetLocalPlayer();
        var host = isHost();
        var versus = state.mode === "versus";

        $("#CSModeVersus").SetHasClass("Active", versus);
        $("#CSModeMixed").SetHasClass("Active", !versus);
        $("#CSModeVersus").SetHasClass("Disabled", !host);
        $("#CSModeMixed").SetHasClass("Disabled", !host);

        $("#CSModeHint").text = host
            ? "Ты хост, режим выбираешь ты."
            : "Режим выбирает хост.";
        if (versus) $("#CSModeHint").text += " Свет играет за дотеров, Тьма за ксников.";

        $("#CSRoleBlock").visible = !versus;
        var iAmCS = state.roles[String(me)] === 1;
        $("#CSRoleCS").SetHasClass("Active", iAmCS);
        $("#CSRoleDota").SetHasClass("Active", !iAmCS);

        $("#CSMyRole").text = iAmCS
            ? "Ты ксник. Выбери любого героя, после старта он станет ксником."
            : "Ты дотер. Выбирай героя как обычно.";

        var names = [];
        Object.keys(state.roles).forEach(function (pid) {
            if (state.roles[pid] === 1) names.push(Players.GetPlayerName(Number(pid)));
        });
        $("#CSPlayersCS").text = names.length ? names.join(", ") : "пока никого";

        if (state.locked) $("#CSPickBox").visible = false;
    }

    $("#CSModeVersus").SetPanelEvent("onactivate", function () {
        if (isHost()) send("cs_set_mode", { mode: "versus" });
    });
    $("#CSModeMixed").SetPanelEvent("onactivate", function () {
        if (isHost()) send("cs_set_mode", { mode: "mixed" });
    });
    $("#CSRoleCS").SetPanelEvent("onactivate", function () { send("cs_set_role", { cs: 1 }); });
    $("#CSRoleDota").SetPanelEvent("onactivate", function () { send("cs_set_role", { cs: 0 }); });

    GameEvents.Subscribe("cs_pick_state", function (data) {
        state = data;
        state.roles = state.roles || {};
        render();
    });

    render();
    send("cs_pick_request");
})();
