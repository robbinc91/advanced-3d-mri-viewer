#include "MainWindow.h"
#include <QSplitter>
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QGridLayout>
#include <QGroupBox>
#include <QPushButton>
#include <QLabel>
#include <QScrollArea>
#include <QSlider>
#include <QSpinBox>
#include <QComboBox>
#include <QCheckBox>
#include <QStyle>
#include <QApplication>
#include <QSizePolicy>

#include <vtkNew.h>
#include <vtkRenderer.h>
#include <vtkGenericOpenGLRenderWindow.h>

// Use QVTKOpenGLNativeWidget if available in user's VTK/Qt setup
#include <QVTKOpenGLNativeWidget.h>

MainWindow::MainWindow(QWidget* parent)
    : QMainWindow(parent)
{
    setupUi();
}

void MainWindow::setupUi()
{
    QWidget* central = new QWidget(this);
    setCentralWidget(central);

    QVBoxLayout* mainLayout = new QVBoxLayout(central);

    QSplitter* splitter = new QSplitter(Qt::Horizontal, central);
    splitter->setHandleWidth(6);

    QWidget* left = buildLeftPanel();
    QWidget* right = buildVisGrid();

    splitter->addWidget(left);
    splitter->addWidget(right);

    splitter->setStretchFactor(0, 1);
    splitter->setStretchFactor(1, 4);
    splitter->setSizes({360, 1100});

    mainLayout->addWidget(splitter);
    setWindowTitle("MRI Viewer Pro - C++ (Qt + VTK)");
    resize(1400, 900);
}

QWidget* MainWindow::buildLeftPanel()
{
    QWidget* panel = new QWidget();
    QVBoxLayout* layout = new QVBoxLayout(panel);
    layout->setContentsMargins(6,6,6,6);
    layout->setSpacing(8);

    // File Operations
    QGroupBox* fileGroup = new QGroupBox(tr("File Operations"));
    fileGroup->setCheckable(true);
    fileGroup->setChecked(true);
    QVBoxLayout* fileLayout = new QVBoxLayout();

    QPushButton* btnLoad = new QPushButton(tr("Load MRI"));
    QPushButton* btnLoadMask = new QPushButton(tr("Load Mask"));
    QPushButton* btnScreenshot = new QPushButton(tr("Export Screenshot"));
    QPushButton* btnExport = new QPushButton(tr("Export Modified MRI (.nii.gz)"));

    fileLayout->addWidget(btnLoad);
    fileLayout->addWidget(btnLoadMask);
    fileLayout->addWidget(btnScreenshot);
    fileLayout->addWidget(btnExport);
    fileGroup->setLayout(fileLayout);

    // Processing group (placeholder controls)
    QGroupBox* procGroup = new QGroupBox(tr("Clinical Image Processing"));
    procGroup->setCheckable(true);
    procGroup->setChecked(true);
    QVBoxLayout* procLayout = new QVBoxLayout();
    procLayout->addWidget(new QLabel(tr("Global Param (Thresh/Gamma/Sigma/Size):")));
    QDoubleSpinBox* paramSpin = new QDoubleSpinBox();
    paramSpin->setRange(0.01, 50000.0);
    paramSpin->setValue(1.0);
    procLayout->addWidget(paramSpin);
    procGroup->setLayout(procLayout);

    // Mask controls
    QGroupBox* maskGroup = new QGroupBox(tr("Mask Controls"));
    maskGroup->setCheckable(true);
    maskGroup->setChecked(true);
    QVBoxLayout* maskLayout = new QVBoxLayout();
    QCheckBox* showMask = new QCheckBox(tr("Show Mask"));
    maskLayout->addWidget(showMask);
    maskGroup->setLayout(maskLayout);

    // Rendering options
    QGroupBox* renderGroup = new QGroupBox(tr("Rendering Options"));
    renderGroup->setCheckable(true);
    renderGroup->setChecked(true);
    QVBoxLayout* renderLayout = new QVBoxLayout();
    QCheckBox* volumeCheck = new QCheckBox(tr("Volume Rendering"));
    renderLayout->addWidget(volumeCheck);
    renderGroup->setLayout(renderLayout);

    // Annotations
    QGroupBox* annoGroup = new QGroupBox(tr("Annotations"));
    annoGroup->setCheckable(true);
    annoGroup->setChecked(true);
    QVBoxLayout* annoLayout = new QVBoxLayout();
    QPushButton* btnAnnot = new QPushButton(tr("Toggle Annotation Mode"));
    annoLayout->addWidget(btnAnnot);
    annoGroup->setLayout(annoLayout);

    layout->addWidget(fileGroup);
    layout->addWidget(procGroup);
    layout->addWidget(maskGroup);
    layout->addWidget(renderGroup);
    layout->addWidget(annoGroup);
    layout->addStretch();

    // Put inside a scroll area and disable horizontal scrollbar
    QScrollArea* scroll = new QScrollArea();
    scroll->setWidgetResizable(true);
    scroll->setWidget(panel);
    scroll->setHorizontalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
    scroll->setMinimumWidth(220);
    scroll->setMaximumWidth(800);

    return scroll;
}

