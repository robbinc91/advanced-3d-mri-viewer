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
#include <QPushButton>
#include <QFileDialog>
#include <QMessageBox>
#include <QFuture>
#include <QFutureWatcher>
#include <QtConcurrent/QtConcurrent>

#include "ViewerCore.h"
#include <vtkImageActor.h>
#include <vtkImageMapToColors.h>
#include <vtkLookupTable.h>
#include <vtkImageActor.h>

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
    axial_ = new QVTKOpenGLNativeWidget();
    sagittal_ = new QVTKOpenGLNativeWidget();
    vol3d_ = new QVTKOpenGLNativeWidget();
    coronal_ = new QVTKOpenGLNativeWidget();
    setCentralWidget(centralWidget_);

    QVBoxLayout* mainLayout = new QVBoxLayout(centralWidget_);

    QSplitter* splitter = new QSplitter(Qt::Horizontal, centralWidget_);
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

    btnLoadMRI_ = new QPushButton(tr("Load MRI"));
    btnLoadMask_ = new QPushButton(tr("Load Mask"));
    QPushButton* btnScreenshot = new QPushButton(tr("Export Screenshot"));
    btnExportReport_ = new QPushButton(tr("Export Report (PDF)"));
    btnCancelExport_ = new QPushButton(tr("Cancel Export"));
    btnCancelExport_->setEnabled(false);

    fileLayout->addWidget(btnLoadMRI_);
    fileLayout->addWidget(btnLoadMask_);
    fileLayout->addWidget(btnScreenshot);
    fileLayout->addWidget(btnExportReport_);
    fileLayout->addWidget(btnCancelExport_);
    connect(btnLoadMRI_, &QPushButton::clicked, this, &MainWindow::onLoadMRI);
    connect(btnLoadMask_, &QPushButton::clicked, this, &MainWindow::onLoadMask);
    connect(btnExportReport_, &QPushButton::clicked, this, &MainWindow::onExportReportClicked);
    connect(btnCancelExport_, &QPushButton::clicked, this, &MainWindow::onCancelExportClicked);
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
    // N4 Bias Correction
    btnRunN4_ = new QPushButton(tr("Run N4 Bias Correction"));
    procLayout->addWidget(btnRunN4_);

    // Multi-Otsu controls
    QWidget* nclassGroup = new QWidget();
    QHBoxLayout* nclassLayout = new QHBoxLayout(nclassGroup);
    nclassLayout->setContentsMargins(0,0,0,0);
    nclassLayout->addWidget(new QLabel(tr("Multi-Otsu Classes:")));
    nClassesSpin_ = new QSpinBox();
    nClassesSpin_->setRange(2, 10);
    nClassesSpin_->setValue(3);
    nclassLayout->addWidget(nClassesSpin_);
    btnRunMultiOtsu_ = new QPushButton(tr("Run Multi-Otsu"));
    nclassLayout->addWidget(btnRunMultiOtsu_);
    procLayout->addWidget(nclassGroup);
    procGroup->setLayout(procLayout);

    connect(btnRunN4_, &QPushButton::clicked, this, &MainWindow::onRunN4);
    connect(btnRunMultiOtsu_, &QPushButton::clicked, this, &MainWindow::onRunMultiOtsu);

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

    // Store renderers for later updates
    r_axial_ = r1;
    r_sagittal_ = r2;
    r_vol3d_ = r3;
    r_coronal_ = r4;

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

void MainWindow::onLoadMRI()
{
    QString path = QFileDialog::getOpenFileName(this, tr("Load MRI"), "", tr("NIfTI Files (*.nii *.nii.gz);;All Files (*)"));
    if (path.isEmpty()) return;
    QString err;
    if (!core_) core_ = std::make_unique<ViewerCore>(this);
    if (!core_->loadMRI(path, err)) {
        QMessageBox::critical(this, tr("Load Error"), err);
        return;
    }

    // connect loaded signal to status updater
    connect(core_.get(), &ViewerCore::loaded, this, &MainWindow::onCoreLoaded, Qt::UniqueConnection);

    // Update all views (axial/coronal/sagittal + 3D if mask present)
    updateViews();
}

