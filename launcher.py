# -*- coding: utf-8 -*-
from PyQt5 import QtCore, QtGui, QtWidgets
from uuid import uuid4 as uuid, UUID
import os
import json
import shutil
import minecraft_launcher_lib
import logging
from datetime import datetime


def fresh(self):
    self.log("正在刷新版本列表...")
    if os.path.exists("versions.json"):
        with open("versions.json", "r", encoding="utf-8") as f:
            try:
                versions = json.load(f)
            except Exception as e:
                self.log(f"读取本地版本列表失败：{e}，将重新获取...")
                versions = self.get_versions()
    else:
        versions = self.get_versions()
                
    with open("versions.json", "w", encoding="utf-8") as f:
        json.dump(versions, f, indent=4, ensure_ascii=False)
    if not versions:
        QtWidgets.QMessageBox.warning(self, "警告", "无法获取版本列表，请检查网络连接！", buttons=QtWidgets.QMessageBox.Ok)
        return
    try:
        self.versions_list.clear()
        self.versions_list.addItems(versions.keys())
        self.list_versions()
    except Exception as e:
        self.log(f"刷新版本列表失败：{e}")
        QtWidgets.QMessageBox.warning(self, "警告", "刷新版本列表失败，请检查网络连接！", buttons=QtWidgets.QMessageBox.Ok)
        return
    self.log("版本列表刷新完成")

class DownloadThread(QtCore.QThread):
    """下载线程"""
    signal_status = QtCore.pyqtSignal(str)
    signal_progress = QtCore.pyqtSignal(int)  # 添加进度信号
    signal_max = QtCore.pyqtSignal(int)  # 添加最大值信号
    signal_finished = QtCore.pyqtSignal(bool)
    signal_error = QtCore.pyqtSignal(str)

    def __init__(self, version_id, download_path):
        super(DownloadThread, self).__init__()
        self.version_id = version_id
        self.download_path = download_path

    def run(self):
        def set_status(status: str):
            self.signal_status.emit(status)

        def set_progress(progress: int):
            self.signal_progress.emit(progress)  # 发送进度信号
            
        def set_max(max_value: int):
            self.signal_max.emit(max_value)  # 发送最大值信号

        callback = {
            "setStatus": set_status,
            "setProgress": set_progress,  # 添加进度回调
            "setMax" : set_max,  # 最大值回调
        }

        minecraft_launcher_lib.install.install_minecraft_version(self.version_id, self.download_path, callback=callback)
        self.signal_finished.emit(True)


