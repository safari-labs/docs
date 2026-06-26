use std::{
    env,
    path::Path,
    process::{Command, exit},
};

const LOCAL_IMAGE_NAME: &str = "ffed_rs:local";
const LOCAL_IMAGE_ARCHIVE: &str = "/tmp/ffed_rs-jetson-image.tar";
const LOCAL_IMAGE_PLATFORM: &str = "linux/arm64";

const FIRE_RISK_LOCAL_IMAGE_NAME: &str = "fire_risk_model:local";
const FIRE_RISK_LOCAL_IMAGE_ARCHIVE: &str = "/tmp/fire_risk_model-jetson-image.tar";

fn main() {
    let args: Vec<String> = env::args().collect();
    let task = args.get(1).map(|s| s.as_str());
    let target = parse_target(&args[2..]);
    match task {
        Some("portainer") => portainer(),
        Some("deploy") => deploy(&target),
        Some("deploy-local") => deploy_local(&target),
        _ => {
            eprintln!("Usage: cargo xtask <task> [--target <host>]");
            eprintln!("Tasks:");
            eprintln!("  portainer    Start Portainer and open browser");
            eprintln!("  deploy       Run the Ansible playbook");
            eprintln!("  deploy-local Build the image locally and deploy with Ansible");
            eprintln!("Options:");
            eprintln!("  --target <host>  Ansible inventory host to deploy to (default: jetson)");
            exit(1);
        }
    }
}

fn parse_target(args: &[String]) -> String {
    let mut iter = args.iter();
    while let Some(arg) = iter.next() {
        if arg == "--target" {
            if let Some(val) = iter.next() {
                return val.clone();
            }
        }
    }
    "jetson".to_string()
}

fn portainer() {
    let root = project_root();

    let compose = root.join("portainer").join("compose.yml");

    run(Command::new("docker")
        .args(["compose", "-f", compose.to_str().unwrap(), "up", "-d"]));

    let url = "http://portainer.localhost";

    #[cfg(target_os = "macos")]
    run(Command::new("open").arg(url));

    #[cfg(target_os = "windows")]
    run(Command::new("cmd").args(["/c", "start", url]));

    #[cfg(target_os = "linux")]
    run(Command::new("xdg-open").arg(url));
}

fn deploy(target: &str) {
    let root = project_root();
    run(Command::new("ansible-playbook")
        .arg(root.join("ansible").join("deploy-ffed_rs.yml"))
        .args(["-e", &format!("target={target}")]));
}

fn deploy_local(target: &str) {
    let root = project_root();

    run(Command::new("docker")
        .arg("version"));

    run(Command::new("docker")
        .args(["buildx", "version"]));

    let mut build = Command::new("docker");
    build.current_dir(&root);
    build.args([
        "buildx",
        "build",
        "--platform",
        LOCAL_IMAGE_PLATFORM,
        "--progress",
        "plain",
    ]);
    build.args([
        "--load",
        "-f",
        "docker/Dockerfile.ffed_rs",
        "-t",
        LOCAL_IMAGE_NAME,
        ".",
    ]);
    run(&mut build);

    if let Some(parent) = Path::new(LOCAL_IMAGE_ARCHIVE).parent() {
        std::fs::create_dir_all(parent).unwrap_or_else(|e| {
            eprintln!("Failed to create {:?}: {}", parent, e);
            exit(1);
        });
    }

    run(Command::new("docker")
        .args(["save", "-o", LOCAL_IMAGE_ARCHIVE, LOCAL_IMAGE_NAME]));

    let mut fire_risk_build = Command::new("docker");
    fire_risk_build.current_dir(&root);
    fire_risk_build.args([
        "buildx", "build",
        "--platform", LOCAL_IMAGE_PLATFORM,
        "--progress", "plain",
        "--load",
        "-f", "docker/Dockerfile.fire_risk_model",
        "-t", FIRE_RISK_LOCAL_IMAGE_NAME,
        "fire_risk_model",
    ]);
    run(&mut fire_risk_build);

    if let Some(parent) = Path::new(FIRE_RISK_LOCAL_IMAGE_ARCHIVE).parent() {
        std::fs::create_dir_all(parent).unwrap_or_else(|e| {
            eprintln!("Failed to create {:?}: {}", parent, e);
            exit(1);
        });
    }

    run(Command::new("docker")
        .args(["save", "-o", FIRE_RISK_LOCAL_IMAGE_ARCHIVE, FIRE_RISK_LOCAL_IMAGE_NAME]));

    run(Command::new("ansible-playbook")
        .arg(root.join("ansible").join("deploy-ffed_rs.yml"))
        .args([
            "-e", "app_build_local=true",
            "-e", "app_skip_local_build=true",
            "-e", "fire_risk_build_local=true",
            "-e", "fire_risk_skip_local_build=true",
            "-e", &format!("target={target}"),
        ]));
}

fn run(cmd: &mut Command) {
    let status = cmd.status().unwrap_or_else(|e| {
        eprintln!("Failed to run {:?}: {}", cmd.get_program(), e);
        exit(1);
    });
    if !status.success() {
        exit(status.code().unwrap_or(1));
    }
}

fn project_root() -> std::path::PathBuf {
    // CARGO_MANIFEST_DIR is xtask/, so go up one level
    std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .to_path_buf()
}
