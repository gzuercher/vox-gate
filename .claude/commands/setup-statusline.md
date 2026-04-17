Richte die Raptus-Statuszeile für Claude Code ein. Folge diesen Schritten exakt:

## Schritt 1 — Betriebssystem erkennen

Erkenne das Betriebssystem (macOS/Linux → Bash-Script, Windows → PowerShell-Script).

## Schritt 2 — Script erstellen

### macOS / Linux

Erstelle die Datei `~/.claude/statusline.sh` mit folgendem Inhalt:

```bash
#!/usr/bin/env bash
# Raptus AG — Claude Code Statusline

input=$(cat)

RESET='\033[0m'
BOLD='\033[1m'
CYAN='\033[96m'
GREEN='\033[92m'
YELLOW='\033[93m'
RED='\033[91m'
WHITE='\033[97m'
GRAY='\033[90m'

model=$(echo "$input"    | jq -r '.model.display_name // "?"')
cwd=$(echo "$input"      | jq -r '.workspace.current_dir // .cwd // ""')
folder=$(basename "$cwd")
used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // 0')
cost=$(echo "$input"     | jq -r '.cost.total_cost_usd // 0')
dur_ms=$(echo "$input"   | jq -r '.cost.total_duration_ms // 0')

branch=""
if [ -n "$cwd" ]; then
  branch=$(GIT_OPTIONAL_LOCKS=0 git -C "$cwd" rev-parse --abbrev-ref HEAD 2>/dev/null)
fi

dur_s=$((dur_ms / 1000))
if   [ "$dur_s" -ge 3600 ]; then dur_fmt="$(( dur_s / 3600 ))h $(( (dur_s % 3600) / 60 ))m"
elif [ "$dur_s" -ge 60 ];   then dur_fmt="$(( dur_s / 60 ))m $(( dur_s % 60 ))s"
else dur_fmt="${dur_s}s"
fi

cost_fmt=$(awk -v c="$cost" 'BEGIN { printf "$%.2f", c }')

filled=$(awk -v p="$used_pct" 'BEGIN { printf "%d", (p/100)*10 + 0.5 }')
empty=$(( 10 - filled ))
bar=""
for i in $(seq 1 "$filled"); do bar="${bar}█"; done
for i in $(seq 1 "$empty");  do bar="${bar}░"; done
pct_int=$(awk -v p="$used_pct" 'BEGIN { printf "%d", p + 0.5 }')

bar_color=$(awk -v p="$used_pct" -v g="$GREEN" -v y="$YELLOW" -v r="$RED" \
  'BEGIN { if (p < 60) print g; else if (p < 80) print y; else print r }')

SEP="${GRAY}  │  ${RESET}"

line1="${CYAN}${BOLD}[${model}]${RESET}${GRAY}  ${RESET}${WHITE}📁 ${folder}${RESET}"
if [ -n "$branch" ] && [ "$branch" != "HEAD" ]; then
  line1+="${SEP}${GREEN}🌿 ${branch}${RESET}"
fi

line2="${bar_color}${bar}${RESET} ${WHITE}${pct_int}%${RESET}"
line2+="${SEP}${YELLOW}${cost_fmt}${RESET}"
line2+="${SEP}${GRAY}⏱ ${dur_fmt}${RESET}"

printf "%b\n%b\n" "$line1" "$line2"
```

Mache die Datei ausführbar: `chmod +x ~/.claude/statusline.sh`

### Windows

Erstelle die Datei `$env:USERPROFILE\.claude\statusline.ps1` mit folgendem Inhalt:

```powershell
# Raptus AG — Claude Code Statusline (Windows)
$data = $input | ConvertFrom-Json

$model    = if ($data.model.display_name)               { $data.model.display_name }               else { "?" }
$cwd      = if ($data.workspace.current_dir)            { $data.workspace.current_dir }             elseif ($data.cwd) { $data.cwd } else { "" }
$folder   = Split-Path -Leaf $cwd
$used_pct = if ($null -ne $data.context_window.used_percentage) { $data.context_window.used_percentage } else { 0 }
$cost     = if ($null -ne $data.cost.total_cost_usd)    { $data.cost.total_cost_usd }               else { 0 }
$dur_ms   = if ($null -ne $data.cost.total_duration_ms) { $data.cost.total_duration_ms }            else { 0 }

$branch = ""
if ($cwd) { try { $branch = git -C $cwd rev-parse --abbrev-ref HEAD 2>$null } catch {} }

$dur_s = [int]($dur_ms / 1000)
if     ($dur_s -ge 3600) { $dur_fmt = "$([int]($dur_s/3600))h $([int](($dur_s%3600)/60))m" }
elseif ($dur_s -ge 60)   { $dur_fmt = "$([int]($dur_s/60))m $($dur_s % 60)s" }
else                     { $dur_fmt = "${dur_s}s" }

$cost_fmt = '$' + '{0:F2}' -f $cost
$filled   = [int](($used_pct / 100) * 10 + 0.5)
$bar      = ('█' * $filled) + ('░' * (10 - $filled))
$pct_int  = [int]($used_pct + 0.5)

$e = [char]27
$RESET  = "$e[0m";  $BOLD   = "$e[1m"
$CYAN   = "$e[96m"; $GREEN  = "$e[92m"
$YELLOW = "$e[93m"; $RED    = "$e[91m"
$WHITE  = "$e[97m"; $GRAY   = "$e[90m"
$SEP    = "${GRAY}  │  ${RESET}"

$bar_color = if ($used_pct -lt 60) { $GREEN } elseif ($used_pct -lt 80) { $YELLOW } else { $RED }

$line1 = "${CYAN}${BOLD}[${model}]${RESET}${GRAY}  ${RESET}${WHITE}📁 ${folder}${RESET}"
if ($branch -and $branch -ne "HEAD") { $line1 += "${SEP}${GREEN}🌿 ${branch}${RESET}" }

$line2  = "${bar_color}${bar}${RESET} ${WHITE}${pct_int}%${RESET}"
$line2 += "${SEP}${YELLOW}${cost_fmt}${RESET}"
$line2 += "${SEP}${GRAY}⏱ ${dur_fmt}${RESET}"

Write-Host $line1
Write-Host $line2
```

## Schritt 3 — settings.json aktualisieren

Öffne `~/.claude/settings.json` (bzw. `$env:USERPROFILE\.claude\settings.json` auf Windows) und füge den `statusLine`-Block hinzu oder ersetze einen bestehenden. Behalte alle anderen Einstellungen.

**macOS / Linux:**
```json
"statusLine": {
  "type": "command",
  "command": "bash ~/.claude/statusline.sh",
  "refreshInterval": 5
}
```

**Windows:**
```json
"statusLine": {
  "type": "command",
  "command": "powershell -NoProfile -File $env:USERPROFILE\\.claude\\statusline.ps1",
  "refreshInterval": 5
}
```

## Schritt 4 — Bestätigen

Melde kurz, welches OS erkannt wurde, wo die Dateien erstellt wurden, und dass Claude Code neu gestartet werden muss, damit die Statuszeile aktiv wird.

---

**Erwartetes Ergebnis:**
```
[Sonnet]  📁 mein-projekt  │  🌿 main
████░░░░░░ 8%  │  $0.00  │  ⏱ 0s
```
