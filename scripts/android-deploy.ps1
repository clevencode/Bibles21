<#
.SYNOPSIS
  Rebuild da UI/DB, sync Capacitor, APK debug e instalação ADB no LG.

.EXAMPLE
  .\scripts\android-deploy.ps1
  .\scripts\android-deploy.ps1 -Serial LMK410HMYP8HSWCIUO
  .\scripts\android-deploy.ps1 -SkipInstall
#>
param(
  [string]$Serial = "",
  [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Mobile = Join-Path $Root "mobile"
$Db = Join-Path $Root "data\biblia.db"

function Ensure-JavaHome {
  $candidates = @(
    "$env:JAVA_HOME",
    "${env:ProgramFiles}\Android\Android Studio\jbr",
    "${env:ProgramFiles}\Java\jdk-17",
    "${env:ProgramFiles}\Java\jdk-21",
    "${env:ProgramFiles}\Java\jdk-23",
    "${env:LocalAppData}\Programs\Android\Android Studio\jbr"
  ) | Where-Object { $_ }
  foreach ($j in $candidates) {
    if (Test-Path (Join-Path $j "bin\java.exe")) {
      $env:JAVA_HOME = $j
      Write-Host "JAVA_HOME=$env:JAVA_HOME"
      return
    }
  }
  throw "JDK nao encontrado (Android Studio jbr ou JDK 17+)."
}

function Find-Adb {
  $cmd = Get-Command adb -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  $candidates = @(
    "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe",
    "$env:ANDROID_HOME\platform-tools\adb.exe",
    "$env:ANDROID_SDK_ROOT\platform-tools\adb.exe"
  )
  foreach ($c in $candidates) {
    if ($c -and (Test-Path $c)) { return $c }
  }
  throw "adb não encontrado. Instala Android platform-tools ou scrcpy."
}

if (-not (Test-Path $Db)) {
  Write-Host "A criar fixture data/biblia.db..."
  & (Join-Path $Root ".venv\Scripts\python.exe") (Join-Path $Root "scripts\migrate.py") --fixture
  if ($LASTEXITCODE -ne 0) { throw "migrate.py falhou" }
}

Ensure-JavaHome
$env:ANDROID_HOME = if ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { Join-Path $env:LOCALAPPDATA "Android\Sdk" }
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME
# Evitar cache Gradle em sandbox (transforms a falhar)
if (-not $env:GRADLE_USER_HOME) {
  $env:GRADLE_USER_HOME = Join-Path $env:USERPROFILE ".gradle"
}

Push-Location $Mobile
try {
  Write-Host "==> npm run sync (prepare DB + vite + cap sync)"
  npm run sync
  if ($LASTEXITCODE -ne 0) { throw "npm run sync falhou" }

  Write-Host "==> gradlew assembleDebug"
  Push-Location (Join-Path $Mobile "android")
  try {
    .\gradlew.bat assembleDebug --quiet
    if ($LASTEXITCODE -ne 0) { throw "assembleDebug falhou" }
  } finally {
    Pop-Location
  }

  $apk = Join-Path $Mobile "android\app\build\outputs\apk\debug\app-debug.apk"
  if (-not (Test-Path $apk)) { throw "APK não encontrado: $apk" }
  Write-Host "APK: $apk"

  if ($SkipInstall) { return }

  $adb = Find-Adb
  if (-not $Serial) {
    $lines = & $adb devices | Select-Object -Skip 1 | Where-Object { $_ -match "device$" }
    if (-not $lines) { throw "Nenhum dispositivo ADB. Liga o LG (USB debugging)." }
    # Preferir serial USB (sem ':') se existir
    $usb = $lines | Where-Object { $_ -notmatch ":" } | Select-Object -First 1
    $pick = if ($usb) { $usb } else { $lines | Select-Object -First 1 }
    $Serial = ($pick -split "\s+")[0]
  }

  Write-Host "==> adb install -r ($Serial)"
  & $adb -s $Serial install -r $apk
  if ($LASTEXITCODE -ne 0) { throw "adb install falhou" }

  Write-Host "==> iniciar app"
  & $adb -s $Serial shell am start -n "com.clevenrec.bibles21/com.clevenrec.bibles21.MainActivity"
  Write-Host "OK - Bible S21 no dispositivo $Serial"
} finally {
  Pop-Location
}
