# Kafka SASL/SSL Configuration

This guide explains how to configure services to connect to Aiven Kafka (or other SASL_SSL brokers) in staging and production environments.

## Issue

The services were failing to connect to Aiven Kafka with:
```
[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate
```

This happens when the Kafka client security configuration (protocol, credentials, and CA certificate) is not properly passed to the deployment environment.

## Solution

All services use the same Kafka client configuration mechanism. Set these environment variables for **each service** in Render:

### Required Environment Variables

| Variable | Value | Source |
|----------|-------|--------|
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka-9780174-imkargi-90f4.l.aivencloud.com:27345` | Aiven console → "Service URI" |
| `KAFKA_SECURITY_PROTOCOL` | `SASL_SSL` | Fixed for Aiven SASL |
| `KAFKA_SASL_MECHANISM` | `SCRAM-SHA-256` | Fixed for Aiven |
| `KAFKA_SASL_USERNAME` | `avnadmin` | Aiven console → "User" |
| `KAFKA_SASL_PASSWORD` | Your password | Aiven console → "Password" → "Show" |
| `KAFKA_SSL_CA` | Full PEM certificate | Aiven console → "CA certificate" → "Show" |

### Getting CA Certificate from Aiven

1. Go to your Aiven Kafka service console
2. Find the **"CA certificate"** section at the bottom
3. Click **"Show"** to reveal the certificate
4. Copy the entire PEM block (including `-----BEGIN CERTIFICATE-----` and `-----END CERTIFICATE-----`)
5. Paste as the `KAFKA_SSL_CA` environment variable value

### Setting Environment Variables in Render

#### Option A: Dashboard (One-time, easiest for quick setup)

For each service in `render.yaml`:

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Select the service (e.g., `sign-recognition-service`)
3. Go to **Settings** → **Environment**
4. Add the 6 variables above
5. Click **Save Changes** → service auto-redeploys
6. Repeat for all services (asr-service, sign-recognition-service, tts-service, etc.)

#### Option B: `render.yaml` (Recommended for team/CI)

Update `render.yaml` to include environment variables for each service:

```yaml
services:
  - type: web
    name: sign-recognition-service
    env: docker
    dockerfilePath: ./services/sign-recognition-service/Dockerfile
    dockerContext: .
    plan: free
    healthCheckPath: /healthz
    envVars:
      - key: KAFKA_BOOTSTRAP_SERVERS
        value: kafka-9780174-imkargi-90f4.l.aivencloud.com:27345
      - key: KAFKA_SECURITY_PROTOCOL
        value: SASL_SSL
      - key: KAFKA_SASL_MECHANISM
        value: SCRAM-SHA-256
      - key: KAFKA_SASL_USERNAME
        fromService:
          name: kafka-credentials
          type: env
          property: KAFKA_SASL_USERNAME
      - key: KAFKA_SASL_PASSWORD
        fromService:
          name: kafka-credentials
          type: env
          property: KAFKA_SASL_PASSWORD
      - key: KAFKA_SSL_CA
        fromService:
          name: kafka-credentials
          type: env
          property: KAFKA_SSL_CA
```

**Note:** This approach references a secret/env service; see Render docs on environment management.

#### Option C: Render Secrets (Most secure for sensitive data)

Alternatively, use Render's **Secret Files** or **Environments** feature to centralize Kafka credentials without duplicating them in `render.yaml`.

## Verification

After deploying with these variables, check the service logs:

1. Go to Render dashboard → service
2. Look for this message (should appear ~1-2 minutes after deploy):
   ```
   INFO: producer.started bootstrap=kafka-9780174-imkargi-90f4.l.aivencloud.com:27345
   INFO: consumer.started group=sign-recognition-service topics=[...]
   ```

If you still see:
```
WARNING: producer.offline error=KafkaConnectionError: Unable to bootstrap...
```

**Troubleshooting:**

- Verify all 6 environment variables are set (not just some)
- Check that `KAFKA_SSL_CA` is the complete PEM (including header/footer lines)
- Ensure the password and username are correct (copy from Aiven console, not from memory)
- Check service logs for the exact error message

## Local Development (Docker Compose)

For local dev with Aiven instead of Redpanda, copy `.env.example` to `.env` and uncomment the Kafka SASL/SSL section:

```bash
cp .env.example .env
# Edit .env to uncomment and fill in Aiven details
docker-compose -f docker-compose.dev.yml up
```

## Architecture Notes

- Both `KafkaEventProducer` and `KafkaEventConsumer` (in `shared/kafka_clients/`) read these env vars
- If `KAFKA_SECURITY_PROTOCOL` is not set or is `PLAINTEXT`, SSL is skipped (dev mode with Redpanda)
- If `KAFKA_SECURITY_PROTOCOL=SASL_SSL` but `KAFKA_SSL_CA` is missing, the client uses system CA store (fails for Aiven's self-signed/custom CA)
- The entire platform degrades gracefully: if Kafka is unreachable, services still boot with HTTP API + stub inference (logged as `pipeline.offline`)
