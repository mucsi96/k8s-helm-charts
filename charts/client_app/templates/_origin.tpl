{{- define "client.origin" -}}
{{- if .Values.staticOrigin -}}
group: traefik.io
kind: TraefikService
name: {{ .Release.Name }}-origin
{{- else -}}
name: {{ .Release.Name }}
port: {{ required "appPort value is required!" .Values.appPort }}
{{- end -}}
{{- end -}}
