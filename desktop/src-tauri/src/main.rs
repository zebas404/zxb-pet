//! Zebot desktop shell (Tauri v2).
//!
//! A small transparent, frameless, always-on-top window that loads the pet UI
//! served by the backend (`<server>/?widget`). Local responsibilities only:
//! - show a sleeping Zebot while the server is unreachable (bundled loader page);
//! - tray icon, autostart and remembered window position;
//! - one command, `crear_nota_inbox`, callable only from the Zebot server origin.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod inbox;

use std::fs;
use std::path::PathBuf;
use std::sync::OnceLock;

use serde::{Deserialize, Serialize};
use tauri::ipc::CapabilityBuilder;
use tauri::menu::{CheckMenuItem, Menu, MenuItem, PredefinedMenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{AppHandle, LogicalPosition, Manager, State, Url, WebviewUrl, WebviewWindowBuilder, WindowEvent};
use tauri_plugin_autostart::{MacosLauncher, ManagerExt};
use tauri_plugin_opener::OpenerExt;
use tauri_plugin_window_state::{StateFlags, WindowExt};

const WINDOW_LABEL: &str = "main";
const WINDOW_SIZE: (f64, f64) = (300.0, 420.0);
const SCREEN_MARGIN: f64 = 16.0;

static LOADER_URL: OnceLock<Url> = OnceLock::new();

/// `%APPDATA%\com.zebas404.zebot\config.json`, created with defaults on first run.
#[derive(Clone, Serialize, Deserialize)]
struct Config {
    server_url: String,
    inbox_dir: PathBuf,
}

impl Default for Config {
    fn default() -> Self {
        let home = std::env::var_os("USERPROFILE")
            .or_else(|| std::env::var_os("HOME"))
            .map(PathBuf::from)
            .unwrap_or_default();
        Self {
            server_url: "http://192.168.1.63:8000".into(),
            inbox_dir: home
                .join("iCloudDrive")
                .join("iCloud~md~obsidian")
                .join("SegundoCerebro")
                .join("00-Inbox"),
        }
    }
}

/// Returns the config and whether this is the first run (no config file yet).
fn load_config(app: &AppHandle) -> (Config, bool) {
    let Ok(dir) = app.path().app_config_dir() else { return (Config::default(), false) };
    let path = dir.join("config.json");
    if let Ok(text) = fs::read_to_string(&path) {
        // Windows PowerShell 5.1 and Notepad may save UTF-8 with a BOM.
        if let Ok(mut cfg) = serde_json::from_str::<Config>(text.trim_start_matches('\u{feff}')) {
            cfg.server_url = cfg.server_url.trim_end_matches('/').to_string();
            return (cfg, false);
        }
        eprintln!("config.json no válido, uso valores por defecto: {}", path.display());
        return (Config::default(), false);
    }
    let cfg = Config::default();
    let _ = fs::create_dir_all(&dir);
    let _ = fs::write(&path, serde_json::to_string_pretty(&cfg).unwrap_or_default());
    (cfg, true)
}

/// Create a new note in the vault Inbox. Returns the file name (not the full path).
#[tauri::command]
fn crear_nota_inbox(titulo: String, cuerpo: Option<String>, config: State<'_, Config>) -> Result<String, String> {
    let now = chrono::Local::now().fixed_offset();
    inbox::create_note(&config.inbox_dir, &titulo, cuerpo.as_deref().unwrap_or(""), &now)
        .map(|p| p.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default())
}

fn toggle_window(app: &AppHandle) {
    if let Some(win) = app.get_webview_window(WINDOW_LABEL) {
        if win.is_visible().unwrap_or(false) {
            let _ = win.hide();
        } else {
            let _ = win.show();
            let _ = win.set_focus();
        }
    }
}

fn show_window(app: &AppHandle) {
    if let Some(win) = app.get_webview_window(WINDOW_LABEL) {
        let _ = win.show();
        let _ = win.set_focus();
    }
}

/// Go back to the bundled loader, which re-checks the server before navigating.
fn reload(app: &AppHandle) {
    if let (Some(win), Some(url)) = (app.get_webview_window(WINDOW_LABEL), LOADER_URL.get()) {
        let _ = win.navigate(url.clone());
        let _ = win.show();
    }
}

/// Bottom-right corner of the primary monitor's work area, in logical pixels.
fn bottom_right(app: &AppHandle) -> Option<(f64, f64)> {
    let monitor = app.primary_monitor().ok()??;
    let scale = monitor.scale_factor();
    let area = monitor.work_area();
    let right = (area.position.x as f64 + area.size.width as f64) / scale;
    let bottom = (area.position.y as f64 + area.size.height as f64) / scale;
    Some((right - WINDOW_SIZE.0 - SCREEN_MARGIN, bottom - WINDOW_SIZE.1 - SCREEN_MARGIN))
}

/// Tray action: bring Zebot back to the corner (handy with several monitors).
fn move_to_corner(app: &AppHandle) {
    if let (Some(win), Some((x, y))) = (app.get_webview_window(WINDOW_LABEL), bottom_right(app)) {
        let _ = win.set_position(LogicalPosition::new(x, y));
        let _ = win.show();
        let _ = win.set_focus();
    }
}

fn build_tray(app: &AppHandle, server_url: String) -> tauri::Result<()> {
    let toggle = MenuItem::with_id(app, "toggle", "Mostrar / ocultar", true, None::<&str>)?;
    let corner = MenuItem::with_id(app, "corner", "Llevar a la esquina", true, None::<&str>)?;
    let reload_item = MenuItem::with_id(app, "reload", "Recargar", true, None::<&str>)?;
    let browser = MenuItem::with_id(app, "browser", "Abrir en el navegador", true, None::<&str>)?;
    let autostart_on = app.autolaunch().is_enabled().unwrap_or(false);
    let autostart = CheckMenuItem::with_id(app, "autostart", "Iniciar con Windows", true, autostart_on, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "Salir", true, None::<&str>)?;
    let menu = Menu::with_items(
        app,
        &[
            &toggle,
            &corner,
            &reload_item,
            &browser,
            &PredefinedMenuItem::separator(app)?,
            &autostart,
            &PredefinedMenuItem::separator(app)?,
            &quit,
        ],
    )?;

    let autostart_item = autostart.clone();
    TrayIconBuilder::with_id("zebot")
        .icon(app.default_window_icon().cloned().expect("app icon"))
        .tooltip("Zebot")
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_menu_event(move |app, event| match event.id.as_ref() {
            "toggle" => toggle_window(app),
            "corner" => move_to_corner(app),
            "reload" => reload(app),
            "browser" => {
                let _ = app.opener().open_url(server_url.clone(), None::<&str>);
            }
            "autostart" => {
                let enable = autostart_item.is_checked().unwrap_or(false);
                let launcher = app.autolaunch();
                let _ = if enable { launcher.enable() } else { launcher.disable() };
            }
            "quit" => app.exit(0),
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click { button: MouseButton::Left, button_state: MouseButtonState::Up, .. } = event {
                toggle_window(tray.app_handle());
            }
        })
        .build(app)?;
    Ok(())
}

fn main() {
    tauri::Builder::default()
        // Must be first: a second launch just shows the existing window.
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| show_window(app)))
        .plugin(tauri_plugin_autostart::init(MacosLauncher::LaunchAgent, None))
        .plugin(tauri_plugin_window_state::Builder::default().with_state_flags(StateFlags::POSITION).build())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![crear_nota_inbox])
        .setup(|app| {
            let handle = app.handle().clone();
            let (config, first_run) = load_config(&handle);
            let server = config.server_url.clone();

            // Only pages from the Zebot server may call crear_nota_inbox (denied everywhere else).
            app.add_capability(
                CapabilityBuilder::new("zebot-server")
                    .remote(format!("{server}/*"))
                    .window(WINDOW_LABEL)
                    .permission("core:window:allow-start-dragging")
                    .permission("allow-crear-nota-inbox"),
            )?;

            let allowed_prefix = format!("{server}/");
            let init = format!("window.ZEBOT_SERVER = {};", serde_json::to_string(&server)?);
            let mut builder = WebviewWindowBuilder::new(app, WINDOW_LABEL, WebviewUrl::App("index.html".into()))
                .title("Zebot")
                .inner_size(WINDOW_SIZE.0, WINDOW_SIZE.1);
            // Created directly at the corner: moving a hidden window afterwards is unreliable on Windows.
            if let Some((x, y)) = bottom_right(&handle) {
                builder = builder.position(x, y);
            }
            let win = builder
                .resizable(false)
                .decorations(false)
                .transparent(true)
                .shadow(false)
                .always_on_top(true)
                .skip_taskbar(true)
                .visible(false)
                .initialization_script(&init)
                // The window may only show the bundled loader or the Zebot server.
                .on_navigation(move |url| {
                    url.scheme() == "tauri"
                        || url.host_str() == Some("tauri.localhost")
                        || url.as_str().starts_with(&allowed_prefix)
                })
                .build()?;

            if let Ok(url) = win.url() {
                let _ = LOADER_URL.set(url);
            }
            // Only restore a position the user actually saved (dragged, then quit).
            let saved = handle.path().app_config_dir().map(|d| d.join(".window-state.json").exists());
            if saved.unwrap_or(false) {
                let _ = win.restore_state(StateFlags::POSITION);
            }
            win.show()?;

            if first_run {
                let _ = handle.autolaunch().enable();
            }
            app.manage(config);
            build_tray(&handle, server)?;
            Ok(())
        })
        .on_window_event(|window, event| {
            // No close button; Alt+F4 hides to the tray instead of quitting.
            if let WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let _ = window.hide();
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running Zebot");
}
