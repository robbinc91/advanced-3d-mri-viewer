#include "ExportWorker.h"
#include "ViewerCore.h"

#include <QPagedPaintDevice> 
#include <QPdfWriter>
#include <QPainter>
#include <QImage>
#include <QRectF>
#include <QFileInfo>
#include <QDir>
#include <QFile>

ExportWorker::ExportWorker(ViewerCore* core, const QString& filepath, QObject* parent)
    : QThread(parent), core_(core), filepath_(filepath), cancelRequested_(false)
{
}

ExportWorker::~ExportWorker() = default;

void ExportWorker::requestCancel()
{
    cancelRequested_.store(true);
}

void ExportWorker::run()
{
    if (!core_) {
        emit finished(false, "No core available");
        return;
    }

    QList<QString> tempImages;
    emit progress(5, "Preparing slices...");

    // 2D central slices
    for (const QString& view : {QString("axial"), QString("coronal"), QString("sagittal")}) {
        if (cancelRequested_.load()) { emit finished(false, "Export canceled"); return; }
        QString p = core_->saveSliceSnapshot(view, -1, QSize(400,400));
        if (!p.isEmpty()) tempImages.append(p);
    }

    emit progress(30, "Preparing 3D overview snapshots...");

    // 3D overview if mask exists
    if (core_->getMaskImage()) {
        for (int i = 0; i < 3; ++i) {
            if (cancelRequested_.load()) { emit finished(false, "Export canceled"); return; }
            QString p = core_->save3DSnapshot(-1, i, QSize(400,400));
            if (!p.isEmpty()) tempImages.append(p);
        }
    }

    emit progress(60, "Collecting per-label 3D snapshots and volumes...");

    // Per-label snapshots and volumes
    std::map<int,double> volumes = core_->computeLabelVolumes();
    QList<QPair<int, QList<QString>>> perLabelImages; // label -> list of image paths
    int labelCount = (int)volumes.size();
    int processedLabels = 0;
    for (auto &kv : volumes) {
        if (cancelRequested_.load()) { emit finished(false, "Export canceled"); return; }
        int label = kv.first;
        QList<QString> imgs;
        for (int a = 0; a < 3; ++a) {
            QString p = core_->save3DSnapshot(label, a, QSize(200,200));
            if (!p.isEmpty()) imgs.append(p);
        }
        perLabelImages.append(qMakePair(label, imgs));
        processedLabels++;
        emit progress(60 + (int)(30.0 * processedLabels / std::max(1, labelCount)), QString("Rendered labels (%1/%2)").arg(processedLabels).arg(labelCount));
    }

    emit progress(85, "Assembling PDF...");

    // Create PDF
    QPdfWriter writer(filepath_);
    writer.setPageSize(QPageSize(QPageSize::A4)); 
    //writer.setPageSize(QPagedPaintDevice::A4);
    writer.setResolution(150);

    QPainter painter(&writer);
    if (!painter.isActive()) {
        emit finished(false, "Failed to open PDF writer for output");
        return;
    }

    // Title
    painter.setFont(QFont("Helvetica", 18));
    painter.drawText(QRectF(0,0,writer.width(), 100), Qt::AlignCenter, QString("MRI Volume Report"));

    // Source info
    painter.setFont(QFont("Helvetica", 10));
    painter.drawText(QRectF(40, 110, writer.width()-80, 40), Qt::AlignLeft, QString("Source: %1").arg(core_->sourcePath()));

    int y = 160;

    // 2D central images
    int idx = 0;
    for (const QString& imgPath : tempImages) {
        if (cancelRequested_.load()) { painter.end(); emit finished(false, "Export canceled"); return; }
        QImage img(imgPath);
        if (img.isNull()) continue;

        int cols = 2;
        int w = (writer.width() - 80) / cols;
        int h = (img.height() * w) / std::max(1, img.width());
        int col = idx % cols;
        int row = idx / cols;
        int x = 40 + col * (w + 20);
        int ypos = y + row * (h + 20);
        painter.drawImage(QRectF(x, ypos, w, h), img);
        ++idx;
        if ((idx % (cols*2)) == 0) { writer.newPage(); y = 40; }
    }

    // Ensure next area has space
    writer.newPage();

    // Volumes table
    painter.setFont(QFont("Helvetica", 12));
    painter.drawText(QRectF(40, 40, writer.width()-80, 30), Qt::AlignLeft, QString("Volumetric Analysis (cm^3):"));
    int ty = 80;
    painter.setFont(QFont("Helvetica", 10));
    painter.drawText(40, ty, QString("Label"));
    painter.drawText(writer.width()/2, ty, QString("Volume (cm^3)"));
    ty += 20;
    for (auto &kv : volumes) {
        painter.drawText(40, ty, QString::number(kv.first));
        painter.drawText(writer.width()/2, ty, QString::number(kv.second, 'f', 3));
        ty += 18;
        if (ty > (int)writer.height() - 50) { writer.newPage(); ty = 40; }
    }

    // Per-label images
    for (auto &pair : perLabelImages) {
        if (cancelRequested_.load()) { painter.end(); emit finished(false, "Export canceled"); return; }
        writer.newPage();
        painter.setFont(QFont("Helvetica", 12));
        painter.drawText(QRectF(40, 40, writer.width()-80, 30), Qt::AlignLeft, QString("Label %1").arg(pair.first));
        int px = 40;
        int py = 80;
        for (const QString &p : pair.second) {
            QImage img(p);
            if (img.isNull()) continue;
            int w = 150;
            int h = (img.height() * w) / std::max(1, img.width());
            painter.drawImage(QRectF(px, py, w, h), img);
            px += w + 20;
        }
    }

    painter.end();

    // Clean up temporary images
    for (const QString& t : tempImages) { QFile::remove(t); }
    for (auto &pair : perLabelImages) for (const QString& t : pair.second) { QFile::remove(t); }

    if (cancelRequested_.load()) { emit finished(false, "Export canceled"); return; }

    emit progress(100, "PDF generated");
    emit finished(true, QString("Exported report to %1").arg(QFileInfo(filepath_).absoluteFilePath()));
}
