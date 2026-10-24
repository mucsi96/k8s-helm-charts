{{/* Called with {root: chart context, external: bool}. Both client charts use this route. */}}
{{- define "app-common.client.route" -}}
{{- $external := .external | default false -}}
{{- $originHost := .originHost -}}
{{- with .root -}}
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: {{ .Release.Name }}-route
  namespace: {{ .Release.Namespace }}
  labels:
    app: {{ .Release.Name }}
spec:
  parentRefs:
    - name: {{ .Values.gateway.name }}
      namespace: {{ .Values.gateway.namespace }}
      sectionName: {{ .Values.gateway.sectionName }}
  hostnames:
    - {{ required "host value is required!" .Values.host | quote }}
  rules:
    - matches:
      {{- range $method := list "GET" "HEAD" }}
      {{- range $path := list "/" "/index.html" }}
        - path:
            type: Exact
            value: {{ $path | quote }}
          method: {{ $method }}
      {{- end }}
        - path:
            type: PathPrefix
            value: /
          method: {{ $method }}
          headers:
            - name: Sec-Fetch-Dest
              type: Exact
              value: document
        - path:
            type: PathPrefix
            value: /
          method: {{ $method }}
          headers:
            - name: Accept
              type: RegularExpression
              value: '(?i)(^|[ ,])text/html([ ;,]|$)'
      {{- end }}
      filters:
        - type: ResponseHeaderModifier
          responseHeaderModifier:
            set:
              - name: Cache-Control
                value: private, no-cache, no-store
            remove: [Authorization, X-Auth-Request-Access-Token, ETag, Last-Modified]
      {{- if ne .Values.auth nil }}
        {{- include "app-common.auth.requestFilters" . | nindent 8 }}
      {{- end }}
      {{- if .Values.runtimeConfig }}
        - type: ExtensionRef
          extensionRef:
            group: traefik.io
            kind: Middleware
            name: {{ .Release.Name }}-index-config
      {{- end }}
        - type: URLRewrite
          urlRewrite:
            {{- if $external }}
            hostname: {{ required "origin hostname is required" $originHost | quote }}
            {{- end }}
            path:
              type: ReplaceFullPath
              replaceFullPath: /index.html
      {{- if $external }}
        - type: ExtensionRef
          extensionRef:
            group: traefik.io
            kind: Middleware
            name: {{ .Release.Name }}-origin-headers
      {{- end }}
      backendRefs:
        - {{ include "app-common.client.backend" (dict "root" . "external" $external) | nindent 10 | trim }}
        {{- if not $external }}
          filters:
            - type: RequestHeaderModifier
              requestHeaderModifier:
                remove: [Authorization, Cookie, X-XSRF-TOKEN, X-Auth-Request-Email, X-Auth-Request-Access-Token, X-Auth-Request-User, X-Forwarded-User, X-Forwarded-Email, If-None-Match, If-Modified-Since, Range, If-Range]
                set:
                  - name: Accept-Encoding
                    value: identity
        {{- end }}
    {{- if not $external }}
    - matches:
        - path:
            type: PathPrefix
            value: /
      filters:
        - type: RequestHeaderModifier
          requestHeaderModifier:
            remove: [Authorization, Cookie, X-XSRF-TOKEN, X-Auth-Request-Email, X-Auth-Request-Access-Token, X-Auth-Request-User, X-Forwarded-User, X-Forwarded-Email]
        - type: ResponseHeaderModifier
          responseHeaderModifier:
            remove: [Authorization, X-Auth-Request-Access-Token]
      backendRefs:
        - {{ include "app-common.client.backend" (dict "root" . "external" $external) | nindent 10 | trim }}
    {{- end }}
{{- end -}}
{{- end -}}
