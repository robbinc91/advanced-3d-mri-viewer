#include "ViewerCore.h"

#include <itkImage.h>
#include <itkImageFileReader.h>
#include <itkImportImageFilter.h>

#include <vtkSmartPointer.h>
#include <vtkImageData.h>
#include <vtkImageImport.h>
#include <itkOtsuThresholdImageFilter.h>
#include <itkN4BiasFieldCorrectionImageFilter.h>


#include <itkOtsuMultipleThresholdsImageFilter.h>
//#include <itkScalarImageToOtsuMultipleThresholdsImageFilter.h>
#include <itkThresholdImageFilter.h>
#include <itkCastImageFilter.h>
#include <itkImageRegionIterator.h>
#include <vector>
#include <vtkImageReslice.h>
#include <vtkMatrix4x4.h>
#include <vtkImageActor.h>
#include <vtkRenderer.h>
#include <vtkRenderWindow.h>
#include <vtkWindowToImageFilter.h>
#include <vtkPNGWriter.h>
#include <vtkImageThreshold.h>
#include <vtkMarchingCubes.h>
#include <vtkPolyData.h>
#include <vtkPolyDataMapper.h>
#include <vtkActor.h>
#include <vtkSmartPointer.h>
#include <vtkImageData.h>
#include <vtkPointData.h>
#include <vtkDataArray.h>
#include <vtkMatrix4x4.h>
#include <QSize>
#include <QDir>
#include <QStandardPaths>
#include <unordered_map>
#include <sstream>

#include <QString>
#include <iostream>

struct ViewerCore::Impl {
    vtkSmartPointer<vtkImageData> mriImage;
    vtkSmartPointer<vtkImageData> maskImage;
    QString mriPath;
    QString maskPath;
};

ViewerCore::ViewerCore(QObject* parent)
    : QObject(parent), pimpl(std::make_unique<Impl>())
{
    spacing[0] = spacing[1] = spacing[2] = 1.0;
}

ViewerCore::~ViewerCore() = default;

bool ViewerCore::loadMRI(const QString& path, QString& err)
{
    try {
        using PixelType = float;
        constexpr unsigned int Dimension = 3;
        using ImageType = itk::Image<PixelType, Dimension>;
        using ReaderType = itk::ImageFileReader<ImageType>;

        auto reader = ReaderType::New();
        reader->SetFileName(path.toStdString());
        reader->Update();

        auto image = reader->GetOutput();
        auto region = image->GetBufferedRegion();
        auto size = region.GetSize();

        // Store spacing
        auto sp = image->GetSpacing();
        spacing[0] = sp[0]; spacing[1] = sp[1]; spacing[2] = sp[2];

        // Copy data into vtkImageData via vtkImageImport
        vtkSmartPointer<vtkImageImport> importer = vtkSmartPointer<vtkImageImport>::New();

        // Ensure contiguous buffer
        const PixelType* buf = image->GetBufferPointer();
        size_t nvox = static_cast<size_t>(size[0]) * size[1] * size[2];

        // Copy to a temporary std::vector that will be owned by VTK importer
        std::vector<PixelType> tmp;
        tmp.assign(buf, buf + nvox);

        importer->SetImportVoidPointer(static_cast<void*>(tmp.data()));
        importer->SetDataScalarTypeToFloat();
        importer->SetNumberOfScalarComponents(1);
        importer->SetDataExtent(0, static_cast<int>(size[0]) - 1,
                                0, static_cast<int>(size[1]) - 1,
                                0, static_cast<int>(size[2]) - 1);
        importer->SetWholeExtent(importer->GetDataExtent());
        importer->SetDataSpacing(sp[0], sp[1], sp[2]);
        importer->Update();

        pimpl->mriImage = vtkSmartPointer<vtkImageData>::New();
        pimpl->mriImage->DeepCopy(importer->GetOutput());
        pimpl->mriPath = path;//QString::fromStdString(path);

        // Keep tmp alive until function exit (VTK deep-copied the data)

        emit loaded(true, "Loaded MRI successfully");
        return true;
    } catch (const itk::ExceptionObject& ex) {
        err = QString::fromStdString(ex.GetDescription());
        emit loaded(false, err);
        return false;
    } catch (const std::exception& ex) {
        err = QString::fromStdString(ex.what());
        emit loaded(false, err);
        return false;
    }
}

