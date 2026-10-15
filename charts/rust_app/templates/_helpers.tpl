{{- define "rust-app.serviceAccountName" -}}
{{- default .Release.Name .Values.serviceAccountName -}}
{{- end -}}
