import re
import subprocess
import json
import requests
import socket
import dns.resolver

def is_ip_address(value):
    """Check if the given value is a valid IP address (IPv4 or IPv6)."""
    try:
        # Try to resolve the address as either IPv4 or IPv6
        socket.inet_pton(socket.AF_INET, value)  # Check if it's IPv4
        return True
    except socket.error:
        pass
    
    try:
        socket.inet_pton(socket.AF_INET6, value)  # Check if it's IPv6
        return True
    except socket.error:
        pass
    
    return False

def check_dns_server(server_ip, port=53, timeout=3):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((server_ip, port))
        sock.close()
        return True, f"Successfully connected to DNS server {server_ip}:{port}\n"
    except Exception as e:
        return False, f"Failed to connect to DNS server {server_ip}:{port}\n"

def resolve_dns_name(domain_name, server_ip=None):
    resolver = dns.resolver.Resolver()
    if server_ip:
        resolver.nameservers = [server_ip]
    try:
        answer = resolver.resolve(domain_name)
        return True, f"Resolved {domain_name} to {[rdata.address for rdata in answer]}" 
    except Exception as e:
        msg = ""
        for server in resolver.nameservers:
            _, info = check_dns_server(server)
            msg += info
        return False, f"Failed to resolve {domain_name}, the following dns servers are tested:\n" + msg

def gateway_ping_test():
    """Find the default gateway and ping it"""
    try:
        # Get the default gateway IP
        route_output = subprocess.check_output(["ip", "route"], universal_newlines=True)
        match = re.search(r"default via (\S+)", route_output)

        if match:
            gateway_ip = match.group(1)
            ok, info = ping_test(gateway_ip)
            if not ok:
                arp_output = subprocess.check_output(["ip", "neigh"], universal_newlines=True)
                if gateway_ip in arp_output:
                    msg = f"Gateway {gateway_ip} is present in the ARP table, but ping failed"
                else:
                    msg = f"Gateway {gateway_ip} not found in the ARP table."
            else:
                msg = info
            return ok, msg
        else:
            return False, "Default gateway not found."

    except subprocess.CalledProcessError as e:
        return False, f"Failed to retrieve default gateway: {e.output}"

def ping_test(host):
    if not is_ip_address(host):
        ok, msg = resolve_dns_name(host)
        if not ok: 
            return False, msg
    try:
        output = subprocess.check_output(["ping", "-c", "4", host], universal_newlines=True)
        return True, f"Ping successful:\n{output}"
    except subprocess.CalledProcessError as e:
        return False, f"Ping failed:\n{e.output}"

def ask_llama_for_action(user_message):
    system_prompt = (
        "You're a system diagnostics assistant. Decide which function to run based on user input.\n"
        "Respond ONLY in JSON format: {\"function\": \"<function_name>\", \"args\": {\"arg1\": \"value\"}}\n"
        "Available functions:\n"
        " - ping_test(host: str): Check if a host is reachable.\n"
        " - gateway_ping_test(): Check if the system's default gateway is reachable.\n"
    )

    prompt = f"{system_prompt}\nUser: {user_message}"

    response = requests.post("http://localhost:11434/api/generate", json={
        "model": "llama3.2",
        "prompt": prompt,
        "stream": False
    })

    return response.json()["response"]

def handle_user_request(user_message):
    llama_response = ask_llama_for_action(user_message)
    print(f"LLM decided: {llama_response}")

    try:
        decision = json.loads(llama_response)
        func_name = decision["function"]
        args = decision["args"]

        if func_name == "ping_test":
            _, msg = ping_test(**args)
        elif func_name == "gateway_ping_test":
            _, msg = gateway_ping_test()
        else:
            msg = f"Function '{func_name}' is not implemented."

    except Exception as e:
        msg = f"Error processing request: {str(e)}"

    return msg

while True:
    user_input = input("You: ")
    result = handle_user_request(user_input)
    print(f"Assistant: {result}")

