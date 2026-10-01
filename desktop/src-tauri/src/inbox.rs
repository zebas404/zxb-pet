//! The shell's only local capability: create **new** notes in the vault Inbox.
//!
//! - Never overwrites or edits: files are opened with `create_new`.
//! - The file name is derived from the title, sanitized, and always prefixed
//!   with a timestamp, so it can't escape the Inbox or hit a reserved name.
//! - Notes carry `origen: mascota` so the vault agent knows where they came from.

use std::fs::OpenOptions;
use std::io::{ErrorKind, Write};
use std::path::{Path, PathBuf};

use chrono::{DateTime, FixedOffset};

pub const MAX_TITLE_CHARS: usize = 120;
pub const MAX_BODY_CHARS: usize = 4000;
const MAX_FILE_STEM_CHARS: usize = 80;

/// Keep only characters that are safe in a Windows/macOS/Linux file name.
pub fn sanitize_file_stem(title: &str) -> String {
    let cleaned: String = title
        .chars()
        .map(|c| match c {
            '<' | '>' | ':' | '"' | '/' | '\\' | '|' | '?' | '*' | '#' | '^' | '[' | ']' => ' ',
            c if c.is_control() => ' ',
            c => c,
        })
        .collect();
    let collapsed = cleaned.split_whitespace().collect::<Vec<_>>().join(" ");
    let trimmed: String = collapsed.chars().take(MAX_FILE_STEM_CHARS).collect();
    let trimmed = trimmed.trim_matches(|c: char| c == '.' || c.is_whitespace());
    if trimmed.is_empty() { "captura".to_string() } else { trimmed.to_string() }
}

/// Remove control characters except newlines and tabs.
fn clean_text(text: &str) -> String {
    text.chars().filter(|c| !c.is_control() || *c == '\n' || *c == '\t').collect()
}

fn yaml_quote(text: &str) -> String {
    format!("\"{}\"", text.replace('\\', "\\\\").replace('"', "\\\""))
}

pub fn render_note(title: &str, body: &str, now: &DateTime<FixedOffset>) -> String {
    let mut note = format!(
        "---\norigen: mascota\ntipo: captura\ncreado: {}\ntitulo: {}\n---\n# {}\n",
        now.format("%Y-%m-%dT%H:%M:%S%:z"),
        yaml_quote(title),
        title,
    );
    if !body.trim().is_empty() {
        note.push('\n');
        note.push_str(body.trim());
        note.push('\n');
    }
    note
}

