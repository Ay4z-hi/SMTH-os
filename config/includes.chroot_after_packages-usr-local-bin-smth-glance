#!/usr/bin/env bash
# Glance widgets for the shell layer: dot meters for cpu / mem / disk.
dots() { local n=$(( ($1*5+50)/100 )) s="" i; for i in 1 2 3 4 5; do [ $i -le $n ] && s+="●" || s+="○"; done; printf '%s' "$s"; }
case "${1:-}" in
  cpu)  read -r l < /proc/loadavg; ld=${l%% *}
        p=$(awk -v l="$ld" -v n="$(nproc)" 'BEGIN{p=l/n*100; if(p>100)p=100; printf "%d",p}')
        printf '{"text":"CPU %s","tooltip":"load %s on %s cores","class":"%s"}\n' "$(dots "$p")" "$ld" "$(nproc)" "$([ "$p" -gt 85 ] && echo hot)" ;;
  mem)  p=$(free | awk '/Mem:/{printf "%d",$3/$2*100}')
        printf '{"text":"RAM %s","tooltip":"%s%% used","class":"%s"}\n' "$(dots "$p")" "$p" "$([ "$p" -gt 85 ] && echo hot)" ;;
  disk) p=$(df --output=pcent / | tail -1 | tr -dc 0-9)
        printf '{"text":"SSD %s","tooltip":"%s%% of / used"}\n' "$(dots "$p")" "$p" ;;
esac
