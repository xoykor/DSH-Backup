use csv::{ReaderBuilder, WriterBuilder};
use quick_xml::events::Event;
use quick_xml::Reader as XmlReader;
use regex::Regex;
use rusqlite::hooks::{AuthAction, AuthContext, Authorization};
use rusqlite::limits::Limit;
use rusqlite::types::{ToSql, Value as SqlValue};
use rusqlite::{Connection, OpenFlags, Row};
use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeSet, HashMap, HashSet};
use std::env;
use std::fs::{self, File, OpenOptions};
use std::io::{self, Read, Write};
use std::os::unix::fs::OpenOptionsExt;
use std::path::{Path, PathBuf};
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc,
};
use std::time::{Duration, Instant};
use zip::write::SimpleFileOptions;
use zip::{ZipArchive, ZipWriter};

type ToolResult = Result<Value, String>;

fn main() {
    let mut args: Vec<String> = env::args().collect();
    let invoked = Path::new(args.first().map(String::as_str).unwrap_or("dsh-rust-tools"))
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("dsh-rust-tools")
        .to_string();
    if invoked == "dsh-rust-tools" || invoked == "dsh_rust_tools" {
        args.remove(0);
    } else {
        args[0] = invoked;
    }
    let name = args.first().cloned().unwrap_or_default();
    let result = match name.as_str() {
        "check_site" => check_site(&args[1..]),
        "validate_research" => validate_research(&args[1..]),
        "table_transform" => table_transform(&args[1..]),
        "table_reconcile" => table_reconcile(&args[1..]),
        "validate_pptx" => validate_package(&args[1..], "ppt/", "a:t"),
        "validate_docx" => validate_package(&args[1..], "word/", "w:t"),
        "fill_pptx" => fill_package(&args[1..], "ppt/", "a:t"),
        "fill_docx" => fill_package(&args[1..], "word/", "w:t"),
        "sqlite_read" => sqlite_read(&args[1..]),
        _ => Err(format!("unknown Rust helper: {name}")),
    };
    match result {
        Ok(value) => {
            let rendered = serde_json::to_string_pretty(&value).unwrap();
            if name == "table_reconcile"
                && value.get("status").and_then(Value::as_str) == Some("mismatch")
            {
                println!("{rendered}");
                std::process::exit(3);
            }
            if matches!(name.as_str(), "validate_pptx" | "validate_docx")
                && value.get("status").and_then(Value::as_str) == Some("error")
            {
                eprintln!("{rendered}");
                std::process::exit(1);
            }
            if matches!(name.as_str(), "fill_pptx" | "fill_docx")
                && value.get("status").and_then(Value::as_str) == Some("error")
            {
                eprintln!("{rendered}");
                std::process::exit(2);
            }
            println!("{rendered}");
        }
        Err(error) => {
            eprintln!("{}", json!({"status":"error", "error":error}));
            std::process::exit(2);
        }
    }
}

fn option(args: &[String], name: &str, required: bool) -> Result<Option<String>, String> {
    for (i, arg) in args.iter().enumerate() {
        if arg == name {
            return args
                .get(i + 1)
                .cloned()
                .map(Some)
                .ok_or_else(|| format!("missing value for {name}"));
        }
        if let Some(value) = arg.strip_prefix(&(name.to_string() + "=")) {
            return Ok(Some(value.to_string()));
        }
    }
    if required {
        Err(format!("missing required {name}"))
    } else {
        Ok(None)
    }
}
fn read_text(path: &Path) -> Result<String, String> {
    fs::read_to_string(path).map_err(|e| format!("{}: {e}", path.display()))
}
fn read_json(path: &Path) -> Result<Value, String> {
    serde_json::from_str(&read_text(path)?).map_err(|e| format!("invalid JSON: {e}"))
}
fn write_new(path: &Path, text: &str) -> Result<(), String> {
    if path.exists() {
        return Err(format!("output already exists: {}", path.display()));
    }
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .open(path)
        .map_err(|e| e.to_string())?;
    file.write_all(text.as_bytes()).map_err(|e| e.to_string())
}
fn sha256(path: &Path) -> Result<String, String> {
    let mut file = File::open(path).map_err(|e| e.to_string())?;
    let mut digest = Sha256::new();
    let mut buf = [0u8; 1024 * 1024];
    loop {
        let n = file.read(&mut buf).map_err(|e| e.to_string())?;
        if n == 0 {
            break;
        }
        digest.update(&buf[..n]);
    }
    Ok(format!("{:x}", digest.finalize()))
}

fn validate_research(args: &[String]) -> ToolResult {
    let input = PathBuf::from(option(args, "--input", true)?.unwrap());
    let data = read_json(&input)?;
    let mut errors = Vec::new();
    let mut source_count = 0;
    let question = data.get("question").and_then(Value::as_str).unwrap_or("");
    if question.trim().is_empty() {
        errors.push(json!("question_required"));
    }
    let claims = data
        .get("claims")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    if claims.is_empty() {
        errors.push(json!("claims_required"));
    }
    for (i, claim) in claims.iter().enumerate() {
        let prefix = format!("claims[{i}]");
        let object = claim.as_object();
        if object
            .and_then(|m| m.get("text"))
            .and_then(Value::as_str)
            .map(str::trim)
            .unwrap_or("")
            .is_empty()
        {
            errors.push(json!(format!("{prefix}.text_required")));
            continue;
        }
        if !matches!(
            object.and_then(|m| m.get("kind")).and_then(Value::as_str),
            Some("fact") | Some("inference")
        ) {
            errors.push(json!(format!("{prefix}.kind_must_be_fact_or_inference")));
        }
        let sources = object
            .and_then(|m| m.get("sources"))
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default();
        if sources.is_empty() {
            errors.push(json!(format!("{prefix}.source_required")));
            continue;
        }
        for (j, source) in sources.iter().enumerate() {
            source_count += 1;
            let path = format!("{prefix}.sources[{j}]");
            let m = source.as_object();
            let url = m
                .and_then(|x| x.get("url"))
                .and_then(Value::as_str)
                .unwrap_or("");
            if !(url.starts_with("http://") || url.starts_with("https://"))
                || url.chars().any(char::is_whitespace)
            {
                errors.push(json!(format!("{path}.valid_http_url_required")));
            }
            if m.and_then(|x| x.get("title"))
                .and_then(Value::as_str)
                .map(str::trim)
                .unwrap_or("")
                .is_empty()
            {
                errors.push(json!(format!("{path}.title_required")));
            }
            if m.and_then(|x| x.get("evidence"))
                .and_then(Value::as_str)
                .map(str::trim)
                .map(|s| s.chars().count() < 20)
                .unwrap_or(true)
            {
                errors.push(json!(format!("{path}.evidence_text_required")));
            }
        }
    }
    Ok(
        json!({"status": if errors.is_empty() {"ok"} else {"invalid"}, "question": if question.is_empty(){Value::Null}else{json!(question)}, "claims": claims.len(), "sources": source_count, "errors": errors}),
    )
}

