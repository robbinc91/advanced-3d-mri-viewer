#include "MainWindow.h"
#include <QApplication>
#include <QFile>
#include <QTextStream>

int main(int argc, char** argv)
{
    QApplication app(argc, argv);

    // Load QSS style: prefer dark theme if available. Resolve path relative to executable.
    QString exeDir = QCoreApplication::applicationDirPath();
    QString darkPath = exeDir + "/../resources/style_dark.qss"; // when running from build/bin
    QString defaultPath = exeDir + "/../resources/style.qss";

    auto tryLoad = [&](const QString &path) -> bool {
        QFile ff(path);
        if (!ff.exists()) return false;
        if (ff.open(QFile::ReadOnly | QFile::Text)) {
            QTextStream ts(&ff);
            app.setStyleSheet(ts.readAll());
            return true;
        }
        return false;
    };

    // Try dark theme first, then fallback to default style.qss, then the original relative path.
    if (!tryLoad(darkPath)) {
        if (!tryLoad(defaultPath)) {
            QFile ff("../resources/style.qss");
            if (ff.open(QFile::ReadOnly | QFile::Text)) {
                QTextStream ts(&ff);
                app.setStyleSheet(ts.readAll());
            }
        }
    }

    MainWindow w;
    w.show();

    return app.exec();
}
