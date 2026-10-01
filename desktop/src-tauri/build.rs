fn main() {
    // `crear_nota_inbox` gets `allow-`/`deny-` permissions and is denied unless
    // a capability grants it (only the Zebot server origin does, see main.rs).
    tauri_build::try_build(
        tauri_build::Attributes::new()
            .app_manifest(tauri_build::AppManifest::new().commands(&["crear_nota_inbox"])),
    )
    .expect("failed to run tauri-build");
}
