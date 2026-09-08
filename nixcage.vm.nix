## nixcage v1.2.0 VM configuration -- edit to customize your environment.
## Run 'nixcage sync' after changes.
{ pkgs, ... }:
let
  libPath = pkgs.lib.makeLibraryPath [ pkgs.file ];

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

  claude_with_env = pkgs.writeShellScriptBin "claude_with_env" ''
    export DISABLE_TELEMETRY=1
    export DISABLE_ERROR_REPORTING=1
    export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
    export CLAUDE_CODE_DISABLE_AUTO_MEMORY=1
    export CLAUDE_CODE_MAX_OUTPUT_TOKENS=128000
    export ENABLE_TOOL_SEARCH=false
    export CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1
    #export ANTHROPIC_BASE_URL=
    #export ANTHROPIC_API_KEY=
    exec claude "$@"
  '';
in
{

  ## Add project-specific packages
  environment.systemPackages = with pkgs; [
    python3
    opencode_with_env
    claude_with_env
    tesseract
    poppler-utils
    vim
    file
  ];

  environment.localBinInPath = true;

  environment.variables = {
    EDITOR = "vim";
    CLAUDE_CONFIG_DIR = "/workspace/.claude";
    LD_LIBRARY_PATH = libPath;
  };

  ## Adjust VM resources (defaults: 2 GB RAM, 2 vCPUs)
  microvm.mem = 4096;
  microvm.vcpu = 4;

}
