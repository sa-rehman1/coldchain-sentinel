$ErrorActionPreference = 'Stop'
$baseUrl = 'http://localhost:8000/api/v1'
$now = [DateTimeOffset]::UtcNow.ToString('o')
$event = @{
    schemaVersion = '1.0'
    eventId = '10000000-0000-4000-8000-000000000002'
    correlationId = '10000000-0000-4000-8000-000000000003'
    occurredAt = $now
    producer = 'milestone-1a-demo'
    shipmentId = '10000000-0000-4000-8000-000000000001'
    vehicleId = 'demo-vehicle-1'
    sensorId = 'demo-sensor-1'
    latitude = 33.77
    longitude = -118.19
    temperatureCelsius = 10.5
    cargoType = 'FRESH_PERISHABLES'
    readingSequence = 1
}
Invoke-RestMethod -Method Post -Uri "$baseUrl/telemetry" -ContentType 'application/json' -Body ($event | ConvertTo-Json)
Start-Sleep -Seconds 2
$incident = Invoke-RestMethod -Uri "$baseUrl/incidents" | Where-Object shipmentId -eq $event.shipmentId | Select-Object -First 1
$incident = Invoke-RestMethod -Uri "$baseUrl/incidents/$($incident.incidentId)"
$headers = @{'X-Actor-ID' = 'dispatcher:demo'; 'X-Actor-Roles' = 'dispatcher'}
$decisionBody = @{rationale = 'Deterministic demo evidence reviewed'; idempotencyKey = 'milestone-1a-demo-approval-v1'} | ConvertTo-Json
$decision = Invoke-RestMethod -Method Post -Uri "$baseUrl/incidents/$($incident.incidentId)/recommendations/$($incident.recommendationId)/approve" -Headers $headers -ContentType 'application/json' -Body $decisionBody
Invoke-RestMethod -Uri "$baseUrl/commands/$($decision.commandId)"
Invoke-RestMethod -Uri "$baseUrl/incidents/$($incident.incidentId)/timeline"
