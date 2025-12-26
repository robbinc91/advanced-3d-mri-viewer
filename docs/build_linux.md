# Build on Linux (Ubuntu) — Linux-first with ITK (recommended via vcpkg)

This document describes how to build the C++ port (Qt + VTK + ITK) on Linux. Using `vcpkg` is recommended to ensure compatible versions of Qt, VTK and ITK.

Prerequisites
- Git, CMake >= 3.16, a C++ compiler (gcc/clang), and curl/wget.

Option A — Recommended: vcpkg (consistent, recent versions)

1. Clone and bootstrap vcpkg

```bash
git clone https://github.com/microsoft/vcpkg.git ~/vcpkg
cd ~/vcpkg
./bootstrap-vcpkg.sh
export VCPKG_ROOT=$(pwd)
```

2. Install required packages

```bash
./vcpkg install qt5-base:x64-linux itk:x64-linux vtk:x64-linux --recurse
```

3. Configure with CMake

```bash
cd /path/to/advanced-3d-mri-viewer
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release -DUSE_VCPKG=ON -DCMAKE_TOOLCHAIN_FILE=$VCPKG_ROOT/scripts/buildsystems/vcpkg.cmake
```

4. Build

```bash
cmake --build . --config Release -j$(nproc)
```

5. Run

If the binary sits under `src/` target, you can run:

```bash
./src/mri_viewer_cpp
```

Notes & Troubleshooting
- VTK must be built with Qt support for QVTKOpenGLNativeWidget to be available.
- If you see dynamic linking errors at runtime, set LD_LIBRARY_PATH to include vcpkg installed libraries (usually handled by RPATH by CMake via vcpkg).
- If you prefer system packages, you can try `apt install qtbase5-dev libvtk9-dev libitk-dev` but versions may be old or missing Qt-enabled VTK.

Optional: enabling ITK components like N4 requires ITK filters — install `itk` via vcpkg as shown above.
