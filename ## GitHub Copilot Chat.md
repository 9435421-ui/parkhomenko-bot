## GitHub Copilot Chat

- Extension: 0.40.2026031004 (prod)
- VS Code: 1.111.0-insider (ce099c1ed25d9eb3076c11e4a280f3eb52b4fbeb)
- OS: linux 6.8.0-101-generic x64
- Remote Name: ssh-remote
- Extension Kind: Workspace
- GitHub Account: 9435421-ui

## Network

User Settings:
```json
  "http.systemCertificatesNode": true,
  "github.copilot.advanced.debug.useElectronFetcher": true,
  "github.copilot.advanced.debug.useNodeFetcher": false,
  "github.copilot.advanced.debug.useNodeFetchFetcher": true
```

Connecting to https://api.github.com:
- DNS ipv4 Lookup: 140.82.121.5 (1 ms)
- DNS ipv6 Lookup: Error (21 ms): getaddrinfo ENOTFOUND api.github.com
- Proxy URL: None (11 ms)
- Electron fetch: Unavailable
- Node.js https: HTTP 200 (157 ms)
- Node.js fetch (configured): HTTP 200 (42 ms)

Connecting to https://api.githubcopilot.com/_ping:
- DNS ipv4 Lookup: 140.82.113.22 (2 ms)
- DNS ipv6 Lookup: Error (10 ms): getaddrinfo ENOTFOUND api.githubcopilot.com
- Proxy URL: None (0 ms)
- Electron fetch: Unavailable
- Node.js https: HTTP 200 (423 ms)
- Node.js fetch (configured): HTTP 200 (440 ms)

Connecting to https://copilot-proxy.githubusercontent.com/_ping:
- DNS ipv4 Lookup: 20.199.39.224 (49 ms)
- DNS ipv6 Lookup: Error (24 ms): getaddrinfo ENOTFOUND copilot-proxy.githubusercontent.com
- Proxy URL: None (0 ms)
- Electron fetch: Unavailable
- Node.js https: HTTP 200 (772 ms)
- Node.js fetch (configured): HTTP 200 (768 ms)

Connecting to https://mobile.events.data.microsoft.com: HTTP 404 (64 ms)
Connecting to https://dc.services.visualstudio.com: HTTP 404 (379 ms)
Connecting to https://copilot-telemetry.githubusercontent.com/_ping: HTTP 200 (437 ms)
Connecting to https://copilot-telemetry.githubusercontent.com/_ping: HTTP 200 (438 ms)
Connecting to https://default.exp-tas.com: HTTP 400 (249 ms)

Number of system certificates: 434

## Documentation

In corporate networks: [Troubleshooting firewall settings for GitHub Copilot](https://docs.github.com/en/copilot/troubleshooting-github-copilot/troubleshooting-firewall-settings-for-github-copilot).