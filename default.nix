# Nix expression for building Tockloader

{ pkgs ? import <nixpkgs> {}, withUnfreePkgs ? true }:

with builtins;
let
  inherit (pkgs) stdenv stdenvNoCC lib;

  python3Packages = lib.fix' (self: with self; pkgs.python3Packages //
  {
    siphash = buildPythonPackage rec {
      pname = "siphash";
      version = "0.0.1";

      src = fetchPypi {
        inherit pname version;
        sha256 = "sha256-rul/6V4JoplYGcBYpeSsbZZmGomNf+CtVeO3LJox1GE=";
      };

      pyproject = true;
      build-system = [ setuptools ];
    };
  });

in pkgs.python3Packages.buildPythonPackage rec {
  pname = "tockloader";
  version = let
      pattern = "^__version__ = ['\"]([^'\"]*)['\"]\n";
  in elemAt (match pattern (readFile ./tockloader/_version.py)) 0;

  src = ./.;

  pyproject = true;

  nativeBuildInputs = with python3Packages; [
    flit
  ];

  propagatedBuildInputs = with python3Packages; [
    appdirs
    argcomplete
    colorama
    crcmod
    intelhex
    pycrypto
    pyserial
    questionary
    siphash
    six
    toml
    tqdm
  ];

  # Ensure that Tockloader can, at runtime, find the `nrfutil` binary:
  postPatch = lib.optionalString withUnfreePkgs ''
    substituteInPlace ./tockloader/nrfutil.py \
      --replace 'shutil.which("nrfutil")' '"${
        pkgs.nrfutil.withExtensions [
            "nrfutil-device"
        ]
      }/bin/nrfutil"'
  '';
}
