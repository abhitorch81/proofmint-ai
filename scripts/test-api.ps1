$ErrorActionPreference = "Stop"
Write-Host "Checking health..."
Invoke-RestMethod http://localhost:8000/api/health | ConvertTo-Json
Write-Host "Registering demo asset..."
$body = @{ title='Demo Image'; creator='ProofMint'; sha256=('a' * 64); license_text='One commercial website'; price_cents=1200 } | ConvertTo-Json
$asset = Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/assets -ContentType 'application/json' -Body $body
$asset | ConvertTo-Json
Write-Host "Checking exact provenance lookup..."
$lookupBody = @{sha256=('a' * 64)} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/provenance/lookup -ContentType 'application/json' -Body $lookupBody | ConvertTo-Json -Depth 4
Write-Host "Success. PayPal checkout requires sandbox credentials and buyer approval in the UI."
