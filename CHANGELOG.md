# Changelog

## 0.11.0

- **PR7-AR**, the startup manager (works like Autoruns), joins the list.

## 0.10.0

- **PR7-FS**, folder comparison and sync (works like FreeFileSync), joins the list.

## 0.9.0

- **PR7-HB**, the video converter (works like HandBrake), joins the list: install, update and remove it with the rest of the family.

## 0.8.0

- **One finish for the whole family.** Choosing OBSIDIAN or AURORA here switches every Paragon app, open ones included (within a couple of seconds), and every app starts in the family's choice.
- In AURORA, group titles and selected rows are dark and readable (they were white on the light finish).

## 0.7.0

- **Install and update everything in one go.** Your Paragon apps has one button for whatever is waiting: UPDATE ALL
  (updates only), INSTALL ALL (the apps you don't have yet) or UPDATE AND INSTALL ALL (both, updates first). When both
  are waiting, UPDATE ONLY brings your apps up to date without adding the rest of the family. New apps install with
  the same quiet first-install choices as on first start, so a batch never stops at a Windows permission prompt.

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