QWidget* MainWindow::buildVisGrid()
{
    QWidget* gridWidget = new QWidget();
    QGridLayout* grid = new QGridLayout(gridWidget);
    grid->setSpacing(4);
    gridWidget->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);
    grid->setRowStretch(0, 1);
    grid->setRowStretch(1, 1);
    grid->setColumnStretch(0, 1);
    grid->setColumnStretch(1, 1);

    // Create 4 VTK render widgets (axial, sagittal, 3D, coronal)
    QVTKOpenGLNativeWidget* axial = new QVTKOpenGLNativeWidget();
    QVTKOpenGLNativeWidget* sagittal = new QVTKOpenGLNativeWidget();
    QVTKOpenGLNativeWidget* vol3d = new QVTKOpenGLNativeWidget();
    QVTKOpenGLNativeWidget* coronal = new QVTKOpenGLNativeWidget();

    axial->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);
    sagittal->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);
    vol3d->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);
    coronal->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);

    // Each needs its own render window and renderer
    vtkNew<vtkGenericOpenGLRenderWindow> rw1;
    vtkNew<vtkGenericOpenGLRenderWindow> rw2;
    vtkNew<vtkGenericOpenGLRenderWindow> rw3;
    vtkNew<vtkGenericOpenGLRenderWindow> rw4;

    axial->setRenderWindow(rw1);
    sagittal->setRenderWindow(rw2);
    vol3d->setRenderWindow(rw3);
    coronal->setRenderWindow(rw4);

    vtkNew<vtkRenderer> r1;
    vtkNew<vtkRenderer> r2;
    vtkNew<vtkRenderer> r3;
    vtkNew<vtkRenderer> r4;

    r1->SetBackground(0.1, 0.1, 0.1);
    r2->SetBackground(0.1, 0.1, 0.1);
    r3->SetBackground(0.1, 0.1, 0.1);
    r4->SetBackground(0.1, 0.1, 0.1);

    rw1->AddRenderer(r1);
    rw2->AddRenderer(r2);
    rw3->AddRenderer(r3);
    rw4->AddRenderer(r4);

    // Simple labeled containers for now
    QWidget* axialContainer = new QWidget();
    QVBoxLayout* axLayout = new QVBoxLayout(axialContainer);
    QLabel* axLabel = new QLabel(tr("Axial"));
    axLayout->addWidget(axLabel);
    axLayout->addWidget(axial);

    QWidget* sagContainer = new QWidget();
    QVBoxLayout* sagLayout = new QVBoxLayout(sagContainer);
    QLabel* sagLabel = new QLabel(tr("Sagittal"));
    sagLayout->addWidget(sagLabel);
    sagLayout->addWidget(sagittal);

    QWidget* volContainer = new QWidget();
    QVBoxLayout* volLayout = new QVBoxLayout(volContainer);
    QLabel* volLabel = new QLabel(tr("3D"));
    volLayout->addWidget(volLabel);
    volLayout->addWidget(vol3d);

    QWidget* corContainer = new QWidget();
    QVBoxLayout* corLayout = new QVBoxLayout(corContainer);
    QLabel* corLabel = new QLabel(tr("Coronal"));
    corLayout->addWidget(corLabel);
    corLayout->addWidget(coronal);

    grid->addWidget(axialContainer, 0, 0);
    grid->addWidget(sagContainer, 0, 1);
    grid->addWidget(volContainer, 1, 0);
    grid->addWidget(corContainer, 1, 1);

    return gridWidget;
}
