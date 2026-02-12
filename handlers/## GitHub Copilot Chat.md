## GitHub Copilot Chat

- Extension: 0.37.1 (prod)
- VS Code: 1.110.0-insider (c308cc9f87e1427a73c5e32c81a1cfe9b1b203d1)
- OS: win32 10.0.26100 x64
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
- DNS ipv4 Lookup: 140.82.121.6 (4 ms)
- DNS ipv6 Lookup: Error (6 ms): getaddrinfo ENOTFOUND api.github.com
- Proxy URL: None (2 ms)
- Electron fetch (configured): HTTP 200 (52 ms)
- Node.js https: HTTP 200 (306 ms)
- Node.js fetch: HTTP 200 (59 ms)

Connecting to https://api.githubcopilot.com/_ping:
- DNS ipv4 Lookup: 140.82.114.22 (67 ms)
- DNS ipv6 Lookup: Error (8 ms): getaddrinfo ENOTFOUND api.githubcopilot.com
- Proxy URL: None (1 ms)
- Electron fetch (configured): HTTP 200 (673 ms)
- Node.js https: HTTP 200 (559 ms)
- Node.js fetch: HTTP 200 (544 ms)

Connecting to https://copilot-proxy.githubusercontent.com/_ping:
- DNS ipv4 Lookup: 4.225.11.192 (31 ms)
- DNS ipv6 Lookup: Error (27 ms): getaddrinfo ENOTFOUND copilot-proxy.githubusercontent.com
- Proxy URL: None (23 ms)
- Electron fetch (configured): HTTP 200 (150 ms)
- Node.js https: HTTP 200 (228 ms)
- Node.js fetch: HTTP 200 (249 ms)

Connecting to https://mobile.events.data.microsoft.com: HTTP 404 (157 ms)
Connecting to https://dc.services.visualstudio.com: HTTP 404 (302 ms)
Connecting to https://copilot-telemetry.githubusercontent.com/_ping: HTTP 200 (785 ms)
Connecting to https://copilot-telemetry.githubusercontent.com/_ping: HTTP 200 (527 ms)
Connecting to https://default.exp-tas.com: HTTP 400 (372 ms)

Number of system certificates: 699

## Documentation

In corporate networks: [Troubleshooting firewall settings for GitHub Copilot](https://docs.github.com/en/copilot/troubleshooting-github-copilot/troubleshooting-firewall-settings-for-github-copilot).