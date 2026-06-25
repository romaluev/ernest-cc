param(
  [switch]$HealthOnly,
  [switch]$Refresh,
  [switch]$NoRun,
  [ValidateSet("local", "vps")]
  [string]$Mode = $(if ($env:ERNEST_MODE) { $env:ERNEST_MODE } else { "local" })
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProfileDir = if ($env:ERNEST_PROFILE_DIR) { $env:ERNEST_PROFILE_DIR } else { Join-Path $HOME ".ernest-cc" }
$VaultDir = if ($env:ERNEST_LOCAL_VAULT) { $env:ERNEST_LOCAL_VAULT } else { Join-Path $HOME "ErnestVault" }
$MemoryFile = if ($env:ERNEST_LOCAL_MEMORY_FILE) { $env:ERNEST_LOCAL_MEMORY_FILE } else { Join-Path $VaultDir "memory.json" }

function Require-File($Path) {
  $Full = Join-Path $Root $Path
  if (!(Test-Path $Full)) {
    throw "Missing required file: $Path"
  }
}

function Health-Check {
  Require-File "CLAUDE.md"
  Require-File ".claude-plugin/plugin.json"
  Require-File "settings.json"
  Require-File ".mcp.json"
  Require-File "ernest.yaml"
  Require-File "hooks/pre_tool_use.py"
  Require-File "hooks/capture_learnings.py"
  Require-File "ernest/cli.py"
  Require-File "ernest/gate.py"
  Require-File "skills/morning-brief/SKILL.md"
  Require-File "skills/account-followup-recovery/SKILL.md"
  Require-File "skills/inbox-prospect-followup/SKILL.md"
  Require-File "commands/ernest-brief.md"
  Write-Output "Ernest health check: ok"
}

function Copy-Code {
  Copy-Item -Force (Join-Path $Root "CLAUDE.md") $ProfileDir
  Copy-Item -Force (Join-Path $Root "settings.json") $ProfileDir
  Copy-Item -Force (Join-Path $Root "ernest.yaml") $ProfileDir
  foreach ($dir in "skills", "commands", "agents", "hooks", "ernest") {
    $dest = Join-Path $ProfileDir $dir
    if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
    Copy-Item -Recurse -Force (Join-Path $Root $dir) $ProfileDir
  }
}

function Write-Launcher {
  New-Item -ItemType Directory -Force -Path (Join-Path $ProfileDir "bin") | Out-Null
@"
@echo off
set ERNEST_PROFILE_DIR=$ProfileDir
set PYTHONPATH=$ProfileDir;%PYTHONPATH%
python -m ernest.cli %*
"@ | Set-Content -Encoding ASCII (Join-Path $ProfileDir "bin/ernest.cmd")
}

Health-Check
if ($HealthOnly) { exit 0 }

if ($Refresh) {
  if (!(Test-Path $ProfileDir)) { throw "Nothing to refresh: $ProfileDir does not exist. Run install.ps1 first." }
  Copy-Code
  Write-Launcher
  Write-Output "Refreshed code/skills/engine in $ProfileDir (memory and config preserved)."
  exit 0
}

New-Item -ItemType Directory -Force -Path $ProfileDir, $VaultDir, (Join-Path $ProfileDir "bin") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $VaultDir "Ernest/00-Watch"), (Join-Path $VaultDir "Ernest/00-Daily"), (Join-Path $VaultDir "Ernest/00-Drafts") | Out-Null
if (!(Test-Path $MemoryFile)) { "{}" | Set-Content -Encoding UTF8 $MemoryFile }

Copy-Code
Copy-Item -Recurse -Force (Join-Path $Root "memory") $ProfileDir
Copy-Item -Recurse -Force (Join-Path $Root "data") $ProfileDir
Write-Launcher

if ($Mode -eq "vps" -and (!$env:ERNEST_BRAIN_URL -or !$env:ERNEST_BRAIN_TOKEN)) {
  Write-Output "VPS mode selected. Set ERNEST_BRAIN_URL and ERNEST_BRAIN_TOKEN, then rerun install.ps1."
  exit 1
}

if ($Mode -eq "vps") {
@"
{
  "mcpServers": {
    "ernest-brain": {
      "type": "http",
      "url": "$env:ERNEST_BRAIN_URL",
      "headers": {
        "Authorization": "Bearer $env:ERNEST_BRAIN_TOKEN"
      }
    }
  }
}
"@ | Set-Content -Encoding UTF8 (Join-Path $ProfileDir ".mcp.json")
} else {
@"
{
  "mcpServers": {
    "local-memory": {
      "type": "stdio",
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-memory"
      ],
      "env": {
        "MEMORY_FILE_PATH": "$MemoryFile"
      }
    }
  }
}
"@ | Set-Content -Encoding UTF8 (Join-Path $ProfileDir ".mcp.json")
}

@"
ERNEST_MODE=$Mode
ERNEST_PROFILE_DIR=$ProfileDir
ERNEST_LOCAL_VAULT=$VaultDir
ERNEST_LOCAL_MEMORY_FILE=$MemoryFile
ERNEST_BRAIN_URL=$env:ERNEST_BRAIN_URL
ERNEST_BRAIN_TOKEN=$env:ERNEST_BRAIN_TOKEN
"@ | Set-Content -Encoding UTF8 (Join-Path $ProfileDir "env")

Write-Output ""
Write-Output "Ernest installed to $ProfileDir"
Write-Output "Mode: $Mode"
Write-Output "Vault: $VaultDir"
Write-Output ""
$ErnestCmd = Join-Path $ProfileDir "bin\ernest.cmd"
if (-not $NoRun) {
  Write-Output ""
  Write-Output "Here is what needs you right now:"
  Write-Output "------------------------------------------------------------"
  & $ErnestCmd start
  Write-Output "------------------------------------------------------------"
}
Write-Output ""
Write-Output "From now on, just run:"
Write-Output "    $ErnestCmd start"
Write-Output ""
Write-Output "Optional: '$ErnestCmd onboard', or open Claude Code in $ProfileDir and run /ernest-onboard to connect accounts."
