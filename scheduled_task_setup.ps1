<#
.SYNOPSIS
    Registers a Windows Task Scheduler job to run run_all.py daily at 7:00 AM.

.DESCRIPTION
    Creates (or updates) a scheduled task named "NewsAggregatorDaily" that
    invokes the project's venv Python to run run_all.py every day at 07:00.

.NOTES
    Run this script once as Administrator (or the task will be registered for
    the current user only, which is also fine for most setups).
#>

$ErrorActionPreference = "Stop"

# ---- Paths ----
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$VenvPython  = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$RunScript   = Join-Path $ProjectRoot "run_all.py"

# Validate venv Python exists
if (-not (Test-Path $VenvPython)) {
    Write-Error "venv Python not found at: $VenvPython`nRun 'python -m venv .venv && .venv\Scripts\pip install -r requirements.txt' first."
    exit 1
}

# ---- Task parameters ----
$TaskName    = "NewsAggregatorDaily"
$TaskDescr   = "Fetches RSS news for all topics and saves Obsidian markdown files."
$TriggerTime = "07:00"

# ---- Build the action ----
$Action = New-ScheduledTaskAction `
    -Execute $VenvPython `
    -Argument "`"$RunScript`"" `
    -WorkingDirectory $ProjectRoot

# ---- Daily trigger at 7 AM ----
$Trigger = New-ScheduledTaskTrigger -Daily -At $TriggerTime

# ---- Settings ----
$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

# ---- Register (or replace) the task ----
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Write-Host "Task '$TaskName' already exists — updating it..."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask `
    -TaskName    $TaskName `
    -Description $TaskDescr `
    -Action      $Action `
    -Trigger     $Trigger `
    -Settings    $Settings `
    -RunLevel    Limited

Write-Host ""
Write-Host "Scheduled task '$TaskName' registered successfully."
Write-Host "  Python  : $VenvPython"
Write-Host "  Script  : $RunScript"
Write-Host "  Schedule: Daily at $TriggerTime"
Write-Host ""
Write-Host "To run it immediately: Start-ScheduledTask -TaskName '$TaskName'"
