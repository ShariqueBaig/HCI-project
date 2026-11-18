<#
setup_station.ps1 -- get one Windows lab station ready for the Aura UI study.

Does, in order:
  1. finds a Python 3.9+ interpreter (py launcher first, Store stubs ignored);
  2. creates .venv and installs requirements.txt  (skip with -SkipDeps);
  3. puts the shared lab_salt.txt in place         (pass -SaltFrom <path>);
  4. runs `lab_setup.py status`, then the real `check` (name + Firestore write);
  5. names the station for a participant           (pass -Code P01);
  6. rebuilds dist\AuraUI.exe with pycaw bundled   (pass -Build).

Usage (PowerShell, from anywhere):
  powershell -ExecutionPolicy Bypass -File tools\setup_station.ps1 `
      -SaltFrom \\labshare\lab_salt.txt

  ... -Code P01                  name it for the first participant
  ... -Code P01 -Condition control
  ... -Code P01 -Build           also rebuild the standalone exe
  ... -SkipDeps -SkipCheck       only do the fast offline parts

Exit codes: 0 ready, 1 problem (read the [FAIL] lines), 2 cannot start.
#>
[CmdletBinding()]
param(
    [string]$Code,
    [ValidateSet('intervention', 'control')][string]$Condition = 'intervention',
    [string]$SaltFrom,
    [switch]$Build,
    [switch]$SkipDeps,
    [switch]$SkipCheck,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$Root  = Split-Path -Parent $PSScriptRoot
$Lab   = Join-Path $Root 'tools\lab_setup.py'
$Salt  = Join-Path $Root 'lab_salt.txt'
$Venv  = Join-Path $Root '.venv'
$VenvPy = Join-Path $Venv 'Scripts\python.exe'

function Say([string]$Tag, [string]$Msg) {
    switch ($Tag) {
        'ok'   { Write-Host ('  [ok]   ' + $Msg) -ForegroundColor Green }
        'warn' { Write-Host ('  [warn] ' + $Msg) -ForegroundColor Yellow }
        'bad'  { Write-Host ('  [FAIL] ' + $Msg) -ForegroundColor Red }
        'step' { Write-Host ''; Write-Host ('== ' + $Msg) -ForegroundColor Cyan }
    }
}

# NB: the probe has no quotes inside it -- PowerShell 5.1 strips inner double
# quotes from arguments it hands to a native exe, which corrupts -c programs.
function Find-Python {
    $probe = 'import sys; print(sys.version_info[0]*100+sys.version_info[1])'
    $candidates = @(
        @{ exe = 'py';      prefix = @('-3') },
        @{ exe = 'python';  prefix = @() },
        @{ exe = 'python3'; prefix = @() }
    )
    foreach ($c in $candidates) {
        if (-not (Get-Command $c.exe -ErrorAction SilentlyContinue)) { continue }
        $out = @()
        try { $out = @(& $c.exe @($c.prefix + @('-c', $probe)) 2>$null) } catch { continue }
        if ($LASTEXITCODE -ne 0 -or $out.Count -eq 0) { continue }
        # A one-line result arrives as a bare string, so force an array above and
        # read the first non-empty line rather than indexing a string's characters.
        $first = ''
        foreach ($line in $out) { if ("$line".Trim()) { $first = "$line".Trim(); break } }
        $n = 0
        if (-not [int]::TryParse($first, [ref]$n)) { continue }
        if ($n -lt 309) { continue }              # 3.9 == 309
        $ver = '{0}.{1}' -f [math]::Floor($n / 100), ($n % 100)
        return [pscustomobject]@{ Exe = $c.exe; Prefix = $c.prefix; Version = $ver }
    }
    return $null
}

# Run python with the interpreter chosen below (system first, then the venv).
$script:PyExe    = $null
$script:PyPrefix = @()

# Out-Host keeps the child's output visible while the function's own return value
# stays the exit code (without it the caller's $rc assignment swallows the output).
function Invoke-Py {
    param([string[]]$Arguments)
    & $script:PyExe @($script:PyPrefix + $Arguments) | Out-Host
    return $LASTEXITCODE
}

Write-Host ''
Write-Host 'Aura UI - lab station setup' -ForegroundColor White
Write-Host ('  project : ' + $Root)

# ---------------------------------------------------------------- 1. python
Say step 'Python'
$py = Find-Python
if (-not $py) {
    Say bad 'no Python 3.9+ found'
    Write-Host '         Install it from python.org (tick "Add python.exe to PATH"),'
    Write-Host '         then run this script again.'
    exit 2
}
$script:PyExe    = $py.Exe
$script:PyPrefix = $py.Prefix
Say ok ('python ' + $py.Version + ' via ' + $py.Exe)

if (-not (Test-Path $Lab)) {
    Say bad ('tools\lab_setup.py not found under ' + $Root)
    exit 2
}

# ------------------------------------------------------- 2. env + packages
Say step 'Environment'
if (-not $SkipDeps -and -not (Test-Path $VenvPy)) {
    Say ok ('creating ' + $Venv)
    $null = Invoke-Py @('-m', 'venv', $Venv)
    if (-not (Test-Path $VenvPy)) {
        Say bad ('could not create a virtual environment at ' + $Venv)
        exit 1
    }
}
if (Test-Path $VenvPy) {
    # Prefer the station's own interpreter whenever it exists, even with -SkipDeps.
    $script:PyExe    = $VenvPy
    $script:PyPrefix = @()
    Say ok ('using ' + $Venv)
} elseif ($SkipDeps) {
    Say warn 'no .venv yet - using the system Python (-SkipDeps)'
}
if ($SkipDeps) {
    Say warn 'skipping pip install (-SkipDeps)'
} else {
    $null = Invoke-Py @('-m', 'pip', 'install', '--upgrade', 'pip',
                        '--quiet', '--disable-pip-version-check')
    Say ok 'installing requirements.txt (the first run takes a few minutes)'
    $rc = Invoke-Py @('-m', 'pip', 'install', '-r', (Join-Path $Root 'requirements.txt'),
                      '--quiet', '--disable-pip-version-check')
    if ($rc -ne 0) {
        Say bad 'pip install failed - read the messages above'
        exit 1
    }
    Say ok 'dependencies installed (pycaw included on Windows)'
}

# ------------------------------------------------------------------ 3. salt
Say step 'Lab salt'
if ($SaltFrom) {
    if (-not (Test-Path -LiteralPath $SaltFrom)) {
        Say bad ('no such file: ' + $SaltFrom)
        exit 1
    }
    Copy-Item -LiteralPath $SaltFrom -Destination $Salt -Force
    Say ok ('shared salt copied to ' + $Salt)
} elseif (Test-Path $Salt) {
    Say ok 'shared salt already in place'
} else {
    Say warn 'no lab_salt.txt yet'
    Write-Host '         Run once on any station:  python tools\lab_setup.py salt-init'
    Write-Host '         then copy lab_salt.txt to every other station (or pass -SaltFrom).'
}

# ---------------------------------------------------------------- 4. status
Say step 'Station status'
$null = Invoke-Py @($Lab, 'status')

# --------------------------------------------------------------- 4. prepare
# Name the station before checking it, otherwise `check` fails on a station
# that is about to be named anyway.
if ($Code) {
    Say step ('Naming the station for ' + $Code.ToUpper())
    $pargs = @($Lab, 'prepare', '--code', $Code, '--condition', $Condition)
    if ($Force) { $pargs += '--force' }
    $rc = Invoke-Py $pargs
    if ($rc -ne 0) {
        Say bad 'prepare failed'
        exit 1
    }
}

# ----------------------------------------------------------------- 5. check
$checked = $false
if ($SkipCheck) {
    Say warn 'skipping the name + database check (-SkipCheck)'
} else {
    Say step 'Named + database check'
    $rc = Invoke-Py @($Lab, 'check')
    $checked = ($rc -eq 0)
    if (-not $checked) {
        Say bad 'the check failed - fix the [FAIL] lines before a participant sits down'
    }
}

# ----------------------------------------------------------------- 6. build
if ($Build) {
    Say step 'Building dist\AuraUI.exe'
    $specArgs = @('-m', 'PyInstaller', '--noconfirm', '--onefile', '--noconsole',
                  '--name', 'AuraUI', '--add-data', 'aura_defaults.json;.',
                  '--hidden-import', 'pycaw', '--hidden-import', 'comtypes', 'run.py')
    Push-Location $Root
    try {
        $rc = Invoke-Py $specArgs
    } finally {
        Pop-Location
    }
    $exe = Join-Path $Root 'dist\AuraUI.exe'
    if ($rc -ne 0 -or -not (Test-Path $exe)) {
        Say bad 'PyInstaller did not produce dist\AuraUI.exe'
        exit 1
    }
    $mb = (Get-Item $exe).Length / 1MB
    Say ok ('built ' + $exe + ' ({0:N1} MB)' -f $mb)

    $listing = & $script:PyExe @($script:PyPrefix +
        @('-m', 'PyInstaller.utils.cliutils.archive_viewer', '-l', '-r', '-b', $exe)) 2>&1
    $hit = @($listing | Select-String -SimpleMatch -Pattern 'pycaw', 'comtypes')
    if ($hit.Count -gt 0) {
        Say ok ('pycaw/comtypes are inside the exe (' + $hit.Count + ' entries)')
    } else {
        Say warn 'could not confirm pycaw inside the exe'
        Write-Host '         Launch it and check the Music panel says:'
        Write-Host '         Audio: Windows volume (Core Audio)'
        Write-Host '         If it says "volume keys", rebuild with --collect-submodules comtypes.'
    }
}

# --------------------------------------------------------------- 7. summary
Say step 'Summary'
if ($checked) {
    Say ok 'station is named and can write to Firestore'
} elseif ($SkipCheck) {
    Say warn 'name + database check was skipped'
}
if ($Code) {
    Say ok ('participant ' + $Code.ToUpper() + ' / ' + $Condition + ' is set - hand the machine over')
}
if (Test-Path $VenvPy) {
    $pyCmd = '"' + $VenvPy + '"'
} elseif ($py.Prefix.Count) {
    $pyCmd = $py.Exe + ' ' + ($py.Prefix -join ' ')
} else {
    $pyCmd = $py.Exe
}
Say ok ('launch: ' + $pyCmd + ' run.py      (or dist\AuraUI.exe on a station)')
Write-Host '  Before the participant: record -> Journal -> ratings -> Save entry -> verify'
foreach ($cmd in @('verify', 'reset')) {
    Write-Host ('  After: ' + $pyCmd + ' tools\lab_setup.py ' + $cmd)
}

if (-not $SkipCheck -and -not $checked) { exit 1 }
exit 0
