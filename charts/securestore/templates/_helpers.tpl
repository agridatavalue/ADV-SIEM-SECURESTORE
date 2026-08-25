{{/*
Name of the MinIO Deployment and Service.
*/}}
{{- define "securestore.minioName" -}}
{{- default .Values.minio.name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Selector labels. Deliberately kept to the single `app` label used by earlier
versions of this chart: Service selectors and Deployment selectors are
immutable, and dependent ADV components may select on it.
*/}}
{{- define "securestore.selectorLabels" -}}
app: {{ include "securestore.minioName" . }}
{{- end -}}

{{/*
Common metadata labels.
*/}}
{{- define "securestore.labels" -}}
{{ include "securestore.selectorLabels" . }}
app.kubernetes.io/name: {{ include "securestore.minioName" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: securestore
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end -}}

{{/*
Name of the Secret holding the MinIO root credentials.

This chart never creates, defaults or generates these credentials. Failing to
render is intentional: it is the mechanism that prevents SECURESTORE from ever
being deployed with a password committed to source control.
*/}}
{{- define "securestore.authSecretName" -}}
{{- if not .Values.minio.auth.existingSecret -}}
{{- fail "\n\nminio.auth.existingSecret is required.\n\nThis chart ships no default MinIO password. Create a Secret first:\n\n  kubectl create secret generic securestore-minio-credentials \\\n    --from-literal=root-user='<user>' \\\n    --from-literal=root-password='<password>'\n\nthen install with:\n\n  --set minio.auth.existingSecret=securestore-minio-credentials\n\nSee README.md for details.\n" -}}
{{- end -}}
{{- .Values.minio.auth.existingSecret -}}
{{- end -}}

{{/*
Fully qualified image reference for the bucket-provisioning Job.
*/}}
{{- define "securestore.createBucketsImage" -}}
{{- if not .Values.createBuckets.image.repository -}}
{{- fail "\n\ncreateBuckets.image.repository is required when createBuckets.enabled is true.\n\nBuild and push the image from docker/createbuckets, then install with:\n\n  --set createBuckets.image.repository=<registry>/<path>/securestore-createbuckets \\\n  --set createBuckets.image.tag=<tag>\n\nAlternatively set createBuckets.enabled=false to deploy MinIO without provisioning buckets.\n" -}}
{{- end -}}
{{- printf "%s:%s" .Values.createBuckets.image.repository (default .Chart.AppVersion .Values.createBuckets.image.tag) -}}
{{- end -}}

{{/*
host:port the bucket Job uses to reach the MinIO API.
*/}}
{{- define "securestore.minioEndpoint" -}}
{{- printf "%s:%v" (include "securestore.minioName" .) .Values.minio.service.apiPort -}}
{{- end -}}