fn html_attributes(tag: &str) -> Vec<(String, String)> {
    let bytes = tag.as_bytes();
    let mut result = Vec::new();
    let mut i = 0;
    while i < bytes.len() {
        while i < bytes.len() && (bytes[i].is_ascii_whitespace() || bytes[i] == b'<') {
            i += 1;
        }
        let start = i;
        while i < bytes.len()
            && (bytes[i].is_ascii_alphanumeric() || bytes[i] == b'-' || bytes[i] == b':')
        {
            i += 1;
        }
        if start == i {
            i += 1;
            continue;
        }
        let key = tag[start..i].to_ascii_lowercase();
        while i < bytes.len() && bytes[i].is_ascii_whitespace() {
            i += 1;
        }
        if i >= bytes.len() || bytes[i] != b'=' {
            continue;
        }
        i += 1;
        while i < bytes.len() && bytes[i].is_ascii_whitespace() {
            i += 1;
        }
        if i >= bytes.len() {
            break;
        }
        let quote = bytes[i];
        let (begin, end);
        if quote == b'"' || quote == b'\'' {
            i += 1;
            begin = i;
            while i < bytes.len() && bytes[i] != quote {
                i += 1;
            }
            end = i;
            i += usize::from(i < bytes.len());
        } else {
            begin = i;
            while i < bytes.len() && !bytes[i].is_ascii_whitespace() && bytes[i] != b'>' {
                i += 1;
            }
            end = i;
        }
        result.push((key, tag[begin..end].to_string()));
    }
    result
}
fn html_refs(text: &str) -> (Vec<String>, bool) {
    let lower = text.to_ascii_lowercase();
    let mut refs = Vec::new();
    let mut viewport = false;
    let mut pos = 0;
    while let Some(offset) = lower[pos..].find('<') {
        let start = pos + offset;
        let Some(end_offset) = lower[start..].find('>') else {
            break;
        };
        let end = start + end_offset;
        let tag = &text[start..=end];
        let attrs = html_attributes(tag);
        for (key, value) in &attrs {
            if key == "href" || key == "src" {
                refs.push(value.clone());
            }
        }
        let name = tag
            .split_whitespace()
            .next()
            .unwrap_or("")
            .trim_start_matches('<')
            .to_ascii_lowercase();
        if name == "meta"
            && attrs
                .iter()
                .any(|(k, v)| k == "name" && v.eq_ignore_ascii_case("viewport"))
        {
            viewport = true;
        }
        pos = end + 1;
    }
    (refs, viewport)
}
fn walk_css(dir: &Path, out: &mut Vec<PathBuf>) -> io::Result<()> {
    for item in fs::read_dir(dir)? {
        let path = item?.path();
        if path.is_dir() {
            walk_css(&path, out)?;
        } else if path.extension().and_then(|x| x.to_str()) == Some("css") {
            out.push(path);
        }
    }
    Ok(())
}
fn target(root: &Path, current: &Path, reference: &str) -> Result<Option<PathBuf>, String> {
    if reference.starts_with('#') || reference.starts_with("//") || reference.contains("://") {
        return Ok(None);
    }
    let raw = reference.split(['?', '#']).next().unwrap_or("");
    if raw.is_empty() {
        return Ok(None);
    }
    let candidate = if raw.starts_with('/') {
        root.join(raw.trim_start_matches('/'))
    } else {
        current.parent().unwrap_or(root).join(raw)
    };
    let root = root.canonicalize().map_err(|e| e.to_string())?;
    let candidate = candidate.canonicalize().unwrap_or(candidate);
    if !candidate.starts_with(&root) {
        return Err("path_outside_root".into());
    }
    Ok(Some(if candidate.is_dir() {
        candidate.join("index.html")
    } else {
        candidate
    }))
}
fn check_site(args: &[String]) -> ToolResult {
    let root = PathBuf::from(option(args, "--root", true)?.unwrap())
        .canonicalize()
        .map_err(|_| "root_or_entry_not_found".to_string())?;
    let entry_arg = option(args, "--entry", false)?.unwrap_or_else(|| "index.html".into());
    let entry = root.join(&entry_arg);
    if !entry.is_file() {
        return Err("root_or_entry_not_found".into());
    }
    let (html_refs, viewport) = html_refs(&read_text(&entry)?);
    let mut errors = Vec::new();
    let mut warnings = Vec::new();
    if !viewport {
        warnings.push(json!("missing_meta_viewport"));
    }
    let mut sources = vec![(entry.clone(), html_refs)];
    let mut css_files = Vec::new();
    walk_css(&root, &mut css_files).map_err(|e| e.to_string())?;
    for css in css_files {
        let body = read_text(&css).unwrap_or_default();
        let mut refs = Vec::new();
        let mut pos = 0;
        while let Some(offset) = body[pos..].find("url(") {
            let begin = pos + offset + 4;
            let end = body[begin..]
                .find(')')
                .map(|x| begin + x)
                .unwrap_or(body.len());
            refs.push(
                body[begin..end]
                    .trim()
                    .trim_matches(['\'', '"'])
                    .to_string(),
            );
            pos = end.saturating_add(1);
        }
        sources.push((css, refs));
    }
    let mut checked = vec![entry
        .strip_prefix(&root)
        .unwrap_or(&entry)
        .display()
        .to_string()];
    let mut count = 0;
    for (current, refs) in sources {
        for reference in refs {
            count += 1;
            match target(&root, &current, &reference) { Ok(Some(path)) if !path.is_file() => errors.push(json!({"file":current.strip_prefix(&root).unwrap_or(&current).display().to_string(),"reference":reference,"error":"missing_local_target"})), Ok(Some(path)) => checked.push(path.strip_prefix(&root).unwrap_or(&path).display().to_string()), Err(error) => errors.push(json!({"file":current.strip_prefix(&root).unwrap_or(&current).display().to_string(),"reference":reference,"error":error})), _ => {} }
        }
    }
    Ok(
        json!({"status":if errors.is_empty(){"ok"}else{"invalid"},"root":root,"entry":entry_arg,"checked":checked.into_iter().collect::<BTreeSet<_>>(),"references":count,"errors":errors,"warnings":warnings}),
    )
}

