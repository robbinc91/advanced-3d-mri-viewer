#pragma once

#include <QMainWindow>
#include <memory>

class QVTKOpenGLNativeWidget;
class QScrollArea;

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
};
