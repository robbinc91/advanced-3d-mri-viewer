#pragma once

#include <QMainWindow>
#include <memory>
#include <QSpinBox>
#include <QFutureWatcher>
#include <QStatusBar>
#include "ExportWorker.h" 
#include "ViewerCore.h"
#include <QSlider>
#include <QKeyEvent>

#include <vtkImageMapper3D.h>
#include <vtkPolyDataMapper.h>
#include <vtkCamera.h>
#include <vtkRendererCollection.h>  
#include <vtkRenderWindowInteractor.h>

class QVTKOpenGLNativeWidget;
class QScrollArea;
class QPushButton;
class ViewerCore;
class vtkCallbackCommand;

class MainWindow : public QMainWindow
{
    Q_OBJECT
public:
    explicit MainWindow(QWidget* parent = nullptr);
    ~MainWindow() override;

private:
    static void vtkInteractorEventCallback(vtkObject* caller, 
                                          long unsigned int eventId,
                                          void* clientData, 
                                          void* callData);
    void setupUi();
    QWidget* buildLeftPanel();
    QWidget* buildVisGrid();
    void setupInteractors();

    QScrollArea* leftScroll_ = nullptr;
    QWidget* visGridWidget_ = nullptr;
    // Controls
    QPushButton* btnLoadMRI_ = nullptr;
    QPushButton* btnLoadMask_ = nullptr;
    QPushButton* btnExportReport_ = nullptr;
    QPushButton* btnCancelExport_ = nullptr;
    QPushButton* btnRunN4_ = nullptr;
    QPushButton* btnRunMultiOtsu_ = nullptr;
    QSpinBox* nClassesSpin_ = nullptr;

    // VTK/Views
    QVTKOpenGLNativeWidget* axial_ = nullptr;
    vtkSmartPointer<class vtkRenderer> r_axial_;
    QVTKOpenGLNativeWidget* sagittal_ = nullptr;
    vtkSmartPointer<class vtkRenderer> r_sagittal_;
    QVTKOpenGLNativeWidget* coronal_ = nullptr;
    vtkSmartPointer<class vtkRenderer> r_coronal_;
    QVTKOpenGLNativeWidget* vol3d_ = nullptr;
    vtkSmartPointer<class vtkRenderer> r_vol3d_;

    QWidget* centralWidget_ = nullptr; 

    // Current slice indices for navigation
    int idx_axial_ = 0;
    int idx_sagittal_ = 0;
    int idx_coronal_ = 0;

    // Last requested seek indices (throttle repeated picks)
    int last_seek_x_ = -1;
    int last_seek_y_ = -1;
    int last_seek_z_ = -1;

    // Sliders for 2D navigation
    QSlider* axial_slider_ = nullptr;
    QSlider* sagittal_slider_ = nullptr;
    QSlider* coronal_slider_ = nullptr;

    // Active axis for keyboard navigation: "axial", "sagittal", "coronal"
    QString activeAxis_ = "axial";
    // Keep VTK callback commands and client data alive
    std::vector<vtkCallbackCommand*> interactorCallbacks_;
    std::vector<void*> interactorCallbackDatas_;

    // Crosshair line sources and actors (one horizontal + one vertical per 2D view)
    vtkSmartPointer<class vtkLineSource> axial_h_line_;
    vtkSmartPointer<class vtkLineSource> axial_v_line_;
    vtkSmartPointer<class vtkActor> axial_h_actor_;
    vtkSmartPointer<class vtkActor> axial_v_actor_;

    vtkSmartPointer<class vtkLineSource> sagittal_h_line_;
    vtkSmartPointer<class vtkLineSource> sagittal_v_line_;
    vtkSmartPointer<class vtkActor> sagittal_h_actor_;
    vtkSmartPointer<class vtkActor> sagittal_v_actor_;

    vtkSmartPointer<class vtkLineSource> coronal_h_line_;
    vtkSmartPointer<class vtkLineSource> coronal_v_line_;
    vtkSmartPointer<class vtkActor> coronal_h_actor_;
    vtkSmartPointer<class vtkActor> coronal_v_actor_;

    // Core backend
    std::unique_ptr<ViewerCore> core_;
    class ExportWorker* exportWorker_ = nullptr;
    QFutureWatcher<QString>* n4Watcher_ = nullptr;
    QFutureWatcher<QString>* otsuWatcher_ = nullptr;

private slots:
    void onRunN4();
    void onRunMultiOtsu();
    void onLoadMRI();
    void onLoadMask();
    void onCoreLoaded(bool success, const QString& message);
    void updateViews();
    void update_axial_slice(int v);
    void update_sagittal_slice(int v);
    void update_coronal_slice(int v);
    void seekToIndices(int x, int y, int z);
    void showVolumes();
    void onExportReportClicked();
    void onCancelExportClicked();
    void onExportProgress(int percent, const QString& message);
    void onExportFinished(bool success, const QString& message);

protected:
    bool eventFilter(QObject* obj, QEvent* event) override;
    void keyPressEvent(QKeyEvent* event) override;
};
