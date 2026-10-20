{{/* Called with {root: application chart context, target: document|api}. */}}
{{- define "p07.auth.middleware" -}}
{{- $root := .root -}}
{{- $target := .target -}}
{{- if ne $root.Values.auth nil -}}
{{- $auth := $root.Values.auth -}}
{{- $service := required "auth.proxyService is required" $auth.proxyService -}}
{{- $port := 80 -}}
{{- if hasKey $auth "proxyPort" -}}{{- $port = $auth.proxyPort -}}{{- end -}}
{{- $mode := $auth.mode | default "api-token" -}}
{{- if or (not (regexMatch "^[a-z0-9]([-a-z0-9]*[a-z0-9])?$" $service)) (gt (len $service) 63) -}}
{{- fail "auth.proxyService must be a same-namespace Service name" -}}
{{- end -}}
{{- if hasKey $auth "cookieName" -}}
{{- fail "auth.cookieName is not configurable; all app hosts use __Host-session" -}}
{{- end -}}
{{- if or (lt (int $port) 1) (gt (int $port) 65535) (ne (float64 $port) (float64 (int $port))) -}}
{{- fail "auth.proxyPort must be an integer between 1 and 65535" -}}
{{- end -}}
{{- if not (has $mode (list "api-token" "email-header" "login-gate")) -}}
{{- fail "auth.mode must match a supported proxy mode" -}}
{{- end -}}
{{- if $root.Values.routeFilters -}}{{- fail "Use auth or routeFilters, not both" -}}{{- end }}
apiVersion: traefik.io/v1alpha1
kind: Middleware
metadata:
  name: {{ $root.Release.Name }}-auth
  namespace: {{ $root.Release.Namespace }}
spec:
  forwardAuth:
    address: {{ printf "http://%s.%s.svc.cluster.local:%v%s" $service $root.Release.Namespace $port (ternary "/oauth2/auth" "/" (eq $target "api")) | quote }}
    trustForwardHeader: false
    forwardBody: false
    preserveLocationHeader: true
    maxResponseBodySize: 65536
    authRequestHeaders: [Cookie, Accept, Origin, X-Requested-With, Sec-WebSocket-Key]
    authResponseHeaders: {{ if and (eq $target "api") (eq $mode "api-token") }}[Authorization]{{ else if and (eq $target "api") (eq $mode "email-header") }}[X-Auth-Request-Email]{{ else }}[]{{ end }}
    addAuthCookiesToResponse: [__Host-session, __Host-session_csrf]
{{- end -}}
{{- end -}}

{{/* Shared request identity stripping and reference to the app-owned middleware. */}}
{{- define "p07.auth.requestFilters" -}}
- type: RequestHeaderModifier
  requestHeaderModifier:
    remove: [Authorization, X-Auth-Request-Email, X-Auth-Request-Access-Token, X-Auth-Request-User, X-Forwarded-User, X-Forwarded-Email]
- type: ExtensionRef
  extensionRef:
    group: traefik.io
    kind: Middleware
    name: {{ .Release.Name }}-auth
{{- end -}}

{{- define "p07.auth.apiFilters" -}}
- type: ResponseHeaderModifier
  responseHeaderModifier:
    set: [{name: Cache-Control, value: no-store}]
    remove: [Authorization, X-Auth-Request-Access-Token]
{{ include "p07.auth.requestFilters" . }}
{{- end -}}
