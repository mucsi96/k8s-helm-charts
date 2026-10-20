{{- define "p07.api.route" -}}
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: {{ .Release.Name }}-route
  namespace: {{ .Release.Namespace }}
  labels:
    app: {{ .Release.Name }}
spec:
  parentRefs:
    - name: traefik
      namespace: traefik
      sectionName: websecure
  hostnames:
    - {{ required "host value is required!" .Values.host | quote }}
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: {{ .Values.basePath | default "/" | quote }}
      {{- if ne .Values.auth nil }}
      filters:
        {{- include "p07.auth.apiFilters" . | nindent 8 }}
      {{- end }}
      backendRefs:
        - name: {{ .Release.Name }}
          port: {{ required "appPort value is required!" .Values.appPort }}
{{- end -}}
