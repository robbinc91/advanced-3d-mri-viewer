cmake_minimum_required(VERSION 3.16)
project(advanced_3d_mri_viewer LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)  # Important for Qt
set(CMAKE_AUTOUIC ON)  # Important for Qt UI files
set(CMAKE_AUTORCC ON)  # Important for Qt resource files

option(USE_VCPKG "Use vcpkg toolchain" OFF)

if(DEFINED ENV{VCPKG_ROOT} AND NOT USE_VCPKG)
  set(USE_VCPKG ON)
endif()

if(USE_VCPKG AND NOT DEFINED CMAKE_TOOLCHAIN_FILE)
  message(STATUS "Using vcpkg toolchain from VCPKG_ROOT: $ENV{VCPKG_ROOT}")
  set(CMAKE_TOOLCHAIN_FILE "$ENV{VCPKG_ROOT}/scripts/buildsystems/vcpkg.cmake" CACHE STRING "vcpkg toolchain file")
endif()


# 1. FIND AND LINK QT
set(QT_VERSION_MAJOR 5)
find_package(Qt6 COMPONENTS Core Widgets Concurrent REQUIRED)

# 2. FIND AND LINK VTK (with Qt support)
find_package(VTK REQUIRED COMPONENTS
    CommonCore
    RenderingOpenGL2
    InteractionStyle
    RenderingFreeType
    GUISupportQt
    RenderingContextOpenGL2
    ChartsCore
)

if(VTK_VERSION VERSION_GREATER_EQUAL 9.0)
    find_package(VTK COMPONENTS 
      #GUISupportQtOpenGL 
    )
endif()

# 3. FIND AND LINK ITK (if you're using ITK for image processing)
find_package(ITK REQUIRED COMPONENTS
    ITKCommon
    ITKIOImageBase
    ITKThresholding
    ITKImageFilterBase
)

include(${ITK_USE_FILE})

# 4. Create your executable
add_subdirectory(src)

# If your src/CMakeLists.txt creates the target, you need to link libraries there
# Alternatively, if src/CMakeLists.txt returns the target name, you can do:
# set(TARGET_NAME advanced_3d_mri_viewer)
# target_link_libraries(${TARGET_NAME}
#     Qt5::Core
#     Qt5::Widgets
#     Qt5::Concurrent
#     ${VTK_LIBRARIES}
#     ${ITK_LIBRARIES}
# )