bool ViewerCore::loadMask(const QString& path, QString& err)
{
    try {
        using PixelType = unsigned short;
        constexpr unsigned int Dimension = 3;
        using ImageType = itk::Image<PixelType, Dimension>;
        using ReaderType = itk::ImageFileReader<ImageType>;

        auto reader = ReaderType::New();
        reader->SetFileName(path.toStdString());
        reader->Update();

        auto image = reader->GetOutput();
        auto region = image->GetBufferedRegion();
        auto size = region.GetSize();

        auto sp = image->GetSpacing();

        // Copy data into vtkImageData via vtkImageImport
        vtkSmartPointer<vtkImageImport> importer = vtkSmartPointer<vtkImageImport>::New();

        const PixelType* buf = image->GetBufferPointer();
        size_t nvox = static_cast<size_t>(size[0]) * size[1] * size[2];
        std::vector<PixelType> tmp;
        tmp.assign(buf, buf + nvox);

        importer->SetImportVoidPointer(static_cast<void*>(tmp.data()));
        importer->SetDataScalarTypeToUnsignedShort();
        importer->SetNumberOfScalarComponents(1);
        importer->SetDataExtent(0, static_cast<int>(size[0]) - 1,
                                0, static_cast<int>(size[1]) - 1,
                                0, static_cast<int>(size[2]) - 1);
        importer->SetWholeExtent(importer->GetDataExtent());
        importer->SetDataSpacing(sp[0], sp[1], sp[2]);
        importer->Update();

        pimpl->maskImage = vtkSmartPointer<vtkImageData>::New();
        pimpl->maskImage->DeepCopy(importer->GetOutput());
        pimpl->maskPath = path;//QString::fromStdString(path);

        emit loaded(true, "Loaded mask successfully");
        return true;
    } catch (const itk::ExceptionObject& ex) {
        err = QString::fromStdString(ex.GetDescription());
        emit loaded(false, err);
        return false;
    } catch (const std::exception& ex) {
        err = QString::fromStdString(ex.what());
        emit loaded(false, err);
        return false;
    }
}

vtkImageData* ViewerCore::getMRIImage() const
{
    return pimpl->mriImage.GetPointer();
}

vtkImageData* ViewerCore::getMaskImage() const
{
    return pimpl->maskImage.GetPointer();
}

void ViewerCore::getRepresentativeSliceIndex(int& axial, int& coronal, int& sagittal) const
{
    axial = coronal = sagittal = 0;
    if (!pimpl->mriImage) return;
    int dims[3];
    pimpl->mriImage->GetDimensions(dims);
    axial = dims[2] > 0 ? dims[2] / 2 : 0;   // Z dimension is 3rd component here
    coronal = dims[1] > 0 ? dims[1] / 2 : 0; // Y
    sagittal = dims[0] > 0 ? dims[0] / 2 : 0; // X
}

vtkSmartPointer<vtkImageData> ViewerCore::extractSlice(const QString& viewName, int index) const
{
    if (!pimpl->mriImage) return nullptr;

    int dims[3];
    pimpl->mriImage->GetDimensions(dims);

    int axial, coronal, sagittal;
    getRepresentativeSliceIndex(axial, coronal, sagittal);
    if (index == -1) {
        if (viewName == "axial") index = axial;
        else if (viewName == "coronal") index = coronal;
        else if (viewName == "sagittal") index = sagittal;
        else index = axial;
    }

    // Setup reslice matrix (same logic as Python port)
    vtkSmartPointer<vtkMatrix4x4> matrix = vtkSmartPointer<vtkMatrix4x4>::New();
    matrix->Identity();

    if (viewName == "axial") {
        matrix->SetElement(2, 3, index);
    } else if (viewName == "coronal") {
        matrix->SetElement(1, 1, 0);
        matrix->SetElement(1, 2, -1);
        matrix->SetElement(2, 1, 1);
        matrix->SetElement(2, 3, index);
    } else if (viewName == "sagittal") {
        matrix->SetElement(0, 0, 0);
        matrix->SetElement(0, 1, 1);
        matrix->SetElement(1, 0, -1);
        matrix->SetElement(2, 3, index);
    }

    vtkSmartPointer<vtkImageReslice> reslice = vtkSmartPointer<vtkImageReslice>::New();
    reslice->SetInputData(pimpl->mriImage);
    reslice->SetResliceAxes(matrix);
    reslice->SetOutputDimensionality(2);
    reslice->Update();

    vtkSmartPointer<vtkImageData> out = vtkSmartPointer<vtkImageData>::New();
    out->DeepCopy(reslice->GetOutput());
    return out;
}