void MainWindow::onLoadMask()
{
    QString path = QFileDialog::getOpenFileName(this, tr("Load Mask"), "", tr("NIfTI Files (*.nii *.nii.gz);;All Files (*)"));
    if (path.isEmpty()) return;
    QString err;
    if (!core_) core_ = std::make_unique<ViewerCore>(this);
    if (!core_->loadMask(path, err)) {
        QMessageBox::critical(this, tr("Load Error"), err);
        return;
    }

    // Overlay mask on the axial view as a colored, semi-transparent layer
    vtkSmartPointer<vtkImageData> mask_slice = core_->extractMaskSlice("axial", -1);
    if (mask_slice) {
        vtkSmartPointer<vtkLookupTable> lut = vtkSmartPointer<vtkLookupTable>::New();
        lut->SetNumberOfTableValues(256);
        lut->Build();
        // simple mapping: label 1->red, 2->green, 3->blue
        lut->SetTableValue(1, 1.0, 0.0, 0.0, 0.6);
        lut->SetTableValue(2, 0.0, 1.0, 0.0, 0.6);
        lut->SetTableValue(3, 0.0, 0.0, 1.0, 0.6);

        vtkSmartPointer<vtkImageMapToColors> colorer = vtkSmartPointer<vtkImageMapToColors>::New();
        //colorer->SetInputData(mask_slice);
        colorer->SetInputData(mask_slice.Get());  
        colorer->SetLookupTable(lut);
        colorer->PassAlphaToOutputOn();
        colorer->Update();

        vtkSmartPointer<vtkImageActor> maskActor = vtkSmartPointer<vtkImageActor>::New();
        maskActor->GetMapper()->SetInputConnection(colorer->GetOutputPort());

        r_axial_->AddActor(maskActor);
        r_axial_->Render();
        if (axial_ && axial_->renderWindow()) axial_->renderWindow()->Render();
    }

    // After loading mask, update views (including 3D) and compute volumes
    updateViews();
    showVolumes();
    }

void MainWindow::onExportReportClicked()
{
    if (!core_) {
        QMessageBox::information(this, tr("Export"), tr("Load an MRI first"));
        return;
    }

    QString filepath = QFileDialog::getSaveFileName(this, tr("Export Report"), "MRI_Report.pdf", tr("PDF Files (*.pdf)"));
    if (filepath.isEmpty()) return;

    // Create and start worker
    if (exportWorker_) {
        QMessageBox::warning(this, tr("Export"), tr("An export is already running."));
        return;
    }

    exportWorker_ = new ExportWorker(core_.get(), filepath, this);
    connect(exportWorker_, &ExportWorker::progress, this, &MainWindow::onExportProgress);
    connect(exportWorker_, &ExportWorker::finished, this, &MainWindow::onExportFinished);
    btnExportReport_->setEnabled(false);
    btnCancelExport_->setEnabled(true);
    exportWorker_->start();
}

void MainWindow::onCancelExportClicked()
{
    if (exportWorker_) {
        exportWorker_->requestCancel();
        btnCancelExport_->setEnabled(false);
        statusBar()->showMessage(tr("Export cancellation requested..."), 3000);
    }
}

void MainWindow::onExportProgress(int percent, const QString& message)
{
    statusBar()->showMessage(QString("Export: %1% - %2").arg(percent).arg(message));
}

void MainWindow::onExportFinished(bool success, const QString& message)
{
    if (exportWorker_) {
        exportWorker_->wait();
        exportWorker_->deleteLater();
        exportWorker_ = nullptr;
    }
    btnExportReport_->setEnabled(true);
    btnCancelExport_->setEnabled(false);

    if (success) QMessageBox::information(this, tr("Export"), message);
    else QMessageBox::critical(this, tr("Export"), message);
    statusBar()->showMessage(message, 5000);
}

void MainWindow::onRunN4()
{
    if (!core_ || core_->sourcePath().isEmpty()) {
        QMessageBox::information(this, tr("N4"), tr("Load an MRI first."));
        return;
    }
    btnRunN4_->setEnabled(false);
    statusBar()->showMessage(tr("Running N4 bias correction..."));

    //QFuture<QString> future = QtConcurrent::run(core_.get(), &ViewerCore::applyN4, 50);
    int maxIterations = 50;
    auto future = QtConcurrent::run([this, maxIterations]() { return core_->applyN4(maxIterations); });
    
    n4Watcher_ = new QFutureWatcher<QString>(this);
    connect(n4Watcher_, &QFutureWatcher<QString>::finished, this, [this]() {
        QString err = n4Watcher_->result();
        if (err.isEmpty()) {
            statusBar()->showMessage(tr("N4 completed"), 3000);
            updateViews();
        } else {
            QMessageBox::critical(this, tr("N4 Error"), err);
            statusBar()->showMessage(tr("N4 failed"), 3000);
        }
        btnRunN4_->setEnabled(true);
        n4Watcher_->deleteLater();
        n4Watcher_ = nullptr;
    });
    n4Watcher_->setFuture(future);
}

