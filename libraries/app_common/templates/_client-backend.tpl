{{- define "p07.client.backend" -}}
{{- if .external -}}
group: traefik.io
kind: TraefikService
name: {{ .root.Release.Name }}-origin
{{- else -}}
name: {{ .root.Release.Name }}
port: {{ required "appPort value is required!" .root.Values.appPort }}
{{- end -}}
{{- end -}}
