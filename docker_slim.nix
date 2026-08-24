{ pkgs ? import <nixpkgs> {} }:

let
  pyproject = builtins.fromTOML (builtins.readFile ./pyproject.toml);
  version = pyproject.project.version;

  # Strip the default 350MB language bundle from the tesseract derivation
  tesseractSlim = pkgs.tesseract.overrideAttrs (old: {
    postInstall = "rm -rf $out/share/tessdata";
  });

  # Link only the 3 languages from nixpkgs
  customTessdata = pkgs.linkFarm "tessdata" [
    { name = "eng.traineddata"; path = pkgs.tesseract.languages.eng; }
    { name = "ukr.traineddata"; path = pkgs.tesseract.languages.ukr; }
    { name = "rus.traineddata"; path = pkgs.tesseract.languages.rus; }
  ];

  runtimePackages = with pkgs; [
    python3
    python3Packages.pip
    tesseractSlim
    poppler-utils
    zlib
    glib
    cacert
    bash
  ];

  libPath = pkgs.lib.makeLibraryPath [
    pkgs.zlib
    pkgs.glib
  ];

  # Startup entrypoint
  entrypoint = pkgs.writeShellScriptBin "entrypoint" ''
    set -e
    cd /app

    if [ -f "/app/pyproject.toml" ]; then
      pip install --quiet --no-cache-dir --break-system-packages --root-user-action=ignore /app
    fi

    echo "Starting Extraction Proxy on $HOST:$PORT (Workers: $MAX_WORKERS, Tesseract params: $TESSERACT_CUSTOM_CONFIG, PDF dpi: $PDF_DPI)..."
    exec python -m anydocte --host "$HOST" --port "$PORT" --max-workers "$MAX_WORKERS" --tesseract-config "$TESSERACT_CUSTOM_CONFIG" --pdf-dpi=$PDF_DPI
  '';

in
pkgs.dockerTools.buildLayeredImage {
  name = "anydocte";
  tag = "${version}-slim";
  maxLayers = 16;

  contents = runtimePackages ++ [
    entrypoint
    customTessdata
    pkgs.dockerTools.binSh
    pkgs.dockerTools.caCertificates
  ];

  extraCommands = ''
    mkdir -p app tmp
    chmod 1777 tmp
    cp -r ${./src} app/src
    cp ${./pyproject.toml} app/pyproject.toml
  '';

  config = {
    Entrypoint = [ "${entrypoint}/bin/entrypoint" ];
    WorkingDir = "/app";
    ExposedPorts = { "5005/tcp" = {}; };
    Env = [
      "HOST=0.0.0.0"
      "PORT=5005"
      "MAX_WORKERS=4"
      "TESSERACT_CUSTOM_CONFIG=-l eng+ukr+rus --oem 1 --psm 3"
      "PDF_DPI=200"
      "TESSDATA_PREFIX=${customTessdata}"
      "LD_LIBRARY_PATH=${libPath}"
      "SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
    ];
  };
}