#[derive(Clone)]
struct Table {
    rows: Vec<Map<String, Value>>,
    columns: Vec<String>,
}
fn format_for(path: &Path, requested: Option<String>) -> Result<String, String> {
    if let Some(value) = requested.filter(|x| x != "auto") {
        return Ok(value);
    }
    match path
        .extension()
        .and_then(|x| x.to_str())
        .unwrap_or("")
        .to_ascii_lowercase()
        .as_str()
    {
        "json" => Ok("json".into()),
        "tsv" => Ok("tsv".into()),
        "csv" | "txt" => Ok("csv".into()),
        _ => Err(format!("cannot infer table format from {}", path.display())),
    }
}
fn load_table(path: &Path, format: &str) -> Result<Table, String> {
    if format == "json" {
        let payload = read_json(path)?;
        let rows = payload
            .get("rows")
            .and_then(Value::as_array)
            .cloned()
            .or_else(|| payload.as_array().cloned())
            .ok_or("JSON must be a list of objects or an object with rows")?;
        let mut columns = Vec::new();
        let mut result = Vec::new();
        for row in rows {
            let object = row.as_object().ok_or("JSON rows must be objects")?.clone();
            for key in object.keys() {
                if !columns.contains(key) {
                    columns.push(key.clone());
                }
            }
            result.push(object);
        }
        return Ok(Table {
            rows: result,
            columns,
        });
    }
    let delimiter = if format == "tsv" { b'\t' } else { b',' };
    let mut reader = ReaderBuilder::new()
        .delimiter(delimiter)
        .from_path(path)
        .map_err(|e| e.to_string())?;
    let headers = reader.headers().map_err(|e| e.to_string())?.clone();
    let columns = headers.iter().map(str::to_string).collect::<Vec<_>>();
    if columns.iter().collect::<HashSet<_>>().len() != columns.len() {
        return Err("CSV/TSV header contains duplicate column names".into());
    }
    let mut rows = Vec::new();
    for record in reader.records() {
        let record = record.map_err(|e| e.to_string())?;
        if record.len() != columns.len() {
            return Err("CSV/TSV row has wrong number of fields".into());
        }
        let mut row = Map::new();
        for (key, value) in columns.iter().zip(record.iter()) {
            row.insert(key.clone(), Value::String(value.to_string()));
        }
        rows.push(row);
    }
    Ok(Table { rows, columns })
}
fn marker(row: &Map<String, Value>, keys: &[String]) -> String {
    keys.iter()
        .map(|key| {
            serde_json::to_string(row.get(key).unwrap_or(&Value::String(String::new()))).unwrap()
        })
        .collect::<Vec<_>>()
        .join("\u{1f}")
}
fn condition(value: &Value, rule: &Value) -> Result<bool, String> {
    if !rule.is_object() {
        return Ok(value == rule);
    }
    let map = rule.as_object().unwrap();
    if map.len() != 1 {
        return Err("each filter condition must contain exactly one operator".into());
    }
    let (operator, expected) = map.iter().next().unwrap();
    match operator.as_str() {
        "eq" => Ok(value == expected),
        "ne" => Ok(value != expected),
        "in" => Ok(expected
            .as_array()
            .ok_or("filter in expects a list")?
            .iter()
            .any(|item| item == value)),
        "contains" => Ok(value
            .as_str()
            .map(|text| text.contains(expected.as_str().unwrap_or("")))
            .unwrap_or(false)),
        "not_empty" => {
            let flag = expected
                .as_bool()
                .ok_or("filter not_empty expects boolean")?;
            Ok(if flag {
                !value.is_null() && value.as_str() != Some("")
            } else {
                value.is_null() || value.as_str() == Some("")
            })
        }
        "gt" | "gte" | "lt" | "lte" => {
            let left = value
                .as_f64()
                .or_else(|| value.as_str().and_then(|x| x.parse().ok()))
                .ok_or("numeric filter received non-numeric data")?;
            let right = expected
                .as_f64()
                .or_else(|| expected.as_str().and_then(|x| x.parse().ok()))
                .ok_or("numeric filter received non-numeric data")?;
            Ok(match operator.as_str() {
                "gt" => left > right,
                "gte" => left >= right,
                "lt" => left < right,
                _ => left <= right,
            })
        }
        _ => Err(format!("unsupported filter operator: {operator}")),
    }
}
fn table_transform(args: &[String]) -> ToolResult {
    let input = PathBuf::from(option(args, "--input", true)?.unwrap());
    let output = PathBuf::from(option(args, "--output", true)?.unwrap());
    let same_inode = output.exists()
        && fs::metadata(&input)
            .ok()
            .zip(fs::metadata(&output).ok())
            .map(|(left, right)| {
                use std::os::unix::fs::MetadataExt;
                left.dev() == right.dev() && left.ino() == right.ino()
            })
            .unwrap_or(false);
    if input.canonicalize().ok() == output.canonicalize().ok() || same_inode {
        return Err("refusing to overwrite the input".into());
    }
    let input_format = format_for(&input, option(args, "--input-format", false)?)?;
    let output_format = format_for(&output, option(args, "--output-format", false)?)?;
    let mut table = load_table(&input, &input_format)?;
    let operations = if let Some(path) = option(args, "--operations", false)? {
        let spec = read_json(Path::new(&path))?;
        spec.get("operations")
            .and_then(Value::as_array)
            .cloned()
            .or_else(|| spec.as_array().cloned())
            .ok_or("operations must be a list or object with operations")?
    } else {
        Vec::new()
    };
    let before = table.rows.len();
    for operation in &operations {
        let name = operation
            .get("op")
            .and_then(Value::as_str)
            .ok_or("operation requires op")?;
        match name {
            "clean" => {
                let trim = operation
                    .get("trim_strings")
                    .and_then(Value::as_bool)
                    .unwrap_or(true);
                let collapse = operation
                    .get("collapse_whitespace")
                    .and_then(Value::as_bool)
                    .unwrap_or(false);
                for row in &mut table.rows {
                    for value in row.values_mut() {
                        if let Some(text) = value.as_str() {
                            let mut result = if trim {
                                text.trim().to_string()
                            } else {
                                text.to_string()
                            };
                            if collapse {
                                result = result.split_whitespace().collect::<Vec<_>>().join(" ");
                            }
                            *value = Value::String(result);
                        }
                    }
                }
            }
            "filter" => {
                let where_map = operation
                    .get("where")
                    .and_then(Value::as_object)
                    .ok_or("filter requires where")?;
                for key in where_map.keys() {
                    if !table.columns.contains(key) {
                        return Err(format!("filter columns not found: {key}"));
                    }
                }
                let mut kept = Vec::new();
                for row in table.rows.drain(..) {
                    let matches = where_map
                        .iter()
                        .map(|(key, rule)| condition(row.get(key).unwrap_or(&Value::Null), rule))
                        .collect::<Result<Vec<_>, _>>()?
                        .into_iter()
                        .all(|v| v);
                    if matches {
                        kept.push(row);
                    }
                }
                table.rows = kept;
            }
            "dedupe" => {
                let keys = operation
                    .get("keys")
                    .and_then(Value::as_array)
                    .ok_or("dedupe requires keys")?
                    .iter()
                    .map(|v| {
                        v.as_str()
                            .map(str::to_string)
                            .ok_or("dedupe keys must be strings")
                    })
                    .collect::<Result<Vec<_>, _>>()?;
                let keep = operation
                    .get("keep")
                    .and_then(Value::as_str)
                    .unwrap_or("first");
                if keep == "first" {
                    let mut seen = HashSet::new();
                    table.rows.retain(|row| seen.insert(marker(row, &keys)));
                } else if keep == "last" {
                    let mut positions = HashMap::new();
                    for (index, row) in table.rows.iter().enumerate() {
                        positions.insert(marker(row, &keys), index);
                    }
                    table.rows = table
                        .rows
                        .into_iter()
                        .enumerate()
                        .filter(|(index, row)| positions.get(&marker(row, &keys)) == Some(index))
                        .map(|(_, row)| row)
                        .collect();
                } else {
                    return Err("dedupe keep must be first or last".into());
                }
            }
            "select" => {
                let columns = operation
                    .get("columns")
                    .and_then(Value::as_array)
                    .ok_or("select requires columns")?
                    .iter()
                    .map(|v| {
                        v.as_str()
                            .map(str::to_string)
                            .ok_or("select columns must be strings")
                    })
                    .collect::<Result<Vec<_>, _>>()?;
                if columns.iter().any(|key| !table.columns.contains(key)) {
                    return Err("select column not found".into());
                }
                table.columns = columns;
                for row in &mut table.rows {
                    row.retain(|key, _| table.columns.contains(key));
                }
            }
            "rename" => {
                let mapping = operation
                    .get("mapping")
                    .and_then(Value::as_object)
                    .ok_or("rename requires mapping")?;
                let columns = table
                    .columns
                    .iter()
                    .map(|column| {
                        mapping
                            .get(column)
                            .and_then(Value::as_str)
                            .unwrap_or(column)
                            .to_string()
                    })
                    .collect::<Vec<_>>();
                if columns.iter().any(String::is_empty)
                    || columns.iter().collect::<HashSet<_>>().len() != columns.len()
                {
                    return Err("rename would create duplicate or empty column names".into());
                }
                for row in &mut table.rows {
                    let old = row.clone();
                    row.clear();
                    for (key, value) in old {
                        row.insert(
                            mapping
                                .get(&key)
                                .and_then(Value::as_str)
                                .unwrap_or(&key)
                                .to_string(),
                            value,
                        );
                    }
                }
                table.columns = columns;
            }
            _ => return Err(format!("unsupported operation: {name}")),
        }
    }
    if output_format == "json" {
        write_new(
            &output,
            &(serde_json::to_string_pretty(&table.rows).unwrap() + "\n"),
        )?;
    } else {
        let mut writer = WriterBuilder::new()
            .delimiter(if output_format == "tsv" { b'\t' } else { b',' })
            .from_path(&output)
            .map_err(|e| e.to_string())?;
        writer
            .write_record(&table.columns)
            .map_err(|e| e.to_string())?;
        for row in &table.rows {
            writer
                .write_record(table.columns.iter().map(|key| {
                    row.get(key)
                        .map(|v| {
                            v.as_str()
                                .map(str::to_string)
                                .unwrap_or_else(|| v.to_string())
                        })
                        .unwrap_or_default()
                }))
                .map_err(|e| e.to_string())?;
        }
        writer.flush().map_err(|e| e.to_string())?;
    }
    Ok(
        json!({"status":"ok", "input":input, "output":output, "input_format":input_format, "output_format":output_format, "input_sha256":sha256(&input)?, "output_sha256":sha256(&output)?, "rows_before":before, "rows_after":table.rows.len(), "removed_rows":before-table.rows.len(), "columns":table.columns, "operations":operations.iter().filter_map(|x| x.get("op").and_then(Value::as_str)).collect::<Vec<_>>() }),
    )
}

