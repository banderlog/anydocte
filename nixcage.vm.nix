## nixcage VM configuration -- edit to customize your environment.
## Run 'nixcage sync' after changes.
{ pkgs, ... }: 
let
   opencode_with_env = pkgs.writeShellScriptBin "opencode_with_env" ''
     # Isolate configs, data, caches, and logs entirely to workspace
     export OPENCODE_CONFIG_DIR="/workspace/.opencode/config"
     export OPENCODE_DATA_DIR="/workspace/.opencode/data"
     export OPENCODE_CACHE_DIR="/workspace/.opencode/cache"
     export OPENCODE_LOG_DIR="/workspace/.opencode/log"
     export OPENCODE_STATE_DIR="/workspace/.opencode/state"
     export OPENCODE_DB="/workspace/.opencode/data/opencode.db"
     export OPENCODE_AUTH_JSON="/workspace/.opencode/data/auth.json"
     exec opencode -c "$@"
   '';

in
{

  ## Add project-specific packages
  environment.systemPackages = with pkgs; [
    python3
    opencode_with_env
    tesseract
    poppler-utils
    vim
    file
  ];

  ## Adjust VM resources (defaults: 2 GB RAM, 2 vCPUs)
  microvm.mem = 4096;
  microvm.vcpu = 4;

  ## Mount extra host paths (proto: "virtiofs" on Linux, "9p" on macOS)
  # microvm.shares = [{
  #   tag = "home-ssh";
  #   source = "/home/me/.ssh";
  #   mountPoint = "/home/nixcage/.ssh";
  #   proto = "virtiofs";  # use "9p" on macOS
  # }];
}
