# Image for the SECURESTORE bucket-provisioning Job.
#
# No credentials are copied in: the previous version of this Dockerfile did
# `COPY .env .`, which baked the MinIO root password into an image layer where
# it stayed readable to anyone who could pull the image. Configuration is now
# injected at runtime from a Kubernetes Secret — see createBuckets.py.
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY createBuckets.py ./

# Run unprivileged; the UID matches the Job's securityContext in the chart.
RUN useradd --no-create-home --uid 10001 securestore
USER 10001

ENTRYPOINT ["python", "createBuckets.py"]
