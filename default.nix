# Nix expression for building Tockloader

{ pkgs ? import <nixpkgs> {}, withUnfreePkgs ? true }:

with builtins;
let
  inherit (pkgs) stdenv stdenvNoCC lib;

  nrf-command-line-tools = stdenvNoCC.mkDerivation {
    pname = "nrf-command-line-tools";
    version = "10.22.1";

    src = builtins.fetchurl {
      url = "https://nsscprodmedia.blob.core.windows.net/prod/software-and-other-downloads/desktop-software/nrf-command-line-tools/sw/versions-10-x-x/10-22-1/nrf-command-line-tools-10.22.1_linux-amd64.tar.gz";
      sha256 = "sha256:0i3dfhp75rizs7kxyfka166k3zy5hmb28c25377pgnzk6w1yx383";
    };

    nativeBuildInputs = with pkgs; [
      autoPatchelfHook
    ];

    propagatedBuildInputs = with pkgs; [
      segger-jlink libusb
    ];

    installPhase = ''
      mkdir -p $out/
      cp -r * $out/
    '';

    meta.license = lib.licenses.unfree;
  };

  pythonPackages = lib.fix' (self: with self; pkgs.python3Packages //
  {
    siphash = buildPythonPackage rec {
      pname = "siphash";
      version = "0.0.1";

      src = fetchPypi {
        inherit pname version;
        sha256 = "sha256-rul/6V4JoplYGcBYpeSsbZZmGomNf+CtVeO3LJox1GE=";
      };
    };

    pynrfjprog = buildPythonPackage {
      pname = "pynrfjprog";
      version = nrf-command-line-tools.version;

      src = nrf-command-line-tools.src;

      preConfigure = ''
        cd ./python
      '';

      format = "pyproject";

      nativeBuildInputs = [
        setuptools
        pkgs.autoPatchelfHook
      ];

      buildInputs = [
        nrf-command-line-tools
      ];

      propagatedBuildInputs = [
        tomli-w
        future
      ];

      meta.license = lib.licenses.unfree;
    };
  });
in pkgs.python3Packages.buildPythonPackage rec {
  pname = "tockloader";
  version = "1.10.0";
  name = "${pname}-${version}";

  propagatedBuildInputs = with pythonPackages; [
    argcomplete
    colorama
    crcmod
    pyserial
    toml
    tqdm
    questionary
    pycrypto
    siphash
  ] ++ (lib.optional withUnfreePkgs pynrfjprog);

  src = ./.;

  # Dependency checks require unfree software
  doCheck = withUnfreePkgs;
}
