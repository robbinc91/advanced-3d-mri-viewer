#include "MainWindow.h"
#include <QApplication>
#include <QFile>
#include <QTextStream>

int main(int argc, char** argv)
{
    QApplication app(argc, argv);

    // Load QSS style
    QFile f("../resources/style.qss");
    if (f.open(QFile::ReadOnly | QFile::Text)) {
        QTextStream ts(&f);
        app.setStyleSheet(ts.readAll());
    }

    MainWindow w;
    w.show();

    return app.exec();
}