fn reconcile_group_key(
    row: &Map<String, Value>,
    keys: &[String],
    number: usize,
) -> Result<String, String> {
    let mut values = Vec::new();
    for key in keys {
        let value = row.get(key).ok_or_else(|| {
            format!("linha de dados {number}: chave ausente, vazia ou não escalar")
        })?;
        if value.is_null()
            || value.as_str() == Some("")
            || !(value.is_string() || value.is_number() || value.is_boolean())
        {
            return Err(format!(
                "linha de dados {number}: chave ausente, vazia ou não escalar"
            ));
        }
        values.push(value.clone());
    }
    serde_json::to_string(&values).map_err(|e| e.to_string())
}

fn row_refs(group: &[(usize, Map<String, Value>)]) -> Value {
    json!({
        "count": group.len(),
        "data_row_numbers": group.iter().take(20).map(|(number, _)| number).collect::<Vec<_>>(),
        "row_numbers_truncated": group.len() > 20,
    })
}

fn table_reconcile(args: &[String]) -> ToolResult {
    let left_path = PathBuf::from(option(args, "--left", true)?.unwrap());
    let right_path = PathBuf::from(option(args, "--right", true)?.unwrap());
    let spec_path = PathBuf::from(option(args, "--spec", true)?.unwrap());
    let output = PathBuf::from(option(args, "--output", true)?.unwrap());
    if output.exists() || output.is_symlink() {
        return Err("saída já existe; use outro caminho".into());
    }
    let sources = [
        left_path.canonicalize().map_err(|e| e.to_string())?,
        right_path.canonicalize().map_err(|e| e.to_string())?,
    ];
    if sources.iter().any(|path| {
        fs::metadata(path)
            .map(|m| m.len() > 32 * 1024 * 1024)
            .unwrap_or(true)
    }) || fs::metadata(&spec_path)
        .map(|m| m.len() > 1024 * 1024)
        .unwrap_or(true)
    {
        return Err("entradas excedem 32 MiB ou spec excede 1 MiB".into());
    }
    let before_hashes = [sha256(&sources[0])?, sha256(&sources[1])?];
    let left_format = format_for(&sources[0], option(args, "--left-format", false)?)?;
    let right_format = format_for(&sources[1], option(args, "--right-format", false)?)?;
    let left = load_table(&sources[0], &left_format)?;
    let right = load_table(&sources[1], &right_format)?;
    if left.rows.len().max(right.rows.len()) > 100_000 {
        return Err("limite de 100000 linhas por tabela".into());
    }
    let spec = read_json(&spec_path)?;
    let spec = spec.as_object().ok_or("spec deve ser um objeto")?;
    let allowed: HashSet<&str> = ["keys", "compare_columns", "expected_counts", "max_examples"]
        .into_iter()
        .collect();
    if spec.keys().any(|key| !allowed.contains(key.as_str())) {
        return Err("spec contém campos desconhecidos".into());
    }
    let keys = spec
        .get("keys")
        .and_then(Value::as_array)
        .ok_or("keys exige colunas únicas presentes nas duas tabelas")?
        .iter()
        .map(|value| {
            value
                .as_str()
                .map(str::to_string)
                .ok_or("keys exige colunas únicas presentes nas duas tabelas")
        })
        .collect::<Result<Vec<_>, _>>()?;
    if keys.is_empty()
        || keys.iter().collect::<HashSet<_>>().len() != keys.len()
        || keys
            .iter()
            .any(|key| !left.columns.contains(key) || !right.columns.contains(key))
    {
        return Err("keys exige colunas únicas presentes nas duas tabelas".into());
    }
    let mut columns = if let Some(values) = spec.get("compare_columns") {
        values
            .as_array()
            .ok_or("compare_columns deve conter colunas únicas existentes")?
            .iter()
            .map(|value| {
                value
                    .as_str()
                    .map(str::to_string)
                    .ok_or("compare_columns deve conter colunas únicas existentes")
            })
            .collect::<Result<Vec<_>, _>>()?
    } else {
        let mut values = left.columns.clone();
        for value in &right.columns {
            if !values.contains(value) {
                values.push(value.clone());
            }
        }
        values
    };
    if columns.iter().collect::<HashSet<_>>().len() != columns.len()
        || columns
            .iter()
            .any(|column| !left.columns.contains(column) && !right.columns.contains(column))
    {
        return Err("compare_columns deve conter colunas únicas existentes".into());
    }
    columns.retain(|column| !keys.contains(column));
    let maximum = match spec.get("max_examples") {
        None => 100usize,
        Some(Value::Number(value))
            if value.is_u64() && (1..=1000).contains(&value.as_u64().unwrap()) =>
        {
            value.as_u64().unwrap() as usize
        }
        _ => return Err("max_examples deve estar entre 1 e 1000".into()),
    };
    let grouped = |rows: &[Map<String, Value>],
                   side: &str|
     -> Result<HashMap<String, Vec<(usize, Map<String, Value>)>>, String> {
        let mut result = HashMap::new();
        for (index, row) in rows.iter().enumerate() {
            let key = reconcile_group_key(row, &keys, index + 1)?;
            result
                .entry(key)
                .or_insert_with(Vec::new)
                .push((index + 1, row.clone()));
        }
        let _ = side;
        Ok(result)
    };
    let left_groups = grouped(&left.rows, "left")?;
    let right_groups = grouped(&right.rows, "right")?;
    let mut counts = HashMap::<String, usize>::new();
    for key in [
        "left_rows",
        "right_rows",
        "left_unique_keys",
        "right_unique_keys",
        "only_left_rows",
        "only_right_rows",
        "ambiguous_left_rows",
        "ambiguous_right_rows",
        "equal_pairs",
        "different_pairs",
        "different_fields",
        "left_duplicate_groups",
        "right_duplicate_groups",
        "left_rows_in_duplicate_groups",
        "right_rows_in_duplicate_groups",
    ] {
        counts.insert(key.into(), 0);
    }
    counts.insert("left_rows".into(), left.rows.len());
    counts.insert("right_rows".into(), right.rows.len());
    counts.insert("left_unique_keys".into(), left_groups.len());
    counts.insert("right_unique_keys".into(), right_groups.len());
    for groups in [&left_groups, &right_groups] {
        let side = if std::ptr::eq(groups, &left_groups) {
            "left"
        } else {
            "right"
        };
        let duplicate_groups = groups.values().filter(|rows| rows.len() > 1).count();
        let duplicate_rows = groups
            .values()
            .filter(|rows| rows.len() > 1)
            .map(Vec::len)
            .sum::<usize>();
        counts.insert(format!("{side}_duplicate_groups"), duplicate_groups);
        counts.insert(format!("{side}_rows_in_duplicate_groups"), duplicate_rows);
    }
    let mut examples = Map::new();
    for category in [
        "only_left",
        "only_right",
        "ambiguous",
        "differences",
        "duplicates_left",
        "duplicates_right",
    ] {
        examples.insert(category.into(), Value::Array(Vec::new()));
    }
    let mut total_examples = 0usize;
    let mut add_example = |category: &str, value: Value| {
        if total_examples < maximum {
            examples
                .get_mut(category)
                .and_then(Value::as_array_mut)
                .unwrap()
                .push(value);
            total_examples += 1;
        }
    };
    let mut all_markers = BTreeSet::new();
    all_markers.extend(left_groups.keys().cloned());
    all_markers.extend(right_groups.keys().cloned());
    for marker in all_markers {
        let a = left_groups.get(&marker).cloned().unwrap_or_default();
        let b = right_groups.get(&marker).cloned().unwrap_or_default();
        let key_values: Vec<Value> = serde_json::from_str(&marker).map_err(|e| e.to_string())?;
        let key_object = keys.iter().cloned().zip(key_values).collect::<Map<_, _>>();
        if b.is_empty() {
            *counts.get_mut("only_left_rows").unwrap() += a.len();
            add_example("only_left", json!({"key":key_object,"left":row_refs(&a)}));
        } else if a.is_empty() {
            *counts.get_mut("only_right_rows").unwrap() += b.len();
            add_example("only_right", json!({"key":key_object,"right":row_refs(&b)}));
        } else if a.len() > 1 || b.len() > 1 {
            *counts.get_mut("ambiguous_left_rows").unwrap() += a.len();
            *counts.get_mut("ambiguous_right_rows").unwrap() += b.len();
            add_example(
                "ambiguous",
                json!({"key":key_object,"left":row_refs(&a),"right":row_refs(&b)}),
            );
        } else {
            let mut changes = Vec::new();
            for column in &columns {
                let left_value = a[0].1.get(column);
                let right_value = b[0].1.get(column);
                if left_value != right_value || left_value.is_some() != right_value.is_some() {
                    let mut left_state = Map::new();
                    left_state.insert("present".into(), Value::Bool(left_value.is_some()));
                    if let Some(value) = left_value {
                        left_state.insert("value".into(), value.clone());
                    }
                    let mut right_state = Map::new();
                    right_state.insert("present".into(), Value::Bool(right_value.is_some()));
                    if let Some(value) = right_value {
                        right_state.insert("value".into(), value.clone());
                    }
                    changes.push(json!({"column":column,"left":left_state,"right":right_state}));
                }
            }
            if changes.is_empty() {
                *counts.get_mut("equal_pairs").unwrap() += 1;
            } else {
                *counts.get_mut("different_pairs").unwrap() += 1;
                *counts.get_mut("different_fields").unwrap() += changes.len();
                add_example(
                    "differences",
                    json!({"key":key_object,"left_data_row":a[0].0,"right_data_row":b[0].0,"fields":changes}),
                );
            }
        }
    }
    for (side, groups) in [("left", &left_groups), ("right", &right_groups)] {
        for (marker, group) in groups {
            if group.len() > 1 {
                let values: Vec<Value> = serde_json::from_str(marker).map_err(|e| e.to_string())?;
                let key = keys.iter().cloned().zip(values).collect::<Map<_, _>>();
                let mut example = Map::new();
                example.insert("key".into(), Value::Object(key));
                if let Value::Object(reference) = row_refs(group) {
                    example.extend(reference);
                }
                add_example(&format!("duplicates_{side}"), Value::Object(example));
            }
        }
    }
    let accounted_left = counts["only_left_rows"]
        + counts["ambiguous_left_rows"]
        + counts["equal_pairs"]
        + counts["different_pairs"];
    let accounted_right = counts["only_right_rows"]
        + counts["ambiguous_right_rows"]
        + counts["equal_pairs"]
        + counts["different_pairs"];
    if accounted_left != left.rows.len() || accounted_right != right.rows.len() {
        return Err("invariante de contagens falhou".into());
    }
    let mut mismatches = Map::new();
    if let Some(expected) = spec.get("expected_counts") {
        let expected = expected.as_object().ok_or(
            "expected_counts deve mapear contagens conhecidas para inteiros não negativos",
        )?;
        for (key, value) in expected {
            let expected_value = value.as_u64().filter(|v| *v <= usize::MAX as u64).ok_or(
                "expected_counts deve mapear contagens conhecidas para inteiros não negativos",
            )? as usize;
            let actual = counts.get(key).ok_or(
                "expected_counts deve mapear contagens conhecidas para inteiros não negativos",
            )?;
            if *actual != expected_value {
                mismatches.insert(
                    key.clone(),
                    json!({"expected":expected_value,"actual":actual}),
                );
            }
        }
    }
    let candidates = left_groups.values().filter(|g| g.is_empty()).count()
        + right_groups.values().filter(|g| g.is_empty()).count()
        + left_groups
            .keys()
            .filter(|key| {
                right_groups
                    .get(*key)
                    .map(|g| !g.is_empty())
                    .unwrap_or(false)
                    && (left_groups[*key].len() > 1 || right_groups[*key].len() > 1)
            })
            .count()
        + counts["different_pairs"]
        + counts["left_duplicate_groups"]
        + counts["right_duplicate_groups"];
    let result = json!({"status":if mismatches.is_empty(){"ok"}else{"mismatch"},"keys":keys,"compare_columns":columns,"counts":counts,"counts_validated":true,"expected_count_mismatches":mismatches,"examples":examples,"examples_truncated":candidates > total_examples,"example_count":total_examples,"duplicate_policy":"report_ambiguous_without_pairing","row_number_basis":"data rows, 1-based, excludes CSV header","input_sha256":{"left":before_hashes[0],"right":before_hashes[1]}});
    if before_hashes != [sha256(&sources[0])?, sha256(&sources[1])?] {
        return Err("entrada mudou durante leitura".into());
    }
    let encoded = serde_json::to_string_pretty(&result).map_err(|e| e.to_string())? + "\n";
    if encoded.len() > 8 * 1024 * 1024 {
        return Err("relatório excede 8 MiB; reduza max_examples ou compare_columns".into());
    }
    write_new(&output, &encoded)?;
    Ok(result)
}

