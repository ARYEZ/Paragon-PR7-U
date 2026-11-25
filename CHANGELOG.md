# Changelog

## 0.6.0

- **PR7-SM** (system monitor, works like Process Explorer) joins the family.

## 0.5.0

- **PR7-PM** (password manager, works like KeePassXC) joins the family.

## 0.4.0

- **PR7-IS** (instant file search, works like Everything) joins the family. A first install from PR7-U leaves out
  its index service, so installing the family never stops for a Windows permission prompt; PR7-IS offers to
  install the service itself.

## 0.3.0

- **PR7-CB** (clipboard history, works like Ditto) joins the family.
- **PR7-DU** (disk usage, works like WizTree) joins the family: Install the family offers it, and Your Paragon
  apps opens, updates and removes it like the others.
- Check for Updates in the other family apps now offers PR7-U.

## 0.1.0

- First release: the one download for the Paragon PR7 family. **Install the family** ticks every app that's missing
  or behind and installs them one after another, each with its own installer from its latest GitHub release (silent,
  per user). It shows each app's download and install progress and a total, and you can cancel. If one app fails,
  the others still install. **Your Paragon apps** shows OPEN, UPDATE or INSTALL for each app, its release notes,
  uninstall, and UPDATE ALL. The command line has `--install`, `--uninstall` and `--list`. The OBSIDIAN and AURORA
  finishes are both here, and PR7-U updates itself like the other apps.
