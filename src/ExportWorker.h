#pragma once

#include <QThread>
//#include <QAtomicBool> 
#include <QString>
#include <QSize>
#include <QObject>

#include <atomic> 
class ViewerCore;

class ExportWorker : public QThread
{
    Q_OBJECT
public:
    explicit ExportWorker(ViewerCore* core, const QString& filepath, QObject* parent = nullptr);
    ~ExportWorker() override;

    void requestCancel();

signals:
    void progress(int percent, const QString& message);
    void finished(bool success, const QString& message);

protected:
    void run() override;

private:
    ViewerCore* core_ = nullptr; // non-owning
    QString filepath_;
    std::atomic<bool> cancelRequested_;
    //QAtomicBool cancelRequested_;
};
