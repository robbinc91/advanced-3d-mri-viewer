#pragma once

#include <QMainWindow>
#include <memory>
#include <QSpinBox>
#include <QFutureWatcher>
#include <QStatusBar>
#include "ExportWorker.h" 
#include "ViewerCore.h"

#include <vtkImageMapper3D.h>
#include <vtkPolyDataMapper.h>
#include <vtkCamera.h>

class QVTKOpenGLNativeWidget;
class QScrollArea;
class QPushButton;
class ViewerCore;

class MainWindow : public QMainWindow
{
    Q_OBJECT
public:
    explicit MainWindow(QWidget* parent = nullptr);
    ~MainWindow() override {}

private:
    void setupUi();
    QWidget* buildLeftPanel();
    QWidget* buildVisGrid();

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
    void showVolumes();
    void onExportReportClicked();
    void onCancelExportClicked();
    void onExportProgress(int percent, const QString& message);
    void onExportFinished(bool success, const QString& message);
};