vtkSmartPointer<vtkImageData> ViewerCore::extractMaskSlice(const QString& viewName, int index) const
{
    if (!pimpl->maskImage) return nullptr;

    int dims[3];
    pimpl->maskImage->GetDimensions(dims);

    int axial, coronal, sagittal;
    getRepresentativeSliceIndex(axial, coronal, sagittal);
    if (index == -1) {
        if (viewName == "axial") index = axial;
        else if (viewName == "coronal") index = coronal;
        else if (viewName == "sagittal") index = sagittal;
        else index = axial;
    }

    vtkSmartPointer<vtkMatrix4x4> matrix = vtkSmartPointer<vtkMatrix4x4>::New();
    matrix->Identity();
    if (viewName == "axial") {
        matrix->SetElement(2, 3, index);
    } else if (viewName == "coronal") {
        matrix->SetElement(1, 1, 0);
        matrix->SetElement(1, 2, -1);
        matrix->SetElement(2, 1, 1);
        matrix->SetElement(2, 3, index);
    } else if (viewName == "sagittal") {
        matrix->SetElement(0, 0, 0);
        matrix->SetElement(0, 1, 1);
        matrix->SetElement(1, 0, -1);
        matrix->SetElement(2, 3, index);
    }

    vtkSmartPointer<vtkImageReslice> reslice = vtkSmartPointer<vtkImageReslice>::New();
    reslice->SetInputData(pimpl->maskImage);
    reslice->SetResliceAxes(matrix);
    reslice->SetOutputDimensionality(2);
    reslice->Update();

    vtkSmartPointer<vtkImageData> out = vtkSmartPointer<vtkImageData>::New();
    out->DeepCopy(reslice->GetOutput());
    return out;
}

std::map<int, double> ViewerCore::computeLabelVolumes() const
{
    std::map<int, double> results;
    if (!pimpl->maskImage) return results;
    vtkDataArray* arr = pimpl->maskImage->GetPointData()->GetScalars();
    if (!arr) return results;
    vtkIdType n = arr->GetNumberOfTuples();
    std::unordered_map<int, size_t> counts;
    for (vtkIdType i = 0; i < n; ++i) {
        int val = static_cast<int>(arr->GetTuple1(i));
        counts[val]++;
    }
    double spm[3] = {1.0, 1.0, 1.0};
    pimpl->maskImage->GetSpacing(spm);
    double voxVol_mm3 = spm[0] * spm[1] * spm[2];
    for (auto &kv : counts) {
        int label = kv.first;
        if (label == 0) continue;
        size_t cnt = kv.second;
        double vol_cm3 = (cnt * voxVol_mm3) / 1000.0;
        results[label] = vol_cm3;
    }
    return results;
}

vtkSmartPointer<vtkPolyData> ViewerCore::create3DMeshForLabel(int labelValue) const
{
    if (!pimpl->maskImage) return nullptr;

    vtkSmartPointer<vtkImageThreshold> thresh = vtkSmartPointer<vtkImageThreshold>::New();
    thresh->SetInputData(pimpl->maskImage);
    if (labelValue < 0) {
        // render all labels by thresholding > 0
        thresh->ThresholdByLower(1); // values >=1
    } else {
        thresh->ThresholdBetween(labelValue, labelValue);
    }
    thresh->ReplaceInOn();
    thresh->SetInValue(1.0);
    thresh->ReplaceOutOn();
    thresh->SetOutValue(0.0);
    thresh->Update();

    vtkSmartPointer<vtkMarchingCubes> mc = vtkSmartPointer<vtkMarchingCubes>::New();
    mc->SetInputConnection(thresh->GetOutputPort());
    mc->SetValue(0, 0.5);
    mc->Update();

    vtkSmartPointer<vtkPolyData> poly = vtkSmartPointer<vtkPolyData>::New();
    poly->DeepCopy(mc->GetOutput());
    return poly;
}

QString ViewerCore::saveSliceSnapshot(const QString& viewName, int index, const QSize& size) const
{
    vtkSmartPointer<vtkImageData> slice = extractSlice(viewName, index);
    if (!slice) return QString();

    vtkSmartPointer<vtkImageActor> actor = vtkSmartPointer<vtkImageActor>::New();
    actor->GetMapper()->SetInputData(slice);

    vtkSmartPointer<vtkRenderer> renderer = vtkSmartPointer<vtkRenderer>::New();
    renderer->AddActor(actor);
    renderer->ResetCamera();

    vtkSmartPointer<vtkRenderWindow> rw = vtkSmartPointer<vtkRenderWindow>::New();
    rw->SetOffScreenRendering(1);
    rw->AddRenderer(renderer);
    rw->SetSize(size.width(), size.height());
    renderer->Render();

    vtkSmartPointer<vtkWindowToImageFilter> w2i = vtkSmartPointer<vtkWindowToImageFilter>::New();
    w2i->SetInput(rw);
    w2i->Update();

    QString tmp = QDir::temp().filePath(QString("slice_%1.png").arg(viewName));
    vtkSmartPointer<vtkPNGWriter> writer = vtkSmartPointer<vtkPNGWriter>::New();
    writer->SetFileName(tmp.toUtf8().constData());
    writer->SetInputConnection(w2i->GetOutputPort());
    writer->Write();
    return tmp;
}

