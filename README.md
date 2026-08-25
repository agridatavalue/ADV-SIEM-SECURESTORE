# ADV-SIEM-SECURESTORE

SECURESTORE is the AgriDataValue (ADV) object storage component. It deploys a
[MinIO](https://min.io/) S3-compatible object store on Kubernetes and provisions the buckets
the ADV platform expects:

| Bucket | Contents |
| --- | --- |
| `models` | Trained ML models |
| `explainators` | Explainability artefacts produced by ADV-ALMA-XAI |
| `sensordata` | Field and in-situ sensor data |
| `dronedata` | UAV imagery and derived products |
| `eodata` | Earth-observation data |

## Contents

```
charts/securestore/     Helm chart: MinIO Deployment, Service, PVC, bucket-provisioning Job
docker/createbuckets/   Image that provisions the buckets (built and pushed by you)
```

## Credentials

**This repository contains no credentials, and the chart has no default password.**

The MinIO root user and password are read from a Kubernetes Secret that you create before
installing. If `minio.auth.existingSecret` is not set, the chart deliberately refuses to render
rather than falling back to a default — so SECURESTORE cannot accidentally be deployed with a
password that lives in source control.

```bash
kubectl create secret generic securestore-minio-credentials \
  --from-literal=root-user='<user>' \
  --from-literal=root-password='<a strong, freshly generated password>'
```

Notes:

- Use single quotes. MinIO passwords often contain `#`, `$` or `!`, which your shell would
  otherwise mangle — and an unquoted `#` silently truncates the rest of the value.
- The password must be at least 8 characters; MinIO refuses to start otherwise.
- If you already have a Secret with different key names, point the chart at them with
  `minio.auth.userKey` and `minio.auth.passwordKey` instead of renaming anything.

## Prerequisites

- Kubernetes 1.23+ and Helm 3.8+
- A default StorageClass, or set `minio.persistence.storageClass`
- A container registry your cluster can pull from, for the bucket-provisioning image

## Install

**1. Build and push the bucket-provisioning image.**

The chart does not reference a published image, because ADV partners deploy into their own
registries:

```bash
docker build -t <registry>/securestore-createbuckets:1.1.0 docker/createbuckets
docker push <registry>/securestore-createbuckets:1.1.0
```

**2. Create the credentials Secret** (see above).

**3. Install the chart.**

```bash
helm install securestore charts/securestore \
  --namespace adv --create-namespace \
  --set minio.auth.existingSecret=securestore-minio-credentials \
  --set createBuckets.image.repository=<registry>/securestore-createbuckets \
  --set createBuckets.image.tag=1.1.0
```

Helm waits for the bucket-provisioning Job, so the install fails if the buckets could not be
created. It does not report success over an empty object store.

To deploy MinIO without provisioning buckets, set `createBuckets.enabled=false`; the image
values are then not required.

## Configuration

| Value | Default | Description |
| --- | --- | --- |
| `minio.name` | `minio` | Name of the Deployment/Service, and the `app` selector label |
| `minio.image.repository` | `quay.io/minio/minio` | MinIO image. Upstream publishes to quay.io |
| `minio.image.tag` | `RELEASE.2024-12-18T13-15-44Z` | Pinned; see *MinIO version* below |
| `minio.auth.existingSecret` | `""` | **Required.** Secret holding the root credentials |
| `minio.auth.userKey` | `root-user` | Key within that Secret for the user |
| `minio.auth.passwordKey` | `root-password` | Key within that Secret for the password |
| `minio.service.type` | `ClusterIP` | Service type |
| `minio.service.apiPort` | `9000` | S3 API port |
| `minio.service.consolePort` | `9001` | Web console port |
| `minio.service.apiNodePort` | `""` | Optional fixed NodePort for the API |
| `minio.service.consoleNodePort` | `""` | Optional fixed NodePort for the console |
| `minio.persistence.enabled` | `true` | Set false to use an emptyDir (test clusters only) |
| `minio.persistence.name` | `miniostorage` | PVC name |
| `minio.persistence.size` | `10Gi` | Requested volume size |
| `minio.persistence.accessMode` | `ReadWriteOnce` | PVC access mode |
| `minio.persistence.storageClass` | `""` | Empty uses the cluster default |
| `minio.tls` | `false` | Whether MinIO is served over HTTPS |
| `createBuckets.enabled` | `true` | Run the bucket-provisioning Job |
| `createBuckets.image.repository` | `""` | **Required when enabled** |
| `createBuckets.image.tag` | `""` | Defaults to the chart's `appVersion` |
| `createBuckets.buckets` | the five above | Buckets to provision |
| `createBuckets.connectRetries` | `30` | Connection attempts while MinIO starts |
| `createBuckets.connectRetryDelaySeconds` | `5` | Delay between attempts |
| `createBuckets.backoffLimit` | `6` | Job-level retries |

The default retry settings give MinIO up to 150 seconds to become reachable per Job attempt.

## Connecting from other ADV components

In-cluster clients reach the store at `minio:9000` (or
`minio.<namespace>.svc.cluster.local:9000` across namespaces). The Service name is kept at
`minio` by default for exactly this reason — if you override `minio.name`, update the
dependent components too.

Clients should read their own credentials from the same Kubernetes Secret rather than embedding
them.

## Verifying a deployment

```bash
kubectl -n adv get pods,svc,pvc
kubectl -n adv get job securestore-... # Completed, unless the hook was cleaned up on success
kubectl -n adv port-forward svc/minio 9001:9001
```

Then open <http://localhost:9001>, sign in with the credentials from your Secret, and confirm
all five buckets are listed.

If the install failed at the bucket-provisioning step, the Job is left in place on purpose:

```bash
kubectl -n adv logs job/minio-createbuckets
```

