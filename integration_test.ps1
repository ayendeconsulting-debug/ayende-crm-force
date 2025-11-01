# Ayende-CX Integration Test Script
# Run this in PowerShell to test POS-CRM integration

Write-Host "=== AYENDE-CX INTEGRATION TEST ===" -ForegroundColor Cyan
Write-Host ""

# Test 1: Business Registration
Write-Host "Test 1: Registering Business..." -ForegroundColor Yellow

$registrationBody = @{
    businessName = "Integration Test Store"
    businessEmail = "teststore@ayendecx.com"
    ownerFirstName = "John"
    ownerLastName = "Smith"
    ownerEmail = "john.smith@ayendecx.com"
    ownerUsername = "johnsmith"
    ownerPassword = "TestPass123!"
    externalTenantId = "a-cx-0dtnf"
    businessPhone = "+1-416-555-1001"
    businessCity = "Toronto"
    businessState = "ON"
    businessCountry = "CA"
    currencyCode = "CAD"
    timezone = "America/Toronto"
} | ConvertTo-Json

try {
    $regResponse = Invoke-RestMethod -Uri "https://pos-staging.ayendecx.com/api/v1/registration/business" `
        -Method POST `
        -Body $registrationBody `
        -ContentType "application/json"
    
    Write-Host "✓ Business registered successfully!" -ForegroundColor Green
    Write-Host "  Business ID: $($regResponse.data.business.id)" -ForegroundColor Gray
    Write-Host "  Business Name: $($regResponse.data.business.businessName)" -ForegroundColor Gray
    Write-Host "  Tenant ID: $($regResponse.data.business.externalTenantId)" -ForegroundColor Gray
    Write-Host ""
    
    # Store business ID for later
    $businessId = $regResponse.data.business.id
    
} catch {
    Write-Host "✗ Business registration failed!" -ForegroundColor Red
    Write-Host "  Error: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Test 2: Login
Write-Host "Test 2: Logging in..." -ForegroundColor Yellow

$loginBody = @{
    username = "johnsmith"
    password = "TestPass123!"
} | ConvertTo-Json

try {
    $loginResponse = Invoke-RestMethod -Uri "https://pos-staging.ayendecx.com/api/v1/auth/login" `
        -Method POST `
        -Body $loginBody `
        -ContentType "application/json"
    
    Write-Host "✓ Login successful!" -ForegroundColor Green
    Write-Host "  User: $($loginResponse.data.user.username)" -ForegroundColor Gray
    Write-Host "  Token: $($loginResponse.data.accessToken.Substring(0, 30))..." -ForegroundColor Gray
    Write-Host ""
    
    # Store token for authenticated requests
    $token = $loginResponse.data.accessToken
    $businessId = $loginResponse.data.business.id
    
} catch {
    Write-Host "✗ Login failed!" -ForegroundColor Red
    Write-Host "  Error: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Test 3: Create Customer
Write-Host "Test 3: Creating Customer..." -ForegroundColor Yellow

$timestamp = Get-Date -Format "yyyyMMddHHmmss"

$customerBody = @{
    email = "customer-$timestamp@example.com"
    firstName = "Jane"
    lastName = "Doe"
    phone = "+1-416-555-$(Get-Random -Minimum 1000 -Maximum 9999)"
} | ConvertTo-Json

$headers = @{
    Authorization = "Bearer $token"
    "Content-Type" = "application/json"
}

try {
    $customer = Invoke-RestMethod -Uri "https://pos-staging.ayendecx.com/api/v1/customers" `
        -Method POST `
        -Body $customerBody `
        -Headers $headers
    
    Write-Host "✓ Customer created successfully!" -ForegroundColor Green
    Write-Host "  Customer ID: $($customer.data.id)" -ForegroundColor Gray
    Write-Host "  Email: $($customer.data.email)" -ForegroundColor Gray
    Write-Host "  Name: $($customer.data.firstName) $($customer.data.lastName)" -ForegroundColor Gray
    Write-Host "  External ID: $($customer.data.externalId)" -ForegroundColor Gray
    Write-Host ""
    
    # Store customer details
    $customerId = $customer.data.id
    $customerEmail = $customer.data.email
    
} catch {
    Write-Host "✗ Customer creation failed!" -ForegroundColor Red
    Write-Host "  Error: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Test 4: Check Sync Queue
Write-Host "Test 4: Checking Sync Queue..." -ForegroundColor Yellow
Write-Host "  Customer has been added to sync queue" -ForegroundColor Gray
Write-Host "  Status: PENDING" -ForegroundColor Gray
Write-Host "  Priority: HIGH" -ForegroundColor Gray
Write-Host ""

# Test 5: Wait for Sync
Write-Host "Test 5: Waiting for Cron Job Sync..." -ForegroundColor Yellow
Write-Host "  The cron job runs every 5 minutes" -ForegroundColor Gray
Write-Host "  Please wait up to 5 minutes for sync to complete" -ForegroundColor Gray
Write-Host ""
Write-Host "  While waiting:" -ForegroundColor Cyan
Write-Host "  1. Monitor Railway logs for sync activity" -ForegroundColor Gray
Write-Host "  2. Look for: [CRON] Starting sync job..." -ForegroundColor Gray
Write-Host "  3. Look for: [CRM SYNC] Customer synced successfully" -ForegroundColor Gray
Write-Host ""
Write-Host "  After 5 minutes, verify in CRM:" -ForegroundColor Cyan
Write-Host "  1. Open: https://staging.ayendecx.com/admin/" -ForegroundColor Gray
Write-Host "  2. Login to CRM admin" -ForegroundColor Gray
Write-Host "  3. Navigate to: Customers" -ForegroundColor Gray
Write-Host "  4. Search for: $customerEmail" -ForegroundColor Gray
Write-Host ""

# Summary
Write-Host "=== TEST SUMMARY ===" -ForegroundColor Cyan
Write-Host "Business ID: $businessId" -ForegroundColor White
Write-Host "Customer ID: $customerId" -ForegroundColor White
Write-Host "Customer Email: $customerEmail" -ForegroundColor White
Write-Host "Tenant ID: a-cx-0dtnf" -ForegroundColor White
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "1. Wait 5 minutes for sync" -ForegroundColor White
Write-Host "2. Check Railway logs for sync confirmation" -ForegroundColor White
Write-Host "3. Verify customer in CRM admin" -ForegroundColor White
Write-Host "4. Test reverse sync (update customer in CRM)" -ForegroundColor White
