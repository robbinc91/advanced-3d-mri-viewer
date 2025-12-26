#pragma once

#include <QSize>
#include <QObject>
#include <QString>
#include <memory>

#include <vtkSmartPointer.h>
#include <vtkImageData.h>
#include <vtkPolyData.h>
#include <vtkRenderer.h>
#include <vtkImageMapper3D.h>  // Add this
#include <vtkCamera.h>  // Add this
#include <vtkPolyDataMapper.h>  // Add this
#include <vtkImageMapToColors.h>  // Add this

class vtkImageData;

class ViewerCore : public QObject
{
    Q_OBJECT
public:
    explicit ViewerCore(QObject* parent = nullptr);
    ~ViewerCore() override;

    // Load MRI using ITK; returns true on success
    bool loadMRI(const QString& path, QString& err);
    bool loadMask(const QString& path, QString& err);

    // Access converted VTK images
    vtkImageData* getMRIImage() const;
    vtkImageData* getMaskImage() const;

    // Helper: fill central slice indices for axial/coronal/sagittal
    void getRepresentativeSliceIndex(int& axial, int& coronal, int& sagittal) const;

    // Extract a 2D slice as a vtkImageData for the given view name: "axial", "coronal", "sagittal".
    // If index == -1, uses the representative (central) index.
    vtkSmartPointer<vtkImageData> extractSlice(const QString& viewName, int index = -1) const;
    vtkSmartPointer<vtkImageData> extractMaskSlice(const QString& viewName, int index = -1) const;

    // Compute label volumes (returns map<label_value, volume_cm3>)
    std::map<int, double> computeLabelVolumes() const;

    // Create a 3D mesh (vtkPolyData) for the given label (or all labels if labelValue == -1)
    vtkSmartPointer<vtkPolyData> create3DMeshForLabel(int labelValue = -1) const;

    // Snapshot helpers: write PNGs for 2D slice or 3D view. Returns path or empty string on error.
    QString saveSliceSnapshot(const QString& viewName, int index, const QSize& size = QSize(300,300)) const;
    QString save3DSnapshot(int labelValue, int angleIndex, const QSize& size = QSize(400,400)) const;

    // Return source file path of last loaded MRI or mask
    QString sourcePath() const;

    // Image processing (ITK): returns empty string on success, error message on failure
    QString applyN4(int maxIterations = 50);
    QString runMultiOtsu(int nClasses = 3);

    // Voxel spacing (mm)
    double spacing[3];

signals:
    void loaded(bool success, const QString& message);

private:
    struct Impl;
    std::unique_ptr<Impl> pimpl;
};
