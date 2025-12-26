#include "MainWindow.h"
#include <QSplitter>
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QGridLayout>
#include <QEvent>
#include <climits>
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

#include <vtkCallbackCommand.h>
#include <vtkCommand.h>
#include <vtkRenderWindowInteractor.h>
#include <vtkRenderWindow.h>
#include <vtkLineSource.h>
#include <vtkProperty.h>
#include <vtkPolyDataMapper.h>
#include <vtkPropPicker.h>

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

struct InteractorCallbackData {
    MainWindow* self;
    int axis; // 0=axial,1=sagittal,2=coronal
    bool leftDown = false;
};

MainWindow::~MainWindow()
{
    // Clean up callback command objects and client data
    for (auto cb : interactorCallbacks_) {
        if (cb) cb->Delete();
    }
    interactorCallbacks_.clear();
    for (auto d : interactorCallbackDatas_) {
        delete static_cast<InteractorCallbackData*>(d);
    }
    interactorCallbackDatas_.clear();
}

void MainWindow::setupUi()
{
    centralWidget_ = new QWidget(this);
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

    // Prepare VTK interactor callbacks (they will work once core_ is loaded)
    setupInteractors();
}

// Helper struct used as clientData for vtk callbacks


// Forward callback invoked by VTK for wheel and left-button events
//static void vtkInteractorEventCallback(vtkObject* caller, unsigned long eventId, void* clientData, void* /*callData*/)
void MainWindow::vtkInteractorEventCallback(vtkObject* caller, long unsigned int eventId, void* clientData, void* callData)
{
    auto d = static_cast<InteractorCallbackData*>(clientData);
    if (!d || !d->self) return;
    MainWindow* self = d->self;

    vtkRenderWindowInteractor* iren = vtkRenderWindowInteractor::SafeDownCast(caller);
    if (!iren) {
        // caller may be renderer's interactor retrieved differently
        vtkRenderWindow* rw = vtkRenderWindow::SafeDownCast(caller);
        if (rw) iren = rw->GetInteractor();
    }

    // Wheel events
    if (eventId == vtkCommand::MouseWheelForwardEvent || eventId == vtkCommand::MouseWheelBackwardEvent) {
        int dir = (eventId == vtkCommand::MouseWheelForwardEvent) ? 1 : -1;
        int dims[3] = {0,0,0};
        if (d->self->core_ && d->self->core_->getMRIImage()) d->self->core_->getMRIImage()->GetDimensions(dims);
        if (d->axis == 0) {
            int maxv = dims[2] > 0 ? dims[2]-1 : INT_MAX;
            self->idx_axial_ = std::max(0, std::min(maxv, self->idx_axial_ + dir));
        } else if (d->axis == 1) {
            int maxv = dims[0] > 0 ? dims[0]-1 : INT_MAX;
            self->idx_sagittal_ = std::max(0, std::min(maxv, self->idx_sagittal_ + dir));
        } else if (d->axis == 2) {
            int maxv = dims[1] > 0 ? dims[1]-1 : INT_MAX;
            self->idx_coronal_ = std::max(0, std::min(maxv, self->idx_coronal_ + dir));
        }
        self->updateViews();
        return;
    }

    // Mouse move -> if dragging (leftDown) perform continuous seek
    if (eventId == vtkCommand::MouseMoveEvent) {
        if (!d->leftDown) return;
        if (!iren) return;
        int eventPos[2];
        iren->GetEventPosition(eventPos);
        vtkRenderWindow* rw = iren->GetRenderWindow();
        if (!rw) return;
        vtkRenderer* renderer = rw->GetRenderers()->GetFirstRenderer();
        if (!renderer) return;
        // Use a prop picker for more robust picking on the image actor
        vtkSmartPointer<vtkPropPicker> picker = vtkSmartPointer<vtkPropPicker>::New();
        if (picker->Pick(eventPos[0], eventPos[1], 0, renderer)) {
            double pickPos[3]; picker->GetPickPosition(pickPos);

            int dims[3] = {0,0,0};
            if (self->core_ && self->core_->getMRIImage()) self->core_->getMRIImage()->GetDimensions(dims);
            int newX = self->idx_sagittal_;
            int newY = self->idx_coronal_;
            int newZ = self->idx_axial_;
            if (d->axis == 0) { newX = static_cast<int>(std::floor(pickPos[0])); newY = static_cast<int>(std::floor(pickPos[1])); }
            else if (d->axis == 1) { newY = static_cast<int>(std::floor(pickPos[0])); newZ = static_cast<int>(std::floor(pickPos[1])); }
            else if (d->axis == 2) { newX = static_cast<int>(std::floor(pickPos[0])); newZ = static_cast<int>(std::floor(pickPos[1])); }
            if (dims[0] > 0) newX = std::max(0, std::min(dims[0]-1, newX));
            if (dims[1] > 0) newY = std::max(0, std::min(dims[1]-1, newY));
            if (dims[2] > 0) newZ = std::max(0, std::min(dims[2]-1, newZ));

            // Throttle identical repeated seeks
            if (newX == self->last_seek_x_ && newY == self->last_seek_y_ && newZ == self->last_seek_z_) {
                return;
            }
            self->last_seek_x_ = newX; self->last_seek_y_ = newY; self->last_seek_z_ = newZ;

            QMetaObject::invokeMethod(self, "seekToIndices", Qt::QueuedConnection,
                                      Q_ARG(int, newX), Q_ARG(int, newY), Q_ARG(int, newZ));
        }
        return;
    }

    // Left button press: perform SEEK-to-position and enter drag mode
    if (eventId == vtkCommand::LeftButtonPressEvent) {
        if (!iren) return;
        int eventPos[2];
        iren->GetEventPosition(eventPos);
        vtkRenderWindow* rw = iren->GetRenderWindow();
        if (!rw) return;
        vtkRenderer* renderer = rw->GetRenderers()->GetFirstRenderer();
        if (!renderer) return;

        // Use a prop picker for better accuracy when clicking
        vtkSmartPointer<vtkPropPicker> picker = vtkSmartPointer<vtkPropPicker>::New();
        if (picker->Pick(eventPos[0], eventPos[1], 0, renderer)) {
            double pickPos[3]; picker->GetPickPosition(pickPos);

            // Map world coords to voxel indices approximately
            int dims[3] = {0,0,0};
            if (self->core_ && self->core_->getMRIImage()) self->core_->getMRIImage()->GetDimensions(dims);

            int newX = self->idx_sagittal_;
            int newY = self->idx_coronal_;
            int newZ = self->idx_axial_;

            if (d->axis == 0) { // axial: pickPos[0]=x, pickPos[1]=y
                newX = static_cast<int>(std::floor(pickPos[0]));
                newY = static_cast<int>(std::floor(pickPos[1]));
            } else if (d->axis == 1) { // sagittal: pickPos[0]=y, pickPos[1]=z
                newY = static_cast<int>(std::floor(pickPos[0]));
                newZ = static_cast<int>(std::floor(pickPos[1]));
            } else if (d->axis == 2) { // coronal: pickPos[0]=x, pickPos[1]=z
                newX = static_cast<int>(std::floor(pickPos[0]));
                newZ = static_cast<int>(std::floor(pickPos[1]));
            }

            // clamp
            if (dims[0] > 0) newX = std::max(0, std::min(dims[0]-1, newX));
            if (dims[1] > 0) newY = std::max(0, std::min(dims[1]-1, newY));
            if (dims[2] > 0) newZ = std::max(0, std::min(dims[2]-1, newZ));

            // Enter drag state so subsequent MouseMoveEvents will update
            d->leftDown = true;
            // also mark this view active
            if (d->axis == 0) self->activeAxis_ = "axial";
            else if (d->axis == 1) self->activeAxis_ = "sagittal";
            else if (d->axis == 2) self->activeAxis_ = "coronal";

            // Throttle identical repeated seeks
            if (!(newX == self->last_seek_x_ && newY == self->last_seek_y_ && newZ == self->last_seek_z_)) {
                self->last_seek_x_ = newX; self->last_seek_y_ = newY; self->last_seek_z_ = newZ;
                QMetaObject::invokeMethod(self, "seekToIndices", Qt::QueuedConnection,
                                          Q_ARG(int, newX), Q_ARG(int, newY), Q_ARG(int, newZ));
            }
        }
        return;
    }

    // Left button release -> stop dragging
    if (eventId == vtkCommand::LeftButtonReleaseEvent) {
        d->leftDown = false;
        return;
    }
}

