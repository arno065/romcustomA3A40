#requires -Version 5.1
<#
Collect A3-A40 Android/recovery diagnostics into one local directory and ZIP.
Only the explicitly listed remote read commands below are issued.
No flash, reboot, unlock, mount, root request or vendor touch sysfs reads.
#>
[CmdletBinding()]
param(
    [string]$AdbPath = '.\adb.exe',
    [string]$Serial = '',
    [string]$OutputDirectory = '',
    [ValidateRange(1, 120)][int]$TimeoutSeconds = 15
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$AdbExecutable = (Resolve-Path -LiteralPath $AdbPath).ProviderPath
$Utf8 = New-Object System.Text.UTF8Encoding($false)

function ConvertTo-NativeArgument {
    param([AllowEmptyString()][string]$Value)
    # Windows CommandLineToArgvW quoting; also accepted by .NET on Linux tests.
    $Builder = New-Object System.Text.StringBuilder
    [void]$Builder.Append('"')
    $Slashes = 0
    foreach ($Character in $Value.ToCharArray()) {
        if ($Character -eq [char]92) { $Slashes++; continue }
        if ($Character -eq [char]34) {
            [void]$Builder.Append(('\' * ($Slashes * 2 + 1)))
        } else {
            [void]$Builder.Append(('\' * $Slashes))
        }
        [void]$Builder.Append($Character)
        $Slashes = 0
    }
    [void]$Builder.Append(('\' * ($Slashes * 2)))
    [void]$Builder.Append('"')
    return $Builder.ToString()
}

function Invoke-AdbRead {
    param([string[]]$AdbArguments)
    $Info = New-Object System.Diagnostics.ProcessStartInfo
    $Info.FileName = $AdbExecutable
    $Info.Arguments = (($AdbArguments | ForEach-Object { ConvertTo-NativeArgument $_ }) -join ' ')
    $Info.UseShellExecute = $false
    $Info.CreateNoWindow = $true
    $Info.RedirectStandardOutput = $true
    $Info.RedirectStandardError = $true
    $Info.StandardOutputEncoding = $Utf8
    $Info.StandardErrorEncoding = $Utf8
    $Process = New-Object System.Diagnostics.Process
    $Process.StartInfo = $Info
    try {
        [void]$Process.Start()
        $StdoutTask = $Process.StandardOutput.ReadToEndAsync()
        $StderrTask = $Process.StandardError.ReadToEndAsync()
        $TimedOut = -not $Process.WaitForExit($TimeoutSeconds * 1000)
        if ($TimedOut) {
            # Terminate only this local adb client, not the adb server/tablet.
            try { $Process.Kill() } catch { }
            [void]$Process.WaitForExit(3000)
        }
        $OutDone = $StdoutTask.Wait(3000)
        $ErrDone = $StderrTask.Wait(3000)
        $Stdout = ''; $Stderr = ''
        if ($OutDone) { $Stdout = $StdoutTask.Result }
        if ($ErrDone) { $Stderr = $StderrTask.Result }
        $Code = -1
        if ($Process.HasExited) { $Code = $Process.ExitCode }
        return [pscustomobject]@{ Stdout = $Stdout; Stderr = $Stderr; ExitCode = $Code; TimedOut = $TimedOut }
    } finally {
        $Process.Dispose()
    }
}

$Version = Invoke-AdbRead -AdbArguments @('version')
if ($Version.TimedOut -or $Version.ExitCode -ne 0) { throw 'adb version failed or timed out.' }
$Listing = Invoke-AdbRead -AdbArguments @('devices')
if ($Listing.TimedOut -or $Listing.ExitCode -ne 0) { throw 'adb devices failed or timed out.' }
$Devices = @()
foreach ($Line in ($Listing.Stdout -split '\r?\n')) {
    if ($Line -match '^(?<serial>\S+)\s+(?<state>device|recovery|sideload|offline|unauthorized)\b') {
        $Devices += [pscustomobject]@{ Serial = $Matches.serial; State = $Matches.state }
    }
}
if ($Serial) {
    $Devices = @($Devices | Where-Object { $_.Serial -ceq $Serial })
}
if ($Devices.Count -ne 1) {
    throw 'Connect exactly one tablet, or select it explicitly with -Serial. No tablet command was sent.'
}
$Selected = $Devices[0]
if ($Selected.State -notin @('device', 'recovery')) {
    throw ('ADB state is ' + $Selected.State + '. Shell diagnostics need device/recovery mode.')
}
$DeviceSerial = $Selected.Serial
if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path (Get-Location).Path ('Acer-Diagnostics-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
}
$ReportDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)
$ZipPath = $ReportDirectory + '.zip'
if ((Test-Path -LiteralPath $ReportDirectory) -or (Test-Path -LiteralPath $ZipPath)) {
    throw 'Output already exists; choose a new OutputDirectory.'
}
[void][System.IO.Directory]::CreateDirectory($ReportDirectory)
[System.IO.File]::WriteAllText((Join-Path $ReportDirectory 'adb-version.txt'), $Version.Stdout, $Utf8)

$Commands = [ordered]@{
    'identity.txt' = @'
for p in ro.product.model ro.product.device ro.board.platform ro.build.display.id ro.build.version.release ro.build.version.security_patch ro.bootmode ro.twrp.version ro.acer.touch_fw_version ro.crypto.state; do printf '%s=' "$p"; getprop "$p"; done
id
uname -a
'@
    'mounts.txt' = 'cat /proc/mounts'
    'partitions.txt' = @'
cat /proc/partitions
ls -l /dev/block/platform/mtk-msdc.0/11230000.MSDC0/by-name /dev/block/platform/soc/11230000.mmc/by-name
'@
    'input-devices.txt' = 'cat /proc/bus/input/devices'
    'input-capabilities.txt' = 'getevent -p'
    'framebuffer.txt' = @'
for n in name virtual_size bits_per_pixel stride modes; do p=/sys/class/graphics/fb0/$n; if [ -r "$p" ]; then printf '\n%s\n' "$p"; cat "$p"; fi; done
'@
    'memory.txt' = 'cat /proc/meminfo'
    'selinux.txt' = 'getenforce; cat /sys/fs/selinux/policyvers'
    'processes.txt' = 'ps'
    'dmesg.txt' = 'dmesg'
    'logcat.txt' = 'logcat -d -t 1500'
    'recovery-log.txt' = @'
if [ -f /tmp/recovery.log ]; then tail -n 3000 /tmp/recovery.log; else echo RECOVERY_LOG_NOT_PRESENT; fi
'@
}

$Results = @()
foreach ($Name in $Commands.Keys) {
    Write-Host ('Reading ' + $Name)
    # ADB passes this single argument to the device shell; no eval on the PC.
    $Command = $Commands[$Name].Replace("`r`n", "`n")
    $Result = Invoke-AdbRead -AdbArguments @('-s', $DeviceSerial, 'shell', $Command)
    $Text = $Result.Stdout + "`n--- stderr ---`n" + $Result.Stderr
    [System.IO.File]::WriteAllText((Join-Path $ReportDirectory $Name), $Text, $Utf8)
    $Results += [pscustomobject]@{
        File = $Name; Command = $Command; ExitCode = $Result.ExitCode; TimedOut = $Result.TimedOut
    }
}
$Identity = [System.IO.File]::ReadAllText((Join-Path $ReportDirectory 'identity.txt'))
$RecoveryLog = [System.IO.File]::ReadAllText((Join-Path $ReportDirectory 'recovery-log.txt'))
$Mode = 'Android baseline or recovery not identified'
if (($Identity -match '(?m)^ro.twrp.version=\S+') -or ($Identity -match '(?m)^ro.bootmode=recovery\s*$') -or
    ($RecoveryLog -notmatch 'RECOVERY_LOG_NOT_PRESENT' -and $RecoveryLog -match '(?i)twrp')) {
    $Mode = 'Recovery detected; hardware functionality still needs manual verification'
}
$Manifest = [ordered]@{
    CollectedUtc = [DateTime]::UtcNow.ToString('o')
    Mode = $Mode
    DeviceSelector = '<selected device>'
    PowerShellVersion = $PSVersionTable.PSVersion.ToString()
    Results = $Results
    Limitations = @('Logs can contain identifiers; review before public sharing.',
        'No vendor touch sysfs reads, firmware update, unlock, reboot, mount or flash.',
        'Static input information does not verify real touch coordinates.',
        'Permission errors on stock Android are retained and are not a recovery test failure.')
}
[System.IO.File]::WriteAllText((Join-Path $ReportDirectory 'manifest.json'), ($Manifest | ConvertTo-Json -Depth 6), $Utf8)
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($ReportDirectory, $ZipPath)
$Digest = (Get-FileHash -LiteralPath $ZipPath -Algorithm SHA256).Hash.ToLowerInvariant()
[System.IO.File]::WriteAllText(($ZipPath + '.sha256'), ($Digest + '  ' + [System.IO.Path]::GetFileName($ZipPath)), $Utf8)
Write-Host $Mode
Write-Host ('Diagnostic ZIP: ' + $ZipPath)