/// Create a new note in `inbox_dir`. Returns the path of the created file.
pub fn create_note(
    inbox_dir: &Path,
    title: &str,
    body: &str,
    now: &DateTime<FixedOffset>,
) -> Result<PathBuf, String> {
    let title = clean_text(title).replace(['\n', '\t'], " ").trim().to_string();
    let body = clean_text(body);
    if title.is_empty() {
        return Err("El título no puede estar vacío.".into());
    }
    if title.chars().count() > MAX_TITLE_CHARS {
        return Err(format!("El título supera {MAX_TITLE_CHARS} caracteres."));
    }
    if body.chars().count() > MAX_BODY_CHARS {
        return Err(format!("El texto supera {MAX_BODY_CHARS} caracteres."));
    }
    if !inbox_dir.is_dir() {
        return Err(format!("No existe la carpeta del Inbox: {}", inbox_dir.display()));
    }

    let stem = format!("{} - {}", now.format("%Y-%m-%d %H%M"), sanitize_file_stem(&title));
    let content = render_note(&title, &body, now);

    for n in 1..=50 {
        let name = if n == 1 { format!("{stem}.md") } else { format!("{stem} ({n}).md") };
        let path = inbox_dir.join(&name);
        // Defense in depth: the final path must be a direct child of the Inbox.
        if path.parent() != Some(inbox_dir) {
            return Err("Nombre de archivo no válido.".into());
        }
        match OpenOptions::new().write(true).create_new(true).open(&path) {
            Ok(mut file) => {
                file.write_all(content.as_bytes()).map_err(|e| format!("No se pudo escribir la nota: {e}"))?;
                return Ok(path);
            }
            Err(e) if e.kind() == ErrorKind::AlreadyExists => continue,
            Err(e) => return Err(format!("No se pudo crear la nota: {e}")),
        }
    }
    Err("Demasiadas notas con el mismo nombre en el mismo minuto.".into())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    fn now() -> DateTime<FixedOffset> {
        DateTime::parse_from_rfc3339("2026-10-01T09:05:00-05:00").unwrap()
    }

    fn temp_inbox(name: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!("zebot-inbox-test-{name}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    #[test]
    fn sanitizes_dangerous_names() {
        assert_eq!(sanitize_file_stem("../../etc/passwd"), "etc passwd");
        assert_eq!(sanitize_file_stem("C:\\Windows\\win.ini"), "C Windows win.ini");
        assert_eq!(sanitize_file_stem("ya hice [[X]] #tag?"), "ya hice X tag");
        assert_eq!(sanitize_file_stem("..."), "captura");
        assert_eq!(sanitize_file_stem("a\u{0}b\nc"), "a b c");
        assert_eq!(sanitize_file_stem(&"x".repeat(200)).chars().count(), 80);
    }

    #[test]
    fn creates_note_with_frontmatter() {
        let dir = temp_inbox("create");
        let path = create_note(&dir, "Ya hice: leer la exam guide", "Capítulo 1 listo.", &now()).unwrap();
        assert_eq!(path.parent().unwrap(), dir);
        assert_eq!(path.file_name().unwrap(), "2026-10-01 0905 - Ya hice leer la exam guide.md");
        let text = fs::read_to_string(&path).unwrap();
        assert!(text.starts_with("---\norigen: mascota\ntipo: captura\ncreado: 2026-10-01T09:05:00-05:00\n"));
        assert!(text.contains("titulo: \"Ya hice: leer la exam guide\"\n"));
        assert!(text.ends_with("# Ya hice: leer la exam guide\n\nCapítulo 1 listo.\n"));
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn never_overwrites_existing_notes() {
        let dir = temp_inbox("no-overwrite");
        let first = create_note(&dir, "misma idea", "uno", &now()).unwrap();
        let second = create_note(&dir, "misma idea", "dos", &now()).unwrap();
        assert_ne!(first, second);
        assert!(second.to_string_lossy().ends_with("misma idea (2).md"));
        assert!(fs::read_to_string(&first).unwrap().contains("uno"));
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn path_traversal_stays_inside_inbox() {
        let dir = temp_inbox("traversal");
        let path = create_note(&dir, "../../fuera", "", &now()).unwrap();
        assert_eq!(path.parent().unwrap(), dir);
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn rejects_invalid_input() {
        let dir = temp_inbox("invalid");
        assert!(create_note(&dir, "   ", "", &now()).is_err());
        assert!(create_note(&dir, &"t".repeat(MAX_TITLE_CHARS + 1), "", &now()).is_err());
        assert!(create_note(&dir, "ok", &"b".repeat(MAX_BODY_CHARS + 1), &now()).is_err());
        assert!(create_note(&dir.join("no-existe"), "ok", "", &now()).is_err());
        assert_eq!(fs::read_dir(&dir).unwrap().count(), 0);
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn multiline_title_stays_on_one_line() {
        let dir = temp_inbox("multiline");
        let path = create_note(&dir, "uno\ndos", "", &now()).unwrap();
        assert!(fs::read_to_string(&path).unwrap().contains("# uno dos\n"));
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn yaml_title_is_escaped() {
        let text = render_note("dijo \"hola\" \\ fin", "", &now());
        assert!(text.contains("titulo: \"dijo \\\"hola\\\" \\\\ fin\"\n"));
    }
}
