{{- define "p07.client.runtimeConfig" -}}
{{- if .Values.runtimeConfig }}
apiVersion: traefik.io/v1alpha1
kind: Middleware
metadata:
  name: {{ .Release.Name }}-index-config
  namespace: {{ .Release.Namespace }}
spec:
  plugin:
    rewritebody:
      rewrites:
        - regex: "[\"']__APP_CONFIG_JSON__[\"']"
          replacement: {{ .Values.runtimeConfig | toJson | replace "$" "$$" | quote }}
{{- end }}
{{- end }}
