#!/usr/bin/env python3
import json
import os
import ssl
import sys
import time
import urllib.request
import urllib.error

BASE = "http://portainer:9000"
ADMIN_PASSWORD = os.environ["PORTAINER_ADMIN_PASSWORD"]
ENDPOINTS_FILE = os.environ.get("PORTAINER_ENDPOINTS_FILE", "/endpoints.json")


def load_endpoints():
    try:
        with open(ENDPOINTS_FILE) as f:
            endpoints = json.load(f)
    except FileNotFoundError:
        sys.exit(f"Endpoints file not found: {ENDPOINTS_FILE}")
    except json.JSONDecodeError as e:
        sys.exit(f"Invalid JSON in {ENDPOINTS_FILE}: {e}")

    errors = [
        f"  [{i}] missing '{key}'"
        for i, ep in enumerate(endpoints)
        for key in ("name", "url")
        if key not in ep
    ]
    if errors:
        sys.exit("Endpoint config errors:\n" + "\n".join(errors))

    return endpoints


def encode_multipart(fields):
    boundary = "PortainerInitBoundary"
    parts = [
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{key}"\r\n'
            f"\r\n"
            f"{value}"
        ).encode()
        for key, value in fields.items()
    ]
    body = b"\r\n".join(parts) + f"\r\n--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


def api(method, path, *, data=None, token=None, form=None):
    headers = {}
    body = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    elif form is not None:
        body, headers["Content-Type"] = encode_multipart(form)

    req = urllib.request.Request(f"{BASE}{path}", data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def wait_for_portainer():
    print("Waiting for Portainer to be ready...")
    while True:
        try:
            urllib.request.urlopen(f"{BASE}/api/status")
            return
        except Exception:
            time.sleep(2)


def init_admin():
    code, body = api("POST", "/api/users/admin/init", data={
        "Username": "admin",
        "Password": ADMIN_PASSWORD,
    })
    if code not in (200, 409):
        sys.exit(f"Admin init failed with HTTP {code}: {body}")


def get_token():
    code, body = api("POST", "/api/auth", data={
        "username": "admin",
        "password": ADMIN_PASSWORD,
    })
    if code != 200:
        sys.exit(f"Authentication failed with HTTP {code}: {body}")
    return body["jwt"]


def check_agent_reachable(name, url):
    print(f"[{name}] Checking agent reachability at {url}...")
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        urllib.request.urlopen(f"https://{url}/ping", context=ctx)
    except urllib.error.HTTPError:
        pass  # Agent responded — reachable
    except Exception as e:
        print(
            f"[{name}] WARNING: agent not reachable at https://{url}/ping: {e}\n"
            "  If using an mDNS hostname (e.g. jetson.local), set a routable IP:9001 instead."
        )
        return False
    return True


def get_existing_endpoint_names(token):
    _, endpoints = api("GET", "/api/endpoints", token=token)
    if not isinstance(endpoints, list):
        return set()
    return {e.get("Name") for e in endpoints}


def create_endpoint(token, name, url):
    code, body = api("POST", "/api/endpoints", token=token, form={
        "Name": name,
        "EndpointCreationType": "2",
        "ContainerEngine": "docker",
        "URL": f"tcp://{url}",
        "TLS": "true",
        "TLSSkipVerify": "true",
        "TLSSkipClientVerify": "true",
    })
    if code not in (200, 201):
        msg = f"[{name}] Endpoint creation failed with HTTP {code}: {body}"
        if "already paired" in str(body).lower():
            msg += (
                "\n\nRemediation:"
                "\n1) Stop any old Portainer server still connected to this agent."
                "\n2) Restart the portainer_agent container on the device to clear in-memory pairing."
                "\n3) Re-run this stack to pair with the current Portainer instance."
                "\n\nIf you need multiple Portainer servers to access the same agent, "
                "set AGENT_SECRET on both the Portainer server and the agent."
            )
        return False, msg
    return True, None


def main():
    endpoints = load_endpoints()
    wait_for_portainer()
    init_admin()
    token = get_token()

    existing = get_existing_endpoint_names(token)
    failures = []

    for ep in endpoints:
        name, url = ep["name"], ep["url"]
        if name in existing:
            print(f"[{name}] Already exists, skipping.")
            continue
        if not check_agent_reachable(name, url):
            failures.append(f"[{name}] Skipped — agent unreachable at {url}")
            continue
        ok, err = create_endpoint(token, name, url)
        if ok:
            print(f"[{name}] Endpoint added.")
        else:
            failures.append(err)

    if failures:
        print("\nThe following endpoints could not be registered:")
        for msg in failures:
            print(f"  {msg}")
        sys.exit(1)


if __name__ == "__main__":
    main()
