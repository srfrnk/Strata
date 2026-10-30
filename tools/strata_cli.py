#!/usr/bin/env python3
"""Unified CLI and switcher for Strata and connected coding agents (Crush, Goose, Pi, Hermes)."""

import argparse
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
import json
from pathlib import Path

STRATA_DIR = Path("/mnt/data/code/Strata")
CONTAINER_NAME = "strata"
IMAGE_NAME = "strata"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
DEFAULT_BASE_URL = f"http://{DEFAULT_HOST}:{DEFAULT_PORT}/v1"
VRAM_RESERVE_MIB = 2048
CONFIG_IN_VOLUME = "/data/config/strata-coder-iq1_m.json"


def get_base_url():
    port = os.environ.get("STRATA_PORT", str(DEFAULT_PORT))
    host = os.environ.get("STRATA_HOST", DEFAULT_HOST)
    return f"http://{host}:{port}/v1"


def get_root_url():
    port = os.environ.get("STRATA_PORT", str(DEFAULT_PORT))
    host = os.environ.get("STRATA_HOST", DEFAULT_HOST)
    return f"http://{host}:{port}"


def is_container_running():
    try:
        out = subprocess.check_output(
            ["docker", "ps", "-q", "-f", f"name=^/{CONTAINER_NAME}$"],
            text=True
        ).strip()
        return bool(out)
    except Exception:
        return False


def is_image_available():
    try:
        out = subprocess.check_output(
            ["docker", "images", "-q", IMAGE_NAME],
            text=True
        ).strip()
        return bool(out)
    except Exception:
        return False


def get_gpu_cuda_arch():
    try:
        cap = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=compute_cap", "--format=csv,noheader"],
            text=True
        ).strip().split("\n")[0]
        # E.g. '8.6' -> '86'
        arch = cap.replace(".", "")
        if arch.isdigit():
            return arch
    except Exception:
        pass
    return "86"


def build_image_if_needed():
    if is_image_available():
        return True

    print(f"[Strata Setup] Docker image '{IMAGE_NAME}' not found.")
    arch = get_gpu_cuda_arch()
    print(f"[Strata Setup] Building Docker image '{IMAGE_NAME}' with CUDA_ARCHITECTURES={arch}...")
    print("[Strata Setup] Note: This may take several minutes on the first run while the C++ engine compiles.")

    build_cmd = [
        "docker", "build", "-t", IMAGE_NAME,
        "--build-arg", f"CUDA_ARCHITECTURES={arch}",
        str(STRATA_DIR)
    ]
    try:
        subprocess.check_call(build_cmd)
        print(f"[Strata Setup] Docker image '{IMAGE_NAME}' built successfully.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[Strata Setup] Error building Docker image: {e}")
        return False


def patch_vram_if_needed():
    """Ensure /data/config/strata-coder-iq1_m.json inside strata-data has the 2048 MiB reserve."""
    try:
        check_script = f"""
if [ -f {CONFIG_IN_VOLUME} ]; then
    grep -q '"2048"' {CONFIG_IN_VOLUME} && echo "ALREADY_PATCHED" || echo "NEEDS_PATCH"
else
    echo "NO_CONFIG_YET"
fi
"""
        res = subprocess.check_output(
            ["docker", "run", "--rm", "-v", "strata-data:/data", "alpine", "sh", "-c", check_script],
            text=True
        ).strip()

        if res == "NEEDS_PATCH":
            print(f"[Strata Setup] Applying VRAM reservation patch ({VRAM_RESERVE_MIB} MiB) to strata-data volume...")
            patch_script = f"""
apk add --no-cache jq >/dev/null 2>&1
jq '.args += ["--vram-reserve-mib", "{VRAM_RESERVE_MIB}"]' {CONFIG_IN_VOLUME} > /tmp/patched.json
mv /tmp/patched.json {CONFIG_IN_VOLUME}
"""
            subprocess.check_call(
                ["docker", "run", "--rm", "-v", "strata-data:/data", "alpine", "sh", "-c", patch_script]
            )
            print("[Strata Setup] VRAM reservation patch applied successfully.")
    except Exception as e:
        # Non-fatal if config doesn't exist yet or alpine fails
        print(f"[Strata Setup] Note: VRAM patch check skipped ({e})")


def http_status(path, timeout_s=2):
    """The status code of a GET on the service, or None when the service is not reachable."""
    try:
        req = urllib.request.Request(f"{get_root_url()}{path}", headers={"User-Agent": "strata-cli"})
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return None