fn options_all(args: &[String], name: &str) -> Vec<String> {
    let mut values = Vec::new();
    for (index, arg) in args.iter().enumerate() {
        if arg == name {
            if let Some(value) = args.get(index + 1) {
                values.push(value.clone());
            }
        } else if let Some(value) = arg.strip_prefix(&(name.to_string() + "=")) {
            values.push(value.to_string());
        }
    }
    values
}

fn find_executable(names: &[&str]) -> Option<String> {
    for name in names {
        if let Ok(path) = std::process::Command::new("sh")
            .args(["-c", &format!("command -v {name}")])
            .output()
        {
            if path.status.success() {
                let value = String::from_utf8_lossy(&path.stdout).trim().to_string();
                if !value.is_empty() {
                    return Some(value);
                }
            }
        }
    }
    None
}

fn render_office(input: &Path, render_dir: &Path) -> (Option<String>, Option<String>) {
    if let Err(error) = fs::create_dir_all(render_dir) {
        return (None, Some(error.to_string()));
    }
    let Some(executable) = find_executable(&["soffice", "libreoffice"]) else {
        return (
            None,
            Some("render_skipped: soffice/libreoffice unavailable".into()),
        );
    };
    let mut child = match std::process::Command::new(executable)
        .args([
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            &render_dir.to_string_lossy(),
            &input.to_string_lossy(),
        ])
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
    {
        Ok(child) => child,
        Err(error) => return (None, Some(error.to_string())),
    };
    let deadline = Instant::now() + Duration::from_secs(120);
    loop {
        match child.try_wait() {
            Ok(Some(status)) if status.success() => {
                let output = render_dir
                    .join(input.file_stem().unwrap_or_default())
                    .with_extension("pdf");
                return (Some(output.to_string_lossy().to_string()), None);
            }
            Ok(Some(_)) => {
                let output = child.wait_with_output().ok();
                let message = output
                    .map(|value| {
                        let text = if value.stderr.is_empty() {
                            value.stdout
                        } else {
                            value.stderr
                        };
                        String::from_utf8_lossy(&text)
                            .trim()
                            .chars()
                            .rev()
                            .take(1000)
                            .collect::<String>()
                            .chars()
                            .rev()
                            .collect()
                    })
                    .unwrap_or_else(|| "libreoffice conversion failed".into());
                return (None, Some(message));
            }
            Ok(None) if Instant::now() < deadline => std::thread::sleep(Duration::from_millis(50)),
            Ok(None) => {
                let _ = child.kill();
                let _ = child.wait();
                return (None, Some("render timeout: 120s".into()));
            }
            Err(error) => return (None, Some(error.to_string())),
        }
    }
}

