"""Generate a Tauri 2 + React project from an Arabic application source."""

import json
import os
import re

from .android import parse_android


def _safe_id(title):
    value = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return value or "albaa-app"


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(content)


def _react_source(program):
    widgets = []
    for widget in program.widgets:
        text = json.dumps(widget.text, ensure_ascii=False)
        style = {
            "color": widget.text_color or ("#ffffff" if widget.kind == "زر" else "#111827"),
            "backgroundColor": widget.background_color or ("#2563eb" if widget.kind == "زر" else "#ffffff"),
        }
        style_json = json.dumps(style, ensure_ascii=False)
        if widget.kind == "نص":
            widgets.append(f"<p style={{{style_json}}}>{{{text}}}</p>")
        elif widget.kind == "زر":
            widgets.append(f"<button style={{{style_json}}}>{{{text}}}</button>")
        else:
            field_type = "password" if widget.kind == "كلمة_مرور" else "text"
            widgets.append(f"<input type=\"{field_type}\" placeholder={{{text}}} style={{{style_json}}} />")
    navigation = "".join(f"<button>{{{json.dumps(item, ensure_ascii=False)}}}</button>" for item in program.bottom_navigation)
    title = json.dumps(program.title, ensure_ascii=False)
    background = json.dumps(program.background_color or "#ffffff")
    try:
        rgb = (program.background_color or "#ffffff").lstrip("#")
        brightness = sum(int(rgb[index:index + 2], 16) * weight for index, weight in ((0, 299), (2, 587), (4, 114))) / 1000
    except (TypeError, ValueError):
        brightness = 255
    foreground = json.dumps("#f2f2f2" if brightness < 128 else "#0f172a")
    return f'''import "./app.css";

export default function App() {{
  return <main className="app" dir="rtl" style={{{{backgroundColor: {background}, color: {foreground}}}}}>
    <header>{title}</header>
    <section className="content">{"".join(widgets)}</section>
    <nav>{navigation}</nav>
  </main>;
}}
'''