void MainWindow::onRunMultiOtsu()
{
    if (!core_ || core_->sourcePath().isEmpty()) {
        QMessageBox::information(this, tr("Otsu"), tr("Load an MRI first."));
        return;
    }
    int classes = nClassesSpin_->value();
    btnRunMultiOtsu_->setEnabled(false);
    statusBar()->showMessage(tr("Running Multi-Otsu..."));

    //QFuture<QString> future = QtConcurrent::run(core_.get(), &ViewerCore::runMultiOtsu, classes);
    auto future = QtConcurrent::run([this, classes]() { return core_->runMultiOtsu(classes); });
    otsuWatcher_ = new QFutureWatcher<QString>(this);
    connect(otsuWatcher_, &QFutureWatcher<QString>::finished, this, [this]() {
        QString err = otsuWatcher_->result();
        if (err.isEmpty()) {
            statusBar()->showMessage(tr("Multi-Otsu completed"), 3000);
            updateViews();
            showVolumes();
        } else {
            QMessageBox::critical(this, tr("Otsu Error"), err);
            statusBar()->showMessage(tr("Multi-Otsu failed"), 3000);
        }
        btnRunMultiOtsu_->setEnabled(true);
        otsuWatcher_->deleteLater();
        otsuWatcher_ = nullptr;
    });
    otsuWatcher_->setFuture(future);
}

void MainWindow::onCoreLoaded(bool success, const QString& message)
{
    if (success) {
        statusBar()->showMessage(message, 5000);
    } else {
        QMessageBox::warning(this, tr("Load"), message);
    }
}

void MainWindow::updateViews()
{
    if (!core_) return;

    // Axial
    vtkSmartPointer<vtkImageData> axialSlice = core_->extractSlice("axial", -1);
    if (axialSlice) {
        vtkSmartPointer<vtkImageActor> actor = vtkSmartPointer<vtkImageActor>::New();
        actor->GetMapper()->SetInputData(axialSlice);
        r_axial_->RemoveAllViewProps();
        r_axial_->AddActor(actor);
        r_axial_->ResetCamera();
        if (axial_ && axial_->renderWindow()) axial_->renderWindow()->Render();
    }

    // Sagittal
    vtkSmartPointer<vtkImageData> sagSlice = core_->extractSlice("sagittal", -1);
    if (sagSlice && r_sagittal_) {
        vtkSmartPointer<vtkImageActor> actor = vtkSmartPointer<vtkImageActor>::New();
        actor->GetMapper()->SetInputData(sagSlice);
        r_sagittal_->RemoveAllViewProps();
        r_sagittal_->AddActor(actor);
        r_sagittal_->ResetCamera();
        // find the widget and render if available
        if (sagittal_ && sagittal_->renderWindow()) sagittal_->renderWindow()->Render();
    }

    // Coronal
    vtkSmartPointer<vtkImageData> corSlice = core_->extractSlice("coronal", -1);
    if (corSlice && r_coronal_) {
        vtkSmartPointer<vtkImageActor> actor = vtkSmartPointer<vtkImageActor>::New();
        actor->GetMapper()->SetInputData(corSlice);
        r_coronal_->RemoveAllViewProps();
        r_coronal_->AddActor(actor);
        r_coronal_->ResetCamera();
        if (coronal_ && coronal_->renderWindow()) coronal_->renderWindow()->Render();
    }

    // 3D: if mask exists, render mesh
    if (core_->getMaskImage() && r_vol3d_) {
        vtkSmartPointer<vtkPolyData> poly = core_->create3DMeshForLabel(-1);
        if (poly && poly->GetNumberOfPoints() > 0) {
            vtkSmartPointer<vtkPolyDataMapper> mapper = vtkSmartPointer<vtkPolyDataMapper>::New();
            mapper->SetInputData(poly);
            vtkSmartPointer<vtkActor> actor = vtkSmartPointer<vtkActor>::New();
            actor->SetMapper(mapper);
            r_vol3d_->RemoveAllViewProps();
            r_vol3d_->AddActor(actor);
            r_vol3d_->ResetCamera();
            if (vol3d_ && vol3d_->renderWindow()) vol3d_->renderWindow()->Render();
        }
    }
}

void MainWindow::showVolumes()
{
    if (!core_ || !core_->getMaskImage()) {
        QMessageBox::information(this, tr("Volumes"), tr("No mask loaded."));
        return;
    }
    auto vols = core_->computeLabelVolumes();
    if (vols.empty()) {
        QMessageBox::information(this, tr("Volumes"), tr("No labels found in mask."));
        return;
    }
    std::ostringstream ss;
    ss << "Volumes (cm^3):\n";
    for (auto &kv : vols) {
        ss << "Label " << kv.first << ": " << kv.second << " cm^3\n";
    }
    QMessageBox::information(this, tr("Volumes"), QString::fromStdString(ss.str()));
}