fn validate_package(args: &[String], prefix: &str, text_tag: &str) -> ToolResult {
    let input = PathBuf::from(option(args, "--input", true)?.unwrap());
    if !input.is_file() {
        return Err("input_not_found".into());
    }
    let file = File::open(&input).map_err(|e| e.to_string())?;
    let mut archive = ZipArchive::new(file).map_err(|e| e.to_string())?;
    let text_pattern = Regex::new(&format!(
        r"(?s)<{}\b[^>]*>(.*?)</{}>",
        regex::escape(text_tag),
        regex::escape(text_tag)
    ))
    .map_err(|e| e.to_string())?;
    let marker_pattern =
        Regex::new(r"\{\{\s*([A-Za-z0-9_.-]+)\s*\}\}").map_err(|e| e.to_string())?;
    let mut joined = String::new();
    for index in 0..archive.len() {
        let mut member = archive.by_index(index).map_err(|e| e.to_string())?;
        let name = member.name().to_string();
        let mut bytes = Vec::new();
        member.read_to_end(&mut bytes).map_err(|e| e.to_string())?;
        if name.starts_with(prefix) && name.ends_with(".xml") {
            let raw = String::from_utf8(bytes).map_err(|e| e.to_string())?;
            let mut reader = XmlReader::from_str(&raw);
            loop {
                match reader.read_event() {
                    Ok(Event::Eof) => break,
                    Ok(_) => {}
                    Err(error) => return Err(error.to_string()),
                }
            }
            for capture in text_pattern.captures_iter(&raw) {
                joined.push_str(
                    capture
                        .get(1)
                        .map(|value| value.as_str())
                        .unwrap_or_default(),
                );
                joined.push('\n');
            }
        }
    }
    let unresolved = marker_pattern
        .captures_iter(&joined)
        .filter_map(|capture| capture.get(1).map(|value| value.as_str().to_string()))
        .collect::<BTreeSet<_>>();
    let required = options_all(args, "--require");
    let missing = required
        .iter()
        .filter(|value| !joined.contains(value.as_str()))
        .cloned()
        .collect::<Vec<_>>();
    if !unresolved.is_empty() || !missing.is_empty() {
        return Ok(json!({"status":"error", "unresolved":unresolved, "missing_required":missing}));
    }
    let mut result = json!({"status":"ok", "input":input, "rendered_pdf":Value::Null});
    if let Some(render_dir) = option(args, "--render-dir", false)? {
        let (rendered, note) = render_office(&input, Path::new(&render_dir));
        result["rendered_pdf"] = rendered.map(Value::String).unwrap_or(Value::Null);
        if let Some(note) = note {
            result["render_note"] = Value::String(note);
        }
    }
    Ok(result)
}

fn python_value_string(value: &Value) -> String {
    match value {
        Value::Null => "None".into(),
        Value::Bool(true) => "True".into(),
        Value::Bool(false) => "False".into(),
        Value::String(value) => value.clone(),
        Value::Number(value) => value.to_string(),
        Value::Array(_) | Value::Object(_) => value.to_string(),
    }
}

fn xml_escape_text(value: &str) -> String {
    value
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
}

fn zip_options(member: &zip::read::ZipFile<'_>) -> SimpleFileOptions {
    let mut options = SimpleFileOptions::default().compression_method(member.compression());
    if let Some(mode) = member.unix_mode() {
        options = options.unix_permissions(mode);
    }
    options
}

fn fill_package(args: &[String], prefix: &str, text_tag: &str) -> ToolResult {
    let template = PathBuf::from(option(args, "--template", true)?.unwrap());
    let values_path = PathBuf::from(option(args, "--values", true)?.unwrap());
    let output = PathBuf::from(option(args, "--output", true)?.unwrap());
    let allow_unresolved = args.iter().any(|arg| arg == "--allow-unresolved");
    if !template.is_file() {
        return Ok(json!({"status":"error", "error":"template_not_found"}));
    }
    let same_inode = output.exists()
        && fs::metadata(&template)
            .ok()
            .zip(fs::metadata(&output).ok())
            .map(|(left, right)| {
                use std::os::unix::fs::MetadataExt;
                left.dev() == right.dev() && left.ino() == right.ino()
            })
            .unwrap_or(false);
    if template.canonicalize().ok() == output.canonicalize().ok() || same_inode {
        return Ok(
            json!({"status":"error", "error":"output must be a different file from template"}),
        );
    }
    let values = read_json(&values_path)?;
    let values = values
        .get("values")
        .and_then(Value::as_object)
        .cloned()
        .or_else(|| values.as_object().cloned())
        .ok_or("values JSON must be an object")?;
    for (key, value) in &values {
        let text = python_value_string(value);
        if text.chars().any(
            |character| matches!(character as u32, 0x00..=0x08 | 0x0b..=0x0c | 0x0e..=0x1f | 0x7f),
        ) {
            return Ok(
                json!({"status":"error", "error":format!("value for {key:?} contains an XML-invalid control character")}),
            );
        }
    }
    let source_file = File::open(&template).map_err(|e| e.to_string())?;
    let mut source = ZipArchive::new(source_file).map_err(|e| e.to_string())?;
    let marker_pattern =
        Regex::new(r"\{\{\s*([A-Za-z0-9_.-]+)\s*\}\}").map_err(|e| e.to_string())?;
    let text_pattern = Regex::new(&format!(
        r"(?s)<{}\b([^>]*)>(.*?)</{}>",
        regex::escape(text_tag),
        regex::escape(text_tag)
    ))
    .map_err(|e| e.to_string())?;
    let mut members = Vec::<(String, Vec<u8>, SimpleFileOptions, bool)>::new();
    let mut changed = Map::new();
    let mut missing = BTreeSet::new();
    let mut text_bodies = String::new();
    for index in 0..source.len() {
        let mut member = source.by_index(index).map_err(|e| e.to_string())?;
        let name = member.name().to_string();
        let directory = member.is_dir();
        let options = zip_options(&member);
        let mut content = Vec::new();
        member
            .read_to_end(&mut content)
            .map_err(|e| e.to_string())?;
        if name.starts_with(prefix) && name.ends_with(".xml") {
            let raw = String::from_utf8(content).map_err(|e| e.to_string())?;
            let mut reader = XmlReader::from_str(&raw);
            loop {
                match reader.read_event() {
                    Ok(Event::Eof) => break,
                    Ok(_) => {}
                    Err(error) => return Err(error.to_string()),
                }
            }
            let replaced = text_pattern
                .replace_all(&raw, |capture: &regex::Captures<'_>| {
                    let body = capture
                        .get(2)
                        .map(|value| value.as_str())
                        .unwrap_or_default();
                    let new_body = marker_pattern
                        .replace_all(body, |marker: &regex::Captures<'_>| {
                            let key = marker
                                .get(1)
                                .map(|value| value.as_str())
                                .unwrap_or_default();
                            let Some(value) = values.get(key) else {
                                missing.insert(key.to_string());
                                return marker.get(0).unwrap().as_str().to_string();
                            };
                            let count = changed.get(key).and_then(Value::as_u64).unwrap_or(0) + 1;
                            changed.insert(key.to_string(), json!(count));
                            xml_escape_text(&python_value_string(value))
                        })
                        .into_owned();
                    format!(
                        "<{}{}>{}</{}>",
                        text_tag,
                        capture
                            .get(1)
                            .map(|value| value.as_str())
                            .unwrap_or_default(),
                        new_body,
                        text_tag
                    )
                })
                .into_owned();
            let mut check_reader = XmlReader::from_str(&replaced);
            loop {
                match check_reader.read_event() {
                    Ok(Event::Eof) => break,
                    Ok(_) => {}
                    Err(error) => return Err(error.to_string()),
                }
            }
            for capture in text_pattern.captures_iter(&replaced) {
                text_bodies.push_str(
                    capture
                        .get(2)
                        .map(|value| value.as_str())
                        .unwrap_or_default(),
                );
            }
            content = replaced.into_bytes();
        }
        members.push((name, content, options, directory));
    }
    let unresolved = marker_pattern
        .captures_iter(&text_bodies)
        .filter_map(|capture| capture.get(1).map(|value| value.as_str().to_string()))
        .collect::<BTreeSet<_>>();
    if (!missing.is_empty() || !unresolved.is_empty()) && !allow_unresolved {
        return Ok(
            json!({"status":"error", "error":"unresolved_markers", "missing_values":missing, "unresolved":unresolved}),
        );
    }
    if let Some(parent) = output.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let output_file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .open(&output)
        .map_err(|e| e.to_string())?;
    let mut target = ZipWriter::new(output_file);
    for (name, content, options, directory) in members {
        if directory {
            target
                .add_directory(name, options)
                .map_err(|e| e.to_string())?;
        } else {
            target
                .start_file(name, options)
                .map_err(|e| e.to_string())?;
            target.write_all(&content).map_err(|e| e.to_string())?;
        }
    }
    target.finish().map_err(|e| e.to_string())?;
    Ok(
        json!({"status":"ok", "output":output, "replaced":changed, "missing":missing, "unresolved":unresolved}),
    )
}