def export_tauri_project(source, directory):
    """Create editable sources and CI builds for desktop and mobile platforms."""
    program = parse_android(source)
    app_id = _safe_id(program.title)
    package = {
        "name": app_id,
        "private": True,
        "version": "0.1.0",
        "type": "module",
        "scripts": {"dev": "vite", "build": "tsc && vite build", "tauri": "tauri"},
        "dependencies": {"@tauri-apps/api": "^2", "react": "^19", "react-dom": "^19"},
        "devDependencies": {"@tauri-apps/cli": "^2", "@types/react": "^19", "@types/react-dom": "^19", "@vitejs/plugin-react": "latest", "typescript": "latest", "vite": "latest"},
    }
    _write(os.path.join(directory, "package.json"), json.dumps(package, ensure_ascii=False, indent=2))
    _write(os.path.join(directory, "index.html"), '<div id="root"></div><script type="module" src="/src/main.tsx"></script>')
    _write(os.path.join(directory, "src", "main.tsx"), 'import React from "react";\nimport {createRoot} from "react-dom/client";\nimport App from "./App";\ncreateRoot(document.getElementById("root")!).render(<App />);\n')
    _write(os.path.join(directory, "src", "App.tsx"), _react_source(program))
    _write(os.path.join(directory, "src", "app.css"), '''*{box-sizing:border-box}html,body,#root{margin:0;min-height:100%;font-family:"Segoe UI",Tahoma,sans-serif}.app{min-height:100vh;display:flex;flex-direction:column;padding:18px;color:#f2f2f2}.app header{text-align:center;font-weight:700;padding:14px;border-bottom:1px solid #2f3336}.content{display:flex;flex:1;flex-direction:column;gap:14px;padding:18px;max-width:760px;width:100%;margin:auto}.content>*{width:100%;padding:12px;border:1px solid #94a3b8;border-radius:10px;font:inherit}button{cursor:pointer;transition:filter .08s ease,transform .08s ease}button:active{filter:brightness(.72);transform:scale(.985)}nav{display:flex;justify-content:space-around;border-top:1px solid #2f3336;padding:8px}nav button{border:0;background:transparent;color:inherit;padding:10px}nav button:active{background:rgba(0,0,0,.18)}@media(min-width:900px){.content{max-width:900px}.app{padding-inline:8vw}}''')
    _write(os.path.join(directory, "src-tauri", "Cargo.toml"), f'''[package]\nname = "{app_id.replace('-', '_')}"\nversion = "0.1.0"\nedition = "2021"\n[build-dependencies]\ntauri-build = {{ version = "2", features = [] }}\n[dependencies]\ntauri = {{ version = "2", features = [] }}\n''')
    _write(os.path.join(directory, "src-tauri", "build.rs"), "fn main() { tauri_build::build() }\n")
    _write(os.path.join(directory, "src-tauri", "src", "main.rs"), "fn main() { tauri::Builder::default().run(tauri::generate_context!()).expect(\"error running app\"); }\n")
    config = {"$schema": "https://schema.tauri.app/config/2", "productName": program.title, "version": "0.1.0", "identifier": f"com.albaa.{app_id.replace('-', '')}", "build": {"beforeDevCommand": "npm run dev", "devUrl": "http://localhost:1420", "beforeBuildCommand": "npm run build", "frontendDist": "../dist"}, "app": {"windows": [{"title": program.title, "width": 1000, "height": 700}]}, "bundle": {"active": True, "targets": "all"}}
    _write(os.path.join(directory, "src-tauri", "tauri.conf.json"), json.dumps(config, ensure_ascii=False, indent=2))
    _write(os.path.join(directory, "vite.config.ts"), 'import {defineConfig} from "vite"; import react from "@vitejs/plugin-react"; export default defineConfig({plugins:[react()],server:{port:1420,strictPort:true}});\n')
    _write(os.path.join(directory, "tsconfig.json"), '{"compilerOptions":{"target":"ES2022","jsx":"react-jsx","module":"ESNext","moduleResolution":"Bundler","strict":true},"include":["src"]}')
    _write(os.path.join(directory, ".github", "workflows", "build-all.yml"), '''name: Build all platforms
on: { workflow_dispatch: {} }
jobs:
  web:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 22 }
      - run: npm install
      - run: npm run build
      - uses: actions/upload-artifact@v4
        with:
          name: albaa-web
          path: dist/**
  desktop:
    strategy:
      fail-fast: false
      matrix:
        os: [windows-latest, ubuntu-24.04, macos-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 22 }
      - uses: dtolnay/rust-toolchain@stable
      - name: Linux dependencies
        if: runner.os == 'Linux'
        run: sudo apt-get update && sudo apt-get install -y libwebkit2gtk-4.1-dev libappindicator3-dev librsvg2-dev patchelf
      - run: npm install
      - run: npm run tauri build
      - uses: actions/upload-artifact@v4
        with:
          name: albaa-${{ runner.os }}
          path: src-tauri/target/release/bundle/**
  android:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 22 }
      - uses: dtolnay/rust-toolchain@stable
      - uses: actions/setup-java@v4
        with: { distribution: temurin, java-version: 17 }
      - run: npm install
      - run: npm run tauri android init
      - run: npm run tauri android build -- --apk
      - uses: actions/upload-artifact@v4
        with:
          name: albaa-android
          path: src-tauri/gen/android/app/build/outputs/**/*.apk
  ios:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 22 }
      - uses: dtolnay/rust-toolchain@stable
      - run: npm install
      - run: npm run tauri ios init
      - run: npm run tauri ios build -- --debug
      - uses: actions/upload-artifact@v4
        with:
          name: albaa-ios-project
          path: src-tauri/gen/apple/**
''')
    _write(os.path.join(directory, ".github", "workflows", "build-windows.yml"), '''name: Build Windows application
on: { workflow_dispatch: {} }
jobs:
  windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 22 }
      - uses: dtolnay/rust-toolchain@stable
      - run: npm install
      - run: npm run tauri build
      - uses: actions/upload-artifact@v4
        with:
          name: albaa-windows-app
          path: src-tauri/target/release/bundle/**
          if-no-files-found: error
''')
    _write(os.path.join(directory, ".github", "workflows", "build-ios.yml"), '''name: Build iOS simulator application
on:
  workflow_dispatch:
jobs:
  ios-simulator:
    runs-on: macos-latest
    timeout-minutes: 45
    steps:
      - name: Checkout project
        uses: actions/checkout@v4
      - name: Set up Node.js
        uses: actions/setup-node@v4
        with: { node-version: 22, cache: npm }
      - name: Set up Rust
        uses: dtolnay/rust-toolchain@stable
        with:
          targets: aarch64-apple-ios-sim
      - name: Install dependencies
        run: npm install
      - name: Initialize iOS project
        run: npm run tauri ios init -- --ci
      - name: Build iOS simulator app
        run: npm run tauri ios build -- --debug --target aarch64-sim
      - name: Upload iOS simulator app
        uses: actions/upload-artifact@v4
        with:
          name: albaa-ios-simulator
          path: src-tauri/gen/apple/build/**
          if-no-files-found: error
''')
    _write(os.path.join(directory, "README.md"), "# تطبيق الباء\n\nمشروع Tauri 2 قابل للبناء على Windows وLinux وmacOS، والتهيئة لـ Android وiOS عبر أوامر Tauri mobile. يتطلب بناء iOS جهاز macOS وXcode.\n")
    return directory
