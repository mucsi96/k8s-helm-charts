{{- define "forwardauth.cookieName" -}}
{{- default (printf "__Host-%s" .Release.Name) .Values.global.forwardAuth.cookieName -}}
{{- end -}}

{{- define "forwardauth.proxyName" -}}
{{- include "oauth2-proxy.fullname" (index .Subcharts "oauth2-proxy") -}}
{{- end -}}

{{- define "forwardauth.bootstrapConfig" -}}
{{- $routes := list -}}
{{- $paths := dict -}}
{{- range .Values.bootstrapRoutes -}}
{{- if hasKey $paths .path -}}{{- fail "bootstrapRoutes paths must be unique" -}}{{- end -}}
{{- $_ := set $paths .path true -}}
{{- $routes = append $routes (dict "path" .path "upstream" (printf "http://%s.%s.svc.cluster.local:%v%s" .service $.Release.Namespace .port .path)) -}}
{{- end -}}
{{- range .Values.excludedRoutes -}}
{{- if and (eq .method "GET") (hasKey $paths .path) -}}{{- fail "bootstrapRoutes must not overlap GET excludedRoutes" -}}{{- end -}}
{{- end -}}
{{- $headers := list -}}
{{- if eq .Values.global.forwardAuth.mode "api-token" -}}{{- $headers = list "Authorization" -}}
{{- else if eq .Values.global.forwardAuth.mode "email-header" -}}{{- $headers = list "X-Auth-Request-Email" -}}{{- end -}}
{{- dict "proxy_root_url" (printf "http://%s.%s.svc.cluster.local:80/" (include "forwardauth.proxyName" .) .Release.Namespace) "public_origin" (printf "https://%s" .Values.global.forwardAuth.host) "identity_headers" $headers "routes" $routes | toJson -}}
{{- end -}}

{{- define "forwardauth.routeFilters" -}}
{{- $request := dict "type" "RequestHeaderModifier" "requestHeaderModifier" (dict "remove" (list "Authorization" "X-Auth-Request-Email" "X-Auth-Request-Access-Token" "X-Auth-Request-User" "X-Forwarded-User" "X-Forwarded-Email")) -}}
{{- $auth := dict "type" "ExtensionRef" "extensionRef" (dict "group" "traefik.io" "kind" "Middleware" "name" (printf "%s-%s" .root.Release.Name .target)) -}}
{{- $cacheControl := ternary "no-store" "private, no-cache" (eq .target "api") -}}
{{- $response := dict "type" "ResponseHeaderModifier" "responseHeaderModifier" (dict "set" (list (dict "name" "Cache-Control" "value" $cacheControl)) "remove" (list "Authorization" "X-Auth-Request-Access-Token")) -}}
{{- list $request $auth $response | toJson -}}
{{- end -}}

{{- define "forwardauth.legacyConfig" -}}
{{- $auth := .Values.global.forwardAuth -}}
email_domains = ["*"]
cookie_name = {{ include "forwardauth.cookieName" . | quote }}
cookie_secure = true
cookie_httponly = true
cookie_samesite = "lax"
cookie_path = "/"
cookie_refresh = {{ $auth.cookieRefresh | quote }}
cookie_expire = {{ $auth.cookieExpire | quote }}
reverse_proxy = true
trusted_proxy_ips = {{ $auth.trustedProxyCIDRs | toJson }}
skip_provider_button = true
redirect_url = {{ printf "https://%s/oauth2/callback" $auth.host | quote }}
whitelist_domains = [{{ $auth.host | quote }}]
skip_jwt_bearer_tokens = false
request_logging = false
{{- end -}}

{{- define "forwardauth.alphaConfig" -}}
{{- $auth := .Values.global.forwardAuth -}}
providers:
  - id: entra
    provider: oidc
    clientID: ${OAUTH2_PROXY_CLIENT_ID}
    clientSecret: ${OAUTH2_PROXY_CLIENT_SECRET}
    scope: {{ printf "openid profile email offline_access%s" (ternary (printf " %s" $auth.apiScope) "" (eq $auth.mode "api-token")) | quote }}
    code_challenge_method: S256
    additionalClaims: [name]
    oidcConfig:
      issuerURL: {{ $auth.issuerURL | quote }}
      emailClaim: {{ ternary "email" "preferred_username" (eq $auth.mode "email-header") }}
      userIDClaim: sub
      audienceClaims: [aud]
      insecureSkipNonce: false
{{ if ne $auth.mode "login-gate" }}
injectResponseHeaders:
  - name: {{ ternary "Authorization" "X-Auth-Request-Email" (eq $auth.mode "api-token") }}
    values:
      - claimSource:
          claim: {{ ternary "access_token" "email" (eq $auth.mode "api-token") }}
{{ if eq $auth.mode "api-token" }}
          prefix: "Bearer "
{{ end }}
{{ end }}
upstreamConfig:
  upstreams:
    - id: forwardauth
      path: /
      static: true
      staticCode: 202
{{- end -}}