const SQLITE_MAX_RESULT: usize = 1024 * 1024;
const SQLITE_MAX_CELL: usize = 64 * 1024;
const SQLITE_READ_PRAGMAS: &[&str] = &[
    "table_info",
    "table_xinfo",
    "index_info",
    "index_xinfo",
    "index_list",
    "foreign_key_list",
];

fn sqlite_value(row: &Row<'_>, index: usize) -> Result<Value, String> {
    match row.get::<_, SqlValue>(index).map_err(|e| e.to_string())? {
        SqlValue::Null => Ok(Value::Null),
        SqlValue::Integer(v) => Ok(json!(v)),
        SqlValue::Real(v) => Ok(json!(v)),
        SqlValue::Text(v) => {
            if v.len() > SQLITE_MAX_CELL {
                return Err(
                    "célula excede 64 KiB; selecione substrings ou agregue a consulta".into(),
                );
            }
            Ok(Value::String(v))
        }
        SqlValue::Blob(v) => {
            if v.len() > SQLITE_MAX_CELL {
                return Err(
                    "célula excede 64 KiB; selecione substrings ou agregue a consulta".into(),
                );
            }
            Ok(json!({"type":"blob", "base64":base64(&v)}))
        }
    }
}
fn base64(data: &[u8]) -> String {
    const TABLE: &[u8] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut out = String::new();
    for chunk in data.chunks(3) {
        let a = chunk[0] as u32;
        let b = chunk.get(1).copied().unwrap_or(0) as u32;
        let c = chunk.get(2).copied().unwrap_or(0) as u32;
        let value = (a << 16) | (b << 8) | c;
        out.push(TABLE[((value >> 18) & 63) as usize] as char);
        out.push(TABLE[((value >> 12) & 63) as usize] as char);
        out.push(if chunk.len() > 1 {
            TABLE[((value >> 6) & 63) as usize] as char
        } else {
            '='
        });
        out.push(if chunk.len() > 2 {
            TABLE[(value & 63) as usize] as char
        } else {
            '='
        });
    }
    out
}
fn sqlite_json_to_value(value: &Value) -> Result<SqlValue, String> {
    match value {
        Value::Null => Ok(SqlValue::Null),
        Value::Bool(v) => Ok(SqlValue::Integer(i64::from(*v))),
        Value::Number(v) if v.is_i64() => Ok(SqlValue::Integer(v.as_i64().unwrap())),
        Value::Number(v) if v.is_u64() && v.as_u64().unwrap() <= i64::MAX as u64 => {
            Ok(SqlValue::Integer(v.as_u64().unwrap() as i64))
        }
        Value::Number(v) if v.is_f64() => Ok(SqlValue::Real(v.as_f64().unwrap())),
        Value::String(v) => Ok(SqlValue::Text(v.clone())),
        _ => Err("params deve ser lista ou objeto de valores escalares JSON".into()),
    }
}

fn sqlite_authorize(context: AuthContext<'_>) -> Authorization {
    match context.action {
        AuthAction::Select | AuthAction::Read { .. } | AuthAction::Recursive => {
            Authorization::Allow
        }
        AuthAction::Pragma { pragma_name, .. }
            if SQLITE_READ_PRAGMAS
                .iter()
                .any(|allowed| allowed.eq_ignore_ascii_case(pragma_name)) =>
        {
            Authorization::Allow
        }
        AuthAction::Function { function_name } => {
            let denied = [
                "load_extension",
                "writefile",
                "readfile",
                "edit",
                "eval",
                "fts3_tokenizer",
            ];
            if denied
                .iter()
                .any(|name| name.eq_ignore_ascii_case(function_name))
            {
                Authorization::Deny
            } else {
                Authorization::Allow
            }
        }
        _ => Authorization::Deny,
    }
}

fn sqlite_export(path: &Path, format: &str, payload: &Value) -> Result<String, String> {
    let columns = payload
        .get("columns")
        .and_then(Value::as_array)
        .ok_or("resultado sem colunas")?;
    let rows = payload
        .get("rows")
        .and_then(Value::as_array)
        .ok_or("resultado sem linhas")?;
    if format == "json" {
        return write_new(
            path,
            &(serde_json::to_string_pretty(payload).map_err(|e| e.to_string())? + "\n"),
        )
        .map(|_| path.to_string_lossy().to_string());
    }
    let mut bytes = Vec::new();
    {
        let mut writer = WriterBuilder::new().from_writer(&mut bytes);
        writer
            .write_record(
                columns
                    .iter()
                    .map(|value| value.as_str().unwrap_or_default()),
            )
            .map_err(|e| e.to_string())?;
        for row in rows {
            let values = row
                .as_array()
                .ok_or("linha de resultado inválida")?
                .iter()
                .map(|value| {
                    if value.is_object() {
                        serde_json::to_string(value).unwrap_or_default()
                    } else if let Some(text) = value.as_str() {
                        text.to_string()
                    } else if value.is_null() {
                        String::new()
                    } else {
                        value.to_string()
                    }
                })
                .collect::<Vec<_>>();
            writer.write_record(values).map_err(|e| e.to_string())?;
        }
        writer.flush().map_err(|e| e.to_string())?;
    }
    write_new(
        path,
        std::str::from_utf8(&bytes).map_err(|e| e.to_string())?,
    )
    .map(|_| path.to_string_lossy().to_string())
}

