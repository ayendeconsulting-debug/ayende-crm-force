# Phase 2D CRM Sync Endpoints - Deployment Script
# Run this script from the outputs directory where you saved the files

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "PHASE 2D CRM SYNC ENDPOINTS DEPLOYMENT" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Configuration
$CRM_PATH = "C:\Users\Admin\OneDrive\Documents\Environment\ayende-cx"
$VIEWS_PATH = "$CRM_PATH\dashboard\views"

Write-Host "CRM Path: $CRM_PATH" -ForegroundColor Yellow
Write-Host ""

# Check if CRM directory exists
if (-not (Test-Path $CRM_PATH)) {
    Write-Host "ERROR: CRM directory not found at $CRM_PATH" -ForegroundColor Red
    Write-Host "Please update the CRM_PATH variable in this script" -ForegroundColor Red
    exit 1
}

# Check if views directory exists
if (-not (Test-Path $VIEWS_PATH)) {
    Write-Host "ERROR: Views directory not found at $VIEWS_PATH" -ForegroundColor Red
    exit 1
}

Write-Host "Step 1: Deploying sync_views.py..." -ForegroundColor Green

# Copy sync_views.py
$SYNC_VIEWS_SOURCE = "sync_views.py"
$SYNC_VIEWS_DEST = "$VIEWS_PATH\sync_views.py"

if (-not (Test-Path $SYNC_VIEWS_SOURCE)) {
    Write-Host "ERROR: sync_views.py not found in current directory" -ForegroundColor Red
    Write-Host "Please ensure sync_views.py is in the same directory as this script" -ForegroundColor Red
    exit 1
}

Copy-Item $SYNC_VIEWS_SOURCE $SYNC_VIEWS_DEST -Force
Write-Host "  ✓ Deployed: $SYNC_VIEWS_DEST" -ForegroundColor Green

Write-Host ""
Write-Host "Step 2: Updating __init__.py..." -ForegroundColor Green

# Update __init__.py to include sync_views
$INIT_FILE = "$VIEWS_PATH\__init__.py"

if (Test-Path $INIT_FILE) {
    $content = Get-Content $INIT_FILE -Raw
    
    # Check if sync_views import already exists
    if ($content -notmatch "from \. import sync_views") {
        # Add the import after the integration import
        $content = $content -replace "(from \. import integration)", "`$1`nfrom . import sync_views"
        
        Set-Content -Path $INIT_FILE -Value $content -NoNewline
        Write-Host "  ✓ Updated: $INIT_FILE" -ForegroundColor Green
    } else {
        Write-Host "  ✓ Already updated: $INIT_FILE" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ⚠ WARNING: __init__.py not found at $INIT_FILE" -ForegroundColor Yellow
    Write-Host "  You'll need to manually add: from . import sync_views" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Step 3: URL Configuration..." -ForegroundColor Green
Write-Host "  ⚠ MANUAL STEP REQUIRED" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Add these routes to your config/urls.py:" -ForegroundColor Cyan
Write-Host ""
Write-Host "  from dashboard.views import sync_views" -ForegroundColor White
Write-Host ""
Write-Host "  urlpatterns = [" -ForegroundColor White
Write-Host "      # ... existing routes ..." -ForegroundColor Gray
Write-Host "      path('api/v1/sync/transaction', sync_views.receive_transaction)," -ForegroundColor White
Write-Host "      path('api/v1/sync/customer', sync_views.receive_customer)," -ForegroundColor White
Write-Host "      path('api/v1/sync/health', sync_views.sync_health)," -ForegroundColor White
Write-Host "  ]" -ForegroundColor White
Write-Host ""

Write-Host "Step 4: Verification..." -ForegroundColor Green

# Check settings.py
$SETTINGS_FILE = "$CRM_PATH\config\settings.py"
if (-not (Test-Path $SETTINGS_FILE)) {
    $SETTINGS_FILE = "$CRM_PATH\ayende_cx\settings.py"
}

if (Test-Path $SETTINGS_FILE) {
    $settings_content = Get-Content $SETTINGS_FILE -Raw
    
    # Check for required settings
    $has_integration_secret = $settings_content -match "INTEGRATION_SECRET"
    $has_enable_crm_sync = $settings_content -match "ENABLE_CRM_SYNC"
    
    if ($has_integration_secret -and $has_enable_crm_sync) {
        Write-Host "  ✓ Settings.py configuration looks good" -ForegroundColor Green
    } else {
        Write-Host "  ⚠ WARNING: Missing required settings in settings.py" -ForegroundColor Yellow
        if (-not $has_integration_secret) {
            Write-Host "    Missing: INTEGRATION_SECRET" -ForegroundColor Yellow
        }
        if (-not $has_enable_crm_sync) {
            Write-Host "    Missing: ENABLE_CRM_SYNC" -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "  ⚠ Could not find settings.py to verify" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "DEPLOYMENT SUMMARY" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Files Deployed:" -ForegroundColor Green
Write-Host "  ✓ dashboard/views/sync_views.py" -ForegroundColor Green
Write-Host ""
Write-Host "Manual Steps Required:" -ForegroundColor Yellow
Write-Host "  1. Add sync routes to config/urls.py (see above)" -ForegroundColor Yellow
Write-Host "  2. Restart Django server" -ForegroundColor Yellow
Write-Host "  3. Test health endpoint: http://localhost:8000/api/v1/sync/health" -ForegroundColor Yellow
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "  1. Review: PHASE_2D_CRM_INTEGRATION_GUIDE.md" -ForegroundColor Cyan
Write-Host "  2. Run tests to verify integration" -ForegroundColor Cyan
Write-Host "  3. Monitor POS logs for successful syncs" -ForegroundColor Cyan
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Prompt to open guide
$response = Read-Host "Would you like to open the integration guide? (y/n)"
if ($response -eq 'y' -or $response -eq 'Y') {
    Start-Process "PHASE_2D_CRM_INTEGRATION_GUIDE.md"
}

Write-Host ""
Write-Host "Deployment script completed!" -ForegroundColor Green
Write-Host ""