void MainWindow::setupInteractors()
{
    // Create callback data for each axis and attach to the widget's interactor if present
    auto attach = [this](QVTKOpenGLNativeWidget* widget, int axis) {
        if (!widget) return;
        vtkRenderWindow* rw = widget->renderWindow();
        if (!rw) return;
        vtkRenderWindowInteractor* iren = rw->GetInteractor();
        if (!iren) return;

            auto* data = new InteractorCallbackData{this, axis};

            vtkCallbackCommand* cb = vtkCallbackCommand::New();
            cb->SetClientData(static_cast<void*>(data));
            cb->SetCallback(vtkInteractorEventCallback);

            // Keep alive by storing pointers in the MainWindow members
            interactorCallbacks_.push_back(cb);
            interactorCallbackDatas_.push_back(static_cast<void*>(data));

            iren->AddObserver(vtkCommand::MouseWheelForwardEvent, cb);
            iren->AddObserver(vtkCommand::MouseWheelBackwardEvent, cb);
            iren->AddObserver(vtkCommand::LeftButtonPressEvent, cb);
            iren->AddObserver(vtkCommand::MouseMoveEvent, cb);
            iren->AddObserver(vtkCommand::LeftButtonReleaseEvent, cb);
    };

    attach(axial_, 0);
    attach(sagittal_, 1);
    attach(coronal_, 2);
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
    axial_ = new QVTKOpenGLNativeWidget();
    sagittal_ = new QVTKOpenGLNativeWidget();
    vol3d_ = new QVTKOpenGLNativeWidget();
    coronal_ = new QVTKOpenGLNativeWidget();

    axial_->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);
    sagittal_->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);
    vol3d_->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);
    coronal_->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);

    // Each needs its own render window and renderer
    vtkNew<vtkGenericOpenGLRenderWindow> rw1;
    vtkNew<vtkGenericOpenGLRenderWindow> rw2;
    vtkNew<vtkGenericOpenGLRenderWindow> rw3;
    vtkNew<vtkGenericOpenGLRenderWindow> rw4;

    axial_->setRenderWindow(rw1);
    sagittal_->setRenderWindow(rw2);
    vol3d_->setRenderWindow(rw3);
    coronal_->setRenderWindow(rw4);


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

    // Create crosshair lines and actors for axial view
    axial_h_line_ = vtkSmartPointer<vtkLineSource>::New();
    axial_v_line_ = vtkSmartPointer<vtkLineSource>::New();
    {
        vtkSmartPointer<vtkPolyDataMapper> mapH = vtkSmartPointer<vtkPolyDataMapper>::New();
        mapH->SetInputConnection(axial_h_line_->GetOutputPort());
        axial_h_actor_ = vtkSmartPointer<vtkActor>::New();
        axial_h_actor_->SetMapper(mapH);
        axial_h_actor_->GetProperty()->SetColor(0.0, 1.0, 1.0);
        axial_h_actor_->GetProperty()->SetLineWidth(2);

        vtkSmartPointer<vtkPolyDataMapper> mapV = vtkSmartPointer<vtkPolyDataMapper>::New();
        mapV->SetInputConnection(axial_v_line_->GetOutputPort());
        axial_v_actor_ = vtkSmartPointer<vtkActor>::New();
        axial_v_actor_->SetMapper(mapV);
        axial_v_actor_->GetProperty()->SetColor(0.0, 1.0, 1.0);
        axial_v_actor_->GetProperty()->SetLineWidth(2);

        r_axial_->AddActor(axial_h_actor_);
        r_axial_->AddActor(axial_v_actor_);
    }

    // Sagittal crosshairs
    sagittal_h_line_ = vtkSmartPointer<vtkLineSource>::New();
    sagittal_v_line_ = vtkSmartPointer<vtkLineSource>::New();
    {
        vtkSmartPointer<vtkPolyDataMapper> mapH = vtkSmartPointer<vtkPolyDataMapper>::New();
        mapH->SetInputConnection(sagittal_h_line_->GetOutputPort());
        sagittal_h_actor_ = vtkSmartPointer<vtkActor>::New();
        sagittal_h_actor_->SetMapper(mapH);
        sagittal_h_actor_->GetProperty()->SetColor(0.0, 1.0, 1.0);
        sagittal_h_actor_->GetProperty()->SetLineWidth(2);

        vtkSmartPointer<vtkPolyDataMapper> mapV = vtkSmartPointer<vtkPolyDataMapper>::New();
        mapV->SetInputConnection(sagittal_v_line_->GetOutputPort());
        sagittal_v_actor_ = vtkSmartPointer<vtkActor>::New();
        sagittal_v_actor_->SetMapper(mapV);
        sagittal_v_actor_->GetProperty()->SetColor(0.0, 1.0, 1.0);
        sagittal_v_actor_->GetProperty()->SetLineWidth(2);

        r_sagittal_->AddActor(sagittal_h_actor_);
        r_sagittal_->AddActor(sagittal_v_actor_);
    }

    // Coronal crosshairs
    coronal_h_line_ = vtkSmartPointer<vtkLineSource>::New();
    coronal_v_line_ = vtkSmartPointer<vtkLineSource>::New();
    {
        vtkSmartPointer<vtkPolyDataMapper> mapH = vtkSmartPointer<vtkPolyDataMapper>::New();
        mapH->SetInputConnection(coronal_h_line_->GetOutputPort());
        coronal_h_actor_ = vtkSmartPointer<vtkActor>::New();
        coronal_h_actor_->SetMapper(mapH);
        coronal_h_actor_->GetProperty()->SetColor(0.0, 1.0, 1.0);
        coronal_h_actor_->GetProperty()->SetLineWidth(2);

        vtkSmartPointer<vtkPolyDataMapper> mapV = vtkSmartPointer<vtkPolyDataMapper>::New();
        mapV->SetInputConnection(coronal_v_line_->GetOutputPort());
        coronal_v_actor_ = vtkSmartPointer<vtkActor>::New();
        coronal_v_actor_->SetMapper(mapV);
        coronal_v_actor_->GetProperty()->SetColor(0.0, 1.0, 1.0);
        coronal_v_actor_->GetProperty()->SetLineWidth(2);

        r_coronal_->AddActor(coronal_h_actor_);
        r_coronal_->AddActor(coronal_v_actor_);
    }

    // Simple labeled containers for now
    QWidget* axialContainer = new QWidget();
    QVBoxLayout* axLayout = new QVBoxLayout(axialContainer);
    QLabel* axLabel = new QLabel(tr("Axial"));
    axLayout->addWidget(axLabel);
    axLayout->addWidget(axial_);
    // axial slider
    axial_slider_ = new QSlider(Qt::Horizontal);
    axial_slider_->setMinimum(0);
    axial_slider_->setMaximum(0);
    axial_slider_->setValue(0);
    axLayout->addWidget(axial_slider_);
    axial_->installEventFilter(this);

    QWidget* sagContainer = new QWidget();
    QVBoxLayout* sagLayout = new QVBoxLayout(sagContainer);
    QLabel* sagLabel = new QLabel(tr("Sagittal"));
    sagLayout->addWidget(sagLabel);
    sagLayout->addWidget(sagittal_);
    sagittal_slider_ = new QSlider(Qt::Horizontal);
    sagittal_slider_->setMinimum(0);
    sagittal_slider_->setMaximum(0);
    sagittal_slider_->setValue(0);
    sagLayout->addWidget(sagittal_slider_);
    sagittal_->installEventFilter(this);

    QWidget* volContainer = new QWidget();
    QVBoxLayout* volLayout = new QVBoxLayout(volContainer);
    QLabel* volLabel = new QLabel(tr("3D"));
    volLayout->addWidget(volLabel);
    volLayout->addWidget(vol3d_);

    QWidget* corContainer = new QWidget();
    QVBoxLayout* corLayout = new QVBoxLayout(corContainer);
    QLabel* corLabel = new QLabel(tr("Coronal"));
    corLayout->addWidget(corLabel);
    corLayout->addWidget(coronal_);
    coronal_slider_ = new QSlider(Qt::Horizontal);
    coronal_slider_->setMinimum(0);
    coronal_slider_->setMaximum(0);
    coronal_slider_->setValue(0);
    corLayout->addWidget(coronal_slider_);
    coronal_->installEventFilter(this);

    grid->addWidget(axialContainer, 0, 0);
    grid->addWidget(sagContainer, 0, 1);
    grid->addWidget(volContainer, 1, 0);
    grid->addWidget(corContainer, 1, 1);

    // Connect sliders to slots
    connect(axial_slider_, &QSlider::valueChanged, this, &MainWindow::update_axial_slice);
    connect(sagittal_slider_, &QSlider::valueChanged, this, &MainWindow::update_sagittal_slice);
    connect(coronal_slider_, &QSlider::valueChanged, this, &MainWindow::update_coronal_slice);

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

    // Initialize slice indices to representatives and attach interactors
    int a=0, c=0, s=0;
    core_->getRepresentativeSliceIndex(a, c, s);
    idx_axial_ = a;
    idx_coronal_ = c;
    idx_sagittal_ = s;

    // Attach interactors now that render windows exist
    setupInteractors();

    // Set slider ranges from MRI dims and set initial positions
    if (core_ && core_->getMRIImage()) {
        int dims[3] = {0,0,0};
        core_->getMRIImage()->GetDimensions(dims);
        // dims: X=0,Y=1,Z=2
        if (axial_slider_) { axial_slider_->setMaximum(dims[2] > 0 ? dims[2]-1 : 0); axial_slider_->setValue(idx_axial_); }
        if (sagittal_slider_) { sagittal_slider_->setMaximum(dims[0] > 0 ? dims[0]-1 : 0); sagittal_slider_->setValue(idx_sagittal_); }
        if (coronal_slider_) { coronal_slider_->setMaximum(dims[1] > 0 ? dims[1]-1 : 0); coronal_slider_->setValue(idx_coronal_); }
    }

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
    vtkSmartPointer<vtkImageData> axialSlice = core_->extractSlice("axial", idx_axial_);
    if (axialSlice) {
        vtkSmartPointer<vtkImageActor> actor = vtkSmartPointer<vtkImageActor>::New();
        actor->GetMapper()->SetInputData(axialSlice);
        r_axial_->RemoveAllViewProps();
        r_axial_->AddActor(actor);
        // re-add crosshair actors (they may have been removed)
        if (axial_h_actor_) r_axial_->AddActor(axial_h_actor_);
        if (axial_v_actor_) r_axial_->AddActor(axial_v_actor_);
        r_axial_->ResetCamera();

        // Update crosshair geometry
        vtkImageData* img = core_->getMRIImage();
        if (img) {
            int dims[3]; img->GetDimensions(dims);
            double sp[3]; img->GetSpacing(sp);
            double org[3]; img->GetOrigin(org);
            double xw = org[0] + idx_sagittal_ * sp[0];
            double yw = org[1] + idx_coronal_ * sp[1];
            double zw = org[2] + idx_axial_ * sp[2];
            // horizontal line across X at Y= yw, Z = zw
            axial_h_line_->SetPoint1(org[0], yw, zw);
            axial_h_line_->SetPoint2(org[0] + (dims[0]-1) * sp[0], yw, zw);
            // vertical line across Y at X = xw, Z = zw
            axial_v_line_->SetPoint1(xw, org[1], zw);
            axial_v_line_->SetPoint2(xw, org[1] + (dims[1]-1) * sp[1], zw);
        }

        if (axial_ && axial_->renderWindow()) axial_->renderWindow()->Render();
    }

    // Sagittal
    vtkSmartPointer<vtkImageData> sagSlice = core_->extractSlice("sagittal", idx_sagittal_);
    if (sagSlice && r_sagittal_) {
        vtkSmartPointer<vtkImageActor> actor = vtkSmartPointer<vtkImageActor>::New();
        actor->GetMapper()->SetInputData(sagSlice);
        r_sagittal_->RemoveAllViewProps();
        r_sagittal_->AddActor(actor);
        if (sagittal_h_actor_) r_sagittal_->AddActor(sagittal_h_actor_);
        if (sagittal_v_actor_) r_sagittal_->AddActor(sagittal_v_actor_);
        r_sagittal_->ResetCamera();

        // Update sagittal crosshairs (plane X fixed)
        vtkImageData* img = core_->getMRIImage();
        if (img) {
            int dims[3]; img->GetDimensions(dims);
            double sp[3]; img->GetSpacing(sp);
            double org[3]; img->GetOrigin(org);
            double xw = org[0] + idx_sagittal_ * sp[0];
            double yw = org[1] + idx_coronal_ * sp[1];
            double zw = org[2] + idx_axial_ * sp[2];
            // horizontal: vary Y at Z = zw  -> points (xw, orgY, zw) -> (xw, orgY + (dims[1]-1)*sp[1], zw) but horizontal in view maps to Y
            sagittal_h_line_->SetPoint1(xw, org[1], zw);
            sagittal_h_line_->SetPoint2(xw, org[1] + (dims[1]-1) * sp[1], zw);
            // vertical: vary Z at Y = yw -> points (xw, yw, orgZ) -> (xw, yw, orgZ + (dims[2]-1)*sp[2])
            sagittal_v_line_->SetPoint1(xw, yw, org[2]);
            sagittal_v_line_->SetPoint2(xw, yw, org[2] + (dims[2]-1) * sp[2]);
        }

        if (sagittal_ && sagittal_->renderWindow()) sagittal_->renderWindow()->Render();
    }

    // Coronal
    vtkSmartPointer<vtkImageData> corSlice = core_->extractSlice("coronal", idx_coronal_);
    if (corSlice && r_coronal_) {
        vtkSmartPointer<vtkImageActor> actor = vtkSmartPointer<vtkImageActor>::New();
        actor->GetMapper()->SetInputData(corSlice);
        r_coronal_->RemoveAllViewProps();
        r_coronal_->AddActor(actor);
        if (coronal_h_actor_) r_coronal_->AddActor(coronal_h_actor_);
        if (coronal_v_actor_) r_coronal_->AddActor(coronal_v_actor_);
        r_coronal_->ResetCamera();

        // Update coronal crosshairs (plane Y fixed)
        vtkImageData* img = core_->getMRIImage();
        if (img) {
            int dims[3]; img->GetDimensions(dims);
            double sp[3]; img->GetSpacing(sp);
            double org[3]; img->GetOrigin(org);
            double xw = org[0] + idx_sagittal_ * sp[0];
            double yw = org[1] + idx_coronal_ * sp[1];
            double zw = org[2] + idx_axial_ * sp[2];
            // horizontal: vary X at Z = zw -> (orgX, yw, zw) -> (orgX + (dims[0]-1)*sp[0], yw, zw)
            coronal_h_line_->SetPoint1(org[0], yw, zw);
            coronal_h_line_->SetPoint2(org[0] + (dims[0]-1) * sp[0], yw, zw);
            // vertical: vary Z at X = xw -> (xw, yw, orgZ) -> (xw, yw, orgZ + (dims[2]-1)*sp[2])
            coronal_v_line_->SetPoint1(xw, yw, org[2]);
            coronal_v_line_->SetPoint2(xw, yw, org[2] + (dims[2]-1) * sp[2]);
        }

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

void MainWindow::update_axial_slice(int v)
{
    idx_axial_ = v;
    updateViews();
}

void MainWindow::update_sagittal_slice(int v)
{
    idx_sagittal_ = v;
    updateViews();
}

void MainWindow::update_coronal_slice(int v)
{
    idx_coronal_ = v;
    updateViews();
}

void MainWindow::seekToIndices(int x, int y, int z)
{
    // Update internal indices
    idx_sagittal_ = x;
    idx_coronal_ = y;
    idx_axial_ = z;

    // Block slider signals while updating
    if (axial_slider_) axial_slider_->blockSignals(true);
    if (sagittal_slider_) sagittal_slider_->blockSignals(true);
    if (coronal_slider_) coronal_slider_->blockSignals(true);

    if (axial_slider_) axial_slider_->setValue(idx_axial_);
    if (sagittal_slider_) sagittal_slider_->setValue(idx_sagittal_);
    if (coronal_slider_) coronal_slider_->setValue(idx_coronal_);

    if (axial_slider_) axial_slider_->blockSignals(false);
    if (sagittal_slider_) sagittal_slider_->blockSignals(false);
    if (coronal_slider_) coronal_slider_->blockSignals(false);

    updateViews();
    statusBar()->showMessage(QString("Navigated to X:%1 Y:%2 Z:%3").arg(x).arg(y).arg(z), 2000);
}

// Event filter to catch clicks on VTK widgets to set the active axis
bool MainWindow::eventFilter(QObject* obj, QEvent* event)
{
    if (event->type() == QEvent::MouseButtonPress) {
        if (obj == axial_) {
            activeAxis_ = "axial";
            statusBar()->showMessage("Active: axial", 1500);
        } else if (obj == sagittal_) {
            activeAxis_ = "sagittal";
            statusBar()->showMessage("Active: sagittal", 1500);
        } else if (obj == coronal_) {
            activeAxis_ = "coronal";
            statusBar()->showMessage("Active: coronal", 1500);
        }
    }
    return QMainWindow::eventFilter(obj, event);
}

// Keyboard navigation for slice up/down
void MainWindow::keyPressEvent(QKeyEvent* event)
{
    if (!core_) { QMainWindow::keyPressEvent(event); return; }
    int dims[3] = {0,0,0};
    if (core_->getMRIImage()) core_->getMRIImage()->GetDimensions(dims);

    bool handled = false;
    if (event->key() == Qt::Key_Up) {
        if (activeAxis_ == "axial") { idx_axial_ = std::min(dims[2]-1, idx_axial_ + 1); handled = true; }
        else if (activeAxis_ == "sagittal") { idx_sagittal_ = std::min(dims[0]-1, idx_sagittal_ + 1); handled = true; }
        else if (activeAxis_ == "coronal") { idx_coronal_ = std::min(dims[1]-1, idx_coronal_ + 1); handled = true; }
    } else if (event->key() == Qt::Key_Down) {
        if (activeAxis_ == "axial") { idx_axial_ = std::max(0, idx_axial_ - 1); handled = true; }
        else if (activeAxis_ == "sagittal") { idx_sagittal_ = std::max(0, idx_sagittal_ - 1); handled = true; }
        else if (activeAxis_ == "coronal") { idx_coronal_ = std::max(0, idx_coronal_ - 1); handled = true; }
    }

    if (handled) {
        // update sliders to reflect programmatic change without re-triggering extra work
        if (axial_slider_) axial_slider_->blockSignals(true);
        if (sagittal_slider_) sagittal_slider_->blockSignals(true);
        if (coronal_slider_) coronal_slider_->blockSignals(true);

        if (axial_slider_) axial_slider_->setValue(idx_axial_);
        if (sagittal_slider_) sagittal_slider_->setValue(idx_sagittal_);
        if (coronal_slider_) coronal_slider_->setValue(idx_coronal_);

        if (axial_slider_) axial_slider_->blockSignals(false);
        if (sagittal_slider_) sagittal_slider_->blockSignals(false);
        if (coronal_slider_) coronal_slider_->blockSignals(false);

        updateViews();
        return;
    }

    QMainWindow::keyPressEvent(event);
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