class ui_MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super(ui_MainWindow, self).__init__()
        self.setupUi(self)
        self.username = ""
        self.uuid = str(uuid())
        self.token = ""
        self.selected_version_id = ""  # 用于下载的版本号
        self.selected_version_name = ""  # 用于启动的版本名
        self.last_max = 0  # 用于记录上一次的最大值
        self.except_version_name = ""   # 跳过更新结构的版本名
        self.load_config()
        self.init_logging()
        self.download_thread = None
        self.is_downloading = False
        fresh(self)

    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(800, 600)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")

        # 添加进度条
        self.progress_bar = QtWidgets.QProgressBar(self.centralwidget)
        self.progress_bar.setGeometry(QtCore.QRect(250, 550, 531, 23))
        self.progress_bar.setProperty("value", 0)
        self.progress_bar.setObjectName("progress_bar")
        self.progress_bar.setRange(0, 0)  # 设置为不确定模式

        # 添加下载状态标签
        self.download_status_label = QtWidgets.QLabel(self.centralwidget)
        self.download_status_label.setGeometry(QtCore.QRect(250, 520, 800, 20))
        self.download_status_label.setObjectName("download_stxatus_label")
        self.download_status_label.setText("下载状态：等待中")

        # 版本选择框架
        self.version_choose_frame = QtWidgets.QFrame(self.centralwidget)
        self.version_choose_frame.setGeometry(QtCore.QRect(20, 20, 201, 91))
        font = QtGui.QFont()
        font.setFamily("Microsoft YaHei")
        font.setBold(False)
        font.setWeight(50)
        self.version_choose_frame.setFont(font)
        self.version_choose_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.version_choose_frame.setFrameShadow(QtWidgets.QFrame.Raised)
        self.version_choose_frame.setObjectName("version_choose_frame")

        # 版本类型选择框
        self.release_checkbox = QtWidgets.QCheckBox(self.version_choose_frame)
        self.release_checkbox.setGeometry(QtCore.QRect(10, 10, 71, 16))
        self.release_checkbox.setFont(font)
        self.release_checkbox.setObjectName("release_checkbox")

        self.snapshot_checlbox = QtWidgets.QCheckBox(self.version_choose_frame)
        self.snapshot_checlbox.setGeometry(QtCore.QRect(120, 10, 71, 16))
        self.snapshot_checlbox.setFont(font)
        self.snapshot_checlbox.setObjectName("snapshot_checlbox")

        self.alpha_checkbox = QtWidgets.QCheckBox(self.version_choose_frame)
        self.alpha_checkbox.setGeometry(QtCore.QRect(120, 40, 71, 16))
        self.alpha_checkbox.setFont(font)
        self.alpha_checkbox.setObjectName("alpha_checkbox")

        self.beta_checkbox = QtWidgets.QCheckBox(self.version_choose_frame)
        self.beta_checkbox.setGeometry(QtCore.QRect(10, 40, 71, 16))
        self.beta_checkbox.setFont(font)
        self.beta_checkbox.setObjectName("beta_checkbox")

        self.choose_version_type_lable = QtWidgets.QLabel(self.version_choose_frame)
        self.choose_version_type_lable.setGeometry(QtCore.QRect(35, 70, 121, 20))
        self.choose_version_type_lable.setFont(font)
        self.choose_version_type_lable.setAlignment(QtCore.Qt.AlignCenter)
        self.choose_version_type_lable.setObjectName("choose_version_type_lable")

        # 版本列表
        self.choose_version_widget = QtWidgets.QWidget(self.centralwidget)
        self.choose_version_widget.setGeometry(QtCore.QRect(20, 120, 201, 421))
        self.choose_version_widget.setFont(font)
        self.choose_version_widget.setObjectName("choose_version_widget")

        self.versions_list = QtWidgets.QListWidget(self.choose_version_widget)
        self.versions_list.setGeometry(QtCore.QRect(0, 20, 201, 211))
        self.versions_list.setFont(font)
        self.versions_list.setObjectName("versions_list")

        self.choose_lable = QtWidgets.QLabel(self.choose_version_widget)
        self.choose_lable.setGeometry(QtCore.QRect(0, 0, 201, 21))
        self.choose_lable.setFont(font)
        self.choose_lable.setAlignment(QtCore.Qt.AlignCenter)
        self.choose_lable.setObjectName("choose_lable")

        self.choose_lable_2 = QtWidgets.QLabel(self.choose_version_widget)
        self.choose_lable_2.setGeometry(QtCore.QRect(0, 230, 201, 21))
        self.choose_lable_2.setFont(font)
        self.choose_lable_2.setAlignment(QtCore.Qt.AlignCenter)
        self.choose_lable_2.setObjectName("choose_lable_2")

        self.versions_list_2 = QtWidgets.QListWidget(self.choose_version_widget)
        self.versions_list_2.setGeometry(QtCore.QRect(0, 250, 201, 171))
        self.versions_list_2.setFont(font)
        self.versions_list_2.setObjectName("versions_list_2")

        # 刷新和下载按钮
        self.refresh_show = QtWidgets.QFrame(self.centralwidget)
        self.refresh_show.setGeometry(QtCore.QRect(250, 20, 531, 91))
        self.refresh_show.setFont(font)
        self.refresh_show.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.refresh_show.setFrameShadow(QtWidgets.QFrame.Raised)
        self.refresh_show.setObjectName("refresh_show")

        self.now_version = QtWidgets.QLabel(self.refresh_show)
        self.now_version.setGeometry(QtCore.QRect(0, 0, 61, 16))
        self.now_version.setFont(font)
        self.now_version.setObjectName("now_version")

        self.now_version_lable = QtWidgets.QLabel(self.refresh_show)
        self.now_version_lable.setGeometry(QtCore.QRect(56, 0, 471, 16))
        self.now_version_lable.setFont(font)
        self.now_version_lable.setText("")
        self.now_version_lable.setObjectName("now_version_lable")

        self.refresh_button = QtWidgets.QPushButton(self.refresh_show)
        self.refresh_button.setGeometry(QtCore.QRect(0, 40, 161, 51))
        self.refresh_button.setFont(font)
        self.refresh_button.setObjectName("refresh_button")

        self.download_button = QtWidgets.QPushButton(self.refresh_show)
        self.download_button.setGeometry(QtCore.QRect(170, 40, 111, 51))
        self.download_button.setFont(font)
        self.download_button.setObjectName("download_button")

        self.run_button = QtWidgets.QPushButton(self.refresh_show)
        self.run_button.setGeometry(QtCore.QRect(290, 40, 241, 51))
        self.run_button.setFont(font)
        self.run_button.setObjectName("run_button")

        self.lineEdit = QtWidgets.QLineEdit(self.refresh_show)
        self.lineEdit.setGeometry(QtCore.QRect(60, 20, 471, 20))
        self.lineEdit.setObjectName("lineEdit")

        self.now_version_2 = QtWidgets.QLabel(self.refresh_show)
        self.now_version_2.setGeometry(QtCore.QRect(12, 20, 41, 16))
        self.now_version_2.setFont(font)
        self.now_version_2.setObjectName("now_version_2")

        # 日志区域
        self.logs_frame = QtWidgets.QFrame(self.centralwidget)
        self.logs_frame.setGeometry(QtCore.QRect(250, 120, 531, 181))
        self.logs_frame.setFont(font)
        self.logs_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.logs_frame.setFrameShadow(QtWidgets.QFrame.Raised)
        self.logs_frame.setObjectName("logs_frame")

        self.log__textedit = QtWidgets.QPlainTextEdit(self.logs_frame)
        self.log__textedit.setGeometry(QtCore.QRect(0, 20, 531, 161))
        self.log__textedit.setFont(font)
        self.log__textedit.setReadOnly(True)
        self.log__textedit.setObjectName("log__textedit")

        self.label = QtWidgets.QLabel(self.logs_frame)
        self.label.setGeometry(QtCore.QRect(0, 0, 531, 21))
        self.label.setFont(font)
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        self.label.setObjectName("label")

        # 登录区域
        self.login = QtWidgets.QFrame(self.centralwidget)
        self.login.setGeometry(QtCore.QRect(250, 320, 531, 51))
        self.login.setFont(font)
        self.login.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.login.setFrameShadow(QtWidgets.QFrame.Raised)
        self.login.setObjectName("login")

        self.login_button = QtWidgets.QPushButton(self.login)
        self.login_button.setGeometry(QtCore.QRect(390, 0, 71, 21))
        self.login_button.setFont(font)
        self.login_button.setObjectName("login_button")

        self.username_lable = QtWidgets.QLabel(self.login)
        self.username_lable.setGeometry(QtCore.QRect(54, 0, 81, 21))
        self.username_lable.setFont(font)
        self.username_lable.setObjectName("username_lable")

        self.username_lineedit = QtWidgets.QLineEdit(self.login)
        self.username_lineedit.setGeometry(QtCore.QRect(140, -1, 251, 21))
        self.username_lineedit.setFont(font)
        self.username_lineedit.setObjectName("username_lineedit")

        self.input_uuid_lable = QtWidgets.QLabel(self.login)
        self.input_uuid_lable.setGeometry(QtCore.QRect(0, 30, 131, 21))
        self.input_uuid_lable.setFont(font)
        self.input_uuid_lable.setObjectName("input_uuid_lable")

        self.uuid_input_lineedit = QtWidgets.QLineEdit(self.login)
        self.uuid_input_lineedit.setGeometry(QtCore.QRect(140, 30, 251, 21))
        self.uuid_input_lineedit.setFont(font)
        self.uuid_input_lineedit.setObjectName("uuid_input_lineedit")

        self.make_uuid_button = QtWidgets.QPushButton(self.login)
        self.make_uuid_button.setFont(font)
        self.make_uuid_button.setObjectName("make_uuid_button")

        self.wha_is_uuid_button = QtWidgets.QPushButton(self.login)
        self.make_uuid_button.setGeometry(QtCore.QRect(390, 30, 71, 21))
        self.wha_is_uuid_button.setGeometry(QtCore.QRect(464, 0, 61, 51))
        self.wha_is_uuid_button.setFont(font)
        self.wha_is_uuid_button.setObjectName("wha_is_uuid_button")

        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 800, 23))
        self.menubar.setObjectName("menubar")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)

        # 连接信号与槽
        self.connect_signals()

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def connect_signals(self):
        # 连接按钮的信号
        self.refresh_button.clicked.connect(self.self_freshing)
        self.download_button.clicked.connect(self.start_download)
        self.run_button.clicked.connect(self.run)
        self.login_button.clicked.connect(self.login_)
        self.make_uuid_button.clicked.connect(lambda: self.uuid_input_lineedit.setText(str(uuid())))
        self.wha_is_uuid_button.clicked.connect(self.tip_uuid)

        # 连接版本选择列表的信号
        self.versions_list.itemClicked.connect(self.choose_version_for_download)
        self.versions_list_2.itemClicked.connect(self.choose_version_for_run)
        
        # 连接版本筛选的信号
        self.release_checkbox.stateChanged.connect(self.checkout_release)
        
        
    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "Minecraft Launcher"))
        self.release_checkbox.setText(_translate("MainWindow", "正式版"))
        self.snapshot_checlbox.setText(_translate("MainWindow", "快照版"))
        self.alpha_checkbox.setText(_translate("MainWindow", "ALPHA版"))
        self.beta_checkbox.setText(_translate("MainWindow", "BETA版"))
        self.choose_version_type_lable.setText(_translate("MainWindow", "选择版本类型"))
        self.choose_lable.setText(_translate("MainWindow", "选择版本号"))
        self.choose_lable_2.setText(_translate("MainWindow", "选择版本名"))
        self.now_version.setText(_translate("MainWindow", "当前版本："))
        self.refresh_button.setText(_translate("MainWindow", "刷新"))
        self.download_button.setText(_translate("MainWindow", "下载"))
        self.run_button.setText(_translate("MainWindow", "启动"))
        self.now_version_2.setText(_translate("MainWindow", "版本名："))
        self.label.setText(_translate("MainWindow", "日志"))
        self.login_button.setText(_translate("MainWindow", "登录"))
        self.username_lable.setText(_translate("MainWindow", "请输入用户名："))
        self.input_uuid_lable.setText(_translate("MainWindow", "请输入UUID或随机生成："))
        self.make_uuid_button.setText(_translate("MainWindow", "生成UUID"))
        self.wha_is_uuid_button.setText(_translate("MainWindow", "什么是\nUUID"))
        self.download_status_label.setText(_translate("MainWindow", "下载状态：等待中"))
        
    def self_freshing(self):
        fresh(self)
        
    def update_progress(self, progress):
        self.progress_bar.setValue(progress)

    def get_versions(self):
        try:
            order = ['release', 'snapshot', 'beta', 'alpha', "old_beta", "old_alpha"]
            t = {}
            for version in minecraft_launcher_lib.utils.get_version_list():
                t[version["id"]] = version["type"]
            sorted_versions = dict(sorted(t.items(), key=lambda item: order.index(item[1])))
            self.log("成功获取版本列表")
            return sorted_versions
        except Exception as e:
            self.log(f"获取版本列表失败：{str(e)}")
            return {}
    
    def checkout_release(self):
        versions = self.get_versions()
        self.versions_list.clear()
        for version in versions:
            if versions[version] == "release":
                self.versions_list.addItem(version)

    def checkout_snapshot(self):
        versions = self.get_versions()
        self.versions_list.clear()
        for version in versions:
            if versions[version] == "snapshot":
                self.versions_list.addItem(version)

    def checkout_beta(self):
        versions = self.get_versions()
        self.versions_list.clear()
        for version in versions:
            if versions[version] == "beta" or versions[version] == "old_beta":
                self.versions_list.addItem(version)

    def checkout_alpha(self):
        versions = self.get_versions()
        self.versions_list.clear()
        for version in versions:
            if versions[version] == "alpha" or versions[version] == "old_alpha":
                self.versions_list.addItem(version)



    def start_download(self):
        if self.uuid == "" or self.username == "":
            QtWidgets.QMessageBox.warning(self, "警告", "请先登录！", buttons=QtWidgets.QMessageBox.Ok)
            return
        if self.selected_version_id == "":
            QtWidgets.QMessageBox.warning(self, "警告", "请先在‘选择版本号’中选择版本！", buttons=QtWidgets.QMessageBox.Ok)
            return
        if self.lineEdit.text() == "":
            QtWidgets.QMessageBox.warning(self, "警告", "请先输入版本名！", buttons=QtWidgets.QMessageBox.Ok)
            return
        download_path = os.path.join(".minecraft/versions", self.selected_version_id + "_" + self.lineEdit.text())
        if os.path.exists(download_path):
            if QtWidgets.QMessageBox.warning(self, "警告", "该版本已下载，是否覆盖？", buttons=QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No):
                shutil.rmtree(download_path)
                self.start_download()
            return

        self.log(f"开始下载版本：{self.selected_version_id}")
        self.download_button.setEnabled(False)
        self.download_thread = DownloadThread(self.selected_version_id, download_path)
        self.download_thread.signal_status.connect(self.update_status)
        self.download_thread.signal_finished.connect(self.download_finished)
        self.download_thread.signal_max.connect(self.set_max_value)
        self.download_thread.signal_error.connect(self.download_error)
        self.download_thread.signal_progress.connect(self.update_progress)
        self.download_thread.start()

        # 启动进度条动画
        self.is_downloading = True
        self.progress_bar.setRange(0, 0)  # 设置为不确定模式
        
    def set_max_value(self, max_value):
        if self.last_max < max_value:
            self.last_max += max_value
        self.progress_bar.setRange(0, self.last_max)

    def download_finished(self, success):
        self.is_downloading = False
        if success:
            QtWidgets.QMessageBox.information(self, "提示", "下载完成！", buttons=QtWidgets.QMessageBox.Ok)
            self.progress_bar.setRange(0, 100)  # 恢复进度条
            self.progress_bar.setValue(100)
            self.log("版本下载完成。")
        else:
            self.log("下载失败。")
        self.download_button.setEnabled(True)
        self.progress_bar.setValue(0)  # 无论成功与否，最后将进度条值设置为0

    def download_error(self, error_message):
        self.is_downloading = False
        QtWidgets.QMessageBox.warning(self, "错误", f"下载失败：{error_message}", buttons=QtWidgets.QMessageBox.Ok)
        self.log(f"下载失败：{error_message}")
        self.progress_bar.setRange(0, 100)  # 恢复进度条
        self.progress_bar.setValue(0)

    def update_status(self, status):
        self.download_status_label.setText(f"下载状态：{status}")

    def tip_uuid(self):
        QtWidgets.QMessageBox.information(self, "Tips", ("UUID（Universally Unique Identifier，通用唯一标识符）是一种由字母、数字和连字符组成的32位字符串，用于唯一标识信息。\n\n"
                                          "UUID的生成方法是通过一套算法，该算法基于当前时间戳、随机数、以及其它一些信息。\n\nUUID的作用主要是用来标识信息，防止信息被篡改或伪造。"),
                                          buttons=QtWidgets.QMessageBox.Ok)

    def login_(self):
        username = self.username_lineedit.text()
        uuid_or_random = self.uuid_input_lineedit.text()
        if username == "" or uuid_or_random == "":
            QtWidgets.QMessageBox.warning(self, "警告", "用户名和UUID不能为空！", buttons=QtWidgets.QMessageBox.Ok)
            return
        try:
            UUID(uuid_or_random)
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "警告", "请输入正确的UUID！", buttons=QtWidgets.QMessageBox.Ok)
            return
        self.username = username
        self.uuid = uuid_or_random
        self.token = ""  # 假设token由其他方式获取
        self.login_button.setText("重新登录")
        self.save_config()
        self.log(f"用户 {self.username} 登录成功。")

    def choose_version_for_download(self):
        self.selected_version_id = self.versions_list.currentItem().text()
        self.now_version_lable.setText(self.selected_version_id)
        self.log(f"选择的版本号已保存：{self.selected_version_id}")

    def choose_version_for_run(self):
        self.selected_version_name = self.versions_list_2.currentItem().text()
        self.now_version_lable.setText(self.selected_version_name)
        self.log(f"选择的版本名已保存：{self.selected_version_name}")
        self.save_config()

    def list_versions(self):
        if not os.path.exists(".minecraft/versions"):
            os.makedirs(".minecraft/versions")
        update = False
        versions = os.listdir(".minecraft/versions")
        self.log(versions)
        self.versions_list_2.clear()
        for version in versions:
            try:
                self.versions_list_2.addItem(version.split("_")[1])
            except IndexError:
                if QtWidgets.QMessageBox.warning(self, "警告", f"出现旧版本格式游戏文件夹，是否更新？", 
                                                 buttons=QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No) == QtWidgets.QMessageBox.Yes or update:
                    os.rename(os.path.join(".minecraft/versions", version), os.path.join(".minecraft/versions", version + "_" + version))
                    self.log(f"旧版本格式游戏文件夹已更新：{version} -> {version}_{version}")
                    update = True
                else:
                    self.log(f"旧版本格式游戏文件夹未更新：{version}")
                    self.except_version_name = version.split("_")[0]
                    self.versions_list_2.addItem(version.split("_")[0])
                    self.save_config()                   
            else:
                print(version.split("_"))
                print(len(version.split("_")))
                print(type(version.split("_")[0]))
                if version.split("_")[1] == "":
                    if QtWidgets.QMessageBox.warning(self, "警告", f"出现空版本名称游戏文件夹，是否更新？", 
                                                     buttons=QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No) == QtWidgets.QMessageBox.Yes or update:
                        os.rename(os.path.join(".minecraft/versions", version.split("_")[0] + "_"), 
                                  os.path.join(".minecraft/versions", version.split("_")[0] + "_" + version))
                        self.list_versions()
                    else:
                        self.log(f"空名称游戏文件夹未更新：{version}")
                        self.except_version_name = version.split("_")[1]
                        self.versions_list_2.addItem(version.split("_")[1])
                        self.save_config()                   

        self.log("已列出所有已下载的版本。")

    def download(self):
        self.start_download()

    def run(self):
        if self.uuid == "" or self.username == "":
            QtWidgets.QMessageBox.warning(self, "警告", "请先登录！", buttons=QtWidgets.QMessageBox.Ok)
            return
        if self.selected_version_name == "":
            QtWidgets.QMessageBox.warning(self, "警告", "请先在‘选择版本名’中选择版本！", buttons=QtWidgets.QMessageBox.Ok)
            return
        for version in os.listdir(".minecraft/versions"):
            if version.split("_")[0] == self.selected_version_name:
                self.selected_version_id = version.split("_")[0]
                v = version
                break
        else:
            QtWidgets.QMessageBox.warning(self, "警告", "该版本未下载，请先下载！", buttons=QtWidgets.QMessageBox.Ok)
            return
        self.log(f"启动版本：{self.selected_version_name}")
        try:
            command = minecraft_launcher_lib.command.get_minecraft_command(version=self.selected_version_id, username=self.username, uuid=self.uuid, token=self.token)
            import subprocess
            subprocess.Popen(command)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "错误", f"启动失败：{str(e)}", buttons=QtWidgets.QMessageBox.Ok)
            self.log(f"启动失败：{str(e)}")

    def init_logging(self):
        """初始化日志功能"""
        self.log_file = "launcher_log.txt"
        logging.basicConfig(filename=self.log_file, level=logging.INFO, format="%(asctime)s - %(message)s")
        self.log__textedit.appendPlainText(f"日志文件已保存到：{self.log_file}")

    def log(self, message):
        """记录日志"""
        logging.info(message)
        self.log__textedit.appendPlainText(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}")

    def load_config(self):
        """加载配置文件"""
        if not os.path.exists("launcher_config.json"):
            with open("launcher_config.json", "w", encoding="utf-8") as f:
                f.write(json.dumps({"username": "", "uuid": "", "token": "", "selected_version_name": ""}))
        with open("launcher_config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
            self.username = config.get("username", "")
            self.uuid = config.get("uuid", "")
            self.token = config.get("token", "")
            self.selected_version_name = config.get("selected_version_name", "")
        self.username_lineedit.setText(self.username)
        self.uuid_input_lineedit.setText(self.uuid)
        self.log("配置文件加载完成。")

    def save_config(self):
        """保存配置文件"""
        config = {
            "username": self.username,
            "uuid": self.uuid,
            "token": self.token,
            "selected_version_name": self.selected_version_name, 
            "except_version_name": self.except_version_name
        }
        with open("launcher_config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
        self.log("配置文件已保存。")


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec_())
    