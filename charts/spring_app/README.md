# Spring App Helm Chart

A Helm chart for deploying Spring Boot Java applications with Actuator support.

## Installation

```bash
helm repo add mucsi96 https://mucsi96.github.io/k8s-helm-charts
helm repo update
helm install my-spring-app mucsi96/spring-app
```

## Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `appPort` | Port the application listens on | `8080` |
| `springActuatorPort` | Spring Actuator management port | `8082` |
| `persistentVolumeClaims` | List of PVC configurations | `[]` |
| `resources.requests.memory` | Memory request | `300Mi` |
| `resources.requests.cpu` | CPU request | `20m` |
| `resources.limits.memory` | Memory limit | `500Mi` |
| `resources.limits.cpu` | CPU limit | `500m` |
