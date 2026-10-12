# Publishing pdfreader to the AUR

This directory holds the packaging metadata for the `pdfreader` package
(GTK4 PDF reader for Omarchy/Arch).

## Test locally

```sh
# in this directory
makepkg -f          # builds; requires the makedepends/depends packages
makepkg -i          # build and install
```

## Publish to AUR

AUR maintains its own git repositories. You need an SSH key registered at
https://aur.archlinux.org first.

```sh
# 1. Clone the AUR package repo (uses your AUR SSH login)
git clone ssh://aur@aur.archlinux.org/pdfreader.git aur-publish
cd aur-publish

# 2. Copy the manifests (regenerate .SRCINFO from the PKGBUILD)
cp ../PKGBUILD .
makepkg --printsrcinfo > .SRCINFO

# 3. Commit and push (by default AUR mirrors the master branch)
git add PKGBUILD .SRCINFO
git commit -m "pdfreader v0.1.0"
git push origin master

# 4. On every new release update pkgver + sha256sums, then repeat.
```

After that, Omarchy users can install it with:

```sh
paru -S pdfreader
# or
yay -S pdfreader
```

## Release checklist

1. Bump `__version__` in `pdfreader/__init__.py`, `version` in `pyproject.toml`,
   and `pkgver` here.
2. Tag and push: `git tag v0.1.1 && git push origin v0.1.1`.
3. Re-download the GitHub tarball and update `sha256sums`.