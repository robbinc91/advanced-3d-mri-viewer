cmake_minimum_required(VERSION 3.16)
project(mri_viewer_cpp LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)  # CRITICAL: This processes Qt moc files automatically
set(CMAKE_AUTOUIC ON)  # If you have .ui files
set(CMAKE_AUTORCC ON)  # If you have .qrc files

# Find Qt components - add Core which you're missing
set(QT_VERSION_MAJOR 6)
find_package(Qt6  REQUIRED COMPONENTS Core Widgets PrintSupport Concurrent)

# Find VTK with specific components you need
find_package(VTK REQUIRED COMPONENTS
    CommonCore
    RenderingOpenGL2
    InteractionStyle
    RenderingFreeType
    GUISupportQt
    RenderingContextOpenGL2
    ChartsCore
    FiltersSources
    FiltersGeneral
)

# For VTK 9+ with Qt support
if(VTK_VERSION VERSION_GREATER_EQUAL 9.0)
    find_package(VTK COMPONENTS
        #GUISupportQtOpenGL
        RenderingQt
    )
endif()

find_package(ITK REQUIRED)
include(${ITK_USE_FILE})

set(SRCS
    main.cpp
    MainWindow.cpp
    ViewerCore.cpp
    ExportWorker.cpp
)

set(HEADERS
    MainWindow.h
    ViewerCore.h
    ExportWorker.h
)

add_executable(${PROJECT_NAME} ${SRCS} ${HEADERS})

# Link libraries
target_link_libraries(${PROJECT_NAME}
    PRIVATE
        Qt6::Core      # Missing in your original - needed for QAtomicBool
        Qt6::Widgets
        Qt6::PrintSupport
        Qt6::Concurrent
        Qt6::OpenGLWidgets
        ${VTK_LIBRARIES}
        ${ITK_LIBRARIES}
)

# Include directories - you were missing Qt and VTK includes
target_include_directories(${PROJECT_NAME} PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${Qt6Core_INCLUDE_DIRS}
    ${Qt6Widgets_INCLUDE_DIRS}
    ${VTK_INCLUDE_DIRS}
    ${ITK_INCLUDE_DIRS}
    ${Qt6_INCLUDE_DIRS}
)

# Add compile definitions for Qt
target_compile_definitions(${PROJECT_NAME} PRIVATE
    $<$<OR:$<CONFIG:Debug>,$<CONFIG:RelWithDebInfo>>:QT_QML_DEBUG>
)

# For VTK 8.x and earlier, use vtk_module_autoinit
if(VTK_VERSION VERSION_LESS 9.0)
    if (VTK_LIBRARIES)
        vtk_module_autoinit(
            TARGETS ${PROJECT_NAME}
            MODULES ${VTK_LIBRARIES}
        )
    endif()
endif()

install(TARGETS ${PROJECT_NAME} RUNTIME DESTINATION bin)