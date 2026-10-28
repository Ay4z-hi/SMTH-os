use std::{collections::HashMap, fs, path::PathBuf, thread::sleep, time::{Duration, Instant}};

const FREEZE_AFTER: Duration = Duration::from_secs(5);

struct App { cgroup: PathBuf, backgrounded_at: Option<Instant>, frozen: bool }

fn set_freeze(cg: &PathBuf, on: bool) {
    let _ = fs::write(cg.join("cgroup.freeze"), if on { "1" } else { "0" });
}

fn memory_pressure_high() -> bool {
    fs::read_to_string("/proc/pressure/memory").ok()
        .and_then(|s| s.split_whitespace().find(|w| w.starts_with("avg10="))
            .and_then(|w| w[6..].parse::<f32>().ok()))
        .map(|v| v > 10.0).unwrap_or(false)
}

// TODO: query smthd over $XDG_RUNTIME_DIR/smth-wm.sock for (app_id, is_foreground).
fn poll_foreground_state() -> Vec<(String, bool)> { vec![] }

fn reap_oldest_frozen(apps: &mut HashMap<String, App>) {
    let victim = apps.iter().filter(|(_, a)| a.frozen)
        .min_by_key(|(_, a)| a.backgrounded_at)
        .map(|(k, a)| (k.clone(), a.cgroup.clone()));
    if let Some((k, cg)) = victim {
        let _ = fs::write(cg.join("cgroup.kill"), "1");
        apps.remove(&k);
    }
}

fn main() {
    let mut apps: HashMap<String, App> = HashMap::new();
    loop {
        for (id, fg) in poll_foreground_state() {
            let a = apps.entry(id.clone()).or_insert_with(|| App {
                cgroup: PathBuf::from(format!("/sys/fs/cgroup/smth.slice/app-{id}.scope")),
                backgrounded_at: None, frozen: false });
            if fg {
                if a.frozen { set_freeze(&a.cgroup, false); a.frozen = false; }
                a.backgrounded_at = None;
            } else {
                let t = *a.backgrounded_at.get_or_insert_with(Instant::now);
                if !a.frozen && t.elapsed() >= FREEZE_AFTER { set_freeze(&a.cgroup, true); a.frozen = true; }
            }
        }
        if memory_pressure_high() { reap_oldest_frozen(&mut apps); }
        sleep(Duration::from_millis(500));
    }
}
