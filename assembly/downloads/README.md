# Digilent downloads

Official Linux x86-64 packages are saved locally in this directory. Installer binaries are not included in Git or the public website; use the official download links below on another computer.

| Package | SHA-256 |
|---|---|
| WaveForms 3.25.1, application + runtime + SDK (`digilent.waveforms_3.25.1_amd64.deb`, local only) | `d2979aab726c9202a48a1c5d2b314531513171c0b62fa2f2a2edcd29202727d3` |
| Adept Runtime 2.30.1 (`digilent.adept.runtime_2.30.1_amd64.deb`, local only) | `e5e51d2640c2ff34ef3b436f3bdf37838120b15160d73dfbab82e90773b6b372` |

Both hashes match the package recipes already present in this computer's AUR cache. Adept Runtime 2.30.1 is already installed. The Adept `.deb` here was copied from its existing downloaded package. WaveForms was downloaded from Digilent using a browser user-agent because the server challenges curl's default user-agent.

This computer uses Arch/Omarchy. These are vendor `.deb` source packages, **not packages to install with apt on this machine**. Use an Arch package built from the existing `digilent.waveforms` recipe for system installation. The `waveforms-extracted/` folder is an inspection copy of the vendor package used to verify the SDK header/examples; extracting it alone is not a system installation.

Downloads and extracted files are excluded from git. Keep this directory locally or download again from the official sources:

- [WaveForms releases](https://digilent.com/reference/software/waveforms/waveforms-3/previous-versions)
- [Adept Runtime](https://digilent.com/reference/software/adept/start)

For a diagnostic SDK enumeration using the extracted library and installed Adept libraries (no outputs enabled):

```sh
LD_LIBRARY_PATH=/usr/lib/digilent/adept \
DWF_LIBRARY="$PWD/assembly/downloads/waveforms-extracted/usr/lib/libdwf.so.3.25.1" \
python assembly/bench/run.py devices
```

Full instrument use requires its firmware/configuration files to be installed as well as its library; use the system installation for real tests.

## Ready-to-install Arch package

The verified source was built into `arch-build/digilent.waveforms-3.25.1-1-x86_64.pkg.tar.zst` (local only) using the existing AUR recipe. All declared dependencies are present. System installation was attempted, but `sudo` requires your password; no WaveForms system installation was completed.

Run this in your own terminal from the project root:

```sh
sudo pacman -U /home/mads/Projects/vinyl-adc/assembly/downloads/arch-build/digilent.waveforms-3.25.1-1-x86_64.pkg.tar.zst
```

This computer's installed Adept libraries are under `/usr/lib/digilent/adept`, outside the current loader cache. The test runner adds that directory to its own library search path automatically on Linux. If the WaveForms GUI reports a missing `libdmgr.so.2`, launch it with:

```sh
LD_LIBRARY_PATH=/usr/lib/digilent/adept waveforms
```

After installation, connect the AD3 and run `python assembly/bench/run.py devices`. This should list its serial number without enabling outputs.


## Startup fix

WaveForms 3.25.1 is now installed. Its user launcher at `~/.local/share/applications/digilent.waveforms.desktop` sets `LD_LIBRARY_PATH=/usr/lib/digilent/adept` for both normal and safe-mode startup. This resolves six missing Adept libraries without changing system files. Safe-mode GUI startup was verified on this machine.