def enable_api_monitor():
    """api_monitor=true in the run config on the strata-data volume; the server reads it when it starts."""
    script = f"""
if [ ! -f {CONFIG_IN_VOLUME} ]; then echo MISSING; exit 1; fi
apk add --no-cache jq >/dev/null 2>&1
jq '.api_monitor = true' {CONFIG_IN_VOLUME} > /tmp/monitor_on.json || exit 1
mv /tmp/monitor_on.json {CONFIG_IN_VOLUME}
"""
    try:
        subprocess.check_call(["docker", "run", "--rm", "-v", "strata-data:/data", "alpine", "sh", "-c", script],
                              text=True)
        print(f"api_monitor=true saved in {CONFIG_IN_VOLUME}; the monitor records from the next start on.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Could not update {CONFIG_IN_VOLUME}: {e}")
        return False


def is_service_ready(timeout_s=3):
    url = f"{get_base_url()}/models"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "strata-cli"})
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode())
                return True, data
    except Exception as e:
        return False, str(e)
    return False, "Unknown status"


def open_in_browser(target_url):
    print(f"Opening browser at: {target_url}")
    for opener in ["xdg-open", "sensible-browser", "google-chrome", "firefox"]:
        if subprocess.run(["which", opener], capture_output=True).returncode == 0:
            subprocess.Popen([opener, target_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return 0
    print(f"Please open {target_url} in your browser.")
    return 0


def cmd_build(args):
    arch = get_gpu_cuda_arch()
    print(f"Building Docker image '{IMAGE_NAME}' with CUDA_ARCHITECTURES={arch}...")
    cmd = [
        "docker", "build", "-t", IMAGE_NAME,
        "--build-arg", f"CUDA_ARCHITECTURES={arch}",
        str(STRATA_DIR)
    ]
    return subprocess.call(cmd)


def cmd_start(args):
    if is_container_running():
        print(f"Container '{CONTAINER_NAME}' is already running.")
        ready, _ = is_service_ready(timeout_s=2)
        if ready:
            print("Strata service is healthy and ready.")
        else:
            print("Waiting for Strata engine initialization...")
        return 0

    # 1. Build image if needed
    if not build_image_if_needed():
        return 1

    # 2. Patch VRAM reservation if needed
    patch_vram_if_needed()

    print(f"Starting Strata container '{CONTAINER_NAME}' in background...")
    cmd = [
        "docker", "run", "-d", "--rm", "--gpus", "all",
        "--name", CONTAINER_NAME,
        "-p", f"{DEFAULT_PORT}:8080",
        "--ulimit", "memlock=-1",
        "-v", "strata-data:/data",
        "-e", "FAMILY=coder",
        "-e", "MODEL=IQ1_M",
        "-e", "CONTEXT=131072",
        "-e", "KV=int8",
        "-e", "VISION=yes",
        "--stop-timeout", "60",
        IMAGE_NAME
    ]
    subprocess.check_call(cmd)
    print("Container started. Loading model weights into VRAM & RAM (this takes ~15-20s)...")

    # Monitor startup
    start_time = time.time()
    last_vram_log = 0
    for elapsed in range(1, 120):
        ready, data = is_service_ready(timeout_s=1)
        if ready:
            print(f"Strata service is ready! (Took {elapsed}s)")
            if isinstance(data, dict) and "data" in data:
                models = [m.get("id") for m in data["data"]]
                print(f"Available model(s): {', '.join(models)}")
            # Re-check patch in case it was a fresh setup.py initialization
            patch_vram_if_needed()
            return 0

        # Log progress periodically
        if elapsed - last_vram_log >= 5:
            last_vram_log = elapsed
            try:
                vram = subprocess.check_output(
                    ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader"],
                    text=True
                ).strip()
                print(f"  [Waiting {elapsed}s] Initializing weights... Current VRAM: {vram}")
            except Exception:
                print(f"  [Waiting {elapsed}s] Initializing weights...")

        time.sleep(1)

    print("Warning: Container started, but model service did not become ready within 120s.")
    print(f"Check logs with: docker logs {CONTAINER_NAME}")
    return 1


def cmd_stop(args):
    if not is_container_running():
        print(f"Container '{CONTAINER_NAME}' is not running.")
        return 0
    print(f"Stopping container '{CONTAINER_NAME}'...")
    subprocess.run(["docker", "stop", "-t", "60", CONTAINER_NAME])
    print("Stopped.")
    return 0


def cmd_restart(args):
    cmd_stop(args)
    return cmd_start(args)


def cmd_status(args):
    running = is_container_running()
    print(f"Container ({CONTAINER_NAME}): {'RUNNING' if running else 'STOPPED'}")

    # Check GPU VRAM
    try:
        smi = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.used,memory.total", "--format=csv,noheader"],
            text=True
        ).strip()
        print(f"GPU Status: {smi}")
    except Exception:
        pass

    # Check Endpoint
    ready, res = is_service_ready(timeout_s=2)
    if ready:
        print(f"Service API: READY at {get_base_url()}")
        if isinstance(res, dict) and "data" in res:
            models = [m.get("id") for m in res["data"]]
            print(f"Loaded Models: {', '.join(models)}")
    else:
        print(f"Service API: NOT REACHABLE ({res})")

    # Check Agents
    print("\nAgents Installed in PATH:")
    for agent in ["crush", "goose", "pi", "hermes"]:
        agent_path = subprocess.run(["which", agent], capture_output=True, text=True).stdout.strip()
        print(f"  - {agent}: {agent_path if agent_path else 'Not found'}")
    return 0


def cmd_open(args):
    port = os.environ.get("STRATA_PORT", str(DEFAULT_PORT))
    host = os.environ.get("STRATA_HOST", DEFAULT_HOST)
    return open_in_browser(f"http://{host}:{port}/")


def monitor_is_on():
    """True when the service answers 200 at /api-monitor, which it only does with the monitor on."""
    return http_status("/api-monitor") == 200


def turn_monitor_on(args):
    """The monitor saved in the run config and the service restarted with it; False when that failed."""
    if not enable_api_monitor():
        return False
    print("Restarting the service with the monitor on...")
    return cmd_restart(args) == 0


def cmd_monitor(args):
    """The chat page's Monitor tab (#monitor): there always, but it records only with the monitor on."""
    if http_status("/") is None:
        print("Strata service is not reachable. Run `strata start` first.")
        return 1
    if not monitor_is_on():
        if getattr(args, "enable", False):
            if not turn_monitor_on(args):
                return 1
        else:
            print("The API request monitor is off, so the #monitor tab shows no requests.")
            print("Run `strata monitor --enable` to turn it on (saves api_monitor=true in the run config and restarts).")
    return open_in_browser(f"{get_root_url()}/#monitor")


def cmd_api_monitor(args):
    """The standalone monitor page at /api-monitor, which the server only serves with the monitor on."""
    status = http_status("/api-monitor")
    if status is None:
        print("Strata service is not reachable. Run `strata start` first.")
        return 1
    if status != 200:
        if not getattr(args, "enable", False):
            print("The API request monitor is off, so /api-monitor answers 404: it keeps the last 100 requests'")
            print("prompts and answers in memory, and is opt-in. Run `strata api-monitor --enable` to turn it on")
            print("(saves api_monitor=true in the run config and restarts the service).")
            return 1
        if not turn_monitor_on(args):
            return 1
    return open_in_browser(f"{get_root_url()}/api-monitor")


def cmd_config(args):
    script = STRATA_DIR / "scripts" / "configure_agents.sh"
    if not script.exists():
        print(f"Error: {script} not found.")
        return 1
    return subprocess.call(["bash", str(script)])


def cmd_completion(args):
    shell = getattr(args, "shell", None)
    completions_dir = STRATA_DIR / "completions"

    if shell == "bash":
        bash_comp = completions_dir / "strata.bash"
        if bash_comp.exists():
            print(bash_comp.read_text())
        return 0
    elif shell == "zsh":
        zsh_comp = completions_dir / "strata.zsh"
        if zsh_comp.exists():
            print(zsh_comp.read_text())
        return 0
    elif shell == "install":
        home = Path.home()
        zshrc = home / ".zshrc"
        bashrc = home / ".bashrc"

        # Install Zsh completion
        zsh_block = f"""
# >>> strata completion >>>
if [ -f "{completions_dir}/strata.zsh" ]; then
  source "{completions_dir}/strata.zsh"
fi
# <<< strata completion <<<
"""
        if zshrc.exists():
            content = zshrc.read_text()
            if "strata completion" not in content:
                with open(zshrc, "a") as f:
                    f.write(zsh_block)
                print(f"Added Zsh completion to {zshrc}")
            else:
                print(f"Zsh completion already present in {zshrc}")

        # Install Bash completion
        bash_block = f"""
# >>> strata completion >>>
if [ -f "{completions_dir}/strata.bash" ]; then
  source "{completions_dir}/strata.bash"
fi
# <<< strata completion <<<
"""
        if bashrc.exists():
            content = bashrc.read_text()
            if "strata completion" not in content:
                with open(bashrc, "a") as f:
                    f.write(bash_block)
                print(f"Added Bash completion to {bashrc}")
            else:
                print(f"Bash completion already present in {bashrc}")
        return 0
    else:
        print("Usage: strata completion [bash|zsh|install]")
        return 1


def cmd_run_agent(agent_name, remaining_args):
    if not is_container_running():
        print("Strata container is not running. Starting it first...")
        cmd_start(None)

    # Check if binary is installed
    if subprocess.run(["which", agent_name], capture_output=True).returncode != 0:
        print(f"Agent '{agent_name}' not found in PATH. Running configuration first...")
        cmd_config(None)

    cmd = [agent_name] + remaining_args
    print(f"Launching {agent_name} in current directory ({os.getcwd()})...")
    return subprocess.call(cmd)


def main():
    parser = argparse.ArgumentParser(
        description="Strata Global Service Controller & Agent Switcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  strata start              Start Strata container (with auto-build & VRAM patch check)
  strata stop               Stop Strata container
  strata restart            Restart Strata container
  strata status             Check health and loaded models
  strata build              Build or rebuild Strata Docker image
  strata open               Open Admin Web UI in browser
  strata monitor            Open the chat page's Monitor tab (#monitor)
  strata api-monitor        Open the standalone API Monitor page (/api-monitor)
  strata config             Codified setup for Crush, Goose, Pi, Hermes
  strata completion install Install shell completions to ~/.zshrc & ~/.bashrc
  strata crush              Run Crush in the current directory
  strata goose              Run Goose in the current directory
  strata pi                 Run Pi in the current directory
  strata hermes             Run Hermes in the current directory
        """
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("start", help="Start Strata service container in background")
    subparsers.add_parser("stop", help="Stop Strata service container")
    subparsers.add_parser("restart", help="Restart Strata service container")
    subparsers.add_parser("status", help="Check status of container and service API")
    subparsers.add_parser("build", help="Build or rebuild Strata Docker image")
    subparsers.add_parser("open", help="Open Strata Admin Web UI in browser")
    monitor_parser = subparsers.add_parser("monitor", help="Open the chat page's Monitor tab (#monitor)")
    monitor_parser.add_argument("--enable", action="store_true",
                                help="turn the monitor on first (saves api_monitor=true in the run config and restarts)")

    api_monitor_parser = subparsers.add_parser("api-monitor",
                                               help="Open the standalone API Monitor page (/api-monitor)")
    api_monitor_parser.add_argument("--enable", action="store_true",
                                    help="turn the monitor on first (saves api_monitor=true in the run config and restarts)")
    subparsers.add_parser("config", help="Codified configuration of Crush, Goose, Pi, and Hermes")

    comp_parser = subparsers.add_parser("completion", help="Generate or install shell completion")
    comp_parser.add_argument("shell", choices=["bash", "zsh", "install"], help="Shell type or 'install' to add to rc files")

    crush_parser = subparsers.add_parser("crush", help="Launch Crush against Strata")
    crush_parser.add_argument("agent_args", nargs=argparse.REMAINDER)

    goose_parser = subparsers.add_parser("goose", help="Launch Goose against Strata")
    goose_parser.add_argument("agent_args", nargs=argparse.REMAINDER)

    pi_parser = subparsers.add_parser("pi", help="Launch Pi against Strata")
    pi_parser.add_argument("agent_args", nargs=argparse.REMAINDER)

    hermes_parser = subparsers.add_parser("hermes", help="Launch Hermes against Strata")
    hermes_parser.add_argument("agent_args", nargs=argparse.REMAINDER)

    args = parser.parse_args()

    if args.command == "start":
        sys.exit(cmd_start(args))
    elif args.command == "stop":
        sys.exit(cmd_stop(args))
    elif args.command == "restart":
        sys.exit(cmd_restart(args))
    elif args.command == "status":
        sys.exit(cmd_status(args))
    elif args.command == "build":
        sys.exit(cmd_build(args))
    elif args.command == "open":
        sys.exit(cmd_open(args))
    elif args.command == "monitor":
        sys.exit(cmd_monitor(args))
    elif args.command == "api-monitor":
        sys.exit(cmd_api_monitor(args))
    elif args.command == "config":
        sys.exit(cmd_config(args))
    elif args.command == "completion":
        sys.exit(cmd_completion(args))
    elif args.command in ["crush", "goose", "pi", "hermes"]:
        sys.exit(cmd_run_agent(args.command, args.agent_args))
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
