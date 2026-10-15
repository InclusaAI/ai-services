# Single-node Redpanda (Kafka protocol) private broker for the Render deployment.
#
# Render private services support raw TCP on any port and are reachable by
# service name on Render's private network, so the broker binds Kafka on the
# standard Render port (10000) and advertises `redpanda:10000` — the private
# DNS name Render clients use.
#
# Differences vs docker-compose.dev.yml (which listens on 29092/advertises
# redpanda:29092): only the ports. The persistent disk attached in render.yaml
# mounts at /var/lib/redpanda/data; we chown it for the image's non-root user.
FROM docker.redpanda.com/redpandadata/redpanda:v24.2.7

EXPOSE 10000

# shell form so we can chown the attached persistent disk before handoff
CMD ["sh", "-c", "chown -R redpanda:redpanda /var/lib/redpanda/data 2>/dev/null || true; exec redpanda start \
  --smp=1 \
  --overprovisioned \
  --node-id=0 \
  --check=false \
  --kafka-addr=PLAINTEXT://0.0.0.0:10000 \
  --advertise-kafka-addr=PLAINTEXT://redpanda:10000"]
