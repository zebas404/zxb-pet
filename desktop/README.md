# Zebot desktop shell (Tauri v2)

A thin native shell: a 300×420 transparent, frameless, always-on-top window that loads the pet UI from the server (`<server>/?widget`). Every UI change ships server-side; the shell is rebuilt only when its own code changes.

| Concern | How |
|---|---|
| Server down | The bundled loader (`ui/index.html`) shows a sleeping Zebot and retries `/health` every 30 s, then navigates to the widget |
| Tray | Show/hide, reload, open in browser, *Iniciar con Windows* toggle, quit |
| Autostart | `tauri-plugin-autostart` (HKCU `Run` key, no admin rights). Enabled on first run |
| Position | Bottom-right of the primary monitor on first run, then remembered (`tauri-plugin-window-state`) |
| Single instance | A second launch just shows the existing window |
| Navigation | Restricted to the bundled loader and the configured server |

## The only local capability: `crear_nota_inbox`

Creates a **new** Markdown note in the vault Inbox ([`src/inbox.rs`](src-tauri/src/inbox.rs)):

- Opened with `create_new`: it never overwrites or edits; name collisions get ` (2)`, ` (3)`…
- The file name is sanitized and prefixed with a timestamp (`2026-10-01 0905 - Title.md`), and the final path must be a direct child of the Inbox.
- Title ≤ 120 chars, body ≤ 4000 chars, control characters stripped.
- Frontmatter `origen: mascota` lets the vault agent recognize captures.

**Permissions:** the command is declared in the app manifest (`build.rs`), so it is **denied by default**. A runtime capability grants `allow-crear-nota-inbox` and window dragging **only to the configured server origin**. The bundled loader cannot call it.

## Configuration

`%APPDATA%\com.zebas404.zebot\config.json` is created on first run:

```json
{
  "server_url": "http://192.168.1.63:8000",
  "inbox_dir": "C:\\Users\\<you>\\iCloudDrive\\iCloud~md~obsidian\\SegundoCerebro\\00-Inbox"
}
```

## Build

Requires Rust (MSVC toolchain) and Visual Studio Build Tools with C++. No Node.js and no Tauri CLI: the `custom-protocol` feature is on by default, so plain cargo embeds the loader.

```powershell
cd desktop\src-tauri
cargo test --release      # Inbox writer unit tests
cargo build --release     # target\release\zebot.exe
```

Icons are generated from pixel art with `python desktop/make_icons.py`. CI builds `zebot.exe` on `windows-latest` and uploads it as an artifact.
