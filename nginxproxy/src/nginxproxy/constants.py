"""Shared constants for the nginxproxy MCP server."""

NAMESPACE = "nginxproxy"

INSTRUCTIONS = """\
Manage a Nginx Proxy Manager instance (https://nginxproxymanager.com) through its REST API.

All tools, prompts, and resources are namespaced with `nginxproxy`.
Tool names look like `nginxproxy_create_service`.
Resource URIs look like `npm://nginxproxy/proxy-hosts`.

When the user asks to expose a LAN service with a domain and a custom/wildcard certificate, call `nginxproxy_create_service`.
Example: "帮我创建一个服务 10.0.0.10 8080 端口，启用自定义证书，域名为 app.home.com"
→ nginxproxy_create_service(domain="app.home.com", ip="10.0.0.10", port=8080, use_custom_certificate=true)

That tool looks up an already-uploaded custom certificate (provider=other), matches *.home.com style SANs, attaches it, and forces HTTPS.
Do not issue Let's Encrypt for this workflow.

For low-level edits use nginxproxy_list_proxy_hosts / nginxproxy_create_proxy_host / nginxproxy_update_proxy_host.
"""