QString ViewerCore::save3DSnapshot(int labelValue, int angleIndex, const QSize& size) const
{
    vtkSmartPointer<vtkPolyData> mesh = create3DMeshForLabel(labelValue);
    if (!mesh || mesh->GetNumberOfPoints() == 0) return QString();

    vtkSmartPointer<vtkPolyDataMapper> mapper = vtkSmartPointer<vtkPolyDataMapper>::New();
    mapper->SetInputData(mesh);

    vtkSmartPointer<vtkActor> actor = vtkSmartPointer<vtkActor>::New();
    actor->SetMapper(mapper);

    vtkSmartPointer<vtkRenderer> renderer = vtkSmartPointer<vtkRenderer>::New();
    renderer->AddActor(actor);
    renderer->SetBackground(0.0, 0.0, 0.0);

    vtkSmartPointer<vtkRenderWindow> rw = vtkSmartPointer<vtkRenderWindow>::New();
    rw->SetOffScreenRendering(1);
    rw->AddRenderer(renderer);
    rw->SetSize(size.width(), size.height());

    renderer->ResetCamera();
    auto camera = renderer->GetActiveCamera();
    // camera angle presets
    if (angleIndex % 3 == 0) {
        camera->Azimuth(0);
        camera->Elevation(0);
    } else if (angleIndex % 3 == 1) {
        camera->Azimuth(45);
        camera->Elevation(15);
    } else {
        camera->Azimuth(90);
        camera->Elevation(0);
    }
    renderer->ResetCameraClippingRange();
    renderer->Render();

    vtkSmartPointer<vtkWindowToImageFilter> w2i = vtkSmartPointer<vtkWindowToImageFilter>::New();
    w2i->SetInput(rw);
    w2i->Update();

    QString tmp = QDir::temp().filePath(QString("3d_%1_%2.png").arg(labelValue).arg(angleIndex));
    vtkSmartPointer<vtkPNGWriter> writer = vtkSmartPointer<vtkPNGWriter>::New();
    writer->SetFileName(tmp.toUtf8().constData());
    writer->SetInputConnection(w2i->GetOutputPort());
    writer->Write();
    return tmp;
}

QString ViewerCore::sourcePath() const
{
    return pimpl->mriPath;
}

QString ViewerCore::applyN4(int maxIterations)
{
    if (pimpl->mriPath.isEmpty()) return "No MRI loaded";
    try {
        using PixelType = float;
        constexpr unsigned int Dimension = 3;
        using ImageType = itk::Image<PixelType, Dimension>;
        using ReaderType = itk::ImageFileReader<ImageType>;

        auto reader = ReaderType::New();
        reader->SetFileName(pimpl->mriPath.toStdString());
        reader->Update();
        auto input = reader->GetOutput();

        // Create a mask using Otsu to identify foreground
        using MaskType = itk::Image<unsigned char, Dimension>;
        using OtsuType = itk::OtsuThresholdImageFilter<ImageType, MaskType>;
        auto otsu = OtsuType::New();
        otsu->SetInput(input);
        otsu->SetInsideValue(0);
        otsu->SetOutsideValue(1);
        otsu->Update();

        using N4FilterType = itk::N4BiasFieldCorrectionImageFilter<ImageType, MaskType, ImageType>;
        auto n4 = N4FilterType::New();
        n4->SetInput(input);
        n4->SetMaskImage(otsu->GetOutput());
        N4FilterType::VariableSizeArrayType maxIt;
        maxIt.SetSize(3);
        maxIt[0] = maxIterations;
        maxIt[1] = maxIterations / 2;
        maxIt[2] = maxIterations / 4;
        n4->SetMaximumNumberOfIterations(maxIt);
        n4->Update();

        auto corrected = n4->GetOutput();

        // Copy corrected ITK image into VTK image
        auto region = corrected->GetBufferedRegion();
        auto size = region.GetSize();
        const PixelType* buf = corrected->GetBufferPointer();
        size_t nvox = static_cast<size_t>(size[0]) * size[1] * size[2];
        std::vector<PixelType> tmp;
        tmp.assign(buf, buf + nvox);

        vtkSmartPointer<vtkImageImport> importer = vtkSmartPointer<vtkImageImport>::New();
        importer->SetImportVoidPointer(static_cast<void*>(tmp.data()));
        importer->SetDataScalarTypeToFloat();
        importer->SetNumberOfScalarComponents(1);
        importer->SetDataExtent(0, static_cast<int>(size[0]) - 1,
                                0, static_cast<int>(size[1]) - 1,
                                0, static_cast<int>(size[2]) - 1);
        importer->SetWholeExtent(importer->GetDataExtent());
        importer->SetDataSpacing(corrected->GetSpacing()[0], corrected->GetSpacing()[1], corrected->GetSpacing()[2]);
        importer->Update();

        pimpl->mriImage = vtkSmartPointer<vtkImageData>::New();
        pimpl->mriImage->DeepCopy(importer->GetOutput());

        return QString(); // success
    } catch (const itk::ExceptionObject& ex) {
        return QString::fromStdString(ex.GetDescription());
    } catch (const std::exception& ex) {
        return QString::fromStdString(ex.what());
    }
}

