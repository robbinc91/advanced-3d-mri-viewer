# Build on Windows (Visual Studio) — using vcpkg

Prerequisites
- Visual Studio 2019/2022 with "Desktop development with C++" workload
- CMake, Git

1. Install vcpkg and packages

```powershell
git clone https://github.com/microsoft/vcpkg.git C:\vcpkg
cd C:\vcpkg
.\bootstrap-vcpkg.bat
.\vcpkg install qt5-base:x64-windows vtk:x64-windows itk:x64-windows --recurse
```

2. Configure CMake (from an Administrator or Developer prompt)

```powershell
mkdir build; cd build
cmake .. -G "Visual Studio 17 2022" -A x64 -DUSE_VCPKG=ON -DCMAKE_TOOLCHAIN_FILE=C:/vcpkg/scripts/buildsystems/vcpkg.cmake
```

3. Build

```powershell
cmake --build . --config Release
```

4. Deployment
- Run `windeployqt` from your Qt installation on the produced executable to bundle Qt DLLs.
- Also ensure VTK/ITK DLLs are packaged or installed on the target machine (copy from vcpkg installed/bin).

Notes
- Use consistent triplets for vcpkg (x64-windows) across all packages.
- Ensure VTK was built with Qt integration so `QVTKOpenGLNativeWidget` is available.
