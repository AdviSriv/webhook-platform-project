# Cloud-Native Webhook Delivery Platform
## Reliable and Fault-Tolerant Event Processing (Shopping Demo)

This repository contains the core event ingestion pipeline, unit test suite, and demo shopping frontend for our cloud-native webhook platform.

---

## 1. Architecture Overview (How it works)

[ Customer / Frontend ]
          │  HTTP POST /events
          ▼
   [ API Gateway ]
          │
          ▼
 [ Ingestion Lambda ] (ingestion/handler.py)
      │          │
      │ PutItem  │ SendMessage
      ▼          ▼
 [ DynamoDB ]   [ SQS Queue ]
 (Status: QUEUED)     │
                      ▼
               [ Worker Lambda ]  <-- Member 2
                      │
                      ▼
             [ Webhook Endpoint ]
           (Retries -> DLQ on fail)

1. Order Placed: The shopping app (frontend/index.html or demo_order.py) submits an ORDER_CREATED JSON payload to the API.
2. Ingestion Lambda:
   - Validates the order schema and payload values.
   - Generates a unique event_id (UUID v4) and UTC timestamp.
   - Saves the canonical event to DynamoDB with initial status QUEUED and attempts: 0.
   - Dispatches the event message to Amazon SQS.
   - Returns 202 Accepted with the event_id.
3. Status Polling: The client calls GET /events/{event_id} to monitor delivery progress (QUEUED -> PROCESSING -> SUCCESS / FAILED).

---

## 2. Canonical Event Contract (Agreed Schema)

Every event traveling through SQS and stored in DynamoDB uses this exact structure:

{
  "event_id": "c1f7b025-a12b-426b-871d-f8d95e869762",
  "event_type": "ORDER_CREATED",
  "timestamp": "2026-10-19T12:00:00+00:00",
  "destination_url": "https://httpbin.org/post",
  "payload": {
    "order_id": "ORD-1001",
    "product": "Sony WH-1000XM5 Headphones",
    "quantity": 1,
    "total": 399.99
  }
}

### DynamoDB Attributes (WebhookEvents table):
- event_id (String, Partition Key)
- event_type (String)
- timestamp (String, ISO-8601 UTC)
- destination_url (String)
- payload (Map)
- status (String: QUEUED, PROCESSING, SUCCESS, FAILED)
- attempts (Number: Delivery attempt count)
- last_error (String or Null: Most recent delivery error message)

---

## 3. How to Run & Test (Member 1's Work)

### Setup Local Environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

### Run Unit Tests
python -m pytest -v

### Run the Shopping Frontend
python -m http.server 3000
Open http://localhost:3000/frontend/index.html in your browser.

### Run Python Demo Client (CLI)
python demo_order.py <API_GATEWAY_URL>

---

## 4. Instructions for Member 2 (Worker Lambda & Reliability)

Your job is to read queued events from SQS and deliver them to destinations reliably.

### Your Deliverables:
1. Worker Lambda (worker/handler.py):
   - Triggered by SQS (Records list).
   - Parse event_id, destination_url, and payload from record["body"].
   - Send HTTP POST to destination_url with the payload.
2. Database Updates in DynamoDB (WebhookEvents):
   - On Success (2xx):
     - status = "SUCCESS"
     - Increment attempts by 1.
   - On Failure (5xx, timeout, network error):
     - Increment attempts by 1.
     - Set last_error = <error message>.
     - Raise an exception in the Lambda handler so SQS knows the message failed.
3. Dead Letter Queue (DLQ) Testing:
   - SQS will automatically retry up to 3 times before routing the message to webhook-event-dlq.
   - Demonstrate a failed receiver (e.g., https://httpbin.org/status/500) causing the message to land in the DLQ and marking DynamoDB as FAILED.

---

## 5. Instructions for Member 3 (Terraform & Infrastructure)

Your job is to provision and connect the AWS resources using Terraform.

### Required Resources:
1. DynamoDB Table:
   - Name: WebhookEvents
   - Hash Key: event_id (Type: String)
   - Billing: PAY_PER_REQUEST
2. SQS Queues:
   - Main Queue: webhook-event-queue (Visibility timeout: 30s)
   - Dead Letter Queue: webhook-event-dlq
   - Redrive Policy on main queue: maxReceiveCount = 3, targetArn = DLQ ARN.
3. Ingestion Lambda:
   - Source: ingestion/handler.py (Handler: handler.lambda_handler)
   - Runtime: python3.12
   - Environment Variables:
     - EVENTS_TABLE = WebhookEvents
     - EVENT_QUEUE_URL = SQS queue URL
     - DEFAULT_WEBHOOK_URL = "https://httpbin.org/post"
   - IAM Permissions: dynamodb:PutItem, dynamodb:GetItem, dynamodb:UpdateItem on WebhookEvents, and sqs:SendMessage on the SQS queue.
4. Worker Lambda:
   - Source: Member 2's worker handler.
   - Event Source Mapping: Triggered by webhook-event-queue (Batch size: 1-10).
5. API Gateway (HTTP API v2):
   - POST /events -> Ingestion Lambda
   - GET /events/{event_id} -> Ingestion Lambda
   - CORS: Enabled (*)
   - Output: api_endpoint_url for testing.