fn sqlite_read(args: &[String]) -> ToolResult {
    let database = PathBuf::from(option(args, "--database", true)?.unwrap());
    if !database.is_file() {
        return Err("database deve ser arquivo regular".into());
    }
    let mode = option(args, "--mode", false)?.unwrap_or_else(|| "schema".into());
    if mode != "schema" && mode != "query" {
        return Err("mode must be schema or query".into());
    }
    let spec = if let Some(path) = option(args, "--spec", false)? {
        let spec_path = PathBuf::from(path);
        let metadata = fs::metadata(&spec_path).map_err(|e| e.to_string())?;
        if metadata.len() > SQLITE_MAX_RESULT as u64 {
            return Err("spec excede 1 MiB".into());
        }
        read_json(&spec_path)?
    } else {
        json!({})
    };
    let object = spec.as_object().ok_or("spec deve ser um objeto JSON")?;
    let allowed: HashSet<&str> = ["sql", "params", "max_rows", "timeout_seconds"]
        .into_iter()
        .collect();
    if object.keys().any(|key| !allowed.contains(key.as_str())) {
        return Err("spec contém campos desconhecidos".into());
    }
    let maximum = match object.get("max_rows") {
        None => 100usize,
        Some(Value::Number(value)) if value.is_u64() => {
            let value = value.as_u64().unwrap();
            if !(1..=10000).contains(&value) {
                return Err("max_rows deve estar entre 1 e 10000".into());
            }
            value as usize
        }
        _ => return Err("max_rows deve estar entre 1 e 10000".into()),
    };
    let timeout = match object.get("timeout_seconds") {
        None => 3.0,
        Some(Value::Number(value)) => value.as_f64().unwrap_or(-1.0),
        _ => -1.0,
    };
    if !(0.1..=30.0).contains(&timeout) {
        return Err("timeout_seconds deve estar entre 0.1 e 30".into());
    }

    let (sql, params) = if mode == "schema" {
        if object.contains_key("sql") || object.contains_key("params") {
            return Err("schema não aceita sql/params".into());
        }
        (
            "SELECT type, name, tbl_name, sql FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name".to_string(),
            Value::Array(Vec::new()),
        )
    } else {
        let sql = object
            .get("sql")
            .and_then(Value::as_str)
            .ok_or("sql obrigatório, até 128 KiB")?;
        if sql.trim().is_empty() || sql.len() > 128 * 1024 || sql.contains(';') {
            return Err("sql obrigatório, até 128 KiB; múltiplas instruções são recusadas".into());
        }
        let params = object.get("params").cloned().unwrap_or_else(|| json!([]));
        match &params {
            Value::Array(values)
                if values.iter().all(|v| {
                    matches!(
                        v,
                        Value::Null | Value::Bool(_) | Value::Number(_) | Value::String(_)
                    )
                }) => {}
            Value::Object(values)
                if values.values().all(|v| {
                    matches!(
                        v,
                        Value::Null | Value::Bool(_) | Value::Number(_) | Value::String(_)
                    )
                }) => {}
            _ => return Err("params deve ser lista ou objeto de valores escalares JSON".into()),
        }
        (sql.to_string(), params)
    };

    let start = Instant::now();
    let deadline = start + Duration::from_secs_f64(timeout);
    let connection = Connection::open_with_flags(database, OpenFlags::SQLITE_OPEN_READ_ONLY)
        .map_err(|e| e.to_string())?;
    connection
        .busy_timeout(Duration::from_secs_f64(timeout.min(1.0)))
        .map_err(|e| e.to_string())?;
    connection
        .pragma_update(None, "query_only", "ON")
        .map_err(|e| e.to_string())?;
    connection
        .pragma_update(None, "trusted_schema", "OFF")
        .map_err(|e| e.to_string())?;
    connection.set_limit(Limit::SQLITE_LIMIT_LENGTH, SQLITE_MAX_RESULT as i32);
    connection.set_limit(Limit::SQLITE_LIMIT_SQL_LENGTH, 128 * 1024);
    connection.set_limit(Limit::SQLITE_LIMIT_COLUMN, 256);
    connection
        .execute_batch("BEGIN")
        .map_err(|e| e.to_string())?;
    connection.authorizer(Some(sqlite_authorize));
    let interrupted = Arc::new(AtomicBool::new(false));
    let progress_interrupted = Arc::clone(&interrupted);
    connection.progress_handler(
        1000,
        Some(move || {
            if Instant::now() >= deadline {
                progress_interrupted.store(true, Ordering::Relaxed);
                true
            } else {
                false
            }
        }),
    );

    let mut statement = connection.prepare(&sql).map_err(|e| {
        if interrupted.load(Ordering::Relaxed) {
            "consulta excedeu timeout_seconds".to_string()
        } else {
            e.to_string()
        }
    })?;
    if statement.column_count() == 0 {
        return Err("consulta não produz tabela".into());
    }
    let columns = statement
        .column_names()
        .iter()
        .map(|s| s.to_string())
        .collect::<Vec<_>>();
    let mut cursor = if let Value::Object(values) = &params {
        let mut named_values = Vec::<(String, SqlValue)>::new();
        for (name, value) in values {
            let parameter_name =
                if name.starts_with(':') || name.starts_with('@') || name.starts_with('$') {
                    name.clone()
                } else {
                    format!(":{name}")
                };
            named_values.push((parameter_name, sqlite_json_to_value(value)?));
        }
        let named_params = named_values
            .iter()
            .map(|(name, value)| (name.as_str(), value as &dyn ToSql))
            .collect::<Vec<_>>();
        statement
            .query(named_params.as_slice())
            .map_err(|e| e.to_string())?
    } else {
        let positional = params
            .as_array()
            .unwrap()
            .iter()
            .map(sqlite_json_to_value)
            .collect::<Result<Vec<_>, _>>()?;
        statement
            .query(rusqlite::params_from_iter(positional.iter()))
            .map_err(|e| e.to_string())?
    };
    let mut rows = Vec::new();
    let mut result_size = 0usize;
    while rows.len() < maximum {
        let Some(row) = cursor.next().map_err(|e| {
            if interrupted.load(Ordering::Relaxed) {
                "consulta excedeu timeout_seconds".to_string()
            } else {
                e.to_string()
            }
        })?
        else {
            break;
        };
        let encoded = (0..columns.len())
            .map(|index| sqlite_value(row, index))
            .collect::<Result<Vec<_>, _>>()?;
        result_size += serde_json::to_vec(&encoded)
            .map_err(|e| e.to_string())?
            .len();
        if result_size > SQLITE_MAX_RESULT {
            return Err("resultado excede 1 MiB; reduza colunas/linhas".into());
        }
        rows.push(Value::Array(encoded));
    }
    let truncated = if rows.len() >= maximum {
        cursor
            .next()
            .map_err(|e| {
                if interrupted.load(Ordering::Relaxed) {
                    "consulta excedeu timeout_seconds".to_string()
                } else {
                    e.to_string()
                }
            })?
            .is_some()
    } else {
        false
    };
    if interrupted.load(Ordering::Relaxed) || Instant::now() >= deadline {
        return Err("consulta excedeu timeout_seconds".into());
    }
    let mut payload = json!({
        "status":"ok",
        "mode":mode,
        "columns":columns,
        "rows":rows,
        "returned_rows":rows.len(),
        "truncated":truncated,
        "max_rows":maximum,
        "read_only":true,
        "snapshot":"SQLite read transaction (includes committed WAL)",
        "elapsed_seconds":((Instant::now() - start).as_secs_f64() * 1000.0).round() / 1000.0,
    });
    if let Some(output) = option(args, "--output", false)? {
        let output_path = PathBuf::from(output);
        let format = option(args, "--output-format", false)?.unwrap_or_else(|| {
            if output_path
                .extension()
                .and_then(|s| s.to_str())
                .map(|s| s.eq_ignore_ascii_case("csv"))
                .unwrap_or(false)
            {
                "csv".into()
            } else {
                "json".into()
            }
        });
        if format != "json" && format != "csv" {
            return Err("output-format deve ser json ou csv".into());
        }
        let written = sqlite_export(&output_path, &format, &payload)?;
        if let Some(map) = payload.as_object_mut() {
            map.remove("rows");
            map.insert("output".into(), Value::String(written));
            map.insert("output_format".into(), Value::String(format));
        }
    }
    Ok(payload)
}
