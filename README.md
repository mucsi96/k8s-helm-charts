# k8s-helm-charts

Helm charts for application deployments in Kubernetes

## Overview

This repository contains reusable Helm charts for deploying various types of applications and databases in Kubernetes clusters. Each chart is designed with best practices and includes support for monitoring, secrets management, and routing.

## Available Charts

- [client_app](#client_app) - Static frontend applications (nginx-based)
- [node_app](#node_app) - Node.js backend applications
- [spring_app](#spring_app) - Spring Boot Java applications
- [postgres_db](#postgres_db) - PostgreSQL database with monitoring
- [redis](#redis) - Redis session store for oauth2-proxy
- [grafana_alloy](#grafana_alloy) - Grafana Alloy telemetry collector

---

## client_app

Deploys a static frontend application using nginx, suitable for React, Vue, Angular, or other client-side applications.

### Required Values

| Parameter | Description | Example |
|-----------|-------------|---------|
| `image` | Container image for the application | `myregistry.io/my-app:1.0.0` |
| `appPort` | Application port (nginx port) | `80` |
| `metricsPort` | Metrics exporter port | `8085` |
| `host` | Hostname for the Ingress route | `myapp.example.com` |
| `entryPoint` | Traefik entrypoint to use | `websecure` |

### Optional Values

| Parameter | Description | Example | Default |
|-----------|-------------|---------|---------|
| `basePath` | Base path prefix for the application | `/app` | - |
| `env` | Environment variables as key-value pairs | See example below | `{}` |

### Example values.yaml

```yaml
image: myregistry.io/my-frontend-app:1.0.0
appPort: 80
metricsPort: 8085
host: myapp.example.com
entryPoint: websecure
basePath: /dashboard
env:
  API_URL: https://api.example.com
  FEATURE_FLAG: "true"
```

---

## node_app

Deploys a Node.js backend application with support for Azure Workload Identity and environment variables.

### Required Values

| Parameter | Description | Example |
|-----------|-------------|---------|
| `image` | Container image for the application | `myregistry.io/my-node-app:1.0.0` |
| `appPort` | Application port | `8080` |
| `host` | Hostname for the Ingress route | `api.example.com` |
| `entryPoint` | Traefik entrypoint to use | `websecure` |
| `serviceAccountName` | Kubernetes service account name | `my-app-sa` |
| `clientId` | Azure AD client ID for workload identity | `12345678-1234-1234-1234-123456789abc` |

### Optional Values

| Parameter | Description | Example | Default |
|-----------|-------------|---------|---------|
| `basePath` | Base path prefix for the application | `/api` | - |
| `env` | Environment variables as key-value pairs | See example below | `{}` |

### Example values.yaml

```yaml
image: myregistry.io/my-node-app:1.0.0
appPort: 8080
host: api.example.com
entryPoint: websecure
basePath: /api/v1
serviceAccountName: my-node-app-sa
clientId: 12345678-1234-1234-1234-123456789abc
env:
  DATABASE_URL: postgresql://localhost:5432/mydb
  LOG_LEVEL: info
  NODE_ENV: production
```

---

## spring_app

Deploys a Spring Boot application with support for Spring Boot Actuator, Azure Workload Identity, config files, and persistent storage.

### Required Values

| Parameter | Description | Example |
|-----------|-------------|---------|
| `image` | Container image for the application | `myregistry.io/my-spring-app:1.0.0` |
| `appPort` | Application port | `8080` |
| `springActuatorPort` | Spring Actuator management port | `8082` |
| `host` | Hostname for the Ingress route | `api.example.com` |
| `entryPoint` | Traefik entrypoint to use | `websecure` |
| `serviceAccountName` | Kubernetes service account name | `my-app-sa` |
| `clientId` | Azure AD client ID for workload identity | `12345678-1234-1234-1234-123456789abc` |
| `springAdminServerHost` | Spring Boot Admin server hostname | `spring-admin.example.com` |
| `springAdminServerPort` | Spring Boot Admin server port | `8080` |

### Optional Values

| Parameter | Description | Example | Default |
|-----------|-------------|---------|---------|
| `basePath` | Base path prefix for the application | `/api` | - |
| `env` | Environment variables as key-value pairs | See example below | `{}` |
| `configFile` | Array of config files to mount as secrets | See example below | `[]` |
| `persistentVolumeClaims` | Array of PVCs to create and mount | See example below | `[]` |

### Config File Structure

Each config file entry supports:

| Field | Description | Required |
|-------|-------------|----------|
| `name` | File name | Yes |
| `mountPath` | Full path where the file should be mounted | Yes |
| `data` | Base64-encoded file contents | Yes |

### Persistent Volume Claim Structure

Each PVC entry supports:

| Field | Description | Required | Example |
|-------|-------------|----------|---------|
| `name` | PVC identifier (unique name) | Yes | `data` |
| `mountPath` | Mount path in the container | Yes | `/data` |
| `accessMode` | Access mode for the volume | Yes | `ReadWriteOnce` |
| `storageClassName` | Storage class name | Yes | `standard` |
| `volumeName` | Persistent volume name to bind to | Yes | `pv-data` |
| `storage` | Storage size | Yes | `10Gi` |

### Example values.yaml

```yaml
image: myregistry.io/my-spring-app:1.0.0
appPort: 8080
springActuatorPort: 8082
host: api.example.com
entryPoint: websecure
basePath: /api
serviceAccountName: my-spring-app-sa
clientId: 12345678-1234-1234-1234-123456789abc
springAdminServerHost: spring-admin.example.com
springAdminServerPort: 8080

env:
  SPRING_PROFILES_ACTIVE: production
  DATABASE_URL: postgresql://localhost:5432/mydb

configFile:
  - name: application.properties
    mountPath: /config/application.properties
    data: c3ByaW5nLmRhdGFzb3VyY2UudXJsPWpkYmM6cG9zdGdyZXNxbDovL2xvY2FsaG9zdDo1NDMyL215ZGI=
  - name: logback.xml
    mountPath: /config/logback.xml
    data: PGNvbmZpZ3VyYXRpb24+PC9jb25maWd1cmF0aW9uPg==

persistentVolumeClaims:
  - name: data
    mountPath: /data
    accessMode: ReadWriteOnce
    storageClassName: standard
    volumeName: pv-data
    storage: 10Gi
  - name: logs
    mountPath: /var/log/app
    accessMode: ReadWriteOnce
    storageClassName: standard
    volumeName: pv-logs
    storage: 5Gi
```

---

## postgres_db

Deploys a PostgreSQL database with Prometheus metrics exporter and persistent storage.

### Required Values

| Parameter | Description | Example |
|-----------|-------------|---------|
| `name` | Database name | `myappdb` |
| `port` | PostgreSQL port | `5432` |
| `metricsPort` | Prometheus exporter port | `8085` |
| `username` | Database username (stored as secret) | `myuser` |
| `password` | Database password (stored as secret) | `mypassword` |
| `exporterUsername` | Prometheus exporter username | `exporter` |
| `exporterPassword` | Prometheus exporter password | `exporterpass` |

### Optional Values

| Parameter | Description | Example | Default |
|-----------|-------------|---------|---------|
| `initSql` | SQL script to run on database initialization | `CREATE TABLE users (id SERIAL);` | `""` |
| `persistentVolumeClaim` | Persistent volume claim configuration object | See below | See below |

### Persistent Volume Claim Configuration

The `persistentVolumeClaim` parameter accepts an object with the following fields:

| Field | Description | Example | Default |
|-------|-------------|---------|---------|
| `accessMode` | Access mode for the volume | `ReadWriteOnce` | `ReadWriteOnce` |
| `storageClassName` | Storage class name for the PVC | `standard` | `""` |
| `volumeName` | Persistent volume name to bind to | `pv-postgres-data` | `""` |
| `storage` | Storage size | `10Gi` | `1Gi` |

### Features

- PostgreSQL 17.6 with configurable persistent storage
- Prometheus metrics exporter for monitoring
- Automatic database initialization with custom SQL
- Automatic creation of exporter user with `pg_monitor` role
- Service monitor for Prometheus integration

### Example values.yaml

```yaml
name: myappdb
port: 5432
metricsPort: 8085
username: myuser
password: securepassword123
exporterUsername: exporter
exporterPassword: exporterpass456
initSql: |
  CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
  );
  CREATE INDEX idx_username ON users(username);
persistentVolumeClaim:
  accessMode: ReadWriteOnce
  storageClassName: standard
  volumeName: pv-postgres-data
  storage: 10Gi
```

---

## redis

Deploys a single-instance Redis suitable for use as a session store for [oauth2-proxy](https://oauth2-proxy.github.io/oauth2-proxy/).

### Required Values

| Parameter | Description | Example |
|-----------|-------------|---------|
| `password` | Redis AUTH password (stored as a secret) | `changeme` |

### Optional Values

| Parameter | Description | Example | Default |
|-----------|-------------|---------|---------|
| `port` | Service port for Redis | `6379` | `6379` |
| `resources` | Container resource requests/limits | See below | See below |
| `persistentVolumeClaim` | PVC configuration object | See below | See below |

### Persistent Volume Claim Configuration

| Field | Description | Example | Default |
|-------|-------------|---------|---------|
| `accessMode` | Access mode for the volume | `ReadWriteOnce` | `ReadWriteOnce` |
| `storageClassName` | Storage class name for the PVC | `standard` | `""` |
| `volumeName` | Persistent volume name to bind to | `pv-redis-data` | `""` |
| `storage` | Storage size | `1Gi` | `1Gi` |

### Features

- Redis 7.4 with AOF persistence enabled
- Password authentication via Kubernetes secret
- Persistent storage for session durability across restarts
- TCP liveness and authenticated readiness probes

### Example values.yaml

```yaml
password: changeme
port: 6379
persistentVolumeClaim:
  accessMode: ReadWriteOnce
  storageClassName: standard
  volumeName: pv-redis-data
  storage: 1Gi
```

### Using with oauth2-proxy

Configure oauth2-proxy with the following arguments:

```
--session-store-type=redis
--redis-connection-url=redis://:<password>@<release-name>.<namespace>.svc.cluster.local:6379
```

---

## grafana_alloy

Deploys [Grafana Alloy](https://grafana.com/oss/alloy/) as a single-replica
telemetry collector for metrics, logs, and traces. The chart provisions a
ServiceAccount with cluster-wide read access for Kubernetes service discovery
and stores the Alloy configuration in a ConfigMap.

### Required Values

| Parameter | Description | Example |
|-----------|-------------|---------|
| `config` | Alloy configuration in [Alloy syntax](https://grafana.com/docs/alloy/latest/reference/) | See example below |

### Optional Values

| Parameter | Description | Example | Default |
|-----------|-------------|---------|---------|
| `port` | HTTP server port | `12345` | `12345` |
| `env` | Environment variables stored as a secret and exposed via `envFrom` | See example below | `{}` |

### Features

- Grafana Alloy v1.16.1
- ConfigMap-based configuration with automatic pod restart on change
- ServiceAccount with cluster-wide read access for Kubernetes service discovery
- Optional environment variables stored in a Secret (e.g. for Grafana Cloud credentials)
- Liveness and readiness probes against `/-/ready`

### Example values.yaml

```yaml
port: 12345
env:
  GRAFANA_CLOUD_USERNAME: "12345"
  GRAFANA_CLOUD_API_KEY: "glc_xxx"
config: |
  logging {
    level = "info"
  }

  prometheus.remote_write "default" {
    endpoint {
      url = "https://prometheus-prod.grafana.net/api/prom/push"
      basic_auth {
        username = sys.env("GRAFANA_CLOUD_USERNAME")
        password = sys.env("GRAFANA_CLOUD_API_KEY")
      }
    }
  }

  discovery.kubernetes "pods" {
    role = "pod"
  }

  prometheus.scrape "pods" {
    targets    = discovery.kubernetes.pods.targets
    forward_to = [prometheus.remote_write.default.receiver]
  }
```

---

## Common Features

### Monitoring

All charts include:
- ServiceMonitor resources for Prometheus integration
- Metrics endpoints properly configured
- Health check probes (where applicable)

### Security

- Secrets management for sensitive data
- Azure Workload Identity support (node_app, spring_app)
- Service accounts with proper permissions

### Routing

- Traefik IngressRoute resources
- Support for path-based and host-based routing
- Configurable entry points

### Resource Management

- Sensible resource requests and limits
- Configurable deployment parameters
- Liveness and startup probes

---

## Usage

### Installing a Chart

```bash
helm install my-release ./charts/spring_app -f my-values.yaml
```

### Upgrading a Release

```bash
helm upgrade my-release ./charts/spring_app -f my-values.yaml
```

### Uninstalling a Release

```bash
helm uninstall my-release
```

---