QString ViewerCore::runMultiOtsu(int nClasses)
{
    if (pimpl->mriPath.isEmpty()) return "No MRI loaded";
    if (nClasses < 2) return "nClasses must be >= 2";
    try {
        using PixelType = float;
        constexpr unsigned int Dimension = 3;
        using ImageType = itk::Image<PixelType, Dimension>;
        using ReaderType = itk::ImageFileReader<ImageType>;

        auto reader = ReaderType::New();
        reader->SetFileName(pimpl->mriPath.toStdString());
        reader->Update();
        auto input = reader->GetOutput();

        using OtsuType = itk::OtsuMultipleThresholdsImageFilter<ImageType, ImageType>;
        auto otsu = OtsuType::New();
        otsu->SetNumberOfThresholds(nClasses - 1);
        otsu->SetInput(input);
        otsu->Update();

        auto thresholds = otsu->GetThresholds();

        // Build label image (unsigned short)
        using LabelPixelType = unsigned short;
        using LabelImageType = itk::Image<LabelPixelType, Dimension>;
        auto labelImage = LabelImageType::New();
        labelImage->SetRegions(input->GetLargestPossibleRegion());
        labelImage->SetSpacing(input->GetSpacing());
        labelImage->SetOrigin(input->GetOrigin());
        labelImage->Allocate();

        auto it = itk::ImageRegionIterator<ImageType>(input, input->GetLargestPossibleRegion());
        auto lit = itk::ImageRegionIterator<LabelImageType>(labelImage, labelImage->GetLargestPossibleRegion());

        for (it.GoToBegin(), lit.GoToBegin(); !it.IsAtEnd(); ++it, ++lit) {
            double v = it.Get();
            unsigned short lab = 0;
            for (unsigned int t = 0; t < thresholds.size(); ++t) {
                if (v > thresholds[t]) lab = static_cast<unsigned short>(t+1);
                else break;
            }
            lit.Set(lab);
        }

        // Copy labels to VTK image
        auto region = labelImage->GetBufferedRegion();
        auto size = region.GetSize();
        using LabelType = LabelPixelType;
        LabelType* buf = labelImage->GetBufferPointer();
        size_t nvox = static_cast<size_t>(size[0]) * size[1] * size[2];
        std::vector<LabelType> tmp;
        tmp.assign(buf, buf + nvox);

        vtkSmartPointer<vtkImageImport> importer = vtkSmartPointer<vtkImageImport>::New();
        importer->SetImportVoidPointer(static_cast<void*>(tmp.data()));
        importer->SetDataScalarTypeToUnsignedShort();
        importer->SetNumberOfScalarComponents(1);
        importer->SetDataExtent(0, static_cast<int>(size[0]) - 1,
                                0, static_cast<int>(size[1]) - 1,
                                0, static_cast<int>(size[2]) - 1);
        importer->SetWholeExtent(importer->GetDataExtent());
        importer->SetDataSpacing(labelImage->GetSpacing()[0], labelImage->GetSpacing()[1], labelImage->GetSpacing()[2]);
        importer->Update();

        pimpl->maskImage = vtkSmartPointer<vtkImageData>::New();
        pimpl->maskImage->DeepCopy(importer->GetOutput());

        return QString();
    } catch (const itk::ExceptionObject& ex) {
        return QString::fromStdString(ex.GetDescription());
    } catch (const std::exception& ex) {
        return QString::fromStdString(ex.what());
    }
}
