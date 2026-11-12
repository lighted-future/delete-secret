# delete-secret

Windows 桌面浏览器历史清理工具：根据网址中包含的关键词，预览并删除匹配的本地访问记录。

## 功能

- 选择 Chrome、Edge、Brave、Firefox 及浏览器配置目录。
- 手动选择 `History` 或 `places.sqlite` 数据库。
- 按字面匹配网址中的文本，可选择是否区分大小写。
- 预览匹配结果，删除选中记录或全部匹配记录。
- 删除前自动备份；Firefox 书签保留。

## 使用

完全退出目标浏览器，包括后台进程。打开程序后选择浏览器配置，输入关键词并预览，再确认删除。

v2 Windows 打包版采用目录发布方式：运行 `HistoryKeywordCleaner.exe`，必须保留旁边的 `_internal` 文件夹。分发时应压缩整个目录，不要只分享 exe。

详细操作和恢复备份方法见 [使用说明](使用说明.txt)。

## 从源码运行

环境：Windows 10 / 11、带 Tkinter 的 Python 3.12。运行本身只使用 Python 标准库。

```powershell
python history_cleaner.py
```

## 测试

```powershell
python tests/test_cleaner.py
```

测试使用临时模拟数据库，覆盖 Chromium / Firefox 的匹配、删除、其他网址保留、Firefox 书签保留、备份及数据库完整性。没有用真实用户历史进行测试；不同浏览器版本的数据库结构仍可能存在兼容性差异。

## 打包

推荐使用 python.org 的 Windows Python 3.12，在独立虚拟环境内打包：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onedir --windowed --name HistoryKeywordCleaner history_cleaner.py
```

输出目录为 `dist/HistoryKeywordCleaner`。发布前应在没有 Python 环境的 Windows 电脑上验证启动。Anaconda 环境可能需要额外显式收集 Tcl / Tk 和 SQLite 的 DLL 与脚本库，不应直接套用上面的常规 Python 打包命令。

## 数据与范围

- 工具不上传浏览器历史。备份保存在 `%LOCALAPPDATA%/HistoryKeywordCleaner/backups`。
- 只处理所选配置的本地访问记录；不处理 Cookie、缓存、下载文件或云端历史。
- 同步服务可能重新带回历史。本工具不是安全擦除工具。
- 备份包含原始历史，应自行保存或清理。不要将浏览器数据库或备份提交到仓库。

## 版本

- **v1**：首次发布，单文件程序；在部分环境出现 `init.tcl` 启动错误。
- **v2**：改用目录发布，显式包含界面运行库，针对上述启动问题调整打包方式。业务功能与 v1 相同。

详见 [更新说明](CHANGELOG.txt)。源码与打包程序应分别管理，Windows 可执行版本适合放在 GitHub Releases，并保留每版更新说明。
