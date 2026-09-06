#!/usr/bin/env sh
# Build the browser checker into web/pkg/. Needs the wasm32-unknown-unknown target, wasm-bindgen-cli
# (same version as the wasm-bindgen crate in Cargo.lock), clang (for zstd) and optionally wasm-opt.
set -e
cd "$(dirname "$0")/.."
cargo build --lib --release --target wasm32-unknown-unknown --no-default-features --features wasm
wasm-bindgen --target no-modules --no-typescript --out-dir web/pkg target/wasm32-unknown-unknown/release/geoparquet_conf.wasm
# Optional size optimisation. Rust emits post-MVP features (bulk memory, sign extension, ...), which
# need binaryen >= 116; older versions write modules browsers reject, so they are skipped.
if command -v wasm-opt >/dev/null 2>&1; then
  VER=$(wasm-opt --version | sed -E 's/[^0-9]*([0-9]+).*/\1/')
  if [ "${VER:-0}" -ge 116 ]; then
    wasm-opt -Oz --enable-bulk-memory --enable-nontrapping-float-to-int --enable-sign-ext \
      --enable-mutable-globals --enable-multivalue --enable-reference-types \
      -o web/pkg/opt.wasm web/pkg/geoparquet_conf_bg.wasm && mv web/pkg/opt.wasm web/pkg/geoparquet_conf_bg.wasm
  else
    echo "wasm-opt $VER is too old (< 116); keeping the unoptimised module"
  fi
fi
ls -la web/pkg
