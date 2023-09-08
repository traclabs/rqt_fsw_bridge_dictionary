#!/usr/bin/env python3

from __future__ import division
import os
import ast

from python_qt_binding import loadUi
from python_qt_binding.QtCore import QTimer, Slot
from python_qt_binding.QtWidgets import QWidget, QTreeWidgetItem, QTableWidgetItem
from PyQt5 import QtCore, QtWidgets

import rclpy
from ament_index_python import get_resource

from fsw_ros2_bridge_msgs.srv import GetMessageInfo, SetMessageInfo, GetPluginInfo

from .dictionary_info import DictionaryInfo
from .confirm_dialog import ConfirmDialog


class BridgeDictionaryWidget(QWidget):

    _column_names = ['structure', 'type']

    def __init__(self, node, plugin):
        super(BridgeDictionaryWidget, self).__init__()

        n = 'rqt_fsw_bridge_dictionary.BridgeDictionaryWidget'

        self._node = node
        self._plugin = plugin
        self._logger = self._node.get_logger().get_child(n)
        self._connected_to_bridge = False
        self._msg_pkg_name = ""
        self._plugin_pkg_name = ""
        self._plugin_name = ""

        # set up UI
        _, package_path = get_resource('packages', 'rqt_fsw_bridge_dictionary')
        ui_file = os.path.join(package_path, 'share', 'rqt_fsw_bridge_dictionary',
                               'resource', 'BridgeDictionaryWidget.ui')
        loadUi(ui_file, self)
        self.setup_ui_connections()

        self._column_index = {}
        for column_name in self._column_names:
            self._column_index[column_name] = len(self._column_index)

        # bridge info
        self._plugin_info = None
        self._msg_dict = {}
        self._dictionary_info = DictionaryInfo(self._node)

        # ros clients
        self.plugin_info_client =\
            self._node.create_client(GetPluginInfo, '/fsw_ros2_bridge/get_plugin_info')
        self.get_message_info_client =\
            self._node.create_client(GetMessageInfo, '/fsw_ros2_bridge/get_message_info')
        self.set_message_info_client =\
            self._node.create_client(SetMessageInfo, '/fsw_ros2_bridge/set_message_info')

        # connection timer
        self._timer_wait_for_bridge = QTimer(self)
        self._timer_wait_for_bridge.timeout.connect(self.wait_for_plugin)

    def start(self):
        self._timer_wait_for_bridge.start(1000)

    def shutdown_plugin(self):
        self._timer_wait_for_bridge.stop()

    def save_settings(self, plugin_settings, instance_settings):
        header_state = self.msg_tree_widget.header().saveState()
        instance_settings.set_value('tree_widget_header_state', header_state)

    def restore_settings(self, pluggin_settings, instance_settings):
        if instance_settings.contains('tree_widget_header_state'):
            header_state = instance_settings.value('tree_widget_header_state')
            if not self.msg_tree_widget.header().restoreState(header_state):
                self._logger.warn('rqt_fsw_bridge_dictionary: Failed to restore header state.')

    def setup_ui_connections(self):
        self.msg_tree_widget.itemClicked.connect(self.on_msg_item_clicked)
        self.clear_info_button.clicked.connect(self.clear_info_pressed)
        self.save_info_button.clicked.connect(self.save_info_pressed)
        self.reload_info_button.clicked.connect(self.reload_info_pressed)

    def send_plugin_info_request(self):
        req = GetPluginInfo.Request()
        future = self.plugin_info_client.call_async(req)
        rclpy.spin_until_future_complete(self._node, future)
        return future.result()

    def send_get_message_info_request(self):
        req = GetMessageInfo.Request()
        future = self.get_message_info_client.call_async(req)
        rclpy.spin_until_future_complete(self._node, future)
        return future.result()

    def send_set_message_info_request(self, msg_name, info):
        req = SetMessageInfo.Request()
        req.msg_info.pkg_name = self._msg_pkg_name
        req.msg_info.msg_name = msg_name
        # probably should get type and json info here and send it back, but it is ignored on
        # the server so whatever
        req.msg_info.info = info
        future = self.set_message_info_client.call_async(req)
        rclpy.spin_until_future_complete(self._node, future)
        return future.result()

    @Slot()
    def wait_for_plugin(self):
        if (not self._connected_to_bridge) and (not self._msg_dict):
            self._node.get_logger().info("Trying to connect to FSW bridge...")
            if self.plugin_info_client.wait_for_service(timeout_sec=1.0):
                if self._plugin_info is None:
                    self._plugin_info = self.send_plugin_info_request()
                    self._plugin_name = self._plugin_info.plugin_name
                    self._plugin_pkg_name = self._plugin_name.split('.')[0]
                    self._msg_pkg_name = self._plugin_info.msg_pkg

                    self._node.get_logger().info("setting plugin: " + self._plugin_name)
                    self._node.get_logger().info("setting plugin pkg: " + self._plugin_pkg_name)
                    self._node.get_logger().info("setting msg pkg: " + self._msg_pkg_name)

                    self.msg_pkg_label.setText(self._msg_pkg_name)
                    self.plugin_name_label.setText(self._plugin_name)

            if self._plugin_info is not None:
                if self.get_message_info_client.wait_for_service(timeout_sec=1.0):
                    r = self.send_get_message_info_request()
                    if r:
                        self._connected_to_bridge = True
                        self._node.get_logger().info("setting msg info with: "
                                                     + str(len(r.msg_info)) + " messages")
                        self._msg_dict = self._dictionary_info.init(self._plugin_pkg_name,
                                                                    self._msg_pkg_name,
                                                                    r.msg_info)
                        if self._msg_dict:
                            self.build_dictionary_tree(self._msg_dict)

    def is_primitive(self, t):
        return t in ["int8", "int16", "int32", "uint8", "uint16", "uint32",
                     "float8", "float16", "float32", "bool", "string"]

    def build_dictionary_tree(self, data):
        items = []
        for key, values in data.items():
            item = QTreeWidgetItem([key])
            for value in values:
                ext = value.split(".")[-1].upper()
                child = QTreeWidgetItem([value, ext])
                item.addChild(child)
            items.append(item)

        self.msg_tree_widget.clear()
        self.msg_tree_widget.insertTopLevelItems(0, items)
        self.msg_tree_widget.expandAll()

    def build_msg_struct_tree(self, data, par=None):
        items = []
        item = None

        if len(data) == 0:
            return items

        data = ast.literal_eval(data)
        for key in data.keys():

            if par is None:
                item = QTreeWidgetItem([key])
            else:
                item = QTreeWidgetItem([key, par])

            dk = data[key]

            if "sequence" in data[key]:
                item.setText(self._column_index['structure'], (key + "[]"))
                dk = dk[9:len(dk)-1]
                item.setText(self._column_index['type'], dk)
            else:
                item.setText(self._column_index['structure'], key)
                item.setText(self._column_index['type'], dk)

            if not self.is_primitive(dk):
                pkg_name = ""
                s = dk.split("/")
                if len(s) == 2:
                    [pkg_name, msg_type] = s
                else:
                    msg_type = dk

                m = self._dictionary_info.get_message_struct(msg_type)

                children = self.build_msg_struct_tree(m, dk)
                for c in children:
                    item.addChild(c)

            items.append(item)

        if par is None:
            self.msg_struct_tree.insertTopLevelItems(0, items)

        return items

    @QtCore.pyqtSlot(QtWidgets.QTreeWidgetItem, int)
    def on_msg_item_clicked(self, it, col):
        self.msg_struct_tree.clear()

        msg_name = ""
        t = it.text(col)
        if any(t in sublist for sublist in self._msg_dict.values()):
            msg_name = t

        msg_name_item = QTableWidgetItem()
        msg_name_item.setText(msg_name)
        self.msg_table_header.setItem(0, 0, msg_name_item)

        msg_pkg_name_item = QTableWidgetItem()
        msg_pkg_name_item.setText(self._msg_pkg_name)
        self.msg_table_header.setItem(1, 0, msg_pkg_name_item)

        msg_type_item = QTableWidgetItem()
        msg_type_item.setText(self._dictionary_info.get_message_type(msg_name))
        self.msg_table_header.setItem(2, 0, msg_type_item)

        info_str = self._dictionary_info.get_message_info(msg_name)
        if info_str is None:
            t = self._dictionary_info.get_message_type(msg_name)
            info_str = "This is info about " + t + " msg: " + msg_name
            self.msg_info_text.setText(info_str)
        else:
            self.msg_info_text.setText(info_str)

        self._node.get_logger().info("info_str: " + info_str)
        s = self._dictionary_info.get_message_struct(msg_name)
        self.build_msg_struct_tree(s)
        self.msg_struct_tree.resizeColumnToContents(0)
        return

    @QtCore.pyqtSlot()
    def clear_info_pressed(self):
        item = self.msg_tree_widget.currentItem().text(0)
        dialog_str = "Really clear message info for \'" + str(item) + "\'?"
        dlg = ConfirmDialog(dialog_str, self)
        if dlg.exec():
            t = self._dictionary_info.get_message_type(item)
            info_str = "This is info about " + t + " msg: " + str(item)
            self.msg_info_text.setText(info_str)
        return

    @QtCore.pyqtSlot()
    def save_info_pressed(self):
        item = self.msg_tree_widget.currentItem().text(0)
        dialog_str = "Really save message info for \'" + str(item) + "\'?"
        dlg = ConfirmDialog(dialog_str, self)
        if dlg.exec():
            info = self.msg_info_text.toPlainText()
            self._dictionary_info.save_message_info(str(item), info)
            r = self.send_set_message_info_request(str(item), info)
            if not r:
                self._node.get_logger().error("problem saving info for: " + str(item))
        return

    @QtCore.pyqtSlot()
    def reload_info_pressed(self):
        item = self.msg_tree_widget.currentItem().text(0)
        dialog_str = "Really reload message info for \'" + str(item) + "\'?"
        dlg = ConfirmDialog(dialog_str, self)
        if dlg.exec():
            stored_info = self._dictionary_info.get_message_info(str(item))
            if stored_info is None:
                t = self._dictionary_info.get_message_type(item)
                info_str = "This is info about " + t + " msg: " + str(item)
                self.msg_info_text.setText(info_str)
            else:
                self.msg_info_text.setText(stored_info)
        return
