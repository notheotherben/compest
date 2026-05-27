{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = [
    pkgs.python313
    pkgs.python313Packages.ipykernel
    pkgs.python313Packages.matplotlib
    pkgs.python313Packages.pandas
    pkgs.python313Packages.pytest
    pkgs.python313Packages.hypothesis
  ];
}

