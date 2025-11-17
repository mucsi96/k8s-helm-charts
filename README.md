# k8s-helm-charts

Helm charts for application deployments in Kubernetes

## Overview

This repository contains reusable Helm charts for deploying various types of applications and databases in Kubernetes clusters. Each chart is designed with best practices and includes support for monitoring, secrets management, and routing.

## Available Charts

- [client_app](#client_app) - Static frontend applications (nginx-based)
- [node_app](#node_app) - Node.js backend applications
- [spring_app](#spring_app) - Spring Boot Java applications
- [postgres_db](#postgres_db) - PostgreSQL database with monitoring

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
| `persistentVolumeClaims` | Array of existing PVCs to mount | See example below | `[]` |

### Config File Structure

Each config file entry supports:

| Field | Description | Required |
|-------|-------------|----------|
| `name` | File name | Yes |
| `mountPath` | Full path where the file should be mounted | Yes |
| `data` | Base64-encoded file contents | Yes |

### Persistent Volume Claim Structure

**Note:** PersistentVolumeClaims must be created and managed outside of this Helm chart. This chart only mounts existing PVCs.

Each PVC entry supports:

| Field | Description | Required | Example |
|-------|-------------|----------|---------|
| `name` | Name of the existing PVC to mount | Yes | `my-app-data-pvc` |
| `mountPath` | Mount path in the container | Yes | `/data` |

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

# Reference existing PVCs that are managed outside Helm
persistentVolumeClaims:
  - name: my-app-data-pvc
    mountPath: /data
  - name: my-app-logs-pvc
    mountPath: /var/log/app
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
| `existingPersistentVolumeClaimName` | Name of existing PVC for database storage | `postgres-data-pvc` |

### Optional Values

| Parameter | Description | Example | Default |
|-----------|-------------|---------|---------|
| `initSql` | SQL script to run on database initialization | `CREATE TABLE users (id SERIAL);` | `""` |

### Features

- PostgreSQL 17.6 with persistent storage
- Prometheus metrics exporter for monitoring
- Automatic database initialization with custom SQL
- Automatic creation of exporter user with `pg_monitor` role
- Service monitor for Prometheus integration

**Note:** The PersistentVolumeClaim must be created and managed outside of this Helm chart. The chart references an existing PVC via `existingPersistentVolumeClaimName`.

### Example values.yaml

```yaml
name: myappdb
port: 5432
metricsPort: 8085
username: myuser
password: securepassword123
exporterUsername: exporter
exporterPassword: exporterpass456
existingPersistentVolumeClaimName: postgres-data-pvc
initSql: |
  CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
  );
  CREATE INDEX idx_username ON users(username);
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
